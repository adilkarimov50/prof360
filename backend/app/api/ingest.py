"""Загрузка Excel через интерфейс: preview маппинга + подтверждённый ingest."""
import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel

from app.ai import llm
from app.analytics.scoring import recompute_all
from app.core.audit import log_action
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import client_ip
from app.core.rbac import require_capability
from app.etl.column_map import build_admin_map, build_crim_map
from app.etl.loaders import load_admin_excel, load_criminal_excel, load_preventive_xls, preview_excel_columns
from app.etl.quality import data_quality_report
from app.models.audit import IngestionLog
from app.models.user import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/ingest", tags=["ingest"])

# /data смонтирован read-only — пишем во внутренний каталог контейнера
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ConfirmIngest(BaseModel):
    stored_name: str
    file_type: str  # admin | alcohol | criminal | preventive
    column_map: dict[str, int] | None = None


def _save_upload(file: UploadFile) -> tuple[str, str]:
    ext = os.path.splitext(file.filename or "data.xlsx")[1] or ".xlsx"
    fd, tmp = tempfile.mkstemp(suffix=ext, dir=UPLOAD_DIR)
    os.close(fd)
    with open(tmp, "wb") as out:
        shutil.copyfileobj(file.file, out)
    stored = os.path.basename(tmp)
    return stored, tmp


@router.post("/preview")
async def preview(file: UploadFile = File(...), user: User = Depends(require_capability("ingest"))):
    stored, path = _save_upload(file)
    info = preview_excel_columns(path)
    info["stored_name"] = stored
    # ИИ может предложить уточнения маппинга по заголовкам
    if llm.is_available() and info.get("headers"):
        prompt = (
            "По заголовкам Excel определи тип файла (admin/alcohol/criminal/preventive) "
            f"и перечисли, какие колонки соответствуют полям загрузки.\nЗаголовки: {info['headers'][:40]}"
        )
        hint = llm.generate(prompt, temperature=0.1, max_tokens=512)
        if hint:
            info["ai_hint"] = hint
    return info


@router.post("/confirm")
def confirm(data: ConfirmIngest, request: Request,
            user: User = Depends(require_capability("ingest")),
            db: Session = Depends(get_db)):
    path = os.path.join(UPLOAD_DIR, data.stored_name)
    if not os.path.isfile(path):
        return {"error": "Файл не найден — загрузите заново"}

    basename = os.path.basename(path)
    dup = db.query(IngestionLog).filter(
        IngestionLog.source_file == basename,
        IngestionLog.accepted > 0,
    ).first()
    if dup:
        return {
            "skipped": True,
            "reason": f"Файл уже загружался ({dup.ts})",
            "accepted": dup.accepted,
            "rejected": dup.rejected,
            "quality": data_quality_report(db),
        }

    colmap = data.column_map
    if data.file_type == "criminal":
        log = load_criminal_excel(db, path, username=user.username, column_map=colmap or build_crim_map(None))
    elif data.file_type == "preventive":
        log = load_preventive_xls(db, path, username=user.username)
    else:
        source = "alcohol" if data.file_type == "alcohol" else "admin"
        log = load_admin_excel(db, path, source=source, username=user.username,
                               column_map=colmap or build_admin_map(None))

    scored = recompute_all(db)
    quality = data_quality_report(db)
    log_action(db, action="ingest_upload", user=user, ip=client_ip(request),
               details={"file": data.stored_name, "type": data.file_type,
                        "accepted": log.accepted, "rejected": log.rejected})
    return {
        "accepted": log.accepted,
        "rejected": log.rejected,
        "persons_scored": scored,
        "quality": quality,
    }


@router.get("/quality")
def quality(user: User = Depends(require_capability("ingest")),
            db: Session = Depends(get_db)):
    from app.core.deps import abac_district_filter
    return data_quality_report(db, abac_district_filter(user))
