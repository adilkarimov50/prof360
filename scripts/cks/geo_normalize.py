from __future__ import annotations

import re
from collections import Counter

from scripts.cks.districts import (
    ALMATY_CITY_DISTRICT_TOKENS,
    detect_district_id,
    norm_key,
)

STREET_MARKERS = (
    "УЛИЦА",
    "УЛ ",
    "ПРОСПЕКТ",
    "ПР ",
    "ПЕРЕУЛОК",
    "МИКРОРАЙОН",
    "МКР",
    "УЧЕТНЫЙ КВАРТАЛ",
    "ПОТРЕБИТЕЛЬСКИЙ",
    "ВОИНСКАЯ",
    "ТРАССА",
    " Д ",
    " Д.",
    " КВ ",
    " КОРПУС",
    "ЛА 155",
    "ЛА-155",
)

OBLAST_TOKENS = ("АЛМАТИНСК", "АЛМАТЫ ОБЛЫС", "АЛМАТИНСКАЯ ОБЛАСТ")
ALMATY_CITY_TOKENS = ("Г АЛМАТЫ", "ГОРОД АЛМАТЫ", " АЛМАТЫ,")
OTHER_REGION_HINTS = (
    "ЖАМБЫЛСК",
    "ТУРКЕСТАН",
    "ОБЛАСТЬ АБАЙ",
    "ЖЕТІСУ",
    "ЖЕТИСУ",
    "АСТАНА",
    "ШЫМКЕНТ",
    "АТЫРАУ",
    "МАНГИСТАУ",
    "КАРАГАНД",
    "ПАВЛОДАР",
    "СКО",
    "В КАЗАХСТАН",
)


def is_street_or_object(token: str) -> bool:
    k = norm_key(token)
    if not k or k in ("-", "NAN"):
        return True
    for m in STREET_MARKERS:
        if m in k:
            return True
    if re.search(r"\bД\s*\d", k):
        return True
    return False


def registration_scope_from_address(addr: str, district_col: str | None = None) -> str:
    k = norm_key(addr)
    if any(t in k for t in ALMATY_CITY_DISTRICT_TOKENS):
        return "almaty_city"
    if any(t in k for t in ALMATY_CITY_TOKENS) and "ОБЛ" not in k[:40]:
        return "almaty_city"
    for t in OTHER_REGION_HINTS:
        if t in k:
            return "other_region"
    if district_col:
        did = detect_district_id(district_col)
        if did:
            return "oblast"
    if any(t in k for t in OBLAST_TOKENS):
        return "oblast"
    return "unresolved"


def parse_address(addr: str) -> dict:
    """Разбор адреса ЦКС: округ, НП, улица; район из сегментов."""
    raw = (addr or "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    out = {
        "address_raw": raw,
        "okrug": "",
        "settlement": "",
        "district_id": None,
        "scope": registration_scope_from_address(raw),
    }
    if not parts:
        return out

    # Family B: Область, Район, улица
    if len(parts) >= 2:
        d_from = detect_district_id(parts[1]) or detect_district_id(parts[0])
        if d_from:
            out["district_id"] = d_from

    for p in parts:
        if detect_district_id(p):
            out["district_id"] = detect_district_id(p)

    # Family A: округ, НП, улица
    if len(parts) >= 3 and not is_street_or_object(parts[0]) and not is_street_or_object(parts[1]):
        if "ОБЛ" not in norm_key(parts[0]) and "РАЙОН" not in norm_key(parts[0]):
            out["okrug"] = parts[0]
            out["settlement"] = parts[1]
            return out

    if len(parts) >= 2:
        a, b = parts[0], parts[1]
        if is_street_or_object(a) and not is_street_or_object(b):
            out["settlement"] = b
        elif not is_street_or_object(a) and is_street_or_object(b):
            out["settlement"] = a
        elif not is_street_or_object(a) and not is_street_or_object(b):
            if "РАЙОН" in norm_key(a):
                pass
            elif "ОКРУГ" in norm_key(a) or "СКИЙ" in norm_key(a):
                out["okrug"] = a
                out["settlement"] = b
            else:
                out["settlement"] = a
    elif len(parts) == 1 and not is_street_or_object(parts[0]):
        out["settlement"] = parts[0]

    if out["settlement"] and is_street_or_object(out["settlement"]):
        out["settlement"] = ""

    return out


def normalize_settlement_name(name: str) -> str:
    n = norm_key(name)
    if not n:
        return ""
    n = re.sub(r"^(СЕЛО|С|Г|ГОРОД)\s+", "", n)
    return n.title() if len(n) < 40 else name.strip()


def build_settlement_aliases(freq: Counter) -> dict[str, str]:
    """Слияние частых вариантов написания НП по нормализованному ключу."""
    canon: dict[str, str] = {}
    for name, _ in freq.most_common():
        if not name or is_street_or_object(name):
            continue
        key = norm_key(name)
        if key not in canon:
            canon[key] = normalize_settlement_name(name)
    return canon
