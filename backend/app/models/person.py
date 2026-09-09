"""Лица, административные дела, профучёт, подозреваемые, сигналы."""
from datetime import date, datetime

from sqlalchemy import String, Integer, Date, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Person(Base):
    """Единый профиль лица. Чувствительные поля шифруются на уровне приложения."""

    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    # ИИН хранится зашифрованным; iin_hash — для поиска/дедупликации
    iin_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    iin_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    last_name: Mapped[str] = mapped_column(String(128), default="")
    first_name: Mapped[str] = mapped_column(String(128), default="")
    patronymic: Mapped[str] = mapped_column(String(128), default="")
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)

    district: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    locality: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Риск-скоринг
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(16), default="Низкий")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    admin_cases: Mapped[list["AdminCase"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    preventive_records: Mapped[list["PreventiveRecord"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    suspects: Mapped[list["Suspect"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    signals: Mapped[list["Signal"]] = relationship(back_populates="person", cascade="all, delete-orphan")

    @property
    def fio(self) -> str:
        return " ".join(p for p in (self.last_name, self.first_name, self.patronymic) if p).strip()


class AdminCase(Base):
    """Административное дело/протокол (адм. практика и алкогольный массив)."""

    __tablename__ = "admin_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)

    material_no: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    case_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    place: Mapped[str | None] = mapped_column(String(512), nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    article_base: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    legal_norm_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_norms.id", ondelete="SET NULL"), index=True, nullable=True,
    )
    fabula: Mapped[str | None] = mapped_column(Text, nullable=True)
    organ: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subdivision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    measure: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fine_amount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intoxication: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="admin")  # admin | alcohol

    person: Mapped["Person"] = relationship(back_populates="admin_cases")


class PreventiveRecord(Base):
    """Профилактический учёт (формы 205/206/301/УДО)."""

    __tablename__ = "preventive_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)

    form: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_post: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_removed: Mapped[date | None] = mapped_column(Date, nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    locality: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsible: Mapped[str | None] = mapped_column(String(255), nullable=True)
    has_special_req: Mapped[bool] = mapped_column(Boolean, default=False)

    person: Mapped["Person"] = relationship(back_populates="preventive_records")


class Suspect(Base):
    """Подозреваемое лицо (ЕРДР, Книга46)."""

    __tablename__ = "suspects"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True, nullable=True)

    erdr_no: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    erdr_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    gravity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    organ: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    iin_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    person: Mapped["Person"] = relationship(back_populates="suspects")


class Signal(Base):
    """Автоматический сигнал риска (таблица 10.2 ТЗ)."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True, nullable=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    level: Mapped[str] = mapped_column(String(16), default="Средний")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    person: Mapped["Person"] = relationship(back_populates="signals")
