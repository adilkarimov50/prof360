"""Нарушения законности при производстве по делам об административных правонарушениях.

Прокурорский надзор за законностью административного производства: выявление дел —
кандидатов на проверку (необоснованное прекращение, занижение меры по серьёзным
составам, отсутствие взыскания, волокита/передача материала). Формулировки —
«кандидат на проверку», без презумпции вины.
"""
from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Session

from app.analytics.normalize import SB_ARTICLES
from app.models.person import AdminCase, Person

# Признаки по тексту решения/меры (значения из источника)
TERMINATED = AdminCase.decision.ilike("%прекращ%")
TRANSFERRED = AdminCase.decision.ilike("%передан%")
IMPOSED = AdminCase.decision.ilike("%наложением%")
WARNING = AdminCase.measure.ilike("%предупрежд%")
NO_MEASURE = or_(AdminCase.measure.is_(None), AdminCase.measure == "")
IS_SB = AdminCase.article_base.in_(SB_ARTICLES)
IS_ZP = AdminCase.article_base == "ст.461"

# code, title, условие. Порядок важен для маркировки конкретного дела (первый сработавший).
CATEGORIES: list[tuple[str, str, object]] = [
    ("termination_sb", "Прекращение/освобождение по семейно-бытовому составу (ст.73)",
     and_(IS_SB, TERMINATED)),
    ("lenient_sb", "Мягкая мера (предупреждение) по семейно-бытовому составу",
     and_(IS_SB, WARNING)),
    ("lenient_zp", "Мягкая мера по нарушению защитного предписания (ст.461)",
     and_(IS_ZP, WARNING)),
    ("no_measure", "Взыскание не назначено при решении о наложении",
     and_(IMPOSED, NO_MEASURE)),
    ("termination_general", "Прочие прекращения/освобождения от ответственности",
     and_(TERMINATED, not_(IS_SB))),
    ("transfer", "Передача материала (волокита/подведомственность)",
     TRANSFERRED),
]

_COMBINED = or_(*[cond for _, _, cond in CATEGORIES])


def _scope(q, df: str | None):
    return q.filter(AdminCase.district == df) if df else q


def admin_proceeding_violations(db: Session, df: str | None = None) -> dict:
    """Сводка нарушений адм. производства: по категориям, по районам, итог."""
    categories = []
    for code, title, cond in CATEGORIES:
        cnt = _scope(db.query(AdminCase).filter(cond), df).count()
        categories.append({"code": code, "title": title, "count": cnt})

    rows = (
        _scope(db.query(AdminCase.district, AdminCase.id), df)
        .filter(_COMBINED)
        .all()
    )
    by_district_map: dict[str, int] = {}
    for district, _id in rows:
        d = district or "—"
        by_district_map[d] = by_district_map.get(d, 0) + 1
    by_district = sorted(
        [{"district": d, "count": c} for d, c in by_district_map.items()],
        key=lambda x: -x["count"],
    )[:12]

    return {"categories": categories, "by_district": by_district, "total": len(rows)}


def _label_case(case: AdminCase) -> str:
    """Возвращает заголовок первой сработавшей категории для конкретного дела."""
    art = case.article_base or ""
    dec = (case.decision or "").lower()
    mea = (case.measure or "").lower()
    is_sb = art in SB_ARTICLES
    is_zp = art == "ст.461"
    if is_sb and "прекращ" in dec:
        return CATEGORIES[0][1]
    if is_sb and "предупрежд" in mea:
        return CATEGORIES[1][1]
    if is_zp and "предупрежд" in mea:
        return CATEGORIES[2][1]
    if "наложением" in dec and not mea:
        return CATEGORIES[3][1]
    if "прекращ" in dec and not is_sb:
        return CATEGORIES[4][1]
    if "передан" in dec:
        return CATEGORIES[5][1]
    return "—"


def proceeding_violation_cases(db: Session, df: str | None = None, limit: int = 500) -> list[dict]:
    """Реестр дел — кандидатов на проверку законности административного производства."""
    q = (
        db.query(AdminCase, Person)
        .join(Person, Person.id == AdminCase.person_id)
        .filter(_COMBINED)
    )
    if df:
        q = q.filter(AdminCase.district == df)
    q = q.order_by(AdminCase.case_date.desc().nullslast()).limit(limit)
    out = []
    for case, person in q.all():
        out.append({
            "case_id": case.id,
            "person_id": person.id,
            "fio": person.fio,
            "material_no": case.material_no,
            "case_date": case.case_date,
            "district": case.district,
            "qualification": case.qualification,
            "decision": case.decision,
            "measure": case.measure or "не указана",
            "violation": _label_case(case),
        })
    return out
