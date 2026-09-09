"""Модель пользователя и роли (RBAC из таблицы 22 ТЗ)."""
import enum
from datetime import datetime

from sqlalchemy import String, Boolean, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Role(str, enum.Enum):
    """Роли согласно матрице доступа ТЗ (Приложение 1)."""

    OBLAST_PROSECUTOR = "oblast_prosecutor"        # прокурор области
    DEPUTY_PROSECUTOR = "deputy_prosecutor"        # заместитель прокурора области
    DEPARTMENT_HEAD = "department_head"            # начальник управления
    ANALYST = "analyst"                            # прокурор-аналитик
    DISTRICT_PROSECUTOR = "district_prosecutor"    # прокурор района
    OSINT_USER = "osint_user"                      # OSINT-пользователь
    ADMIN = "admin"                                # администратор системы
    SECURITY_AUDITOR = "security_auditor"          # аудитор безопасности


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.ANALYST)
    # ABAC: ограничение по территории (район). NULL = вся область.
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # ABAC: спец-доступ к данным несовершеннолетних / потерпевших
    can_access_minors: Mapped[bool] = mapped_column(Boolean, default=False)
    can_export: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Инвалидация JWT при logout / смене пароля
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
