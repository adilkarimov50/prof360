"""API документов комиссии по профилактике правонарушений."""
from __future__ import annotations

import mimetypes
import os
import tempfile
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.commission.service import UPLOAD_DIR, ensure_upload_dir, run_analysis
from app.core.audit import log_action
from app.core.db import get_db
from app.core.deps import abac_district_filter, client_ip, get_current_user
from app.core.rbac import require_capability
from app.core.tasks import enqueue
from app.models.commission import CommissionDocument
from app.models.user import Role, User
from app.schemas.commission import CommissionDocumentDetail, CommissionDocumentOut, CommissionSummary

router = APIRouter(prefix="/commission", tags=["commission"])

MAX_FILE_BYTES = 20 * 1024 * 1024  # inline Gemini limit

ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
    "image/jpg",
}

DOC_TYPES = {"protocol", "report", "execution_plan"}


def _ensure_upload_access(user: User, district: str) -> None:
    df = abac_district_filter(user)
    if df and district != df:
        raise HTTPException(status_code=403, detail="Нет доступа к этому району (ABAC)")


def _ensure_read_access(user: User, doc: CommissionDocument) -> None:
    df = abac_district_filter(user)
    if df and doc.district != df:
        raise HTTPException(status_code=403, detail="Нет доступа к документу района (ABAC)")


def _resolve_mime(file: UploadFile) -> str:
    mt = (file.content_type or "").split(";")[0].strip().lower()
    if mt and mt != "application/octet-stream":
        return mt
    guessed, _ = mimetypes.guess_type(file.filename or "")
    return (guessed or "application/octet-stream").lower()


def _save_commission_file(file: UploadFile) -> tuple[str, str, str]:
    ext = os.path.splitext(file.filename or "document.pdf")[1] or ".pdf"
    fd, tmp = tempfile.mkstemp(suffix=ext, dir=ensure_upload_dir())
    os.close(fd)
    size = 0
    with open(tmp, "wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                os.remove(tmp)
                raise HTTPException(status_code=413, detail="Файл превышает лимит 20 МБ")
            out.write(chunk)
    stored = os.path.basename(tmp)
    mime = _resolve_mime(file)
    return stored, tmp, mime


def _to_out(doc: CommissionDocument) -> CommissionDocumentOut:
    return CommissionDocumentOut.model_validate(doc)


@router.post("/documents", response_model=CommissionDocumentOut)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    district: str = Form(...),
    period: str = Form(...),
    session_date: date | None = Form(None),
    title: str | None = Form(None),
    user: User = Depends(require_capability("commission")),
    db: Session = Depends(get_db),
):
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type должен быть одним из: {', '.join(sorted(DOC_TYPES))}")

    mime = _resolve_mime(file)
    ext = (file.filename or "").lower().rsplit(".", 1)[-1]
    if mime not in ALLOWED_MIMES and ext not in ("pdf", "docx", "jpg", "jpeg", "png"):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются PDF, DOCX, JPG, PNG. Старый .doc конвертируйте в PDF или DOCX.",
        )

    _ensure_upload_access(user, district.strip())

    stored, path, mime = _save_commission_file(file)

    doc = CommissionDocument(
        doc_type=doc_type,
        title=(title or file.filename or "").strip() or None,
        district=district.strip(),
        period=period.strip(),
        session_date=session_date,
        stored_name=stored,
        mime_type=mime,
        original_filename=file.filename or stored,
        uploaded_by=user.username,
        status="analyzing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_action(
        db,
        action="commission_upload",
        user=user,
        ip=client_ip(request),
        entity_type="commission_document",
        entity_id=doc.id,
        details={
            "district": doc.district,
            "doc_type": doc.doc_type,
            "filename": doc.original_filename,
            "mime_type": mime,
            "external_ai": True,
        },
    )

    enqueue(f"commission_analyze_{doc.id}", run_analysis, doc.id, username=user.username)
    return _to_out(doc)


@router.get("/documents", response_model=list[CommissionDocumentOut])
def list_documents(
    district: str | None = Query(None),
    doc_type: str | None = Query(None),
    period: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(CommissionDocument).order_by(CommissionDocument.uploaded_at.desc())
    df = abac_district_filter(user)
    if df:
        q = q.filter(CommissionDocument.district == df)
    elif district:
        q = q.filter(CommissionDocument.district == district)
    if doc_type:
        q = q.filter(CommissionDocument.doc_type == doc_type)
    if period:
        q = q.filter(CommissionDocument.period == period)
    return [_to_out(d) for d in q.limit(200).all()]


@router.get("/documents/{doc_id}", response_model=CommissionDocumentDetail)
def get_document(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(CommissionDocument).filter(CommissionDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    _ensure_read_access(user, doc)
    return CommissionDocumentDetail.model_validate(doc)


@router.post("/documents/{doc_id}/reanalyze", response_model=CommissionDocumentOut)
def reanalyze_document(
    doc_id: int,
    user: User = Depends(require_capability("commission")),
    db: Session = Depends(get_db),
):
    doc = db.query(CommissionDocument).filter(CommissionDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    _ensure_upload_access(user, doc.district)
    doc.status = "analyzing"
    doc.error_message = None
    db.commit()
    enqueue(f"commission_reanalyze_{doc.id}", run_analysis, doc.id, username=user.username)
    return _to_out(doc)


@router.get("/documents/{doc_id}/file")
def download_file(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(CommissionDocument).filter(CommissionDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    _ensure_read_access(user, doc)
    path = os.path.join(UPLOAD_DIR, doc.stored_name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, media_type=doc.mime_type, filename=doc.original_filename)


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    user: User = Depends(require_capability("admin")),
    db: Session = Depends(get_db),
):
    doc = db.query(CommissionDocument).filter(CommissionDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ not found")
    path = os.path.join(UPLOAD_DIR, doc.stored_name)
    if os.path.isfile(path):
        os.remove(path)
    db.delete(doc)
    db.commit()
    return {"deleted": True, "id": doc_id}


@router.get("/summary", response_model=CommissionSummary)
def commission_summary(
    district: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    df = abac_district_filter(user)
    target = df or district
    q = db.query(CommissionDocument)
    if target:
        q = q.filter(CommissionDocument.district == target)
    rows = q.order_by(CommissionDocument.uploaded_at.desc()).all()

    analyzed = [r for r in rows if r.status == "analyzed"]
    qualities = [r.quality_score for r in analyzed if r.quality_score is not None]
    effects = [r.effectiveness_score for r in analyzed if r.effectiveness_score is not None]

    rec_counts = {"yes": 0, "revise": 0, "no": 0}
    for r in analyzed:
        key = (r.include_recommendation or "revise").lower()
        if key in rec_counts:
            rec_counts[key] += 1

    return CommissionSummary(
        district=target,
        total=len(rows),
        analyzed=len(analyzed),
        avg_quality=round(sum(qualities) / len(qualities), 1) if qualities else None,
        avg_effectiveness=round(sum(effects) / len(effects), 1) if effects else None,
        include_yes=rec_counts["yes"],
        include_revise=rec_counts["revise"],
        include_no=rec_counts["no"],
        documents=[_to_out(d) for d in rows[:20]],
    )
