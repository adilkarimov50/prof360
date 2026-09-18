#!/usr/bin/env python3
"""Нормализация всех лиц ЦКС + отчёт по гео (контрольная точка)."""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.cks.districts import district_title, norm_key
from scripts.cks.geo_normalize import build_settlement_aliases, is_street_or_object, norm_key as _nk
from scripts.cks.load_sources import load_cks_person_rows
from scripts.cks.paths import PRIVATE_CKS, PERSONS_STORE, REPORTS


def apply_settlement_canon(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    alias_global: dict[str, str] = {}
    for did, sub in df[df["district_id"] != ""].groupby("district_id"):
        freq = Counter(sub["settlement"].astype(str))
        alias_global.update(build_settlement_aliases(freq))

    def canon_settlement(row) -> str:
        s = str(row.get("settlement") or "").strip()
        if not s or is_street_or_object(s):
            return ""
        k = norm_key(s)
        return alias_global.get(k, s.strip())

    df["settlement_canon"] = df.apply(canon_settlement, axis=1)
    return df


def write_geo_report(df: pd.DataFrame) -> None:
    lines = [
        "# Отчёт геонормализации ЦКС",
        "",
        f"Сформировано: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Доля разобранных адресов по району",
        "",
        "| Район | Строк | district_id | settlement | scope oblast | other_region | almaty_city | unresolved |",
        "|-------|------:|------------:|-----------:|-------------:|-------------:|------------:|-----------:|",
    ]
    for did in sorted(df["district_id"].unique(), key=lambda x: (x == "", x)):
        sub = df[df["district_id"] == did] if did else df[df["district_id"] == ""]
        title = district_title(did) if did else "— не определён"
        n = len(sub)
        with_set = int((sub["settlement_canon"] != "").sum())
        scopes = sub["registration_scope"].value_counts().to_dict()
        lines.append(
            f"| {title} | {n} | {int((sub['district_id']!='').sum())} | {with_set} "
            f"({round(100*with_set/max(n,1),1)}%) | {scopes.get('oblast',0)} | "
            f"{scopes.get('other_region',0)} | {scopes.get('almaty_city',0)} | {scopes.get('unresolved',0)} |"
        )

    lines.extend(["", "## Нераспознанные токены settlement (частота ≥ 20)", ""])
    bad = Counter()
    for s in df["settlement"].astype(str):
        if s and s != "nan" and is_street_or_object(s):
            bad[s[:60]] += 1
    for tok, cnt in bad.most_common(40):
        if cnt >= 20:
            lines.append(f"- `{tok}`: {cnt}")

    lines.extend(
        [
            "",
            "## Ограничение",
            "",
            "Строки «Статистика неработающего населения» не содержат НП в источнике — settlement пустой по дизайну.",
            "",
        ]
    )
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "cks_geo_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    df = load_cks_person_rows()
    df = apply_settlement_canon(df)
    PRIVATE_CKS.mkdir(parents=True, exist_ok=True)
    df.to_pickle(PERSONS_STORE)
    write_geo_report(df)
    print(f"Persons: {len(df)} rows, {df['iin'].nunique()} unique -> {PERSONS_STORE}")


if __name__ == "__main__":
    main()
