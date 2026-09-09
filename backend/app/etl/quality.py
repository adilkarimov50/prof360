"""Отчёт качества данных Excel/БД: пропуски ИИН, дат, решений."""
from sqlalchemy.orm import Session

from app.models.person import AdminCase, Person, PreventiveRecord, Suspect


def data_quality_report(db: Session, district_filter: str | None = None) -> dict:
    """Агрегированный отчёт пропусков и аномалий для контроля ввода."""
    pq = db.query(Person)
    ac = db.query(AdminCase)
    pr = db.query(PreventiveRecord)
    sq = db.query(Suspect)
    if district_filter:
        pq = pq.filter(Person.district == district_filter)
        ac = ac.filter(AdminCase.district == district_filter)
        pr = pr.filter(PreventiveRecord.district == district_filter)

    total_persons = pq.count()
    no_iin = pq.filter((Person.iin_hash.is_(None)) | (Person.iin_hash == "")).count()
    no_district = pq.filter((Person.district.is_(None)) | (Person.district == "")).count()

    total_cases = ac.count()
    no_date = ac.filter(AdminCase.case_date.is_(None)).count()
    no_qual = ac.filter((AdminCase.qualification.is_(None)) | (AdminCase.qualification == "")).count()
    no_decision = ac.filter((AdminCase.decision.is_(None)) | (AdminCase.decision == "")).count()
    no_measure = ac.filter((AdminCase.measure.is_(None)) | (AdminCase.measure == "")).count()
    imposed_no_measure = ac.filter(
        AdminCase.decision.ilike("%наложением%"),
        (AdminCase.measure.is_(None)) | (AdminCase.measure == ""),
    ).count()

    prev_total = pr.count()
    prev_no_date = pr.filter(PreventiveRecord.date_post.is_(None)).count()

    suspects_total = sq.count()
    suspects_unlinked = sq.filter(Suspect.person_id.is_(None)).count()

    return {
        "persons": {
            "total": total_persons,
            "missing_iin": no_iin,
            "missing_iin_pct": round(no_iin / total_persons * 100, 1) if total_persons else 0,
            "missing_district": no_district,
        },
        "admin_cases": {
            "total": total_cases,
            "missing_date": no_date,
            "missing_date_pct": round(no_date / total_cases * 100, 1) if total_cases else 0,
            "missing_qualification": no_qual,
            "missing_decision": no_decision,
            "missing_measure": no_measure,
            "imposed_without_measure": imposed_no_measure,
        },
        "preventive": {
            "total": prev_total,
            "missing_date_post": prev_no_date,
        },
        "suspects": {
            "total": suspects_total,
            "unlinked_to_person": suspects_unlinked,
        },
        "district_filter": district_filter,
    }


def district_completeness(db: Session, limit: int = 15) -> list[dict]:
    """Топ районов с наибольшей долей пропусков дат в делах."""
    out: list[dict] = []
    districts = db.query(AdminCase.district).distinct().all()
    for (district,) in districts:
        d = district or "—"
        q = db.query(AdminCase).filter(AdminCase.district == district)
        total = q.count()
        missing = q.filter(AdminCase.case_date.is_(None)).count()
        if total:
            out.append({
                "district": d, "cases": total,
                "missing_date": missing,
                "missing_date_pct": round(missing / total * 100, 1),
            })
    out.sort(key=lambda x: -x["missing_date_pct"])
    return out[:limit]
