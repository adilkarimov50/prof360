"""Оцифровка расширенного криминологического паспорта с. Чунджа (50+ разделов)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path("/Users/alima_2023/prof/Уйгур, Чунджа/Криминологический_паспорт_Чунджа_2026.docx")
OUT = ROOT / "data" / "chundzha.json"

SECTION_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*\.\s*(.+)$")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def to_number(text: str):
    m = re.search(r"(\d[\d\s]*(?:[.,]\d+)?)", text.replace("\xa0", " "))
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace(",", ".")
    n = float(raw)
    return int(n) if n.is_integer() else n


def parse_sections(doc: Document) -> list[dict]:
    sections: list[dict] = []
    cur: dict | None = None
    for child in doc.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            t = clean(Paragraph(child, doc).text)
            if not t:
                continue
            m = SECTION_RE.match(t)
            if m and len(t) < 120 and not t.startswith("ст."):
                cur = {"num": m.group(1), "title": clean(m.group(2)), "paragraphs": [], "tables": []}
                sections.append(cur)
                continue
            if cur:
                cur["paragraphs"].append(t)
        elif tag == "tbl" and cur is not None:
            tbl = Table(child, doc)
            rows = [[clean(c.text) for c in r.cells] for r in tbl.rows]
            cur["tables"].append(rows)
    return sections


def table_dict(rows: list[list[str]], keys: tuple[str, ...]) -> list[dict]:
    if len(rows) < 2:
        return []
    return [dict(zip(keys, [row[i] if i < len(row) else "" for i in range(len(keys))])) for row in rows[1:]]


def find_section(sections: list[dict], num: str) -> dict | None:
    for s in sections:
        if s["num"] == num:
            return s
    return None


def main() -> None:
    doc = Document(SOURCE)
    sections = parse_sections(doc)

    general = find_section(sections, "1")
    g = {r[0]: r[1] for r in general["tables"][0][1:] if len(r) > 1} if general and general["tables"] else {}

    crimes_raw = g.get("Зарегистрировано уголовных правонарушений", "36")
    crimes_current = to_number(crimes_raw)
    appg = re.search(r"(\d+)", crimes_raw.split("АППГ")[-1] if "АППГ" in crimes_raw else "")
    delta = re.search(r"([−\-+]?\d+[,.]?\d*)\s*%", crimes_raw)
    delta_val = None
    if delta:
        delta_val = float(delta.group(1).replace(",", ".").replace("−", "-"))
        if "снижен" in crimes_raw.lower() and delta_val > 0:
            delta_val = -delta_val

    passport = {
        "id": "chundzha",
        "name": g.get("Населенный пункт", "с. Чунджа (Шонжы)"),
        "title": "с. Чунджа (Шонжы) Уйгурского района",
        "district": "Уйгурский район Алматинской области",
        "year": 2026,
        "source_document": SOURCE.name,
        "summary": {
            "settlement": g.get("Населенный пункт", ""),
            "district": g.get("Район", ""),
            "status": g.get("Статус", ""),
            "population": to_number(g.get("Численность населения", "")),
            "crimes": {
                "raw": crimes_raw,
                "current": crimes_current,
                "previous": to_number(appg.group(1)) if appg else 58,
                "delta_pct": delta_val if delta_val is not None else -38.0,
            },
            "rate_per_10k": round((crimes_current or 36) / (to_number(g.get("Численность населения", "")) or 22000) * 10000, 1),
            "description": (
                "Административный центр Уйгурского района. Населённый пункт с выраженной "
                "социальной, возрастной и территориальной концентрацией преступности; "
                "52 % установленных эпизодов — в вечернее и ночное время."
            ),
        },
        "characteristic": " ".join(find_section(sections, "3")["paragraphs"]) if find_section(sections, "3") else "",
        "crime_structure": table_dict(
            find_section(sections, "4.2")["tables"][0] if find_section(sections, "4.2") else [],
            ("indicator", "value", "share", "comment"),
        ) if find_section(sections, "4.2") else [],
        "crime_severity": table_dict(
            find_section(sections, "4.1")["tables"][0] if find_section(sections, "4.1") else [],
            ("category", "previous", "current", "delta"),
        ) if find_section(sections, "4.1") else [],
        "offender_profile": table_dict(
            find_section(sections, "6")["tables"][0] if find_section(sections, "6") else [],
            ("indicator", "value", "share"),
        ) if find_section(sections, "6") else [],
        "victim_profile": table_dict(
            find_section(sections, "7")["tables"][0] if find_section(sections, "7") else [],
            ("indicator", "value", "share"),
        ) if find_section(sections, "7") else [],
        "time_of_day": [
            {"period": r["period"], "count": to_number(r["count"]), "share": r.get("share", "")}
            for r in table_dict(
                find_section(sections, "8.1")["tables"][0] if find_section(sections, "8.1") else [],
                ("period", "count", "share"),
            )
        ],
        "hotspots": [
            {
                "object": r["object"],
                "count": to_number(r["count"]),
                "types": r["crimes"],
                "measures": r["required"],
            }
            for r in table_dict(
                find_section(sections, "8.2")["tables"][0] if find_section(sections, "8.2") else [],
                ("object", "count", "crimes", "required"),
            )
        ],
        "factors": table_dict(
            find_section(sections, "10")["tables"][0] if find_section(sections, "10") else [],
            ("factor", "risk", "details"),
        ) if find_section(sections, "10") else [],
        "causes": table_dict(
            find_section(sections, "11")["tables"][0] if find_section(sections, "11") else [],
            ("type", "details", "examples"),
        ) if find_section(sections, "11") else [],
        "criminogenic_objects": table_dict(
            find_section(sections, "13")["tables"][0] if find_section(sections, "13") else [],
            ("object", "details"),
        ) if find_section(sections, "13") else [],
        "admin_practice": {
            "total": 2345,
            "period": "01.01.2026 – 14.08.2026",
            "top_articles": table_dict(
                find_section(sections, "17")["tables"][0] if find_section(sections, "17") else [],
                ("article", "title", "count", "share"),
            ),
        },
        "measures": [],
        "expected_results": find_section(sections, "22")["paragraphs"] if find_section(sections, "22") else [],
        "sections_raw": [
            {"num": s["num"], "title": s["title"], "paragraphs": s["paragraphs"], "table_count": len(s["tables"])}
            for s in sections
        ],
    }

    # Мероприятия из раздела 21.
    m21 = find_section(sections, "21")
    if m21:
        skip_intro = {"мероприятия сформированы"}
        for p in m21["paragraphs"]:
            text = clean(p)
            if any(text.lower().startswith(s) for s in skip_intro):
                continue
            passport["measures"].append({
                "number": len(passport["measures"]) + 1,
                "title": text,
                "object": "с. Чунджа (Шонжы)",
                "executors": "ОВД, акимат, ЦЗН, прокуратура",
                "term": "2026",
                "criterion": "Снижение повторных фактов на объекте",
                "rationale": "Раздел 21 криминологического паспорта",
            })

    # Сравнение с АППГ (§4.1) + ключевые виды для таблицы на главной.
    def _parse_num(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return int(v) if float(v).is_integer() else float(v)
        m = re.search(r"-?\d+", str(v).replace(" ", ""))
        return int(m.group()) if m else None

    def _parse_delta_pct(delta_str, prev, cur):
        if delta_str:
            m = re.search(r"([−\-+]?[\d,]+(?:\.[\d]+)?)", str(delta_str))
            if m:
                return float(m.group(1).replace(",", ".").replace("−", "-"))
        if prev not in (None, 0) and cur is not None:
            return round((cur - prev) / prev * 100, 1)
        return None

    compare_rows = []
    for row in passport.get("crime_severity", []):
        prev = _parse_num(row.get("previous"))
        cur = _parse_num(row.get("current"))
        delta = _parse_delta_pct(row.get("delta"), prev, cur)
        direction = "up" if delta and delta > 0 else "down" if delta and delta < 0 else None
        entry = {
            "indicator": row["category"],
            "raw": f"{cur} / {prev}" if prev is not None and cur is not None else str(cur or ""),
            "current": cur,
            "previous": prev,
            "delta_pct": delta,
            "comment": row.get("delta", ""),
        }
        if direction:
            entry["direction"] = direction
        compare_rows.append(entry)

    by_type = {r["indicator"]: r for r in passport.get("crime_structure", []) if r.get("indicator") != "ВСЕГО"}
    for ind, val, note in (
        ("Кражи", by_type.get("Кражи", {}).get("value"), ""),
        ("Мошенничества", by_type.get("Мошенничества", {}).get("value"), ""),
        ("Против половой неприкосновенности", by_type.get("Половые преступления", {}).get("value"), ""),
        ("Семейно-бытовые преступления", "4", "в составе побоев (§14)"),
        ("В состоянии алкогольного опьянения", "5", "5 из 27 установленных эпизодов"),
    ):
        n = _parse_num(val)
        compare_rows.append({"indicator": ind, "raw": str(val), "current": n, "comment": note})

    skip = {"Кражи", "Мошенничества", "Половые преступления", "ВСЕГО"}
    rest = [r for r in passport.get("crime_structure", []) if r.get("indicator") not in skip]
    passport["crime_structure"] = compare_rows + rest

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(passport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT} — hotspots: {len(passport['hotspots'])}, measures: {len(passport['measures'])}")


if __name__ == "__main__":
    main()
