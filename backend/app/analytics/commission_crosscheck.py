"""Перекрёстный анализ: темы МВК vs реальная статистика по районам."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics.insights import _district_topic_count
from app.models.commission_session import CommissionAssignment, CommissionSession
from app.models.person import AdminCase, Person, PreventiveRecord

MVK_TOPICS: list[dict] = [
    {"key": "cyber", "label": "Интернет-мошенничество", "articles": "ст.190 УК"},
    {"key": "extortion", "label": "Вымогательство", "articles": "ст.194 УК"},
    {"key": "juvenile", "label": "Несовершеннолетние", "articles": "ст.58 Закона о профилактике"},
    {"key": "vape", "label": "Незаконный оборот вейпов", "articles": "ст.301-1 УК"},
    {"key": "alcohol", "label": "Алкогольная преступность", "articles": "ст.200, ст.440 КоАП"},
]

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cyber": ("мошенни", "кибер", "интернет", "фишинг", "190"),
    "extortion": ("вымогател", "бопсалау", "шантаж", "194"),
    "juvenile": ("несовершеннолетн", "кәмелетке", "пдн", "юп", "молодёж"),
    "vape": ("вейп", "электрон", "301-1", "сигарет"),
    "alcohol": ("алкогол", "опьянен", "200", "440"),
}


def _all_districts(db: Session) -> list[str]:
    districts: set[str] = set()
    for col in (Person.district, AdminCase.district, PreventiveRecord.district):
        districts.update(d for d, in db.query(col).distinct().all() if d)
    return sorted(districts)


def _assignments_for_topic(db: Session, topic: str, year: int | None) -> list[CommissionAssignment]:
    q = (
        db.query(CommissionAssignment)
        .join(CommissionSession, CommissionSession.id == CommissionAssignment.session_id)
    )
    if year:
        q = q.filter(CommissionSession.year == year)
    assignments = q.all()
    return [
        a for a in assignments
        if (a.topic or "").lower() == topic
        or any(kw in (a.text or "").lower() for kw in TOPIC_KEYWORDS.get(topic, ()))
    ]


def _district_covered_by_mvk(db: Session, district: str, assignments: list[CommissionAssignment]) -> bool:
    """Район охвачен поручением МВК, если есть исполнение от органа района или упоминание в тексте."""
    d_low = district.lower()
    d_root = d_low.replace("ский", "").replace("ский", "")[:8]
    for a in assignments:
        text = (a.text or "").lower()
        if d_low in text or (d_root and d_root in text):
            return True
        for ex in a.executions:
            organ = (ex.organ_name or "").lower()
            if d_low[:6] in organ or (d_root and d_root in organ):
                return True
    return False


def _topic_has_oblast_assignment(assignments: list[CommissionAssignment]) -> bool:
    """Областное поручение по теме (без привязки к конкретному району)."""
    return len(assignments) > 0


def _worst_districts(db: Session, topic: str, limit: int = 8) -> list[dict]:
    districts = _all_districts(db)
    ranked = [
        {"district": d, "count": _district_topic_count(db, d, topic)}
        for d in districts
    ]
    ranked = [r for r in ranked if r["count"] > 0]
    ranked.sort(key=lambda x: -x["count"])
    return ranked[:limit]


def commission_vs_reality(db: Session, year: int | None = None) -> dict:
    """Сопоставление приоритетов МВК с реальной статистикой по районам."""
    districts = _all_districts(db)
    topics_out: list[dict] = []
    matched: list[dict] = []
    missed: list[dict] = []
    alarms: list[dict] = []

    for topic_def in MVK_TOPICS:
        topic = topic_def["key"]
        assignments = _assignments_for_topic(db, topic, year)
        has_oblast = _topic_has_oblast_assignment(assignments)
        ranked = _worst_districts(db, topic)
        total = sum(r["count"] for r in ranked)

        district_rows = []
        for row in ranked:
            covered = _district_covered_by_mvk(db, row["district"], assignments) or has_oblast
            entry = {
                "district": row["district"],
                "stat_count": row["count"],
                "mvk_covered": covered,
                "status": "matched" if covered else "missed",
            }
            district_rows.append(entry)
            if covered:
                matched.append({**entry, "topic": topic, "topic_label": topic_def["label"]})
            else:
                missed.append({**entry, "topic": topic, "topic_label": topic_def["label"]})
                if row["count"] >= max(1, (ranked[0]["count"] if ranked else 0) * 0.5):
                    alarms.append({
                        **entry,
                        "topic": topic,
                        "topic_label": topic_def["label"],
                        "severity": "high" if row["count"] == (ranked[0]["count"] if ranked else 0) else "medium",
                        "message": (
                            f"Высокий показатель по «{topic_def['label']}» ({row['count']}), "
                            f"но поручение МВК по району не выявлено"
                        ),
                    })

        topics_out.append({
            "topic": topic,
            "label": topic_def["label"],
            "articles": topic_def["articles"],
            "total_stat": total,
            "assignments_count": len(assignments),
            "has_oblast_assignment": has_oblast,
            "districts": district_rows,
            "worst_district": ranked[0]["district"] if ranked else None,
            "worst_count": ranked[0]["count"] if ranked else 0,
        })

    coverage_rate = round(
        len(matched) / max(1, len(matched) + len(missed)) * 100, 1
    ) if (matched or missed) else None

    return {
        "year": year,
        "topics": topics_out,
        "matched": matched,
        "missed": missed,
        "alarms": alarms,
        "summary": {
            "topics_analyzed": len(MVK_TOPICS),
            "matched_district_topics": len(matched),
            "missed_district_topics": len(missed),
            "alarm_count": len(alarms),
            "coverage_rate_pct": coverage_rate,
            "verdict": (
                "МВК в целом охватывает ключевые проблемные районы"
                if coverage_rate and coverage_rate >= 60
                else "Выявлены слепые пятна: проблемные районы без поручений МВК"
            ),
        },
        "districts_total": len(districts),
    }
