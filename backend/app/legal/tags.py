"""Авто-тегирование норм: category/subject/measure/keywords (перекрёстные ссылки)."""
import re

_XREF_RE = re.compile(r"ст(?:ать[яеи])?\.?\s*(\d+(?:-\d+)?)", re.IGNORECASE)

_SUBJECT_RULES: list[tuple[str, str]] = [
    ("прокуратур", "прокуратура"),
    ("органов внутренних дел", "полиция (ОВД)"),
    ("полици", "полиция (ОВД)"),
    ("овд", "полиция (ОВД)"),
    ("суд", "суд"),
    ("аким", "МИО"),
    ("местн", "МИО"),
    ("исполнительн", "МИО"),
    ("социальн", "МИО"),
    ("налогов", "налоговый орган"),
]

_MEASURE_RULES: list[tuple[str, str]] = [
    ("протест", "протест"),
    ("представлен", "представление"),
    ("апелляц", "апелляционное ходатайство"),
    ("ходатайств", "ходатайство"),
    ("указани", "указание прокурора"),
    ("требован", "требование прокурора"),
    ("профилактическ", "профилактический учёт"),
    ("учёт", "профилактический учёт"),
    ("защитн", "защитное предписание"),
    ("штраф", "штраф"),
    ("арест", "административный арест"),
    ("предупрежден", "предупреждение"),
]


def extract_xrefs(text: str) -> list[str]:
    return sorted({f"ст.{m.group(1)}" for m in _XREF_RE.finditer(text or "")})


def auto_tags(title: str, text: str, category: str | None) -> dict:
    blob = f"{title or ''} {text or ''}".lower()
    subject = None
    for needle, val in _SUBJECT_RULES:
        if needle in blob:
            subject = val
            break
    measure = None
    for needle, val in _MEASURE_RULES:
        if needle in blob:
            measure = val
            break
    xrefs = extract_xrefs(text)
    keywords = ", ".join(xrefs) if xrefs else None
    cat = (category or "")[:128] or None
    if not cat and "семейно-быт" in blob:
        cat = "семейно-бытовая"
    elif not cat and "алкогол" in blob:
        cat = "оборот алкоголя"
    elif not cat and "несовершеннолет" in blob:
        cat = "несовершеннолетние"
    return {"category": cat, "subject": subject, "measure": measure, "keywords": keywords}
