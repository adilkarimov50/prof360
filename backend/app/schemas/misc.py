"""Pydantic legal, AI and report schemas."""
from datetime import date

from pydantic import BaseModel


class NormOut(BaseModel):
    id: int
    act: str
    act_number: str | None
    article: str | None
    point: str | None
    title: str | None
    text_ru: str | None
    status: str
    edition_start: date | None
    category: str | None
    subject: str | None
    measure: str | None
    source_url: str | None


class ChatTurn(BaseModel):
    role: str
    content: str


class AiChatRequest(BaseModel):
    question: str
    context_type: str | None = None
    context_id: str | None = None
    history: list[ChatTurn] | None = None


class ReportRequest(BaseModel):
    kind: str
    target: str | None = None
    case_id: int | None = None
    district: str | None = None
    period: str | None = None
    format: str = "docx"
