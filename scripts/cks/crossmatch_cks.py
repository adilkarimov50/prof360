#!/usr/bin/env python3
"""Сверки ЦКС: умершие, уголовный/адм. контур, мультикатегории."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.cks.districts import DISTRICTS, detect_district_id
from scripts.cks.load_sources import load_adm, load_deceased, load_prof_dela
from scripts.cks.paths import CROSSMATCH_JSON, DATA_CKS, PERSONS_STORE

VIOLATIONS_PUBLIC = DATA_CKS / "violations_public.json"


def category_label(slug: str) -> str:
    return slug.replace("_", " ")[:120]


def load_persons() -> pd.DataFrame:
    if not PERSONS_STORE.exists():
        raise SystemExit(f"Нет {PERSONS_STORE}; сначала: python scripts/cks/normalize_persons.py")
    return pd.read_pickle(PERSONS_STORE)


def person_index(df: pd.DataFrame) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for iin, g in df.groupby("iin"):
        cats = sorted(set(g["category"].astype(str)))
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


def _district_rows(counter: Counter) -> list[dict]:
    rows = []
    for d in DISTRICTS:
        c = counter.get(d["id"], 0)
        if c:
            rows.append({"id": d["id"], "title": d["title"], "count": int(c)})
    unk = counter.get("", 0) + counter.get("unknown", 0)
    if unk:
        rows.append({"id": "unknown", "title": "— не определён", "count": int(unk)})
    rows.sort(key=lambda x: -x["count"])
    return rows


def build_violations_public(
    persons: dict[str, dict],
    dead: pd.DataFrame,
    prof: pd.DataFrame,
    adm: pd.DataFrame,
) -> dict:
    dead_set = set(dead["iin"])
    prof_set = set(prof["iin"]) if len(prof) else set()
    adm_set = set(adm["iin"]) if len(adm) else set()
    cks_set = set(persons.keys())

    dead_in_cks = dead_set & cks_set
    prof_in_cks = prof_set & cks_set
    adm_in_cks = adm_set & cks_set
    prof_adm = prof_set & adm_set
    prof_adm_in_cks = prof_adm & cks_set
    dead_in_prof = dead_set & prof_set
    dead_in_adm = dead_set & adm_set

    dead_dist: Counter = Counter()
    dead_cat: Counter = Counter()
    dead_year: Counter = Counter()
    dead_map = dead.set_index("iin")["death_dt"].to_dict()

    prof_cks_dist: Counter = Counter()
    adm_cks_dist: Counter = Counter()
    dead_prof_dist: Counter = Counter()
    dead_adm_dist: Counter = Counter()

    for iin in dead_in_cks:
        p = persons[iin]
        dead_dist[p["district_id"] or "unknown"] += 1
        for c in p["categories"]:
            dead_cat[c] += 1
        dt = dead_map.get(iin)
        if pd.notna(dt):
            dead_year[int(dt.year)] += 1

    prof_by_source: Counter = Counter()
    if len(prof):
        prof = prof.copy()
        if "source" not in prof.columns:
            prof["source"] = "prof_dela"
        if "district_id" not in prof.columns and "district_text" in prof.columns:
            prof["district_id"] = prof["district_text"].map(
                lambda x: detect_district_id(str(x)) or ""
            )
        for _, r in prof.iterrows():
            if r["iin"] in prof_in_cks:
                did = persons[r["iin"]]["district_id"] or r.get("district_id") or "unknown"
                prof_cks_dist[did] += 1
                prof_by_source[str(r.get("source", ""))] += 1

    if len(adm):
        for _, r in adm.iterrows():
            if r["iin"] in adm_in_cks:
                adm_cks_dist[persons[r["iin"]]["district_id"] or "unknown"] += 1

    for iin in dead_in_prof:
        if len(prof):
            sub = prof[prof["iin"] == iin]
            if len(sub):
                dead_prof_dist[str(sub.iloc[0].get("district_id") or sub.iloc[0].get("district_text") or "")] += 1

    for iin in dead_in_adm:
        if len(adm):
            sub = adm[adm["iin"] == iin]
            if len(sub):
                dead_adm_dist[str(sub.iloc[0].get("district_id") or "")] += 1

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "dead_in_cks": len(dead_in_cks),
            "dead_in_prof_dela": len(dead_in_prof),
            "dead_in_adm_protocols": len(dead_in_adm),
            "prof_in_cks": len(prof_in_cks),
            "adm_in_cks": len(adm_in_cks),
            "prof_and_adm_any": len(prof_adm),
            "prof_and_adm_in_cks": len(prof_adm_in_cks),
        },
        "dead_in_active_cks": {
            "total": len(dead_in_cks),
            "by_district": _district_rows(dead_dist),
            "by_category": [
                {"id": k, "label": category_label(k), "count": v}
                for k, v in dead_cat.most_common(20)
            ],
            "by_death_year": [{"year": y, "count": c} for y, c in sorted(dead_year.items())],
        },
        "prof_accountability": {
            "prof_dela_in_cks_total": len(prof_in_cks),
            "by_district": _district_rows(prof_cks_dist),
            "by_source_file": [{"source": k, "count": v} for k, v in prof_by_source.most_common()],
            "dead_still_in_prof_dela": len(dead_in_prof),
        },
        "admin_accountability": {
            "adm_protocols_in_cks_total": len(adm_in_cks),
            "by_district": _district_rows(adm_cks_dist),
            "dead_still_in_adm": len(dead_in_adm),
            "adm_other_region_protocols": int((adm["registration_scope"] == "other_region").sum()) if len(adm) else 0,
        },
    }


def main() -> None:
    df = load_persons()
    persons = person_index(df)
    dead = load_deceased()
    prof = load_prof_dela()
    adm = load_adm()

    violations = build_violations_public(persons, dead, prof, adm)

    dead_map = dead.set_index("iin")["death_dt"].to_dict()
    dead_in_cks = set(dead["iin"]) & set(persons.keys())
    dead_after_death_in_cks: list[dict] = []
    for iin in dead_in_cks:
        p = persons[iin]
        dead_after_death_in_cks.append(
            {
                "iin": iin,
                "fio": p["fio"],
                "death_dt": dead_map[iin].isoformat() if pd.notna(dead_map.get(iin)) else "",
                "district_id": p["district_id"],
                "settlement": p["settlement"],
                "categories": p["categories"],
            }
        )

    multi3 = [p for p in persons.values() if p["category_count"] >= 3]
    other_region = [p for p in persons.values() if p["registration_scope"] == "other_region"]

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "cks_unique_persons": len(persons),
            "cks_rows": len(df),
            "deceased_index": len(set(dead["iin"])),
            **violations["summary"],
            "persons_3plus_categories": len(multi3),
            "other_region_persons": len(other_region),
            "almaty_city_scope": sum(
                1 for p in persons.values() if p["registration_scope"] == "almaty_city"
            ),
            "adm_other_region": violations["admin_accountability"]["adm_other_region_protocols"],
            "prof_unique": len(set(prof["iin"])) if len(prof) else 0,
            "adm_unique": len(set(adm["iin"])) if len(adm) else 0,
            "prof_in_cks": violations["summary"]["prof_in_cks"],
            "adm_in_cks": violations["summary"]["adm_in_cks"],
            "prof_and_adm": violations["summary"]["prof_and_adm_any"],
            "dead_in_cks": violations["summary"]["dead_in_cks"],
            "dead_in_prof": violations["summary"]["dead_in_prof_dela"],
            "dead_in_adm": violations["summary"]["dead_in_adm_protocols"],
        },
        "dead_in_active_lists_sample": dead_after_death_in_cks,
        "multi_category_sample": multi3[:500],
        "other_region_sample": other_region[:200],
    }

    DATA_CKS.mkdir(parents=True, exist_ok=True)
    CROSSMATCH_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    VIOLATIONS_PUBLIC.write_text(json.dumps(violations, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {CROSSMATCH_JSON}")
    print(f"Wrote {VIOLATIONS_PUBLIC}")
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
