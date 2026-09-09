"""Администрирование: загрузка данных, пересчёт риска, сид НПА, пользователи."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analytics.scoring import recompute_all
from app.core.audit import log_action
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import client_ip
from app.core.rbac import require_capability
from app.core.security import hash_password
from app.etl.loaders import discover_and_load_all
from app.legal.entitlements_seed import seed_entitlements
from app.legal.seed import seed_legal
from app.models.audit import IngestionLog
from app.models.user import Role, User

router = APIRouter(prefix="/admin", tags=["admin"])


class NewUser(BaseModel):
    username: str
    full_name: str
    password: str
    role: Role = Role.ANALYST
    district: str | None = None
    can_export: bool = False
    can_access_minors: bool = False


@router.post("/ingest")
def ingest(request: Request, user: User = Depends(require_capability("admin")),
           db: Session = Depends(get_db)):
    summary = discover_and_load_all(db, settings.data_dir, username=user.username)
    count = recompute_all(db)
    log_action(db, action="ingest", user=user, ip=client_ip(request),
               details={"files": summary, "persons_scored": count})
    return {"summary": summary, "persons_scored": count}


@router.post("/recompute-risk")
def recompute(user: User = Depends(require_capability("admin")), db: Session = Depends(get_db)):
    from app.core.tasks import enqueue

    def _run():
        from app.core.db import SessionLocal
        from app.analytics.scoring import recompute_all as ra
        s = SessionLocal()
        try:
            return ra(s)
        finally:
            s.close()

    task = enqueue("recompute_all", _run)
    return {"task": task["status"], "message": "Пересчёт запущен в фоне"}


@router.post("/seed-legal")
def seed(user: User = Depends(require_capability("admin")), db: Session = Depends(get_db)):
    return {"norms_seeded": seed_legal(db)}


@router.post("/seed-entitlements")
def seed_entitlements_admin(user: User = Depends(require_capability("admin")),
                            db: Session = Depends(get_db)):
    return seed_entitlements(db)


@router.post("/download-legal-docs")
def download_legal_docs(user: User = Depends(require_capability("admin")), db: Session = Depends(get_db)):
    from app.legal.document_cache import download_all

    cache_results = download_all(None, force=False)
    ok = sum(1 for r in cache_results if r.get("status") in ("cached", "downloaded"))
    return {
        "documents_cached": ok,
        "documents_total": len(cache_results),
        "cache_results": cache_results,
    }


@router.post("/import-registry-mkb")
def import_registry_mkb(user: User = Depends(require_capability("admin")), db: Session = Depends(get_db)):
    from app.legal.person_icd import import_registry_mkb

    return import_registry_mkb(db)


@router.post("/ingest-codes")
def ingest_codes(user: User = Depends(require_capability("admin")), db: Session = Depends(get_db)):
    from app.legal.code_ingest import ingest_all
    from app.legal.topics import INGEST_PRIORITY

    results = ingest_all(db, INGEST_PRIORITY)
    total = sum(r.get("added", 0) for r in results if not r.get("error"))
    errors = [r for r in results if r.get("error")]
    return {"added": total, "results": results, "errors": len(errors)}


@router.get("/ingestion-logs")
def ingestion_logs(
    user: User = Depends(require_capability("admin")),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    rows = db.query(IngestionLog).order_by(IngestionLog.ts.desc()).offset(offset).limit(limit).all()
    return [
        {"id": r.id, "ts": r.ts, "file": r.source_file, "total": r.total,
         "accepted": r.accepted, "rejected": r.rejected}
        for r in rows
    ]


@router.post("/users")
def create_user(data: NewUser, request: Request,
                user: User = Depends(require_capability("admin")), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=409, detail="Пользователь уже существует")
    new = User(
        username=data.username, full_name=data.full_name,
        hashed_password=hash_password(data.password), role=data.role,
        district=data.district, can_export=data.can_export,
        can_access_minors=data.can_access_minors,
    )
    db.add(new)
    db.commit()
    log_action(db, action="create_user", user=user, ip=client_ip(request),
               entity_type="user", entity_id=new.id)
    return {"id": new.id, "username": new.username, "role": new.role.value}
