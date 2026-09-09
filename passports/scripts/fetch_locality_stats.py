#!/usr/bin/env python3
"""Обновляет locality_profile в JSON паспортов из manual_stats.csv и localities_registry.yaml."""

from __future__ import annotations

import csv
import json
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CSV_PATH = DATA / "manual_stats.csv"
REGISTRY = DATA / "localities_registry.yaml"
BNS_SOURCE = {
    "title": "Бюро национальной статистики РК",
    "url": "https://stat.gov.kz",
    "as_of": "2025",
}


def load_registry() -> dict[str, dict]:
    if not REGISTRY.exists() or yaml is None:
        return {}
    raw = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    return {item["id"]: item for item in raw.get("localities", [])}


def load_csv_rows() -> dict[str, dict]:
    if not CSV_PATH.exists():
        return {}
    rows = {}
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["id"]] = row
    return rows


def build_profile(row: dict, reg: dict) -> dict:
    activities = [a.strip() for a in row.get("primary_activity", "").split(";") if a.strip()]
    ethnic = []
    for key, label in (
        ("ethnic_kazakh_pct", "казахи"),
        ("ethnic_russian_pct", "русские"),
        ("ethnic_other_pct", "другие"),
    ):
        val = row.get(key, "").strip()
        if val:
            ethnic.append({"group": label, "share_pct": float(val)})

    local_pct = row.get("local_permanent_pct", "").strip()
    pop_total = int(row.get("population_total") or 0)
    local_perm = int(pop_total * float(local_pct) / 100) if local_pct and pop_total else None

    social = [s.strip() for s in row.get("social_features", "").split(";") if s.strip()]
    highlights = [row.get("highlight_1", "").strip(), row.get("highlight_2", "").strip()]
    highlights = [h for h in highlights if h]

    prevention = []
    if row.get("prevention_factor_1"):
        prevention.append({
            "factor": row["prevention_factor_1"],
            "risk": row.get("prevention_risk_1", "medium"),
            "implication": row.get("prevention_implication_1", ""),
        })

    stype = reg.get("settlement_type", "city")
    is_agri = any("сельхоз" in a or "животновод" in a for a in activities)

    return {
        "settlement_type": stype,
        "admin_unit": reg.get("admin_unit", ""),
        "region": reg.get("region", "Алматинская область"),
        "population": {
            "total": pop_total,
            "year": int(row.get("population_year") or 2025),
            "local_permanent": local_perm,
            "arrivals": None,
            "departures": None,
            "internal_migrants_note": row.get("migrants_note", ""),
        },
        "ethnic_composition": ethnic,
        "economy": {
            "primary_activity": activities,
            "sme_registered": int(row["sme_count"]) if row.get("sme_count") else None,
            "agriculture": {"livestock": is_agri, "crops": []},
            "industry_services_note": "; ".join(activities),
        },
        "social_features": social,
        "prevention_factors": prevention,
        "highlights": highlights,
        "sources": [BNS_SOURCE, {"title": "Перепись населения РК 2021", "url": "https://stat.gov.kz", "as_of": "2021"}],
    }


def reg_from_row(row: dict, reg: dict) -> dict:
    return {
        "id": row.get("id") or reg.get("id", ""),
        "name": row.get("name") or reg.get("name", row.get("id", "")),
        "settlement_type": row.get("settlement_type") or reg.get("settlement_type", "city"),
        "admin_unit": row.get("admin_unit") or reg.get("admin_unit", ""),
        "region": row.get("region") or reg.get("region", "Алматинская область"),
    }


def profile_only_stub(reg: dict, row: dict) -> dict:
    meta = reg_from_row(row, reg)
    pop = int(row.get("population_total") or 0)
    profile = build_profile(row, meta)
    desc = profile["highlights"][0] if profile["highlights"] else meta["name"]
    return {
        "id": meta["id"],
        "name": meta["name"],
        "title": f"Криминологический профиль — {meta['name']}",
        "district": meta.get("admin_unit", ""),
        "year": 2026,
        "passport_status": "profile_only",
        "summary": {
            "settlement": meta["name"],
            "district": meta.get("admin_unit", ""),
            "population": pop,
            "description": desc,
            "crimes": {"current": None, "previous": None, "delta_pct": None},
            "rate_per_10k": None,
        },
        "locality_profile": profile,
        "data_quality": {
            "completeness": "profile",
            "as_of": "2026-09-09",
            "verified_by": "manual_stats.csv + БНС",
        },
        "crime_structure": [],
        "admin_practice": [],
        "registry": [],
        "measures": [],
        "expected_results": [],
    }


def merge_into(path: Path, profile: dict, status: str | None = None) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["locality_profile"] = profile
    if status:
        data["passport_status"] = status
    if "data_quality" not in data:
        data["data_quality"] = {
            "completeness": "full" if status == "full" else "profile",
            "as_of": "2026-09-09",
            "verified_by": "manual_stats.csv + паспорт",
        }
    if profile.get("population", {}).get("total") and data.get("summary"):
        if not data["summary"].get("population"):
            data["summary"]["population"] = profile["population"]["total"]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    registry = load_registry()
    csv_rows = load_csv_rows()
    profile_only_ids = {"alatau", "konaev", "talgar", "otegen_batyr", "uzynagash", "issyk"}
    full_ids = {"kaskelen", "irgeli", "chundzha"}

    for lid, row in csv_rows.items():
        reg = reg_from_row(row, registry.get(lid, {"id": lid}))
        profile = build_profile(row, reg)
        path = DATA / f"{lid}.json"
        if lid in profile_only_ids:
            stub = profile_only_stub(reg, row)
            path.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"created profile_only: {path.name}")
        elif path.exists():
            merge_into(path, profile, "full" if lid in full_ids else None)
            print(f"updated profile in: {path.name}")
        else:
            print(f"skip missing: {path.name}")

    print("Done.")


if __name__ == "__main__":
    main()
