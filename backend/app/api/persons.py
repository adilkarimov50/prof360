"""Лица: поиск (с ABAC по району), карточка с риск-профилем и timeline."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.analytics.scoring import compute_person_factors
from app.core.audit import log_action
from app.core.crypto import decrypt, mask_iin
from app.core.db import get_db
from app.core.deps import abac_district_filter, client_ip, get_current_user
from app.core.rbac import allow_pii
from app.models.person import Person
from app.models.user import User
from app.schemas import (
    AdminCaseOut,
    FactorOut,
    PersonDetail,
    PersonShort,
    PreventiveOut,
    SignalOut,
    SuspectOut,
    TimelineEvent,
)

router = APIRouter(prefix="/persons", tags=["persons"])

_MINOR_MARKERS = ("несовершеннолет", "205", "опек")


def _filter_preventive(records, user: User):
    if allow_pii(user):
        return records
    return [
        p for p in records
        if not any(m in (p.category or "").lower() or m in (p.form or "").lower() for m in _MINOR_MARKERS)
    ]


@router.get("", response_model=list[PersonShort])
def search_persons(
    q: str | None = Query(None),
    risk: str | None = Query(None),
    district: str | None = Query(None),
    limit: int = Query(50, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Person)
    abac = abac_district_filter(user)
    if abac:
        query = query.filter(Person.district == abac)
    elif district:
        query = query.filter(Person.district == district)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            Person.last_name.ilike(like),
            Person.first_name.ilike(like),
            Person.patronymic.ilike(like),
        ))
    if risk:
        query = query.filter(Person.risk_level == risk)

    rows = query.order_by(Person.risk_score.desc()).limit(limit).all()
    return [
        PersonShort(
            id=p.id, fio=p.fio, iin_masked=mask_iin(decrypt(p.iin_enc)),
            district=p.district, risk_score=p.risk_score, risk_level=p.risk_level,
        )
        for p in rows
    ]


def _build_timeline(person: Person) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for c in person.admin_cases:
        events.append(TimelineEvent(
            date=c.case_date, type="admin",
            title=f"Адм. правонарушение {c.qualification or ''}".strip(),
            detail=(c.fabula or "")[:200] or None,
        ))
    for p in person.preventive_records:
        events.append(TimelineEvent(
            date=p.date_post, type="preventive",
            title=f"Постановка на учёт ({p.form or ''})",
            detail=p.category,
        ))
    for s in person.suspects:
        events.append(TimelineEvent(
            date=None, type="suspect",
            title=f"Подозреваемый (ЕРДР {s.erdr_year or ''})",
            detail=f"{s.qualification or ''} {s.gravity or ''}".strip(),
        ))
    events.sort(key=lambda e: (e.date is None, e.date or ""))
    return events


@router.get("/{person_id}", response_model=PersonDetail)
def get_person(person_id: int, request: Request,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Лицо не найдено")

    abac = abac_district_filter(user)
    if abac and person.district != abac:
        raise HTTPException(status_code=403, detail="Нет доступа к лицу вне вашего района (ABAC)")

    # обязательное логирование просмотра карточки лица
    log_action(db, action="view_person", user=user, entity_type="person",
               entity_id=person.id, ip=client_ip(request))

    score, factors, signals = compute_person_factors(person)

    return PersonDetail(
        id=person.id, fio=person.fio, iin_masked=mask_iin(decrypt(person.iin_enc)),
        birth_date=person.birth_date, gender=person.gender,
        district=person.district, locality=person.locality,
        risk_score=score, risk_level=person.risk_level,
        factors=[FactorOut(**f) for f in factors],
        signals=[SignalOut(**s) for s in signals],
        admin_cases=[AdminCaseOut.model_validate(c) for c in person.admin_cases],
        preventive_records=[PreventiveOut.model_validate(p) for p in _filter_preventive(person.preventive_records, user)],
        suspects=[SuspectOut.model_validate(s) for s in person.suspects],
        timeline=_build_timeline(person),
    )


@router.get("/{person_id}/support")
def person_support(person_id: int, request: Request,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """МКБ-10, меры государственной поддержки и разрывы реестров для карточки лица."""
    from app.legal.person_icd import person_support_payload

    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Лицо не найдено")
    abac = abac_district_filter(user)
    if abac and person.district != abac:
        raise HTTPException(status_code=403, detail="Нет доступа (ABAC)")
    log_action(db, action="view_person_support", user=user, entity_type="person",
               entity_id=person.id, ip=client_ip(request))
    return person_support_payload(db, person)


@router.get("/{person_id}/measures")
def person_measures(person_id: int, request: Request,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Рекомендованные акты прокурорского реагирования по Приказу ГП РК №32."""
    from app.prosecutor.measures import recommend_measures

    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Лицо не найдено")
    abac = abac_district_filter(user)
    if abac and person.district != abac:
        raise HTTPException(status_code=403, detail="Нет доступа (ABAC)")
    log_action(db, action="view_measures", user=user, entity_type="person",
               entity_id=person.id, ip=client_ip(request))
    return {"person_id": person.id, "fio": person.fio, "measures": recommend_measures(person)}
