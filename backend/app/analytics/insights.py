"""Агрегированная аналитика: дашборд области, повторность, эскалация."""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics.normalize import (
    ALC_ARTICLES,
    CYBER_FRAUD_ARTICLES,
    CYBER_FRAUD_KEYWORDS,
    EXTORTION_ARTICLES,
    EXTORTION_KEYWORDS,
    JUVENILE_CATEGORIES,
    SB_ARTICLES,
    VAPE_ARTICLES,
)
from app.analytics.organ import classify_organ, is_mio_preventive
from app.models.person import AdminCase, Person, PreventiveRecord, Signal, Suspect


def district_risk(db: Session, district_filter: str | None = None) -> list[dict]:
    rows = (
        db.query(Person.district, Person.risk_level, func.count(Person.id))
        .group_by(Person.district, Person.risk_level)
        .all()
    )
    agg: dict[str, dict] = {}
    for district, level, cnt in rows:
        d = district or "—"
        if district_filter and d != district_filter:
            continue
        agg.setdefault(d, {"district": d, "total": 0, "high": 0, "critical": 0})
        agg[d]["total"] += cnt
        if level == "Высокий":
            agg[d]["high"] += cnt
        elif level == "Критический":
            agg[d]["critical"] += cnt
    return sorted(agg.values(), key=lambda x: -(x["critical"] * 10 + x["high"]))


def top_persons(db: Session, limit: int = 10, district_filter: str | None = None) -> list[dict]:
    q = db.query(Person).order_by(Person.risk_score.desc())
    if district_filter:
        q = q.filter(Person.district == district_filter)
    return [
        {"id": p.id, "fio": p.fio, "district": p.district,
         "risk_score": p.risk_score, "risk_level": p.risk_level}
        for p in q.limit(limit).all()
    ]


def signal_summary(db: Session) -> list[dict]:
    rows = (
        db.query(Signal.type, Signal.level, func.count(Signal.id))
        .group_by(Signal.type, Signal.level)
        .all()
    )
    return [{"type": t, "level": lvl, "count": c} for t, lvl, c in rows]


def overview_counters(db: Session, district_filter: str | None = None) -> dict:
    pq = db.query(Person)
    if district_filter:
        pq = pq.filter(Person.district == district_filter)
    total_persons = pq.count()
    high = pq.filter(Person.risk_level.in_(["Высокий", "Критический"])).count()

    should_register = db.query(Signal).filter(Signal.type == "should_be_registered").count()
    repeat_on_reg = db.query(Signal).filter(Signal.type == "repeat_on_register").count()
    escalation = db.query(Signal).filter(Signal.type == "escalation_during_register").count()

    return {
        "persons": total_persons,
        "high_risk": high,
        "admin_cases": db.query(AdminCase).count(),
        "preventive": db.query(PreventiveRecord).count(),
        "suspects": db.query(Suspect).count(),
        "should_be_registered": should_register,
        "repeat_on_register": repeat_on_reg,
        "escalation_during_register": escalation,
    }


def article_stats(db: Session, limit: int = 12, district_filter: str | None = None) -> list[dict]:
    q = db.query(AdminCase.article_base, func.count(AdminCase.id)).filter(
        AdminCase.article_base.is_not(None))
    if district_filter:
        q = q.filter(AdminCase.district == district_filter)
    rows = (
        q.group_by(AdminCase.article_base)
        .order_by(func.count(AdminCase.id).desc())
        .limit(limit)
        .all()
    )
    return [{"article": a, "count": c} for a, c in rows]


def escalation_during_register(db: Session, limit: int = 100) -> list[dict]:
    """Лица, ставшие подозреваемыми в период нахождения на профучёте."""
    out: list[dict] = []
    persons = (
        db.query(Person)
        .join(Suspect, Suspect.person_id == Person.id)
        .join(PreventiveRecord, PreventiveRecord.person_id == Person.id)
        .distinct()
        .all()
    )
    for p in persons:
        for s in p.suspects:
            if not s.erdr_year:
                continue
            for pr in p.preventive_records:
                if not pr.date_post:
                    continue
                end_year = (pr.date_removed or date.today()).year
                if pr.date_post.year <= s.erdr_year <= end_year:
                    out.append({
                        "person_id": p.id, "fio": p.fio, "district": p.district,
                        "date_post": pr.date_post, "date_removed": pr.date_removed,
                        "category": pr.category, "erdr_no": s.erdr_no,
                        "erdr_year": s.erdr_year, "qualification": s.qualification,
                        "gravity": s.gravity, "in_period": True,
                    })
                    break
            else:
                continue
            break
    out.sort(key=lambda x: (x["gravity"] or "", x["fio"]))
    return out[:limit]


def cases_timeseries(db: Session, district_filter: str | None = None) -> list[dict]:
    """Динамика административных дел по месяцам (тренд)."""
    month = func.date_trunc("month", AdminCase.case_date)
    q = db.query(month.label("m"), func.count(AdminCase.id)).filter(AdminCase.case_date.is_not(None))
    if district_filter:
        q = q.filter(AdminCase.district == district_filter)
    rows = q.group_by(month).order_by(month).all()
    return [{"month": m.strftime("%Y-%m"), "count": c} for m, c in rows if m]


def sb_stats(db: Session, district_filter: str | None = None) -> dict:
    """Семейно-бытовая статистика: ст.73, нарушение защитного предписания (ст.461), защитные предписания."""
    ac = db.query(AdminCase)
    pr = db.query(PreventiveRecord)
    if district_filter:
        ac = ac.filter(AdminCase.district == district_filter)
        pr = pr.filter(PreventiveRecord.district == district_filter)

    sb_cases = ac.filter(AdminCase.article_base.in_(SB_ARTICLES)).count()
    zp_violations = ac.filter(AdminCase.article_base == "ст.461").count()
    protective_orders = pr.filter(PreventiveRecord.has_special_req.is_(True)).count()

    # разбивка ст.73 по районам (топ-10)
    bd = db.query(AdminCase.district, func.count(AdminCase.id)).filter(
        AdminCase.article_base.in_(SB_ARTICLES))
    if district_filter:
        bd = bd.filter(AdminCase.district == district_filter)
    by_district = [
        {"district": d or "—", "count": c}
        for d, c in bd.group_by(AdminCase.district).order_by(func.count(AdminCase.id).desc()).limit(10).all()
    ]
    return {
        "sb_cases": sb_cases,
        "zp_violations": zp_violations,
        "protective_orders": protective_orders,
        "by_district": by_district,
    }


def organ_breakdown(db: Session, district_filter: str | None = None) -> dict:
    """Разрез административной практики по линиям ответственности: полиция / МИО / не распознано."""
    q = db.query(AdminCase.organ, AdminCase.subdivision, func.count(AdminCase.id))
    if district_filter:
        q = q.filter(AdminCase.district == district_filter)
    rows = q.group_by(AdminCase.organ, AdminCase.subdivision).all()
    buckets = {"police": 0, "mio": 0, "unknown": 0}
    for organ, subdivision, cnt in rows:
        buckets[classify_organ(organ, subdivision)] += cnt
    return {
        "police": buckets["police"],
        "mio": buckets["mio"],
        "unknown": buckets["unknown"],
        "series": [
            {"line": "Полиция (ОВД)", "count": buckets["police"]},
            {"line": "МИО", "count": buckets["mio"]},
            {"line": "Не распознано", "count": buckets["unknown"]},
        ],
    }


def mio_indicators(db: Session, district_filter: str | None = None) -> dict:
    """Производные индикаторы зоны ответственности МИО (социальная профилактика).

    Внимание: в исходных данных орган МИО отсутствует, поэтому индикаторы выводятся
    из категорий профучёта (несовершеннолетние/социальные формы) и охвата мерами.
    """
    pr = db.query(PreventiveRecord)
    if district_filter:
        pr = pr.filter(PreventiveRecord.district == district_filter)
    records = pr.all()
    mio_records = [r for r in records if is_mio_preventive(r.category)]
    mio_person_ids = {r.person_id for r in mio_records}

    # лица из зоны МИО, по которым есть эскалация (признак провала соц. профилактики)
    escalated = 0
    if mio_person_ids:
        escalated = (
            db.query(func.count(func.distinct(Suspect.person_id)))
            .filter(Suspect.person_id.in_(mio_person_ids))
            .scalar() or 0
        )
    # разбивка по формам учёта
    forms: dict[str, int] = {}
    for r in mio_records:
        forms[r.form or "—"] = forms.get(r.form or "—", 0) + 1
    return {
        "mio_preventive_records": len(mio_records),
        "mio_persons": len(mio_person_ids),
        "mio_escalated_persons": int(escalated),
        "by_form": [{"form": f, "count": c} for f, c in sorted(forms.items(), key=lambda x: -x[1])],
    }


def district_drilldown(db: Session, district: str) -> dict:
    """Детализация по одному району для drilldown-панели."""
    return {
        "district": district,
        "counters": overview_counters(db, district),
        "top_persons": top_persons(db, 15, district),
        "articles": article_stats(db, 10, district),
        "sb": sb_stats(db, district),
        "organs": organ_breakdown(db, district),
    }


def _qualify_matches(qualification: str | None, articles: tuple, keywords: tuple) -> bool:
    if not qualification:
        return False
    q = qualification.upper()
    for art in articles:
        if art.upper() in q:
            return True
    for kw in keywords:
        if kw.upper() in q:
            return True
    return False


def commission_stats(db: Session, district_filter: str | None = None) -> dict:
    """Агрегат по темам повестки МВК: интернет-мошенничество, вымогательство, алкоголь, вейп, несовершеннолетние."""
    suspects = db.query(Suspect)
    admin = db.query(AdminCase)
    preventive = db.query(PreventiveRecord)

    if district_filter:
        admin = admin.filter(AdminCase.district == district_filter)
        preventive = preventive.filter(PreventiveRecord.district == district_filter)

    all_suspects = suspects.all()
    if district_filter:
        person_ids_in_district = {
            p.id for p in db.query(Person.id).filter(Person.district == district_filter).all()
        }
        all_suspects = [s for s in all_suspects if s.person_id in person_ids_in_district]

    cyber_fraud = sum(
        1 for s in all_suspects
        if _qualify_matches(s.qualification, CYBER_FRAUD_ARTICLES, CYBER_FRAUD_KEYWORDS)
    )
    extortion = sum(
        1 for s in all_suspects
        if _qualify_matches(s.qualification, EXTORTION_ARTICLES, EXTORTION_KEYWORDS)
    )
    vape = sum(
        1 for s in all_suspects
        if _qualify_matches(s.qualification, VAPE_ARTICLES, ())
    )

    alc_cases = admin.filter(AdminCase.article_base.in_(ALC_ARTICLES)).count()
    alc_intox = admin.filter(
        AdminCase.intoxication.is_not(None),
        AdminCase.intoxication != "",
    ).count()

    juv_records = preventive.filter(
        func.upper(PreventiveRecord.category).contains("НЕСОВЕРШЕННОЛЕТН")
        | func.upper(PreventiveRecord.category).contains("КӘМЕЛЕТКЕ")
    ).count()

    by_district_cyber: list[dict] = []
    if not district_filter:
        rows = (
            db.query(Person.district, func.count(Suspect.id))
            .join(Suspect, Suspect.person_id == Person.id)
            .filter(Suspect.qualification.in_(CYBER_FRAUD_ARTICLES))
            .group_by(Person.district)
            .order_by(func.count(Suspect.id).desc())
            .limit(11)
            .all()
        )
        by_district_cyber = [{"district": d or "—", "count": c} for d, c in rows]

    return {
        "cyber_fraud": cyber_fraud,
        "extortion": extortion,
        "vape_violations": vape,
        "alcohol_admin_cases": alc_cases,
        "alcohol_intoxicated_offenders": alc_intox,
        "juvenile_preventive_records": juv_records,
        "by_district_cyber_fraud": by_district_cyber,
    }


def repeat_offenders(db: Session, min_cases: int = 2, limit: int = 100) -> list[dict]:
    rows = (
        db.query(Person, func.count(AdminCase.id).label("cnt"))
        .join(AdminCase, AdminCase.person_id == Person.id)
        .group_by(Person.id)
        .having(func.count(AdminCase.id) >= min_cases)
        .order_by(func.count(AdminCase.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {"person_id": p.id, "fio": p.fio, "district": p.district,
         "cases": cnt, "risk_level": p.risk_level,
         "on_register": len(p.preventive_records) > 0}
        for p, cnt in rows
    ]


def hot_spots(db: Session, district_filter: str | None = None, article: str | None = None) -> dict:
    """Гео/временные горячие точки: топ районов и месяцев по числу дел."""
    ac = db.query(AdminCase).filter(AdminCase.case_date.is_not(None))
    if district_filter:
        ac = ac.filter(AdminCase.district == district_filter)
    if article:
        ac = ac.filter(AdminCase.article_base == article)

    by_district = (
        ac.with_entities(AdminCase.district, func.count(AdminCase.id))
        .group_by(AdminCase.district)
        .order_by(func.count(AdminCase.id).desc())
        .limit(10)
        .all()
    )
    month = func.date_trunc("month", AdminCase.case_date)
    by_month = (
        ac.with_entities(month, func.count(AdminCase.id))
        .group_by(month)
        .order_by(func.count(AdminCase.id).desc())
        .limit(6)
        .all()
    )
    return {
        "districts": [{"district": d or "—", "count": c} for d, c in by_district],
        "months": [{"month": m.strftime("%Y-%m"), "count": c} for m, c in by_month if m],
        "article_filter": article,
    }


def alcohol_correlation(db: Session, district_filter: str | None = None) -> dict:
    """Корреляция опьянения с семейно-бытовыми и алкогольными составами."""
    from app.analytics.normalize import is_intoxicated

    q = db.query(AdminCase)
    if district_filter:
        q = q.filter(AdminCase.district == district_filter)
    cases = q.filter(AdminCase.intoxication.is_not(None)).all()
    sb_intox = sum(
        1 for c in cases
        if c.article_base in ("ст.73", "ст.73-1", "ст.73-2") and is_intoxicated(c.intoxication)
    )
    alc_intox = sum(
        1 for c in cases
        if c.article_base and c.article_base.startswith("ст.2") and is_intoxicated(c.intoxication)
    )
    return {
        "cases_with_intox_field": len(cases),
        "sb_with_intoxication": sb_intox,
        "alcohol_articles_with_intoxication": alc_intox,
    }


def decision_quality(db: Session, district_filter: str | None = None) -> dict:
    """Качество решений: наложение без меры, мягкие меры по СБ."""
    from app.analytics.proceedings import admin_proceeding_violations

    summary = admin_proceeding_violations(db, district_filter)
    imposed_no_measure = next(
        (c for c in summary["categories"] if c["code"] == "no_measure"), {"count": 0}
    )
    return {
        "violation_candidates_total": summary["total"],
        "imposed_without_measure": imposed_no_measure["count"],
        "by_category": summary["categories"][:4],
    }


def _signal_count(db: Session, signal_type: str, district_filter: str | None = None) -> int:
    q = db.query(Signal).filter(Signal.type == signal_type)
    if district_filter:
        q = q.join(Person, Person.id == Signal.person_id).filter(Person.district == district_filter)
    return q.count()


def _persons_on_register(db: Session, district_filter: str | None = None) -> int:
    q = db.query(func.count(func.distinct(PreventiveRecord.person_id)))
    if district_filter:
        q = q.filter(PreventiveRecord.district == district_filter)
    return q.scalar() or 0


def _pct(part: int, whole: int) -> float | None:
    if whole <= 0:
        return None
    return round(part / whole * 100, 1)


def prevention_pipeline(db: Session, district_filter: str | None = None) -> dict:
    """Воронка профилактики: адм. дела → СБ → учёт → пропуски → эскалация → ЕРДР."""
    ac = db.query(AdminCase)
    if district_filter:
        ac = ac.filter(AdminCase.district == district_filter)

    total_admin = ac.count()
    sb_cases = ac.filter(AdminCase.article_base.in_(SB_ARTICLES)).count()
    on_register = _persons_on_register(db, district_filter)
    missed = _signal_count(db, "should_be_registered", district_filter)
    repeat_on_reg = _signal_count(db, "repeat_on_register", district_filter)
    escalated = _signal_count(db, "escalation_during_register", district_filter)

    sq = db.query(Suspect)
    if district_filter:
        person_ids = {p.id for p in db.query(Person.id).filter(Person.district == district_filter).all()}
        suspects = sum(1 for s in sq.all() if s.person_id in person_ids)
    else:
        suspects = sq.count()

    steps = [
        {"key": "total_admin_cases", "label": "Адм. дела (все)", "count": total_admin, "pct_of_prev": 100.0},
        {"key": "sb_cases", "label": "Семейно-бытовые (ст.73)", "count": sb_cases,
         "pct_of_prev": _pct(sb_cases, total_admin)},
        {"key": "on_register", "label": "На профучёте", "count": on_register,
         "pct_of_prev": _pct(on_register, sb_cases or total_admin)},
        {"key": "should_be_registered", "label": "Пропущено (должны быть на учёте)", "count": missed,
         "pct_of_prev": _pct(missed, sb_cases or total_admin)},
        {"key": "repeat_on_register", "label": "Повторность на учёте", "count": repeat_on_reg,
         "pct_of_prev": _pct(repeat_on_reg, on_register)},
        {"key": "escalation_during_register", "label": "Эскалация в период учёта", "count": escalated,
         "pct_of_prev": _pct(escalated, on_register)},
        {"key": "suspects", "label": "Подозреваемые (ЕРДР)", "count": suspects,
         "pct_of_prev": _pct(suspects, total_admin)},
    ]

    by_district: list[dict] = []
    if not district_filter:
        districts = {
            d for d, in db.query(AdminCase.district).distinct().all() if d
        }
        districts.update(d for d, in db.query(Person.district).distinct().all() if d)
        for d in sorted(districts):
            pipe = prevention_pipeline(db, d)
            by_district.append({
                "district": d,
                "total_admin_cases": pipe["steps"][0]["count"],
                "sb_cases": pipe["steps"][1]["count"],
                "on_register": pipe["steps"][2]["count"],
                "should_be_registered": pipe["steps"][3]["count"],
                "escalated": pipe["steps"][5]["count"],
                "suspects": pipe["steps"][6]["count"],
            })

    return {
        "district_filter": district_filter,
        "steps": steps,
        "summary": {
            "conversion_to_register_pct": _pct(on_register, sb_cases),
            "missed_registration_pct": _pct(missed, sb_cases),
            "escalation_rate_pct": _pct(escalated, on_register),
        },
        "by_district": by_district,
    }


def law_compliance(db: Session, district_filter: str | None = None) -> dict:
    """Соблюдение ключевых норм: Закон о профилактике, КоАП, УК."""
    ac = db.query(AdminCase)
    if district_filter:
        ac = ac.filter(AdminCase.district == district_filter)

    sb_cases = ac.filter(AdminCase.article_base.in_(SB_ARTICLES)).all()
    sb_person_ids = {c.person_id for c in sb_cases}
    sb_with_register = 0
    if sb_person_ids:
        sb_with_register = (
            db.query(func.count(func.distinct(PreventiveRecord.person_id)))
            .filter(PreventiveRecord.person_id.in_(sb_person_ids))
            .scalar() or 0
        )

    sb_with_measure = sum(
        1 for c in sb_cases
        if (c.measure or "").strip() or (c.decision or "").lower().find("предупрежд") >= 0
    )
    sb_imposed_no_measure = sum(
        1 for c in sb_cases
        if "наложением" in (c.decision or "").lower() and not (c.measure or "").strip()
    )

    zp_cases = [c for c in ac.all() if c.article_base == "ст.461"]
    zp_person_repeat: dict[int, int] = {}
    for c in zp_cases:
        zp_person_repeat[c.person_id] = zp_person_repeat.get(c.person_id, 0) + 1
    zp_repeat_persons = sum(1 for cnt in zp_person_repeat.values() if cnt >= 2)

    all_suspects = db.query(Suspect).all()
    if district_filter:
        person_ids = {p.id for p in db.query(Person.id).filter(Person.district == district_filter).all()}
        all_suspects = [s for s in all_suspects if s.person_id in person_ids]

    cyber_by_district: dict[str, int] = {}
    extortion_by_district: dict[str, int] = {}
    for s in all_suspects:
        if not s.person_id:
            continue
        person = db.query(Person).filter(Person.id == s.person_id).first()
        if not person or not person.district:
            continue
        d = person.district
        if _qualify_matches(s.qualification, CYBER_FRAUD_ARTICLES, CYBER_FRAUD_KEYWORDS):
            cyber_by_district[d] = cyber_by_district.get(d, 0) + 1
        if _qualify_matches(s.qualification, EXTORTION_ARTICLES, EXTORTION_KEYWORDS):
            extortion_by_district[d] = extortion_by_district.get(d, 0) + 1

    norms = [
        {
            "law": "Закон о профилактике №245-VIII",
            "article": "ст.58",
            "requirement": "Постановка на профилактический учёт лиц, совершивших семейно-бытовые правонарушения",
            "numerator": sb_with_register,
            "denominator": len(sb_person_ids),
            "compliance_pct": _pct(sb_with_register, len(sb_person_ids)),
            "verdict": (
                "соблюдается" if _pct(sb_with_register, len(sb_person_ids) or 0) and
                (_pct(sb_with_register, len(sb_person_ids) or 0) or 0) >= 70
                else "нарушается"
            ) if sb_person_ids else "нет данных",
        },
        {
            "law": "КоАП РК",
            "article": "ст.54",
            "requirement": "Назначение административного взыскания / меры по семейно-бытовым составам",
            "numerator": sb_with_measure,
            "denominator": len(sb_cases),
            "compliance_pct": _pct(sb_with_measure, len(sb_cases)),
            "verdict": (
                "соблюдается" if (_pct(sb_with_measure, len(sb_cases) or 0) or 0) >= 85
                else "нарушается"
            ) if sb_cases else "нет данных",
        },
        {
            "law": "КоАП РК",
            "article": "ст.461",
            "requirement": "Повторные нарушения защитного предписания — усиление ответственности",
            "numerator": zp_repeat_persons,
            "denominator": len(zp_person_repeat),
            "compliance_pct": _pct(zp_repeat_persons, len(zp_person_repeat)),
            "verdict": (
                "требует контроля" if zp_repeat_persons > 0 else "без повторов"
            ) if zp_cases else "нет данных",
        },
        {
            "law": "КоАП РК",
            "article": "ст.73",
            "requirement": "Решение о наложении должно сопровождаться мерой взыскания",
            "numerator": sb_imposed_no_measure,
            "denominator": len(sb_cases),
            "compliance_pct": _pct(sb_imposed_no_measure, len(sb_cases)),
            "verdict": (
                "нарушается" if sb_imposed_no_measure > 0 else "соблюдается"
            ) if sb_cases else "нет данных",
            "inverted": True,
        },
        {
            "law": "УК РК",
            "article": "ст.190",
            "requirement": "Мошенничество — мониторинг роста по районам",
            "numerator": sum(cyber_by_district.values()),
            "denominator": len(cyber_by_district) or 1,
            "compliance_pct": None,
            "verdict": "мониторинг",
            "by_district": sorted(
                [{"district": d, "count": c} for d, c in cyber_by_district.items()],
                key=lambda x: -x["count"],
            )[:10],
        },
        {
            "law": "УК РК",
            "article": "ст.194",
            "requirement": "Вымогательство — мониторинг роста по районам",
            "numerator": sum(extortion_by_district.values()),
            "denominator": len(extortion_by_district) or 1,
            "compliance_pct": None,
            "verdict": "мониторинг",
            "by_district": sorted(
                [{"district": d, "count": c} for d, c in extortion_by_district.items()],
                key=lambda x: -x["count"],
            )[:10],
        },
    ]

    return {
        "district_filter": district_filter,
        "norms": norms,
        "overall_score": round(
            sum(n["compliance_pct"] or 0 for n in norms[:3 if len(norms) >= 3 else len(norms)])
            / max(1, sum(1 for n in norms[:3] if n.get("compliance_pct") is not None)),
            1,
        ) if any(n.get("compliance_pct") is not None for n in norms) else None,
    }


def _district_topic_count(db: Session, district: str, topic: str) -> int:
    """Подсчёт показателя темы МВК по одному району."""
    if topic == "cyber":
        suspects = (
            db.query(Suspect)
            .join(Person, Person.id == Suspect.person_id)
            .filter(Person.district == district)
            .all()
        )
        return sum(
            1 for s in suspects
            if _qualify_matches(s.qualification, CYBER_FRAUD_ARTICLES, CYBER_FRAUD_KEYWORDS)
        )
    if topic == "extortion":
        suspects = (
            db.query(Suspect)
            .join(Person, Person.id == Suspect.person_id)
            .filter(Person.district == district)
            .all()
        )
        return sum(
            1 for s in suspects
            if _qualify_matches(s.qualification, EXTORTION_ARTICLES, EXTORTION_KEYWORDS)
        )
    if topic == "vape":
        suspects = (
            db.query(Suspect)
            .join(Person, Person.id == Suspect.person_id)
            .filter(Person.district == district)
            .all()
        )
        return sum(1 for s in suspects if _qualify_matches(s.qualification, VAPE_ARTICLES, ()))
    if topic == "alcohol":
        return (
            db.query(AdminCase)
            .filter(AdminCase.district == district, AdminCase.article_base.in_(ALC_ARTICLES))
            .count()
        )
    if topic == "juvenile":
        return (
            db.query(PreventiveRecord)
            .filter(
                PreventiveRecord.district == district,
                func.upper(PreventiveRecord.category).contains("НЕСОВЕРШЕННОЛЕТН")
                | func.upper(PreventiveRecord.category).contains("КӘМЕЛЕТКЕ"),
            )
            .count()
        )
    return 0


def _mvk_effectiveness_by_district(db: Session) -> dict[str, float]:
    """Средняя оценка исполнения поручений МВК по районам (по organ_name)."""
    from app.models.commission_session import CommissionExecution

    scores: dict[str, list[float]] = {}
    for ex in db.query(CommissionExecution).filter(CommissionExecution.quality_score.is_not(None)).all():
        organ = (ex.organ_name or "").lower()
        for d, in db.query(Person.district).distinct().all():
            if not d:
                continue
            if d.lower()[:6] in organ or organ[:6] in d.lower():
                scores.setdefault(d, []).append(ex.quality_score or 0)
                break
    return {d: round(sum(v) / len(v), 1) for d, v in scores.items() if v}


def _build_district_matrix(db: Session, district_filter: str | None = None) -> list[dict]:
    """Районная матрица: все измерения в одной строке."""
    districts = set()
    if district_filter:
        districts.add(district_filter)
    else:
        for model, col in (
            (Person, Person.district),
            (AdminCase, AdminCase.district),
            (PreventiveRecord, PreventiveRecord.district),
        ):
            districts.update(d for d, in db.query(col).distinct().all() if d)

    mvk_eff = _mvk_effectiveness_by_district(db)
    matrix: list[dict] = []

    for d in sorted(districts):
        risk = district_risk(db, d)
        risk_row = risk[0] if risk else {"total": 0, "high": 0, "critical": 0}
        admin_cnt = db.query(AdminCase).filter(AdminCase.district == d).count()
        prev_cnt = db.query(PreventiveRecord).filter(PreventiveRecord.district == d).count()
        signals = {
            "should_be_registered": _signal_count(db, "should_be_registered", d),
            "repeat_on_register": _signal_count(db, "repeat_on_register", d),
            "escalation": _signal_count(db, "escalation_during_register", d),
        }
        comm = commission_stats(db, d)
        matrix.append({
            "district": d,
            "risk_total": risk_row["total"],
            "risk_high": risk_row["high"],
            "risk_critical": risk_row["critical"],
            "admin_cases": admin_cnt,
            "preventive": prev_cnt,
            "signals_total": sum(signals.values()),
            "signals": signals,
            "cyber_fraud": comm["cyber_fraud"],
            "extortion": comm["extortion"],
            "juvenile": comm["juvenile_preventive_records"],
            "alcohol": comm["alcohol_admin_cases"],
            "vape": comm["vape_violations"],
            "mvk_effectiveness": mvk_eff.get(d),
        })

    matrix.sort(key=lambda x: -(x["risk_critical"] * 10 + x["risk_high"] + x["signals_total"]))
    return matrix


def unified_oblast_picture(db: Session, district_filter: str | None = None) -> dict:
    """Единая сводная картина области: все потоки данных и взаимосвязи."""
    from app.analytics.proceedings import admin_proceeding_violations

    pipeline = prevention_pipeline(db, district_filter)
    proceedings = admin_proceeding_violations(db, district_filter)

    return {
        "district_filter": district_filter,
        "overview": overview_counters(db, district_filter),
        "district_risk": district_risk(db, district_filter),
        "district_matrix": _build_district_matrix(db, district_filter),
        "sb_stats": sb_stats(db, district_filter),
        "organ_breakdown": organ_breakdown(db, district_filter),
        "mio_indicators": mio_indicators(db, district_filter),
        "commission_stats": commission_stats(db, district_filter),
        "proceedings": {
            "total": proceedings["total"],
            "categories": proceedings["categories"],
            "by_district": proceedings["by_district"],
        },
        "pipeline": pipeline,
        "hot_spots": hot_spots(db, district_filter),
        "alcohol_correlation": alcohol_correlation(db, district_filter),
        "decision_quality": decision_quality(db, district_filter),
        "signals": signal_summary(db),
    }
