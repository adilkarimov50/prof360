"""Маппинг колонок Excel по заголовкам с фолбэком на позиционные индексы."""
from __future__ import annotations

# Позиционные индексы (legacy) для адм. массива
ADM_FALLBACK = {
    "organ": 1, "subdivision": 2, "district": 3, "place": 4, "material_no": 5,
    "date": 6, "qual": 9, "fabula": 10, "surname": 11, "name": 12, "patronymic": 13,
    "gender": 14, "res_region": 17, "res_district": 18, "res_locality": 19,
    "iin": 20, "intox": 22, "phone": 23, "decision": 24, "measure": 28, "fine": 29,
}

# Ключевые слова заголовков -> поле
ADM_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "organ": ("орган", "орган вынес"),
    "subdivision": ("подраздел", "отдел", "служб"),
    "district": ("район", "территори"),
    "place": ("место", "адрес соверш", "место соверш"),
    "material_no": ("материал", "номер материал", "протокол"),
    "date": ("дата", "дата соверш", "дата правонар"),
    "qual": ("квалиф", "статья", "состав"),
    "fabula": ("фабул", "описание", "содержание"),
    "surname": ("фамил",),
    "name": ("имя",),
    "patronymic": ("отчеств",),
    "gender": ("пол",),
    "res_region": ("область", "регион прож"),
    "res_district": ("район прож", "район регист"),
    "res_locality": ("населен", "нас. пункт", "город", "село"),
    "iin": ("иин", "инн", "идентиф"),
    "intox": ("опьян", "алкогол", "состоян"),
    "phone": ("телефон", "контакт"),
    "decision": ("решение", "постановлен"),
    "measure": ("мера", "взыскан", "наказан"),
    "fine": ("штраф", "сумм"),
}

CRIM_FALLBACK = {
    "erdr": 1, "organ": 3, "iin": 6, "surname": 7, "name": 8, "patronymic": 9,
    "dob": 10, "qual": 11, "gravity": 13, "region": 15,
}

CRIM_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "erdr": ("ердр", "номер ердр"),
    "organ": ("орган", "инициатор"),
    "iin": ("иин",),
    "surname": ("фамил",),
    "name": ("имя",),
    "patronymic": ("отчеств",),
    "dob": ("дата рожд", "рожд"),
    "qual": ("квалиф", "статья"),
    "gravity": ("тяжест", "категор"),
    "region": ("район", "регион", "област"),
}


def _find_col(headers: list[str], aliases: tuple[str, ...]) -> int | None:
    for i, h in enumerate(headers):
        hl = (h or "").lower()
        if any(a in hl for a in aliases):
            return i
    return None


def build_map(headers: list[str] | None, field_aliases: dict[str, tuple[str, ...]],
              fallback: dict[str, int]) -> dict[str, int]:
    """Строит маппинг поле -> индекс колонки."""
    if not headers or all(not (h or "").strip() for h in headers):
        return dict(fallback)
    result: dict[str, int] = {}
    for field, aliases in field_aliases.items():
        idx = _find_col(headers, aliases)
        result[field] = idx if idx is not None else fallback.get(field, 0)
    return result


def build_admin_map(headers: list[str] | None) -> dict[str, int]:
    return build_map(headers, ADM_HEADER_ALIASES, ADM_FALLBACK)


def build_crim_map(headers: list[str] | None) -> dict[str, int]:
    return build_map(headers, CRIM_HEADER_ALIASES, CRIM_FALLBACK)


def row_get(row: tuple, colmap: dict[str, int], field: str):
    idx = colmap.get(field)
    if idx is None or idx >= len(row):
        return None
    return row[idx]
