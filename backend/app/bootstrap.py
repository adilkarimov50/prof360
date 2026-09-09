"""Первичная инициализация: создание администратора по умолчанию."""
import os

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import Role, User


def ensure_default_admin(db: Session) -> None:
    if db.query(User).filter(User.role == Role.ADMIN).first():
        return
    username = os.getenv("DEFAULT_ADMIN_USER", "admin")
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", "Prof360!admin")
    admin = User(
        username=username,
        full_name="Администратор системы",
        hashed_password=hash_password(password),
        role=Role.ADMIN,
        can_export=True,
        can_access_minors=False,
        must_change_password=True,
    )
    db.add(admin)
    # демонстрационный прокурор области с полным доступом
    if not db.query(User).filter(User.username == "prokuror").first():
        db.add(User(
            username="prokuror",
            full_name="Прокурор Алматинской области",
            hashed_password=hash_password(os.getenv("DEFAULT_PROSECUTOR_PASSWORD", "Prof360!prok")),
            role=Role.OBLAST_PROSECUTOR,
            can_export=True,
            can_access_minors=True,
            must_change_password=True,
        ))
    db.commit()
