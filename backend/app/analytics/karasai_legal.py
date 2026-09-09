"""Привязка выявленных разрывов к Закону №245-VIII и подзаконным актам."""

from __future__ import annotations

from app.prosecutor.order32_refs import ORDER32, REACTION_ACTS

LAW245 = "Закон РК «О профилактике правонарушений» от 30.12.2025 № 245-VIII"

# Канонические нормы для сопоставления «реальной картины»
LEGAL_FRAME: dict[str, dict] = {
    "population": {
        "law": f"{LAW245}, ст.41–43 (мониторинг эффективности мер)",
        "mvd": "Приказ МВД РК №662 (КАП, учёт показателей)",
        "reaction": "representation",
        "summary": "Некорректная база численности искажает уровень преступности и приоритеты профилактики.",
    },
    "crime_erdr": {
        "law": f"{LAW245}, ст.13 (учёт и индивидуальная профилактика ОВД)",
        "mvd": "Приказ МВД РК №662, учёт ЕРДР",
        "reaction": "requirement",
        "summary": "Расхождение паспорта и ЕРДР указывает на разрыв учётной дисциплины.",
    },
    "hotspot": {
        "law": f"{LAW245}, ст.48–69 (меры индивидуальной и средовой профилактики)",
        "mvd": "Приказ МВД РК №163 от 05.03.2026 (правила профучёта)",
        "reaction": "representation",
        "summary": "Разные методики привязки к объектам не позволяют адресно выставить наряд.",
    },
    "admin_geo": {
        "law": f"{LAW245}, ст.13, ст.59",
        "mvd": "Приказ МВД РК №662 (адм. практика, форма 1-АД)",
        "reaction": "representation",
        "summary": "Агрегация по району вместо НП маскирует масштаб адм. правонарушений в городе.",
    },
    "registry": {
        "law": f"{LAW245}, ст.59, п.9 (продление профучёта при неэффективности мер)",
        "mvd": "Приказ МВД РК №163; Приказ Минздрава №814 (медицинский учёт)",
        "reaction": "representation",
        "summary": "Разрыв медучёта, профучёта ОВД и адм. материалов — формальный характер профилактики.",
    },
    "minors": {
        "law": f"{LAW245}, ст.77 (несовершеннолетние)",
        "mvd": "Приказ МВД РК №163; Приказ МВД №1008 (координация профилактики)",
        "reaction": "representation",
        "summary": "Массовые ст.442 при минимальном учёте несовершеннолетних — системный провал.",
    },
    "commission_kpi": {
        "law": f"{LAW245}, ст.38 (межведомственная комиссия), ст.41–43 (KPI)",
        "mvd": "Приказ МВД №1008 (Комитет по координации профилактики)",
        "reaction": "representation",
        "summary": "Поручения комиссии без количественных KPI не обеспечивают контроль исполнения.",
    },
    "infrastructure": {
        "law": f"{LAW245}, ст.48–69 (средовая профилактика)",
        "mvd": "Приказ МВД №1008 (мониторинг); решения комиссии при акимате",
        "reaction": "representation",
        "summary": "Недостаток камер и освещения в точках концентрации снижает раскрываемость.",
    },
    "alcohol": {
        "law": f"{LAW245}, ст.74 (алкогольная преступность)",
        "mvd": "Приказ Минздрава №814; Приказ МВД №163",
        "reaction": "representation",
        "summary": "284 алкообъекта при 16 лицах на профучёте — неадресная профилактика.",
    },
}


def attach_legal(gap: dict) -> dict:
    """Добавить правовую оценку к записи расхождения."""
    kind = gap.get("kind", "")
    frame = LEGAL_FRAME.get(kind, {})
    reaction_key = frame.get("reaction", "representation")
    act = REACTION_ACTS.get(reaction_key, {})
    return {
        **gap,
        "legal": {
            "law": frame.get("law", LAW245),
            "subordinate": frame.get("mvd", ""),
            "summary": frame.get("summary", gap.get("note", "")),
            "reaction_type": reaction_key,
            "reaction_title": act.get("title", ""),
            "reaction_ref": act.get("legal_ref", ORDER32),
            "addressee": act.get("addressee", ""),
        },
    }


def legal_assessment(gaps: list[dict]) -> list[dict]:
    return [attach_legal(g) for g in gaps]
