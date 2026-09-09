"""Журнал аудита и сигналов DLP (доступ для аудитора/администратора)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.rbac import require_capability
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
def events(
    action: str | None = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_capability("audit")),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog).order_by(AuditLog.ts.desc())
    if action:
        q = q.filter(AuditLog.action == action)
    rows = q.offset(offset).limit(limit).all()
    return [
        {"id": r.id, "ts": r.ts, "username": r.username, "action": r.action,
         "entity_type": r.entity_type, "entity_id": r.entity_id, "ip": r.ip,
         "export_id": r.export_id, "details": r.details}
        for r in rows
    ]


@router.get("/dlp/mass-exports")
def mass_exports(user: User = Depends(require_capability("audit")), db: Session = Depends(get_db)):
    """DLP: пользователи с числом экспортов выше порога."""
    rows = (
        db.query(AuditLog.username, func.count(AuditLog.id))
        .filter(AuditLog.action == "export")
        .group_by(AuditLog.username)
        .having(func.count(AuditLog.id) >= settings.mass_export_threshold)
        .all()
    )
    return [{"username": u, "exports": c, "threshold": settings.mass_export_threshold} for u, c in rows]
