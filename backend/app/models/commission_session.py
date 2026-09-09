"""Модели для отслеживания заседаний МВК и исполнения поручений."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.db import Base


class CommissionSession(Base):
    """Заседание МВК по профилактике правонарушений."""

    __tablename__ = "commission_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_number: Mapped[str] = mapped_column(String(32), index=True)   # "1", "1/1", "2"
    session_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    session_type: Mapped[str] = mapped_column(String(32), default="ordinary")  # ordinary | extraordinary
    quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 1-4
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chairman: Mapped[str | None] = mapped_column(String(256), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    agenda_raw: Mapped[str | None] = mapped_column(Text, nullable=True)   # повестка дня (сырой текст)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # AI-заключение
    effectiveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    assignments: Mapped[list["CommissionAssignment"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class CommissionAssignment(Base):
    """Поручение председателя МВК, принятое по итогам заседания."""

    __tablename__ = "commission_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("commission_sessions.id", ondelete="CASCADE"), index=True
    )
    point_number: Mapped[str] = mapped_column(String(32))   # "2.1", "3", "4.2"
    text: Mapped[str] = mapped_column(Text)
    responsible_organs: Mapped[str | None] = mapped_column(Text, nullable=True)  # CSV
    deadline: Mapped[str | None] = mapped_column(String(128), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(64), nullable=True)  # cyber|extortion|juvenile|vape|alcohol|road|other
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)  # high|medium|low

    session: Mapped["CommissionSession"] = relationship(back_populates="assignments")
    executions: Mapped[list["CommissionExecution"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class CommissionExecution(Base):
    """Факт исполнения поручения конкретным органом (ответ на хаттама)."""

    __tablename__ = "commission_executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("commission_assignments.id", ondelete="CASCADE"), index=True
    )
    organ_name: Mapped[str] = mapped_column(String(256), index=True)   # "Кеген ауданы"
    organ_type: Mapped[str | None] = mapped_column(String(64), nullable=True)  # akimat|pd|dsb|education|other
    source_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_status: Mapped[str] = mapped_column(String(32), default="unknown")
    # executed|partial|formal|not_executed|unknown
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    ai_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues: Mapped[list | None] = mapped_column(JSON, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    assignment: Mapped["CommissionAssignment"] = relationship(back_populates="executions")
