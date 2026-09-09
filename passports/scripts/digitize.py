"""Оцифровка криминологического паспорта: .docx -> структурированный JSON.

Паспорта построены по единому шаблону из 18 разделов и 16 таблиц, поэтому
добавление нового населённого пункта не требует правки кода: достаточно
подать .docx того же шаблона.

    python digitize.py "Крим паспорт Каскелен.docx" --id kaskelen
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

SECTION_RE = re.compile(r"^(\d{1,2})\s*\.\s*(.+)$")
MEASURE_RE = re.compile(r"^(\d{1,2})\s*\.\s*(.*)$")

# Служебные ремарки шаблона, не несущие данных.
BOILERPLATE = (
    "Строки ниже добавлены с учётом специфики",
    "Каждая мера должна иметь объект",
    "Раздел заполняется при наличии зарегистрированных фактов",
)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def is_empty(value: str) -> bool:
    """Незаполненная строка шаблона: прочерк или подчёркивания."""
    stripped = value.strip(" _-–—\u2014")
    return not stripped


def to_number(text: str) -> float | int | None:
    """Первое число в строке: '87 023 человек' -> 87023, '63,6 преступления' -> 63.6."""
    match = re.search(r"(\d[\d\s\u00a0]*(?:[.,]\d+)?)", text.replace("\xa0", " "))
    if not match:
        return None
    raw = match.group(1).replace(" ", "").replace(",", ".")
    number = float(raw)
    return int(number) if number.is_integer() else number


def parse_pair(text: str) -> dict:
    """Разбор 'текущий/АППГ' в разных написаниях.

    Поддерживает '554/435', '554 (АППГ — 435, рост на 27,3%)' и обычное число.
    """
    text = clean(text)
    result: dict = {"raw": text}

    slash = re.match(r"^(\d[\d\s]*)\s*/\s*(\d[\d\s]*)$", text)
    if slash:
        result["current"] = to_number(slash.group(1))
        result["previous"] = to_number(slash.group(2))
    else:
        appg = re.search(r"АППГ\s*[—\-–]?\s*(\d[\d\s]*)", text)
        if appg:
            result["current"] = to_number(text)
            result["previous"] = to_number(appg.group(1))
        elif re.match(r"^[\d\s.,]+(человек|преступлени\w*)?$", text):
            result["current"] = to_number(text)

    delta = re.search(r"(рост|снижение)\D{0,10}?(\d+(?:[.,]\d+)?)\s*%", text, re.IGNORECASE)
    if delta:
        value = float(delta.group(2).replace(",", "."))
        result["direction"] = "up" if delta.group(1).lower() == "рост" else "down"
        result["delta_pct"] = value if result["direction"] == "up" else -value
    return result


def dynamics_row(row: dict) -> dict:
    """Строка вида «показатель | текущий/АППГ | причины роста»."""
    parsed = parse_pair(row["value"])
    if "delta_pct" not in parsed:
        # Процент динамики в паспортах вынесен в колонку комментария.
        from_comment = parse_pair(row["comment"])
        for key in ("direction", "delta_pct"):
            if key in from_comment:
                parsed[key] = from_comment[key]
    return {"indicator": row["indicator"], **parsed, "comment": row["comment"]}


def read_blocks(doc: Document) -> list[tuple[str, object]]:
    """Тело документа в исходном порядке: ('p', текст) и ('tbl', матрица)."""
    blocks: list[tuple[str, object]] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            text = clean(Paragraph(child, doc).text)
            if text:
                blocks.append(("p", text))
        elif tag == "tbl":
            table = Table(child, doc)
            rows = [[clean(cell.text) for cell in row.cells] for row in table.rows]
            blocks.append(("tbl", rows))
    return blocks


def split_sections(blocks: list[tuple[str, object]]) -> tuple[list[str], dict[int, dict]]:
    """Шапка документа + разделы, пронумерованные заголовками '<N>. <название>'."""
    header: list[str] = []
    sections: dict[int, dict] = {}
    current: dict | None = None

    for kind, payload in blocks:
        if kind == "p":
            match = SECTION_RE.match(payload)
            # Заголовок раздела — короткая строка без завершающей точки,
            # иначе это пункт перечня внутри раздела 17.
            if match and len(payload) < 90 and not payload.rstrip().endswith("."):
                number = int(match.group(1))
                if number not in sections and (current is None or number == len(sections) + 1):
                    current = {"title": clean(match.group(2)), "paragraphs": [], "tables": []}
                    sections[number] = current
                    continue
            if any(payload.startswith(prefix) for prefix in BOILERPLATE):
                continue
            (current["paragraphs"] if current else header).append(payload)
        else:
            if current is not None:
                current["tables"].append(payload)
    return header, sections


def kv_rows(rows: list[list[str]], keys: tuple[str, ...]) -> list[dict]:
    """Таблица с шапкой -> список записей; пустые строки шаблона отбрасываются."""
    result = []
    for row in rows[1:]:
        values = [row[i] if i < len(row) else "" for i in range(len(keys))]
        if all(is_empty(v) for v in values[1:]):
            continue
        record = dict(zip(keys, values))
        for key in list(record):
            if key != keys[0] and is_empty(record[key]):
                record[key] = ""
        result.append(record)
    return result


def parse_measures(paragraphs: list[str]) -> list[dict]:
    """Раздел 17: мероприятия с объектом, исполнителем, сроком и критерием."""
    labels = (
        ("object", r"^Объект(?:ом)?\s*(?:профилактики\s*)?(?:определить\s*)?[:\-—]?\s*"),
        ("executors", r"^Исполнител(?:и|ями)\s*(?:определить\s*)?[:\-—]?\s*"),
        ("term", r"^(?:Срок(?:\s+исполнения)?|Мероприятия проводить)\s*[:\-—]?\s*"),
        ("criterion", r"^Критери(?:й|ем)\s*оценки\s*(?:определить\s*)?[:\-—]?\s*"),
    )
    # Составные абзацы вида «Исполнители: … Срок: …» разбиваем по меткам.
    splitter = re.compile(r"(?<=[.;])\s+(?=(?:Срок|Критери(?:й|ем)|Исполнител|Объект)\b)")

    measures: list[dict] = []
    current: dict | None = None
    for raw in paragraphs:
        for part in splitter.split(raw):
            part = clean(part)
            if not part:
                continue
            head = MEASURE_RE.match(part)
            if head and head.group(2).strip() and not any(
                re.match(pattern, part) for _, pattern in labels
            ):
                current = {
                    "number": int(head.group(1)),
                    "title": clean(head.group(2)),
                    "object": "",
                    "executors": "",
                    "term": "",
                    "criterion": "",
                    "rationale": "",
                }
                measures.append(current)
                continue
            if current is None:
                continue
            for field, pattern in labels:
                if re.match(pattern, part):
                    current[field] = re.sub(pattern, "", part).strip()
                    break
            else:
                current["rationale"] = clean(f"{current['rationale']} {part}")
    return measures


def digitize(path: Path, locality_id: str) -> dict:
    doc = Document(path)
    header, sections = split_sections(read_blocks(doc))

    def table(number: int, index: int = 0) -> list[list[str]]:
        tables = sections.get(number, {}).get("tables", [])
        return tables[index] if index < len(tables) else []

    def paragraphs(number: int) -> list[str]:
        return sections.get(number, {}).get("paragraphs", [])

    general_rows = {row[0]: row[1] for row in table(1)[1:] if len(row) > 1}
    crimes = parse_pair(general_rows.get("Зарегистрировано уголовных правонарушений", ""))

    passport = {
        "id": locality_id,
        # Заголовок паспорта стоит в родительном падеже, для интерфейса берём
        # именительный из таблицы общей характеристики.
        "name": general_rows.get("Населённый пункт") or (clean(header[1]) if len(header) > 1 else locality_id),
        "title": clean(header[1]) if len(header) > 1 else "",
        "district": clean(header[2]) if len(header) > 2 else "",
        "year": to_number(header[3]) if len(header) > 3 else None,
        "note": clean(header[4]) if len(header) > 4 else "",
        "source_document": path.name,
        "summary": {
            "settlement": general_rows.get("Населённый пункт", ""),
            "district": general_rows.get("Район", ""),
            "population": to_number(general_rows.get("Численность населения", "")),
            "crimes": crimes,
            "rate_per_10k": to_number(
                general_rows.get("Уровень преступности на 10 тыс. населения", "")
            ),
            "description": general_rows.get("Краткая характеристика", ""),
        },
        "socio": kv_rows(table(2), ("indicator", "value", "meaning")),
        "characteristic": " ".join(paragraphs(3)),
        "crime_structure": [
            dynamics_row(row)
            for row in kv_rows(table(4), ("indicator", "value", "comment"))
        ],
        "offender_profile": kv_rows(table(5), ("indicator", "value")),
        "victim_profile": kv_rows(table(6), ("indicator", "value")),
        "time_of_day": [
            {"period": row["period"], "count": to_number(row["count"])}
            for row in kv_rows(table(7, 0), ("period", "count"))
        ],
        "hotspots": [
            {
                "number": to_number(row["number"]),
                "object": row["object"],
                "count": to_number(row["count"]),
                "types": row["types"],
            }
            for row in kv_rows(table(7, 1), ("number", "object", "count", "types"))
        ],
        "admin_practice": [
            {"indicator": row["indicator"], "count": to_number(row["value"]), "raw": row["value"]}
            for row in kv_rows(table(8), ("indicator", "value"))
        ],
        "factors": kv_rows(table(9), ("factor", "details")),
        "causes": kv_rows(table(10), ("type", "details", "examples")),
        "registry": [
            {"category": row["category"], "count": to_number(row["value"]), "raw": row["value"]}
            for row in kv_rows(table(11), ("category", "value"))
        ],
        "criminogenic_objects": kv_rows(table(12), ("object", "details")),
        "domestic_crime": [
            dynamics_row(row)
            for row in kv_rows(table(13), ("indicator", "value", "comment"))
        ],
        "minors": [
            dynamics_row(row)
            for row in kv_rows(table(14), ("indicator", "value", "comment"))
        ],
        "cattle_theft": kv_rows(table(15), ("indicator", "value", "comment")),
        "special": {
            "title": sections.get(16, {}).get("title", ""),
            "rows": kv_rows(table(16), ("indicator", "value")),
        },
        "measures": parse_measures(paragraphs(17)),
        "expected_results": paragraphs(18),
    }
    return passport


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="путь к .docx паспорта")
    parser.add_argument("--id", required=True, help="идентификатор населённого пункта (латиницей)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
        help="каталог для JSON",
    )
    args = parser.parse_args()

    passport = digitize(args.source, args.id)
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / f"{args.id}.json"
    target.write_text(
        json.dumps(passport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"{target}")
    print(f"  разделов с данными: социально-экономических {len(passport['socio'])}, "
          f"структура преступности {len(passport['crime_structure'])}, "
          f"точек концентрации {len(passport['hotspots'])}, "
          f"факторов {len(passport['factors'])}, "
          f"мероприятий {len(passport['measures'])}")


if __name__ == "__main__":
    main()
