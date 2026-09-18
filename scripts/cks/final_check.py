#!/usr/bin/env python3
"""Проверка перед публикацией: сходимость totals и отсутствие PII в docs/."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.cks.iin_utils import IIN_RE

DOCS = ROOT / "passports" / "docs"
DATA = ROOT / "passports" / "data" / "cks"
FIO_RE = re.compile(
    r"\b[А-ЯЁA-Z][а-яёa-z]{2,}\s+[А-ЯЁA-Z][а-яёa-z]{2,}\s+[А-ЯЁA-Z][а-яёa-z]{2,}\b"
)


def check_totals() -> list[str]:
    errs = []
    oblast = json.loads((DATA / "oblast.json").read_text(encoding="utf-8"))
    sum_persons = sum(d["persons"] for d in oblast.get("districts", []))
    sum_rows = sum(d["rows"] for d in oblast.get("districts", []))
    if sum_persons > oblast["totals"]["persons"]:
        errs.append(f"Сумма лиц по районам ({sum_persons}) > уникальных по области ({oblast['totals']['persons']}) — ожидаемо из-за дублей между районами")
    if abs(sum_rows - oblast["totals"]["rows"]) > 5000:
        errs.append(f"Строки: область {oblast['totals']['rows']} vs сумма районов {sum_rows}")
    for p in (DATA / "districts").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        np_sum = sum(s["persons"] for s in d.get("settlements", []))
        if d["totals"]["persons"] and np_sum > d["totals"]["persons"] * 1.05:
            errs.append(f"{p.name}: сумма НП {np_sum} >> persons {d['totals']['persons']} (дубли НП)")
    return errs


def check_pii() -> list[str]:
    errs = []
    html_paths = list(DOCS.glob("cks*.html"))
    json_paths = list((DOCS / "assets" / "data" / "cks").rglob("*.json"))
    for path in json_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if IIN_RE.search(text):
            errs.append(f"ИИН в {path.relative_to(ROOT)}")
        if '"fio"' in text.lower():
            errs.append(f"поле fio в {path.relative_to(ROOT)}")
    for path in html_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if IIN_RE.search(text):
            errs.append(f"ИИН в {path.relative_to(ROOT)}")
        if FIO_RE.search(text):
            errs.append(f"возможное ФИО в {path.relative_to(ROOT)}")
    return errs


def main() -> None:
    warnings = check_totals()
    errors = check_pii()
    print("=== Сходимость ===")
    for w in warnings:
        print("  note:", w)
    if not warnings:
        print("  OK")
    print("=== PII в docs ===")
    if errors:
        for e in errors:
            print("  FAIL:", e)
        raise SystemExit(1)
    print("  OK")
    manifest = ROOT / "passports" / "private" / "data" / "cks" / "persons" / "manifest.json"
    print("=== Шарды ===", "OK" if manifest.exists() else "нет manifest")


if __name__ == "__main__":
    main()
