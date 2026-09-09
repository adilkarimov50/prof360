"""Канонические ссылки на акты реагирования по Приказу ГП РК №32.

Важно: п.1 Приказа — «Утвердить прилагаемые» (служебная норма), НЕ представление.
Представление — отдельный раздел приказа (в базе: article «Представление», norm_id=12).
"""
ORDER32 = "Приказ ГП РК №32 от 17.01.2023"

# Тип акта → как правильно ссылаться в тексте и как искать норму в БД
REACTION_ACTS: dict[str, dict] = {
    "representation": {
        "title": "Представление об устранении нарушений законности",
        "legal_ref": f"{ORDER32}, раздел «Представление об устранении нарушений законности»",
        "db_article": "Представление",
        "forbidden_point_refs": ("п.1", "пункт 1", "п. 1"),
        "addressee": "начальник Департамента полиции области / начальник ОВД района",
        "also_cite": f"{ORDER32}, п.5 (требования к актам реагирования)",
    },
    "protest": {
        "title": "Протест",
        "legal_ref": f"{ORDER32}, п.53–56",
        "db_article": "п.53",
        "forbidden_point_refs": ("п.1",),
        "addressee": "орган, принявший незаконный акт",
    },
    "appeal": {
        "title": "Апелляционное ходатайство",
        "legal_ref": f"{ORDER32}, п.57–58",
        "db_article": "п.57",
        "forbidden_point_refs": ("п.1",),
        "addressee": "суд",
    },
    "requirement": {
        "title": "Указание (требование) прокурора",
        "legal_ref": f"{ORDER32}, раздел «Указание и требование прокурора»",
        "db_article": "Указание",
        "forbidden_point_refs": ("п.1",),
        "addressee": "начальник территориального ОВД",
    },
}

# Сценарий: неполнота профилактики / продление учёта без решения
PROLONGATION_SCENARIO = {
    "law_ref": "Закон РК «О профилактике правонарушений» №245-VIII, ст.59, п.9",
    "law_norm_article": "ст.59",
    "law_norm_point": "9",
    "triggers": (
        "неполнот", "неэффектив", "продлен", "продлить профилакт",
        "без решения", "формальный учёт", "повтор на учёте",
    ),
    "reaction": "representation",
    "reason_template": (
        "выявлена неполнота или неэффективность профилактических мероприятий; "
        "имеются основания для продления профилактического учёта (ст.59, п.9 Закона о профилактике), "
        "но решение не принято / меры не обеспечены"
    ),
}


def reaction_legal_ref(reaction_type: str) -> str:
    return REACTION_ACTS.get(reaction_type, {}).get("legal_ref", ORDER32)


def fix_wrong_order32_points(text: str) -> tuple[str, list[str]]:
    """Заменяет типичную ошибку «п.1» при ссылке на представление."""
    warnings: list[str] = []
    low = text.lower()
    if "представлен" in low and any(b in low for b in ("п.1", "пункт 1", "п. 1")):
        fixed = text
        for bad in REACTION_ACTS["representation"]["forbidden_point_refs"]:
            if bad in fixed.lower():
                fixed = fixed.replace(
                    f"({bad} {ORDER32}",
                    f"({REACTION_ACTS['representation']['legal_ref']}",
                )
                fixed = fixed.replace(
                    f"({bad} Приказа",
                    f"({REACTION_ACTS['representation']['legal_ref']}",
                )
        if "п.1" in fixed and "представлен" in fixed.lower():
            fixed = fixed.replace(
                "п.1 Приказа ГП РК №32",
                REACTION_ACTS["representation"]["legal_ref"],
            ).replace(
                "п.1 Приказа №32",
                REACTION_ACTS["representation"]["legal_ref"],
            )
        if fixed != text:
            warnings.append(
                "Исправлена ссылка: п.1 Приказа №32 — это «Утвердить прилагаемые», "
                "не представление. Подставлен корректный раздел приказа."
            )
            text = fixed
    return text, warnings
