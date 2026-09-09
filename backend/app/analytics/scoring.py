"""Риск-скоринг лиц и генерация автоматических сигналов (таблицы 18-19, 10.2 ТЗ)."""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.analytics.normalize import SB_ARTICLES, ALC_ARTICLES, art_base, is_intoxicated
from app.models.person import AdminCase, Person, PreventiveRecord, Signal, Suspect

PROTECTIVE_VIOLATION = "ст.461"


def risk_level(score: int) -> str:
    if score >= 19:
        return "Критический"
    if score >= 11:
        return "Высокий"
    if score >= 5:
        return "Средний"
    return "Низкий"


def _is_sb(article_base: str | None) -> bool:
    return bool(article_base) and any(article_base.startswith(a) for a in SB_ARTICLES)


def compute_person_factors(person: Person) -> tuple[int, list[dict], list[dict]]:
    """Возвращает (балл, факторы, сигналы) на основе связанных данных лица."""
    cases: list[AdminCase] = list(person.admin_cases)
    prev: list[PreventiveRecord] = list(person.preventive_records)
    suspects: list[Suspect] = list(person.suspects)

    factors: list[dict] = []
    signals: list[dict] = []
    score = 0

    n = len(cases)
    if n >= 1:
        score += 1
        factors.append({"factor": "Административное правонарушение", "points": 1})
    # повторность за 12 месяцев
    dated = sorted([c.case_date for c in cases if c.case_date])
    repeat_12m = False
    for i in range(1, len(dated)):
        if dated[i] - dated[i - 1] <= timedelta(days=365):
            repeat_12m = True
            break
    if repeat_12m:
        score += 3
        factors.append({"factor": "Повторное правонарушение за 12 мес.", "points": 3})
        signals.append({"type": "repeat_admin", "level": "Средний",
                        "message": "Лицо повторно привлечено к административной ответственности"})
    if n >= 3:
        score += 5
        factors.append({"factor": "Три и более правонарушения", "points": 5})

    sb_cases = [c for c in cases if _is_sb(c.article_base)]
    if sb_cases:
        score += 4
        factors.append({"factor": "Семейно-бытовое правонарушение", "points": 4})
    if any(art_base(c.article_base) == PROTECTIVE_VIOLATION for c in cases):
        score += 6
        factors.append({"factor": "Нарушение защитного предписания", "points": 6})

    on_register = len(prev) > 0
    if on_register:
        score += 3
        factors.append({"factor": "Состоит на профилактическом учёте", "points": 3})

    # повторность после постановки на учёт
    repeat_after = False
    for p in prev:
        if not p.date_post:
            continue
        end = p.date_removed or date.today()
        if any(p.date_post <= c.case_date <= end for c in cases if c.case_date):
            repeat_after = True
            break
    if repeat_after:
        score += 7
        factors.append({"factor": "Повторность после постановки на учёт", "points": 7})
        signals.append({"type": "repeat_on_register", "level": "Высокий",
                        "message": "Лицо на учёте повторно совершило правонарушение (признак формального учёта)"})

    if suspects:
        score += 8
        factors.append({"factor": "Признан подозреваемым (ЕРДР)", "points": 8})
        # эскалация в период учёта
        for s in suspects:
            for p in prev:
                if p.date_post and s.erdr_year:
                    end_year = (p.date_removed or date.today()).year
                    if p.date_post.year <= s.erdr_year <= end_year:
                        signals.append({"type": "escalation_during_register", "level": "Критический",
                                        "message": f"Стал подозреваемым ({s.qualification}) в период профучёта"})
                        break

    # возможное бездействие: повторные СБ, но не на учёте
    if len(sb_cases) >= 2 and not on_register:
        score += 6
        factors.append({"factor": "Отсутствие профилактической меры (СБ без учёта)", "points": 6})
        signals.append({"type": "should_be_registered", "level": "Высокий",
                        "message": "Лицо подлежит постановке на профилактический учёт, но не поставлено"})

    # алкоголь / ст.200 (продажа несовершеннолетним)
    alc_cases = [c for c in cases if c.article_base in ALC_ARTICLES or c.source == "alcohol"]
    if alc_cases:
        score += 2
        factors.append({"factor": "Алкогольное правонарушение", "points": 2})
    if any(c.article_base == "ст.200" for c in cases):
        score += 4
        factors.append({"factor": "ст.200 КоАП (оборот алкоголя)", "points": 4})
        signals.append({"type": "alcohol_200", "level": "Средний",
                        "message": "Правонарушение по обороту алкоголя (ст.200)"})

    # опьянение как усиливающий фактор
    if any(is_intoxicated(c.intoxication) for c in cases):
        score += 2
        factors.append({"factor": "Состояние опьянения зафиксировано", "points": 2})

    # качество решения: наложение без меры
    if any(
        (c.decision or "").lower().find("наложением") >= 0 and not (c.measure or "").strip()
        for c in cases
    ):
        score += 3
        factors.append({"factor": "Решение о наложении без указания меры", "points": 3})
        signals.append({"type": "decision_quality", "level": "Средний",
                        "message": "Постановление о наложении взыскания без указания меры — кандидат на проверку"})

    return score, factors, signals


def recompute_person(db: Session, person: Person, persist_signals: bool = True) -> dict:
    score, factors, signals = compute_person_factors(person)
    person.risk_score = score
    person.risk_level = risk_level(score)
    if persist_signals:
        db.query(Signal).filter(Signal.person_id == person.id).delete()
        for sig in signals:
            db.add(Signal(person_id=person.id, **sig))
    return {"score": score, "level": person.risk_level, "factors": factors, "signals": signals}


def recompute_all(db: Session, batch: int = 500) -> int:
    persons = db.query(Person).all()
    for i, person in enumerate(persons, 1):
        recompute_person(db, person)
        if i % batch == 0:
            db.flush()
    db.commit()
    return len(persons)
