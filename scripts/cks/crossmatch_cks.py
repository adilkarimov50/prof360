#!/usr/bin/env python3
"""Сверки ЦКС: умершие, уголовный/адм. контур, мультикатегории."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.cks.districts import DISTRICTS, district_title
from scripts.cks.load_sources import load_adm, load_deceased, load_prof_dela
from scripts.cks.paths import CROSSMATCH_JSON, DATA_CKS, PERSONS_STORE


def load_persons() -> pd.DataFrame:
    if not PERSONS_STORE.exists():
        raise SystemExit(f"Нет {PERSONS_STORE}; сначала: python scripts/cks/normalize_persons.py")
    return pd.read_pickle(PERSONS_STORE)


def person_index(df: pd.DataFrame) -> dict[str, dict]:
    """Одна запись на ИИН: категории, район, ФИО."""
    idx: dict[str, dict] = {}
    for iin, g in df.groupby("iin"):
        cats = sorted(set(g["category"].astype(str)))
        row = g.iloc[0]
        idx[iin] = {
            "iin": iin,
            "fio": str(g["fio"].dropna().iloc[0]) if g["fio"].notna().any() else "",
            "district_id": str(g["district_id"].mode().iloc[0]) if (g["district_id"] != "").any() else "",
            "settlement": str(g["settlement_canon"].mode().iloc[0]) if (g["settlement_canon"] != "").any() else "",
            "registration_scope": str(g["registration_scope"].mode().iloc[0]),
            "categories": cats,
            "category_count": len(cats),
            "record_count": len(g),
        }
    return idx


def main() -> None:
    df = load_persons()
    persons = person_index(df)
    dead = load_deceased()
    prof = load_prof_dela()
    adm = load_adm()

    dead_set = set(dead["iin"])
    prof_set = set(prof["iin"]) if len(prof) else set()
    adm_set = set(adm["iin"]) if len(adm) else set()
    cks_set = set(persons.keys())

    dead_in_cks = dead_set & cks_set
    dead_after_death_in_cks: list[dict] = []
    dead_map = dead.set_index("iin")["death_dt"].to_dict()
    for iin in dead_in_cks:
        p = persons[iin]
        dead_after_death_in_cks.append(
            {
                "iin": iin,
                "fio": p["fio"],
                "death_dt": dead_map[iin].isoformat() if pd.notna(dead_map[iin]) else "",
                "district_id": p["district_id"],
                "settlement": p["settlement"],
                "categories": p["categories"],
            }
        )

    prof_in_cks = prof_set & cks_set
    adm_in_cks = adm_set & cks_set
    prof_adm = prof_set & adm_set

    multi3 = [p for p in persons.values() if p["category_count"] >= 3]

    other_region = [p for p in persons.values() if p["registration_scope"] == "other_region"]
    almaty_city = [p for p in persons.values() if p["registration_scope"] == "almaty_city"]

    adm_other = []
    if len(adm):
        for _, r in adm[adm["registration_scope"] == "other_region"].iterrows():
            adm_other.append(
                {
                    "iin": r["iin"],
                    "oblast_residence": r["oblast_residence"],
                    "district_text": r["district_text"],
                }
            )

    dead_in_prof = dead_set & prof_set
    dead_in_adm = dead_set & adm_set

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "cks_unique_persons": len(persons),
            "cks_rows": len(df),
            "deceased_index": len(dead_set),
            "dead_in_cks": len(dead_in_cks),
            "prof_unique": len(prof_set),
            "prof_in_cks": len(prof_in_cks),
            "adm_unique": len(adm_set),
            "adm_in_cks": len(adm_in_cks),
            "prof_and_adm": len(prof_adm),
            "persons_3plus_categories": len(multi3),
            "other_region_persons": len(other_region),
            "almaty_city_scope": len(almaty_city),
            "adm_other_region": len(adm_other),
            "dead_in_prof": len(dead_in_prof),
            "dead_in_adm": len(dead_in_adm),
        },
        "dead_in_active_lists_sample": dead_after_death_in_cks[:500],
        "multi_category_sample": multi3[:500],
        "other_region_sample": other_region[:200],
        "adm_other_region_sample": adm_other[:200],
    }

    DATA_CKS.mkdir(parents=True, exist_ok=True)
    CROSSMATCH_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {CROSSMATCH_JSON}")
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
