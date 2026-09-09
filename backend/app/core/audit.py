"""Хелпер записи в неизменяемый журнал аудита."""
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_action(
    db: Session,
    *,
    action: str,
    user=None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    ip: str | None = None,
    export_id: str | None = None,
    details: dict | None = None,
) -> None:
    entry = AuditLog(
        action=action,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        ip=ip,
        export_id=export_id,
        details=details,
    )
    db.add(entry)
    db.commit()
