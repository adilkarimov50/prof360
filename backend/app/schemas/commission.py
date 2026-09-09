"""Pydantic schemas for commission documents."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class CommissionDocumentOut(BaseModel):
    id: int
    doc_type: str
    title: str | None
    district: str
    period: str
    session_date: date | None
    original_filename: str
    mime_type: str
    uploaded_by: str | None
    uploaded_at: datetime
    status: str
    error_message: str | None = None
    quality_score: float | None = None
    legal_compliance_score: float | None = None
    effectiveness_score: float | None = None
    include_recommendation: str | None = None

    model_config = {"from_attributes": True}


class CommissionDocumentDetail(CommissionDocumentOut):
    extracted_text: str | None = None
    analysis_document: dict | None = None
    analysis_execution: dict | None = None
    analysis_legal: dict | None = None


class CommissionSummary(BaseModel):
    district: str | None = None
    total: int
    analyzed: int
    avg_quality: float | None = None
    avg_effectiveness: float | None = None
    include_yes: int = 0
    include_revise: int = 0
    include_no: int = 0
    documents: list[CommissionDocumentOut] = Field(default_factory=list)
