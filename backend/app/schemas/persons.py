"""Pydantic person schemas."""
from datetime import date

from pydantic import BaseModel


class PersonShort(BaseModel):
    id: int
    fio: str
    iin_masked: str
    district: str | None
    risk_score: int
    risk_level: str


class FactorOut(BaseModel):
    factor: str
    points: int


class SignalOut(BaseModel):
    type: str
    level: str
    message: str


class AdminCaseOut(BaseModel):
    id: int
    material_no: str | None
    case_date: date | None
    district: str | None
    qualification: str | None
    fabula: str | None
    decision: str | None
    measure: str | None
    intoxication: str | None
    source: str

    class Config:
        from_attributes = True


class PreventiveOut(BaseModel):
    id: int
    form: str | None
    category: str | None
    status: str | None
    date_post: date | None
    date_removed: date | None
    district: str | None
    has_special_req: bool

    class Config:
        from_attributes = True


class SuspectOut(BaseModel):
    id: int
    erdr_no: str | None
    erdr_year: int | None
    qualification: str | None
    gravity: str | None
    region: str | None

    class Config:
        from_attributes = True


class TimelineEvent(BaseModel):
    date: date | None
    type: str
    title: str
    detail: str | None = None


class PersonDetail(BaseModel):
    id: int
    fio: str
    iin_masked: str
    birth_date: date | None
    gender: str | None
    district: str | None
    locality: str | None
    risk_score: int
    risk_level: str
    factors: list[FactorOut]
    signals: list[SignalOut]
    admin_cases: list[AdminCaseOut]
    preventive_records: list[PreventiveOut]
    suspects: list[SuspectOut]
    timeline: list[TimelineEvent]
