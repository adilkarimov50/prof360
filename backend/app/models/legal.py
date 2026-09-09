"""Нормативное ядро: акты и нормы (акт -> статья -> пункт)."""
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Integer, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.db import Base


class LegalAct(Base):
    __tablename__ = "legal_acts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    act_type: Mapped[str] = mapped_column(String(64))  # закон, кодекс, приказ, конституция ...
    number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    adopt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=3)  # 1=Конституция ... 5=региональные
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    norms: Mapped[list["LegalNorm"]] = relationship(back_populates="act", cascade="all, delete-orphan")


class LegalNorm(Base):
    """Структурная единица НПА с карточкой (таблица 3 ТЗ) и вектором для RAG."""

    __tablename__ = "legal_norms"

    id: Mapped[int] = mapped_column(primary_key=True)
    act_id: Mapped[int] = mapped_column(ForeignKey("legal_acts.id", ondelete="CASCADE"), index=True)

    article: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    point: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    text_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_kz: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="действует")  # действует/утратила силу/изменена
    edition_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    edition_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    category: Mapped[str | None] = mapped_column(String(128), nullable=True)  # семейно-бытовая, несовершеннолетние ...
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)   # субъект исполнения
    measure: Mapped[str | None] = mapped_column(String(255), nullable=True)   # мера реагирования
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dim), nullable=True)

    act: Mapped["LegalAct"] = relationship(back_populates="norms")

    @property
    def ref(self) -> str:
        parts = []
        if self.article:
            parts.append(self.article)
        if self.point:
            parts.append(f"п.{self.point}")
        return " ".join(parts)
