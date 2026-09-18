from __future__ import annotations

import re

IIN_RE = re.compile(r"\b\d{12}\b")
WEIGHTS1 = list(range(1, 12))
WEIGHTS2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]


def raw_iin_digits(v) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return ""
    s = re.sub(r"\D", "", str(v).replace(".0", ""))
    return s


def normalize_iin(v) -> str:
    s = raw_iin_digits(v)
    if not s:
        return ""
    if len(s) < 12:
        s = s.zfill(12)
    if len(s) != 12:
        return ""
    if not (s[2:4].isdigit() and 1 <= int(s[2:4]) <= 12):
        return ""
    if not (s[4:6].isdigit() and 1 <= int(s[4:6]) <= 31):
        return ""
    return s


def iin_checksum_valid(iin: str) -> bool:
    if len(iin) != 12 or not iin.isdigit():
        return False
    digits = [int(c) for c in iin[:11]]

    def calc(weights: list[int]) -> int:
        return sum(d * w for d, w in zip(digits, weights)) % 11

    c1 = calc(WEIGHTS1)
    if c1 == 10:
        c1 = calc(WEIGHTS2)
    if c1 == 10:
        return False
    return c1 == int(iin[11])


def mask_iin(iin: str) -> str:
    if not iin or len(iin) < 4:
        return ""
    return "*" * (len(iin) - 4) + iin[-4:]
