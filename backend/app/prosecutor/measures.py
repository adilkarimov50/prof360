"""Подбор актов прокурорского реагирования по Приказу ГП РК №32 от 17.01.2023.

Возвращает рекомендованные меры (представление, протест, апелляционное ходатайство,
указание/требование) с обоснованием, правовой привязкой и сроками.
"""
from datetime import date, timedelta

from app.analytics.normalize import SB_ARTICLES, art_base
from app.analytics.scoring import compute_person_factors
from app.models.person import AdminCase, Person

# Срок обжалования постановления по делу об адм. правонарушении (КоАП РК) — 10 суток
APPEAL_TERM_DAYS = 10

from app.prosecutor.order32_refs import ORDER32, REACTION_ACTS, reaction_legal_ref


def _termination(decision: str | None) -> bool:
    d = (decision or "").lower()
    return any(k in d for k in ("прекращ", "возврат", "отказано"))


def _is_court(case: AdminCase) -> bool:
    blob = " ".join(filter(None, [case.decision, case.organ, case.subdivision])).lower()
    return "суд" in blob


def _lenient_measure(case: AdminCase) -> bool:
    m = (case.measure or "").lower()
    return (not m) or ("предупрежд" in m)


def protest_candidates(person: Person) -> list[dict]:
    """Адм. дела с признаками незаконности/необоснованной мягкости (кандидаты на протест)."""
    out: list[dict] = []
    for c in person.admin_cases:
        reasons = []
        if _termination(c.decision):
            reasons.append("прекращение/возврат материала — проверить обоснованность")
        if art_base(c.article_base) in SB_ARTICLES and _lenient_measure(c):
            reasons.append("семейно-бытовой состав при мягкой мере/без взыскания (риск занижения)")
        if reasons:
            out.append({
                "case_id": c.id,
                "material_no": c.material_no,
                "qualification": c.qualification,
                "case_date": c.case_date,
                "reason": "; ".join(reasons),
            })
    return out


def appeal_candidates(person: Person) -> list[dict]:
    """Судебные материалы в пределах срока обжалования (КоАП — 10 суток)."""
    out: list[dict] = []
    today = date.today()
    for c in person.admin_cases:
        if not _is_court(c) or not c.case_date:
            continue
        deadline = c.case_date + timedelta(days=APPEAL_TERM_DAYS)
        out.append({
            "case_id": c.id,
            "material_no": c.material_no,
            "qualification": c.qualification,
            "case_date": c.case_date,
            "deadline": deadline,
            "in_term": today <= deadline,
        })
    return out


def recommend_measures(person: Person) -> list[dict]:
    """Список рекомендованных актов прокурорского реагирования (Приказ ГП РК №32)."""
    _, _, signals = compute_person_factors(person)
    signal_types = {s["type"] for s in signals}
    measures: list[dict] = []

    # 1. Представление об устранении нарушений законности
    repr_reasons = []
    if "should_be_registered" in signal_types:
        repr_reasons.append("лицо подлежит постановке на профилактический учёт, но не поставлено")
    if "repeat_on_register" in signal_types:
        repr_reasons.append("повторность правонарушений в период нахождения на учёте (формальный учёт)")
    if "repeat_on_register" in signal_types or "escalation_during_register" in signal_types:
        repr_reasons.append(
            "неполнота/неэффективность профилактических мер; основания для продления учёта "
            "(ст.59, п.9 Закона о профилактике) без соответствующего решения"
        )
    if "escalation_during_register" in signal_types:
        repr_reasons.append("эскалация в уголовное правонарушение в период учёта (бездействие субъектов профилактики)")
    measures.append({
        "type": "representation",
        "title": "Представление об устранении нарушений законности",
        "applicable": bool(repr_reasons),
        "reason": "; ".join(repr_reasons) or "системных нарушений по имеющимся данным не выявлено",
        "legal_basis": [
            reaction_legal_ref("representation"),
            f"{ORDER32}, п.5",
            "Закон РК «О профилактике правонарушений» №245-VIII, ст.58, ст.59 п.9, ст.72",
        ],
        "addressee": REACTION_ACTS["representation"]["addressee"],
    })

    # 2. Протест на незаконное постановление
    prot = protest_candidates(person)
    measures.append({
        "type": "protest",
        "title": "Протест на постановление по делу об административном правонарушении",
        "applicable": bool(prot),
        "reason": (f"выявлено материалов с признаками незаконности: {len(prot)}"
                   if prot else "признаков незаконности постановлений не выявлено"),
        "legal_basis": [reaction_legal_ref("protest"), "КоАП РК"],
        "candidates": prot,
    })

    # 3. Апелляционное ходатайство (судебные материалы в пределах срока)
    appeals = appeal_candidates(person)
    in_term = [a for a in appeals if a["in_term"]]
    measures.append({
        "type": "appeal",
        "title": "Апелляционное ходатайство (обжалование судебного акта)",
        "applicable": bool(in_term),
        "reason": (f"судебных материалов в пределах срока обжалования: {len(in_term)}"
                   if in_term else
                   ("судебные материалы есть, срок обжалования истёк" if appeals
                    else "судебных материалов не выявлено")),
        "legal_basis": [reaction_legal_ref("appeal"), "КоАП РК (срок обжалования — 10 суток)"],
        "candidates": appeals,
    })

    # 4. Указание / требование прокурора
    req_applicable = bool(signal_types & {"should_be_registered", "repeat_on_register", "escalation_during_register"})
    measures.append({
        "type": "requirement",
        "title": "Указание (требование) прокурора в ОВД",
        "applicable": req_applicable,
        "reason": ("о постановке на профилактический учёт и усилении индивидуальной профилактической работы"
                   if req_applicable else "оснований для безотлагательного требования не выявлено"),
        "legal_basis": [reaction_legal_ref("requirement"), "Конституционный закон «О прокуратуре»"],
        "addressee": REACTION_ACTS["requirement"]["addressee"],
    })

    return measures
