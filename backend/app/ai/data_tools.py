"""Безопасные аналитические инструменты для ИИ-консультанта (ABAC, без сырого SQL)."""
from datetime import date, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.analytics import insights, proceedings
from app.analytics.normalize import ALC_ARTICLES, SB_ARTICLES, is_intoxicated
from app.analytics.scoring import risk_level
from app.models.person import AdminCase, Person, PreventiveRecord, Signal, Suspect

# JSON-схемы для Gemini functionDeclarations
TOOL_DECLARATIONS: list[dict] = [
    {
        "name": "count_persons",
        "description": "Счётчик лиц в базе с фильтром по району и уровню риска",
        "parameters": {
            "type": "object",
            "properties": {
                "district": {"type": "string", "description": "Район (опционально)"},
                "risk_level": {"type": "string", "description": "Низкий|Средний|Высокий|Критический"},
            },
        },
    },
    {
        "name": "count_admin_cases",
        "description": "Количество административных дел с фильтрами",
        "parameters": {
            "type": "object",
            "properties": {
                "district": {"type": "string"},
                "article": {"type": "string", "description": "Базовая статья, напр. ст.73"},
                "source": {"type": "string", "description": "admin|alcohol"},
                "period_days": {"type": "integer", "description": "За последние N дней"},
            },
        },
    },
    {
        "name": "repeat_on_register",
        "description": "Лица, повторно нарушившие на профилактическом учёте",
        "parameters": {
            "type": "object",
            "properties": {
                "district": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "top_risk_persons",
        "description": "Топ лиц по риск-скорингу",
        "parameters": {
            "type": "object",
            "properties": {
                "district": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "article_statistics",
        "description": "Статистика по статьям КоАП",
        "parameters": {
            "type": "object",
            "properties": {
                "district": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "escalation_cases",
        "description": "Эскалация учёт → ЕРДР (подозреваемый в период профучёта)",
        "parameters": {
            "type": "object",
            "properties": {
                "district": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "proceeding_violations",
        "description": "Нарушения законности административного производства",
        "parameters": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
        },
    },
    {
        "name": "alcohol_stats",
        "description": "Статистика алкогольных правонарушений и опьянения",
        "parameters": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
        },
    },
    {
        "name": "hot_spots",
        "description": "Горячие точки: районы/месяцы с пиком дел",
        "parameters": {
            "type": "object",
            "properties": {
                "district": {"type": "string"},
                "article": {"type": "string"},
            },
        },
    },
    {
        "name": "overview",
        "description": "Сводные счётчики дашборда",
        "parameters": {
            "type": "object",
            "properties": {"district": {"type": "string"}},
        },
    },
]


def _district(abac: str | None, requested: str | None) -> str | None:
    """ABAC: районный прокурор не может выйти за свой район."""
    if abac:
        return abac
    return requested


def execute_tool(db: Session, name: str, args: dict | None, abac_district: str | None = None) -> dict:
    args = args or {}
    district = _district(abac_district, args.get("district"))

    if name == "count_persons":
        q = db.query(Person)
        if district:
            q = q.filter(Person.district == district)
        if args.get("risk_level"):
            q = q.filter(Person.risk_level == args["risk_level"])
        return {"count": q.count(), "district": district, "risk_level": args.get("risk_level")}

    if name == "count_admin_cases":
        q = db.query(AdminCase)
        if district:
            q = q.filter(AdminCase.district == district)
        if args.get("article"):
            q = q.filter(AdminCase.article_base == args["article"])
        if args.get("source"):
            q = q.filter(AdminCase.source == args["source"])
        if args.get("period_days"):
            since = date.today() - timedelta(days=int(args["period_days"]))
            q = q.filter(AdminCase.case_date >= since)
        return {"count": q.count(), "filters": {k: v for k, v in args.items() if v}}

    if name == "repeat_on_register":
        q = db.query(Signal).filter(Signal.type == "repeat_on_register")
        if district:
            q = q.join(Person).filter(Person.district == district)
        rows = q.limit(int(args.get("limit") or 20)).all()
        return {
            "count": db.query(Signal).filter(Signal.type == "repeat_on_register").count(),
            "examples": [
                {"person_id": s.person_id, "message": s.message, "level": s.level}
                for s in rows
            ],
        }

    if name == "top_risk_persons":
        return {"persons": insights.top_persons(db, int(args.get("limit") or 10), district)}

    if name == "article_statistics":
        return {"articles": insights.article_stats(db, int(args.get("limit") or 12), district)}

    if name == "escalation_cases":
        rows = insights.escalation_during_register(db, int(args.get("limit") or 50))
        if district:
            rows = [r for r in rows if r.get("district") == district]
        return {"count": len(rows), "cases": rows[: int(args.get("limit") or 20)]}

    if name == "proceeding_violations":
        return proceedings.admin_proceeding_violations(db, district)

    if name == "alcohol_stats":
        return _alcohol_stats(db, district)

    if name == "hot_spots":
        return insights.hot_spots(db, district, args.get("article"))

    if name == "overview":
        return insights.overview_counters(db, district)

    return {"error": f"Неизвестный инструмент: {name}"}


def _alcohol_stats(db: Session, district: str | None) -> dict:
    q = db.query(AdminCase)
    if district:
        q = q.filter(AdminCase.district == district)
    alc_cases = q.filter(AdminCase.article_base.in_(ALC_ARTICLES)).count()
    st200 = q.filter(AdminCase.article_base == "ст.200").count()
    intox = q.filter(AdminCase.intoxication.is_not(None)).all()
    intox_yes = sum(1 for c in intox if is_intoxicated(c.intoxication))
    intox_total = len(intox)
    return {
        "alcohol_articles_cases": alc_cases,
        "article_200_cases": st200,
        "intoxication_marked": intox_total,
        "intoxication_confirmed": intox_yes,
        "intoxication_rate_pct": round(intox_yes / intox_total * 100, 1) if intox_total else 0,
    }


def is_data_question(text: str) -> bool:
    """Эвристика: вопрос про данные Excel/аналитику, а не только право."""
    low = text.lower()
    markers = (
        "сколько", "число", "количеств", "статистик", "топ", "рейтинг", "повтор",
        "учёт", "учете", "учёте", "район", "эскалац", "ердр", "риск", "лиц",
        "дел", "протокол", "горяч", "алкогол", "опьян", "ст.200", "ст 200",
        "нарушени", "производств", "дашборд", "данн",
    )
    return any(m in low for m in markers)
