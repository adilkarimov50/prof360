"""Аналитические выборки: повторность, эскалация в период учёта."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import commission_crosscheck, insights
from app.core.db import get_db
from app.core.deps import abac_district_filter, get_current_user
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _by_district(rows: list[dict], df: str | None) -> list[dict]:
    """ABAC: район-прокурор видит только свой район."""
    if not df:
        return rows
    return [r for r in rows if r.get("district") == df]


@router.get("/repeat-offenders")
def repeat_offenders(min_cases: int = Query(2, ge=2), limit: int = Query(100, le=500),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = insights.repeat_offenders(db, min_cases=min_cases, limit=limit)
    return _by_district(rows, abac_district_filter(user))


@router.get("/escalation")
def escalation(limit: int = Query(100, le=500),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Лица, ставшие подозреваемыми в период нахождения на профилактическом учёте."""
    rows = insights.escalation_during_register(db, limit=limit)
    return _by_district(rows, abac_district_filter(user))


@router.get("/articles")
def articles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return insights.article_stats(db, limit=20, district_filter=abac_district_filter(user))


@router.get("/commission-stats")
def commission_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Агрегат по темам МВК: интернет-мошенничество, вымогательство, алкоголь, вейп, несовершеннолетние."""
    return insights.commission_stats(db, district_filter=abac_district_filter(user))


@router.get("/unified")
def unified(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Единая сводная картина области: адм. практика, профучёт, МВК, риски."""
    return insights.unified_oblast_picture(db, district_filter=abac_district_filter(user))


@router.get("/prevention-pipeline")
def prevention_pipeline(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Воронка профилактики: адм. дела → учёт → пропуски → эскалация → ЕРДР."""
    return insights.prevention_pipeline(db, district_filter=abac_district_filter(user))


@router.get("/law-compliance")
def law_compliance(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Законодательный комплаенс: ст.58/59 Закона о профилактике, КоАП, УК."""
    return insights.law_compliance(db, district_filter=abac_district_filter(user))


@router.get("/commission-crosscheck")
def commission_crosscheck_endpoint(
    year: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """МВК vs реальность: охват проблемных районов поручениями комиссии."""
    result = commission_crosscheck.commission_vs_reality(db, year=year)
    df = abac_district_filter(user)
    if df:
        for key in ("matched", "missed", "alarms"):
            result[key] = _by_district(result.get(key, []), df)
        for topic in result.get("topics", []):
            topic["districts"] = _by_district(topic.get("districts", []), df)
    return result
