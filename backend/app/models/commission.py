"""Документы комиссии по профилактике правонарушений."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base


class CommissionDocument(Base):
    __tablename__ = "commission_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(32), index=True)  # protocol | report | execution_plan
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    district: Mapped[str] = mapped_column(String(128), index=True)
    period: Mapped[str] = mapped_column(String(64), index=True)
    session_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    stored_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128))
    original_filename: Mapped[str] = mapped_column(String(512))

    uploaded_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_document: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_execution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_legal: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    legal_compliance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    effectiveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    include_recommendation: Mapped[str | None] = mapped_column(String(64), nullable=True)
