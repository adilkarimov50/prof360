"""Оценка эффективности МВК: достижение целей, кто не исполняет, верное ли направление."""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.ai import llm
from app.analytics import insights
from app.models.commission_session import CommissionAssignment, CommissionExecution, CommissionSession

logger = logging.getLogger("prof360.effectiveness")

SYSTEM_PROMPT = (
    "Ты прокурор-аналитик Алматинской области. "
    "Даёшь объективную оценку работы Межведомственной комиссии по профилактике. "
    "Опираешься только на факты. Отвечай строго в JSON без markdown."
)

STATUS_SCORES = {
    "executed": 100,
    "partial": 60,
    "formal": 25,
    "not_executed": 0,
    "unknown": 40,
}


def _organ_execution_matrix(session: CommissionSession) -> dict:
    """Матрица исполнения: орган → точки → статус."""
    matrix: dict[str, dict[str, dict]] = {}
    for assignment in session.assignments:
        pt = assignment.point_number
        for ex in assignment.executions:
            organ = ex.organ_name
            if organ not in matrix:
                matrix[organ] = {}
            matrix[organ][pt] = {
                "status": ex.execution_status,
                "quality_score": ex.quality_score,
                "assessment": ex.ai_assessment,
                "issues": ex.issues or [],
                "organ_type": ex.organ_type,
            }
    return matrix


def _assignment_completion_rate(assignment: CommissionAssignment) -> dict:
    execs = assignment.executions
    if not execs:
        return {"rate": 0, "responded": 0, "total_expected": 0}
    scores = [STATUS_SCORES.get(e.execution_status, 40) for e in execs]
    return {
        "rate": round(sum(scores) / len(scores), 1),
        "responded": len(execs),
        "executed_count": sum(1 for e in execs if e.execution_status == "executed"),
        "partial_count": sum(1 for e in execs if e.execution_status == "partial"),
        "formal_count": sum(1 for e in execs if e.execution_status == "formal"),
        "not_executed_count": sum(1 for e in execs if e.execution_status == "not_executed"),
    }


def _underperforming_organs(matrix: dict) -> list[dict]:
    """Органы с низким качеством исполнения."""
    organ_scores: dict[str, list[float]] = {}
    for organ, points in matrix.items():
        scores = []
        for pt, data in points.items():
            scores.append(STATUS_SCORES.get(data["status"], 40))
        if scores:
            organ_scores[organ] = scores

    result = []
    for organ, scores in organ_scores.items():
        avg = sum(scores) / len(scores)
        if avg < 65:
            formal_count = sum(
                1 for pt_data in matrix[organ].values()
                if pt_data["status"] in ("formal", "not_executed", "unknown")
            )
            result.append({
                "organ": organ,
                "avg_score": round(avg, 1),
                "points_count": len(scores),
                "formal_or_no_response": formal_count,
                "level": "critical" if avg < 30 else ("low" if avg < 55 else "medium"),
            })
    return sorted(result, key=lambda x: x["avg_score"])


def compute_session_effectiveness(db: Session, session: CommissionSession) -> dict:
    """Рассчитать эффективность заседания без AI (на основе оценок исполнений)."""
    if not session.assignments:
        return {"score": None, "note": "Поручения не загружены"}

    assignment_scores = []
    for assignment in session.assignments:
        comp = _assignment_completion_rate(assignment)
        assignment_scores.append(comp["rate"])

    overall = round(sum(assignment_scores) / len(assignment_scores), 1) if assignment_scores else None
    matrix = _organ_execution_matrix(session)
    underperformers = _underperforming_organs(matrix)

    return {
        "overall_score": overall,
        "assignments_count": len(session.assignments),
        "matrix": matrix,
        "underperforming_organs": underperformers,
        "assignment_breakdown": [
            {
                "point": a.point_number,
                "text": a.text[:200],
                "topic": a.topic,
                **_assignment_completion_rate(a),
            }
            for a in session.assignments
        ],
    }


def ai_effectiveness_report(db: Session, session: CommissionSession, district_stats: dict | None = None) -> dict:
    """AI-заключение: достигает ли МВК целей, кто недорабатывает, правильное ли направление."""
    basic = compute_session_effectiveness(db, session)
    matrix_json = json.dumps(basic.get("matrix", {}), ensure_ascii=False)[:4000]
    underperf_json = json.dumps(basic.get("underperforming_organs", []), ensure_ascii=False)

    # Реальная статистика из базы
    stats = district_stats or insights.commission_stats(db)
    stats_text = json.dumps(stats, ensure_ascii=False, indent=2)

    assignments_text = "\n".join(
        f"- П.{a.point_number} ({a.topic}): {a.text[:200]}"
        for a in session.assignments
    )

    prompt = f"""Проведи независимое прокурорское заключение об эффективности МВК.

Заседание №{session.session_number} от {session.session_date or '—'} (тип: {session.session_type}).

Поручения председателя:
{assignments_text}

Матрица исполнения (орган → точка → статус+оценка):
{matrix_json}

Органы с низкими показателями:
{underperf_json}

Реальная статистика из базы «Профилактика 360»:
{stats_text}

Ответь в JSON:
{{
  "goals_achieved": "yes|partial|no",
  "goals_summary": "2-3 предложения: достигнуты ли цели заседания на основе статистики",
  "critical_failures": ["конкретные факты провала исполнения"],
  "underperformers": [
    {{"organ": "...", "reason": "конкретная причина", "severity": "critical|medium|low"}}
  ],
  "direction_assessment": "right|needs_correction|wrong",
  "direction_comment": "верно ли МВК выбирает приоритеты, охватывает ли главные проблемы",
  "missed_priorities": ["что МВК не охватывает, но должна"],
  "recommendations": [
    "конкретная рекомендация прокурора по улучшению работы комиссии"
  ],
  "overall_grade": "A|B|C|D|F",
  "overall_comment": "итоговый вывод для председателя в 2-3 предложениях"
}}

Будь объективен. Если данных недостаточно — укажи это явно. Не хвали формальные отчёты как реальный результат.
"""
    raw = llm.generate(prompt, system=SYSTEM_PROMPT, temperature=0.15, max_tokens=4096)
    ai_result = llm.parse_json_from_llm(raw) or {
        "goals_achieved": "unknown",
        "overall_comment": raw[:500] if raw else "ИИ недоступен",
    }

    # Объединяем
    result = {**basic, "ai_analysis": ai_result}

    # Сохраняем в сессию
    session.analysis_json = result
    session.effectiveness_score = basic.get("overall_score")
    db.commit()

    return result


def get_cross_session_report(db: Session, year: int | None = None) -> dict:
    """Сводный отчёт по всем сессиям: динамика, системные проблемы, рейтинг органов."""
    q = db.query(CommissionSession)
    if year:
        q = q.filter(CommissionSession.year == year)
    sessions = q.order_by(CommissionSession.session_date).all()

    organ_totals: dict[str, list[float]] = {}
    session_summaries = []

    for s in sessions:
        if s.analysis_json:
            underp = s.analysis_json.get("underperforming_organs", [])
            for u in underp:
                organ = u.get("organ", "")
                score = u.get("avg_score", 50)
                organ_totals.setdefault(organ, []).append(score)

        session_summaries.append({
            "id": s.id,
            "number": s.session_number,
            "date": s.session_date.isoformat() if s.session_date else None,
            "type": s.session_type,
            "quarter": s.quarter,
            "effectiveness_score": s.effectiveness_score,
            "grade": (s.analysis_json or {}).get("ai_analysis", {}).get("overall_grade"),
            "goals_achieved": (s.analysis_json or {}).get("ai_analysis", {}).get("goals_achieved"),
        })

    # Рейтинг органов по всем сессиям
    organ_ratings = sorted([
        {"organ": org, "avg_score": round(sum(scores) / len(scores), 1), "sessions_count": len(scores)}
        for org, scores in organ_totals.items()
    ], key=lambda x: x["avg_score"])

    return {
        "sessions": session_summaries,
        "year": year,
        "total_sessions": len(sessions),
        "organ_ratings": organ_ratings,
    }
