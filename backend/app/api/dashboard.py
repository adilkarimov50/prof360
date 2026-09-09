"""Главная панель прокуратуры области."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics import insights, proceedings
from app.core.db import get_db
from app.core.deps import abac_district_filter, get_current_user
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = abac_district_filter(user)
    return {
        "counters": insights.overview_counters(db, df),
        "district_risk": insights.district_risk(db, df),
        "top_persons": insights.top_persons(db, 10, df),
        "signals": insights.signal_summary(db),
        "articles": insights.article_stats(db, 12, df),
    }


@router.get("/timeseries")
def timeseries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Динамика административных дел по месяцам."""
    return {"series": insights.cases_timeseries(db, abac_district_filter(user))}


@router.get("/sb")
def family_domestic(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Дашборд семейно-бытовой сферы (ст.73, ст.461, защитные предписания)."""
    return insights.sb_stats(db, abac_district_filter(user))


@router.get("/organs")
def organs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Разрез по линиям ответственности (полиция / МИО) + МИО-индикаторы."""
    df = abac_district_filter(user)
    return {
        "breakdown": insights.organ_breakdown(db, df),
        "mio": insights.mio_indicators(db, df),
    }


@router.get("/proceedings")
def proceedings_violations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Нарушения законности при административном производстве (сводка + примеры)."""
    df = abac_district_filter(user)
    summary = proceedings.admin_proceeding_violations(db, df)
    summary["cases"] = proceedings.proceeding_violation_cases(db, df, limit=50)
    return summary


@router.get("/district/{name}")
def district(name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Детализация по району (drilldown). ABAC: район-прокурор видит только свой район."""
    df = abac_district_filter(user)
    if df and name != df:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Нет доступа к данному району (ABAC)")
    return insights.district_drilldown(db, name)
