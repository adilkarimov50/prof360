#!/usr/bin/env python3
"""Агрегаты ЦКС для публикации + шарды лиц в private."""

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

from scripts.cks.districts import DISTRICTS, district_title
from scripts.cks.iin_utils import mask_iin
from scripts.cks.load_sources import load_deceased
from scripts.cks.paths import (
    CROSSMATCH_JSON,
    DATA_CKS,
    DATA_DISTRICTS,
    PRIVATE_PERSONS,
    PERSONS_STORE,
)

NP_MINI_THRESHOLD = 50
SHARD_SIZE = 400


def load_crossmatch() -> dict:
    if CROSSMATCH_JSON.exists():
        return json.loads(CROSSMATCH_JSON.read_text(encoding="utf-8"))
    return {"counts": {}, "dead_in_active_lists_sample": [], "multi_category_sample": []}


def category_label(slug: str) -> str:
    return slug.replace("_", " ")[:120]


def aggregate_persons(df: pd.DataFrame) -> tuple[dict, dict[str, dict]]:
    """oblast payload + district payloads (без ФИО/ИИН)."""
    cross = load_crossmatch()
    dead = load_deceased()
    dead_set = set(dead["iin"]) if len(dead) else set()
    multi_iins = set(
        df.groupby("iin")["category"].nunique()[lambda s: s >= 3].index.astype(str)
    )

    by_district_rows: dict[str, list] = defaultdict(list)
    for _, r in df.iterrows():
        did = r["district_id"] or "unknown"
        by_district_rows[did].append(r)

    district_payloads: dict[str, dict] = {}

    oblast_categories = Counter()
    oblast_scopes = Counter()
    district_totals = []

    for d in DISTRICTS:
        did = d["id"]
        sub = df[df["district_id"] == did]
        if sub.empty:
            district_payloads[did] = {
                "id": did,
                "title": d["title"],
                "mini_passport": _mini_passport(did, d["title"], sub, cross),
                "settlements": [],
                "categories": [],
                "scopes": {},
                "totals": {"rows": 0, "persons": 0},
            }
            continue

        persons_n = sub["iin"].nunique()
        cat_counts = Counter(sub["category"].astype(str))
        scope_counts = Counter(sub["registration_scope"].astype(str))
        oblast_categories.update(cat_counts)
        oblast_scopes.update(scope_counts)
        district_totals.append({"id": did, "title": d["title"], "rows": len(sub), "persons": persons_n})

        np_rows = []
        g = sub.groupby(["okrug", "settlement_canon"], dropna=False)
        for (okrug, np), sg in g:
            np_name = str(np or "").strip() or "—"
            ok = str(okrug or "").strip()
            cnt = sg["iin"].nunique()
            np_rows.append(
                {
                    "okrug": ok,
                    "settlement": np_name,
                    "persons": int(cnt),
                    "rows": int(len(sg)),
                    "mini_passport": _mini_passport_np(did, ok, np_name, sg) if cnt >= NP_MINI_THRESHOLD else None,
                }
            )
        np_rows.sort(key=lambda x: -x["persons"])

        district_payloads[did] = {
            "id": did,
            "title": d["title"],
            "mini_passport": _mini_passport(did, d["title"], sub, cross),
            "settlements": np_rows[:500],
            "categories": [
                {"id": k, "label": category_label(k), "persons": int(sub[sub["category"] == k]["iin"].nunique())}
                for k, _ in cat_counts.most_common(40)
            ],
            "scopes": dict(scope_counts),
            "totals": {"rows": int(len(sub)), "persons": int(persons_n)},
            "flags": {
                "dead_in_lists_persons": int(sub.loc[sub["iin"].isin(dead_set), "iin"].nunique()),
                "multi_category_persons": int(sub.loc[sub["iin"].isin(multi_iins), "iin"].nunique()),
            },
        }

    unknown = df[df["district_id"] == ""]
    oblast = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "title": "Алматинская область — данные ЦКС",
        "totals": {
            "rows": int(len(df)),
            "persons": int(df["iin"].nunique()),
            "district_unknown_rows": int(len(unknown)),
        },
        "districts": district_totals,
        "top_categories": [
            {"id": k, "label": category_label(k), "persons": v}
            for k, v in oblast_categories.most_common(25)
        ],
        "registration_scope": dict(oblast_scopes),
        "crossmatch": cross.get("counts", {}),
        "district_ids": [d["id"] for d in DISTRICTS],
    }
    return oblast, district_payloads


def _mini_passport(did: str, title: str, sub: pd.DataFrame, cross: dict) -> dict:
    if sub.empty:
        return {"title": title, "highlights": ["Нет строк в выгрузке ЦКС для этого района."]}
    top_cat = sub["category"].value_counts().head(3).index.tolist()
    neet = int(sub["category"].str.contains("nezanjat", case=False, na=False).sum())
    convicted = int(sub["category"].str.contains("osuzhd", case=False, na=False).sum())
    highlights = [
        f"Уникальных лиц в строках района: {sub['iin'].nunique():,}".replace(",", " "),
        f"Записей (с дублями категорий): {len(sub):,}".replace(",", " "),
        f"Топ категорий: {', '.join(category_label(c) for c in top_cat)}",
    ]
    if neet:
        highlights.append(f"Молодёжь NEET / незанятые (строк): {neet:,}".replace(",", " "))
    if convicted:
        highlights.append(f"Отбывающие наказание (строк): {convicted}")
    other = int((sub["registration_scope"] == "other_region").sum())
    if other:
        highlights.append(f"Признак регистрации в другом регионе (строк): {other:,}".replace(",", " "))
    return {"title": title, "district_id": did, "highlights": highlights}


def _mini_passport_np(did: str, okrug: str, np: str, sg: pd.DataFrame) -> dict:
    return {
        "settlement": np,
        "okrug": okrug,
        "persons": int(sg["iin"].nunique()),
        "top_categories": [
            category_label(c) for c in sg["category"].value_counts().head(3).index
        ],
    }


def write_person_shards(df: pd.DataFrame) -> dict:
    """Шарды для private: полный ИИН + ФИО."""
    PRIVATE_PERSONS.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, list[str]] = defaultdict(list)

    agg = (
        df.groupby(["district_id", "settlement_canon", "iin"], dropna=False)
        .agg(
            fio=("fio", "first"),
            categories=("category", lambda s: sorted(set(s.astype(str)))),
            registration_scope=("registration_scope", "first"),
            okrug=("okrug", "first"),
            address=("address", "first"),
        )
        .reset_index()
    )

    for did, sub in agg.groupby("district_id"):
        sub = sub.sort_values(["settlement_canon", "fio"])
        pages = max(1, (len(sub) + SHARD_SIZE - 1) // SHARD_SIZE)
        for page in range(pages):
            chunk = sub.iloc[page * SHARD_SIZE : (page + 1) * SHARD_SIZE]
            records = []
            for _, r in chunk.iterrows():
                records.append(
                    {
                        "iin": r["iin"],
                        "iin_masked": mask_iin(r["iin"]),
                        "fio": r["fio"],
                        "settlement": r["settlement_canon"] or "",
                        "okrug": r["okrug"] or "",
                        "categories": r["categories"],
                        "registration_scope": r["registration_scope"],
                    }
                )
            fname = f"{did or 'unknown'}__p{page:04d}.json"
            path = PRIVATE_PERSONS / fname
            path.write_text(
                json.dumps(
                    {
                        "district_id": did or "unknown",
                        "page": page,
                        "page_size": SHARD_SIZE,
                        "records": records,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest[did or "unknown"].append(fname)

    manifest_path = PRIVATE_PERSONS / "manifest.json"
    manifest_path.write_text(json.dumps(dict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(manifest)


def write_public_person_index(manifest: dict) -> None:
    """Публичный индекс: только счётчики страниц, без записей."""
    idx = {
        "shard_size": SHARD_SIZE,
        "districts": {k: {"pages": len(v), "files": v} for k, v in manifest.items()},
    }
    (DATA_CKS / "person_shards_index.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    if not PERSONS_STORE.exists():
        raise SystemExit("Сначала normalize_persons.py")
    df = pd.read_pickle(PERSONS_STORE)
    oblast, districts = aggregate_persons(df)
    DATA_CKS.mkdir(parents=True, exist_ok=True)
    DATA_DISTRICTS.mkdir(parents=True, exist_ok=True)
    (DATA_CKS / "oblast.json").write_text(json.dumps(oblast, ensure_ascii=False, indent=2), encoding="utf-8")
    for did, payload in districts.items():
        (DATA_DISTRICTS / f"{did}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    manifest = write_person_shards(df)
    write_public_person_index(manifest)
    print(f"Oblast + {len(districts)} districts; shards: {sum(len(v) for v in manifest.values())}")


if __name__ == "__main__":
    main()
