"""Оцифровка расширенного кримпаспорта _итог (7 месяцев 2026).

Структура отличается от базового шаблона: таблицы идут подряд без жёсткой
привязки к номерам разделов. Извлекаем данные по заголовкам таблиц.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from docx import Document

from digitize import (
    clean,
    dynamics_row,
    is_empty,
    kv_rows,
    parse_measures,
    parse_pair,
    read_blocks,
    split_sections,
    to_number,
)


def find_table_by_header(tables: list[list[list[str]]], *needles: str) -> list[list[str]]:
    for tbl in tables:
        if not tbl:
            continue
        head = " ".join(tbl[0]).lower()
        if all(n.lower() in head for n in needles):
            return tbl
        for row in tbl[:3]:
            row_text = " ".join(row).lower()
            if all(n.lower() in row_text for n in needles):
                return tbl
    for tbl in tables:
        if not tbl:
            continue
        body = " ".join(" ".join(r) for r in tbl[:8]).lower()
        if all(n.lower() in body for n in needles):
            return tbl
    return []


def kv_from_indicator(tables: list[list[list[str]]], indicator_col: str = "Показатель") -> list[dict]:
    for tbl in tables:
        if not tbl or tbl[0][0] != indicator_col:
            continue
        keys = ("indicator", "value", "comment") if len(tbl[0]) >= 3 else ("indicator", "value")
        return kv_rows(tbl, keys)
    return []


def digitize_itog(path: Path, locality_id: str) -> dict:
    doc = Document(path)
    all_tables = [
        [[clean(c.text) for c in r.cells] for r in t.rows]
        for t in doc.tables
    ]
    header, sections = split_sections(read_blocks(doc))

    general_tbl = find_table_by_header(all_tables, "Показатель", "Сведения") or all_tables[0]
    general_rows = {row[0]: row[1] for row in general_tbl[1:] if len(row) > 1 and row[0]}

    pop_raw = general_rows.get("Численность населения", "")
    crimes_raw = general_rows.get("Зарегистрировано уголовных правонарушений", "")
    rate_raw = general_rows.get("Уровень преступности на 10 тыс.", "") or general_rows.get(
        "Уровень преступности на 10 тыс. населения", ""
    )
    erdr_raw = general_rows.get("По выгрузке ЕРДР за 2026 год", "")

    crimes = parse_pair(crimes_raw)
    passport = {
        "id": locality_id,
        "name": general_rows.get("Населённый пункт", "").split(",")[0].strip()
        or (clean(header[1]) if len(header) > 1 else locality_id),
        "title": clean(header[1]) if len(header) > 1 else "",
        "district": clean(header[2]) if len(header) > 2 else "",
        "year": 2026,
        "note": clean(header[4]) if len(header) > 4 else "",
        "source_document": path.name,
        "edition": "итог 7 месяцев 2026",
        "summary": {
            "settlement": general_rows.get("Населённый пункт", ""),
            "district": general_rows.get("Район", "Карасайский район"),
            "population": to_number(pop_raw),
            "population_raw": pop_raw,
            "crimes": crimes,
            "rate_per_10k": to_number(rate_raw.split("/")[0] if "/" in rate_raw else rate_raw),
            "rate_raw": rate_raw,
            "erdr_records": to_number(erdr_raw),
            "erdr_raw": erdr_raw,
            "description": general_rows.get("Краткая характеристика", ""),
        },
        "socio_extended": [],
        "crime_structure": [],
        "offender_profile": [],
        "victim_profile": [],
        "time_of_day": [],
        "hotspots": [],
        "hotspots_detailed": [],
        "admin_practice": [],
        "factors": [],
        "causes": [],
        "registry": [],
        "criminogenic_objects": [],
        "domestic_crime": [],
        "minors": [],
        "special": {"title": "", "rows": []},
        "kpi_execution": [],
        "measures": parse_measures(sections.get(17, {}).get("paragraphs", [])),
        "expected_results": sections.get(18, {}).get("paragraphs", []),
        "narrative_blocks": [],
    }

    for tbl in all_tables:
        if not tbl:
            continue
        h0 = tbl[0][0] if tbl[0] else ""
        head = " ".join(tbl[0]).lower()

        if h0 == "Показатель" and "текущий" in head and len(passport["crime_structure"]) == 0:
            passport["crime_structure"] = [
                dynamics_row(row)
                for row in kv_rows(tbl, ("indicator", "value", "comment"))
            ]
        elif h0 == "Показатель" and "административ" in " ".join(
            r[0].lower() for r in tbl[1:4] if r
        ):
            passport["admin_practice"] = [
                {"indicator": row["indicator"], "count": to_number(row["value"]), "raw": row["value"]}
                for row in kv_rows(tbl, ("indicator", "value", "comment"))
                if row["indicator"] and not is_empty(row["value"])
            ]
        elif h0 == "Категория" and "Состоит" in head:
            passport["registry"] = [
                {"category": row["category"], "count": to_number(row["value"]), "raw": row["value"]}
                for row in kv_rows(tbl, ("category", "value", "comment"))
            ]
        elif h0 == "№" and "объект" in head.lower():
            rows = kv_rows(tbl, ("number", "object", "count", "types"))
            if rows and to_number(rows[0].get("count")):
                if passport["hotspots"]:
                    passport["hotspots_detailed"] = [
                        {
                            "number": to_number(r["number"]),
                            "object": r["object"],
                            "count": to_number(r["count"]),
                            "types": r.get("types", ""),
                        }
                        for r in rows
                    ]
                else:
                    passport["hotspots"] = [
                        {
                            "number": to_number(r["number"]),
                            "object": r["object"],
                            "count": to_number(r["count"]),
                            "types": r.get("types", ""),
                        }
                        for r in rows
                    ]
        elif h0 == "Объект" and "Фактов" in head:
            passport["hotspots_detailed"] = [
                {
                    "object": row["object"],
                    "count": to_number(row["count"]),
                    "types": row.get("types", ""),
                    "note": row.get("note", ""),
                }
                for row in kv_rows(tbl, ("object", "count", "types", "note"))
            ]
        elif h0 == "Показатель" and any("безработ" in " ".join(r).lower() for r in tbl[1:4]):
            passport["socio_extended"].append({"table": "employment", "rows": kv_rows(tbl, ("indicator", "value", "comment"))})
        elif h0 == "Тип объекта":
            passport["criminogenic_objects"] = kv_rows(tbl, ("object", "details"))
        elif h0 == "Показатель" and "выездов" in " ".join(r[0].lower() for r in tbl if r):
            passport["kpi_execution"] = kv_rows(tbl, ("indicator", "value", "comment"))

    for sec_num in (3, 5, 6, 7, 9, 10, 13, 14, 16):
        paras = sections.get(sec_num, {}).get("paragraphs", [])
        if paras:
            passport["narrative_blocks"].append(
                {"section": sec_num, "title": sections.get(sec_num, {}).get("title", ""), "text": " ".join(paras[:5])}
            )

    return passport


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
    )
    args = parser.parse_args()
    passport = digitize_itog(args.source, args.id)
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / f"{args.id}.json"
    target.write_text(json.dumps(passport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{target}")


if __name__ == "__main__":
    main()
