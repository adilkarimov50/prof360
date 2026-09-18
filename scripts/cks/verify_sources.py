#!/usr/bin/env python3
"""Проверка источников ЦКС перед сборкой дашбордов."""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.cks.districts import detect_district_id, file_hint_district, norm_key
from scripts.cks.iin_utils import iin_checksum_valid, normalize_iin, raw_iin_digits
from scripts.cks.load_sources import load_cks_person_rows, list_cks_files
from scripts.cks.paths import ADM_XLSX, CKS_DIR, DEAD_XLSX, PROF_DIR, REPORTS


def analyze_file(path: Path) -> dict:
    df = pd.read_excel(path)
    out = {"file": path.name, "rows": len(df), "has_iin": "ИИН" in df.columns}
    if "ИИН" not in df.columns:
        return out
    raw_lens = df["ИИН"].map(lambda x: len(raw_iin_digits(x)))
    norm = df["ИИН"].map(normalize_iin)
    valid_ck = norm.map(lambda x: iin_checksum_valid(x) if x else False)
    out.update(
        {
            "iin_filled": int(norm.ne("").sum()),
            "unique_iin": int(norm[norm != ""].nunique()),
            "zfill_recovered": int((raw_lens < 12).sum()),
            "checksum_ok": int(valid_ck.sum()),
            "checksum_fail": int((norm != "").sum() - valid_ck.sum()),
            "addr_fill": int(df["Адрес"].notna().sum()) if "Адрес" in df.columns else 0,
            "raj_fill": int(df["Район"].notna().sum()) if "Район" in df.columns else 0,
            "fio_fill": int(df["ФИО"].notna().sum()) if "ФИО" in df.columns else 0,
        }
    )
    return out


def unemployed_mismatch() -> list[dict]:
    rows = []
    for path in sorted(CKS_DIR.glob("*.xlsx")):
        if "статистика неработающего" not in path.name.lower():
            continue
        hint = file_hint_district(path.name)
        df = pd.read_excel(path, usecols=["Адрес"], nrows=5000)
        if hint:
            matched = 0
            for a in df["Адрес"].dropna().astype(str):
                parts = a.split(",")
                seg = parts[1].strip() if len(parts) > 1 else parts[0]
                if detect_district_id(seg) == hint:
                    matched += 1
            rows.append(
                {
                    "file": path.name,
                    "hint": hint,
                    "sample": len(df),
                    "match_pct": round(100 * matched / max(len(df), 1), 1),
                }
            )
    return rows


def category_overlap(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    g = df.groupby("iin")["category"].nunique()
    buckets = Counter()
    for n in g:
        if n >= 5:
            buckets["5+"] += 1
        else:
            buckets[str(n)] += 1
    return dict(buckets)


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Отчёт проверки источников ЦКС",
        "",
        f"Сформировано: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Файлы с персональными данными",
        "",
        "| Файл | Строк | ИИН | Уник. ИИН | zfill | checksum OK | checksum fail |",
        "|------|------:|----:|----------:|------:|------------:|--------------:|",
    ]
    for path in list_cks_files():
        a = analyze_file(path)
        if not a.get("has_iin"):
            lines.append(f"| {a['file']} | {a['rows']} | — | — | — | — | — |")
            continue
        lines.append(
            f"| {a['file']} | {a['rows']} | {a['iin_filled']} | {a['unique_iin']} | "
            f"{a.get('zfill_recovered', 0)} | {a.get('checksum_ok', 0)} | {a.get('checksum_fail', 0)} |"
        )

    lines.extend(["", "## Неработающие: район в адресе vs имя файла (выборка 5000)", ""])
    for r in unemployed_mismatch():
        lines.append(f"- **{r['file']}** → `{r['hint']}`: совпадение {r['match_pct']}% (n={r['sample']})")

    lines.append("\n## Пересечения категорий по лицам\n")
    df = load_cks_person_rows()
    lines.append(f"Всего строк после нормализации ИИН: **{len(df)}**, уникальных лиц: **{df['iin'].nunique()}**")
    ov = category_overlap(df)
    for k in sorted(ov.keys(), key=lambda x: (x == "5+", x)):
        lines.append(f"- категорий на лицо = {k}: **{ov[k]}** лиц")

    lines.append("\n## Внешние источники\n")
    for label, p in [
        ("Умершие", DEAD_XLSX),
        ("АДМ 1-АД", ADM_XLSX),
        ("проф дела", PROF_DIR),
    ]:
        lines.append(f"- {label}: `{p}` — {'есть' if p.exists() else 'нет'}")

    out = REPORTS / "cks_verification.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
