from __future__ import annotations

import re
import unicodedata

# 11 канонических единиц области (город Алатау области ≠ район «Алатау» г. Алматы)
DISTRICTS: list[dict] = [
    {"id": "karasai", "title": "Карасайский район"},
    {"id": "talgar", "title": "Талгарский район"},
    {"id": "enbekshi", "title": "Енбекшиказахский район"},
    {"id": "ile", "title": "Илийский район"},
    {"id": "zhambyl", "title": "Жамбылский район"},
    {"id": "uygur", "title": "Уйгурский район"},
    {"id": "balkhash", "title": "Балхашский район"},
    {"id": "kegen", "title": "Кегенский район"},
    {"id": "raiymbek", "title": "Райымбекский район"},
    {"id": "konaev", "title": "г. Конаев"},
    {"id": "alatau_oblast", "title": "г. Алатау"},
]

ID_BY_TITLE = {d["title"]: d["id"] for d in DISTRICTS}

# Подстроки для сопоставления (после norm_key)
DISTRICT_PATTERNS: list[tuple[str, str]] = [
    ("karasai", "КАРАСАЙ"),
    ("talgar", "ТАЛГАР"),
    ("enbekshi", "ЕНБЕКШИКАЗАХ"),
    ("enbekshi", "ЕНБЕКШ"),
    ("ile", "ИЛИЙ"),
    ("zhambyl", "ЖАМБЫЛ"),
    ("uygur", "УЙГУР"),
    ("balkhash", "БАЛХАШ"),
    ("kegen", "КЕГЕН"),
    ("raiymbek", "РАЙЫМБЕК"),
    ("konaev", "КОНАЕВ"),
    ("konaev", "КАПЧАГАЙ"),
    ("alatau_oblast", "АЛАТАУ Г"),
    ("alatau_oblast", "Г АЛАТАУ"),
]

# Районы г. Алматы (не город Алатау области)
ALMATY_CITY_DISTRICT_TOKENS = (
    "АЛАТАУСК",
    "НАУРЫЗБАЙ",
    "АУЭЗОВ",
    "БОСТАНД",
    "ЖЕТЫСУ",
    "МЕДЕУ",
    "ТУРКСИБ",
    "АЛМАЛЫ",
)


def norm_key(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().upper()
    s = unicodedata.normalize("NFKC", s)
    for a, b in (
        ("Ё", "Е"),
        ("І", "И"),
        ("Ұ", "У"),
        ("Ү", "У"),
        ("Қ", "К"),
        ("Ғ", "Г"),
        ("Ә", "А"),
        ("Ө", "О"),
        ("Ң", "Н"),
        ("-", " "),
        (".", " "),
    ):
        s = s.replace(a, b)
    s = re.sub(r"[^A-ZА-Я0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def detect_district_id(text: str) -> str | None:
    k = norm_key(text)
    if not k:
        return None
    for did, tok in DISTRICT_PATTERNS:
        if tok in k:
            # «АЛАТАУСК» не путать с городом Алатау области
            if did == "alatau_oblast" and any(t in k for t in ALMATY_CITY_DISTRICT_TOKENS):
                continue
            return did
    if "АЛАТАУ" in k and "Г" in k:
        return "alatau_oblast"
    return None


def district_title(did: str | None) -> str:
    if not did:
        return "—"
    for d in DISTRICTS:
        if d["id"] == did:
            return d["title"]
    return did


def file_hint_district(filename: str) -> str | None:
    fn = norm_key(filename)
    hints = [
        ("karasai", "КАРАСАЙ"),
        ("talgar", "ТАЛГАР"),
        ("enbekshi", "ЕНБЕКШИКАЗАХ"),
        ("ile", "ИЛИЙ"),
        ("zhambyl", "ЖАМБЫЛ"),
        ("uygur", "УЙГУР"),
        ("balkhash", "БАЛХАШ"),
        ("kegen", "КЕГЕН"),
        ("konaev", "КОНАЕВ"),
        ("alatau_oblast", "АЛАТАУ"),
        ("raiymbek", "РАЙЫМБЕК"),
    ]
    for did, tok in hints:
        if tok in fn:
            if did == "alatau_oblast" and "АЛАТАУСК" in fn:
                continue
            return did
    return None
