"""Оцифровка криминологического паспорта с. Отеген батыр (Илийский район).

Документ построен по общему шаблону из 18 разделов, но отклоняется от него так,
что digitize.py даёт пустые разделы 8-18:

  * заголовок раздела 8 «Административная практика» в документе отсутствует;
  * таблицы разделов 8, 9 и 10 вставлены не таблицами, а обычным текстом —
    ячейки строки слиты в один абзац;
  * время суток и точки концентрации раздела 7 изложены прозой;
  * мероприятия раздела 17 оформлены таблицей, а не перечнем абзацев.

    python digitize_otegen_batyr.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document

from digitize import SECTION_RE, clean, dynamics_row, kv_rows, parse_pair, read_blocks, to_number

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT.parent / "Илийский район" / "Крим_паспорт_Илийский_район СУ и ЗОИ 28.08.2026.DOCX.docx"
OUT = ROOT / "data" / "otegen_batyr.json"

# Разделы 8-10 вставлены текстом, поэтому наименования строк (первая колонка)
# приходится знать заранее — они заданы шаблоном паспорта.
ADMIN_ROW_RE = re.compile(r"^(.*?)\s+(\d[\d\s]*)\s+([\d,]+)\s*%$")
FACTOR_LABELS = (
    "Алкоголизация населения",
    "Семейно-бытовые конфликты",
    "Незанятость населения",
    "Недостаточное видеонаблюдение",
    "Неосвещённые участки",
    "Подростки группы риска",
    "Маятниковая миграция (население, работающее в г. Алматы)",
    "Приток строительных рабочих на объекты застройки",
    "Кражи на промышленных и складских объектах",
    "ДТП на транспортных развязках БАКАД и трассы Алматы–Капчагай",
)
CAUSE_LABELS = ("Социальные", "Организационные", "Инфраструктурные")

TIME_PERIODS = (
    ("Ночное", r"ночное время\D{0,20}(\d+)"),
    ("Вечернее", r"вечернее время совершено (\d+)"),
    ("Дневное", r"в дневное\D{0,5}(\d+)"),
    ("Время не установлено", r"по (\d+) фактам время не установлено"),
)


def split_sections(blocks: list[tuple[str, object]]) -> tuple[list[str], dict[int, dict]]:
    """Шапка и разделы. В отличие от digitize.py допускает пропуск номера:
    заголовка раздела 8 в документе нет, нумерация идёт 7, 9, 10..."""
    header: list[str] = []
    sections: dict[int, dict] = {}
    current: dict | None = None

    for kind, payload in blocks:
        if kind == "tbl":
            if current is not None:
                current["tables"].append(payload)
            continue
        match = SECTION_RE.match(payload)
        if match and len(payload) < 120 and int(match.group(1)) > max(sections, default=0):
            current = {"title": clean(match.group(2)), "paragraphs": [], "tables": []}
            sections[int(match.group(1))] = current
            continue
        (current["paragraphs"] if current else header).append(payload)
    return header, sections


def take_text_table(paragraphs: list[str], head: str, row_re: re.Pattern) -> tuple[list[tuple], list[str]]:
    """Таблица, вставленная в документ текстом: абзац-шапка и абзацы-строки.

    Возвращает разобранные строки и остаток абзацев раздела (без таблицы).
    """
    if head not in paragraphs:
        return [], paragraphs
    start = paragraphs.index(head)
    rows, index = [], start + 1
    while index < len(paragraphs) and (match := row_re.match(paragraphs[index])):
        rows.append(match.groups())
        index += 1
    return rows, paragraphs[:start] + paragraphs[index:]


def take_labelled_rows(paragraphs: list[str], head: str, labels: tuple[str, ...]) -> tuple[list[tuple[str, str]], list[str]]:
    """То же для строк, где первая ячейка — наименование из шаблона."""
    if head not in paragraphs:
        return [], paragraphs
    start = paragraphs.index(head)
    rows, index = [], start + 1
    while index < len(paragraphs):
        text = paragraphs[index]
        label = next((l for l in labels if text.startswith(l)), None)
        if label is None:
            break
        rows.append((label, text[len(label):].strip()))
        index += 1
    return rows, paragraphs[:start] + paragraphs[index:]


def parse_hotspots(paragraphs: list[str]) -> list[dict]:
    """Точки концентрации раздела 7 перечислены в тексте, а не таблицей."""
    streets_text = next((p for p in paragraphs if p.startswith("Наибольшее количество фактов")), "")
    types = next(
        (p.split(":", 1)[1].split(". ")[0].strip(" .") for p in paragraphs if "характерна смешанная структура" in p),
        "",
    )
    hotspots = [
        {
            "number": rank,
            "object": name if name.startswith("ул.") else f"ул. {name}",
            "count": int(count),
            "types": types,
        }
        for rank, (name, count) in enumerate(
            re.findall(r"((?:ул\.\s*)?[А-ЯЁ][а-яёА-ЯЁ]+)\s*[—–-]\s*(\d+)", streets_text), start=1
        )
    ]

    # Два адресных объекта названы отдельными абзацами после перечня улиц.
    for marker, label in (("«Ольга»", "Магазин «Ольга», ул. Жансугурова, 153"), ("мост", "Мост по ул. Батталханова")):
        text = next((p for p in paragraphs if marker in p and "соверш" in p), "")
        if not text:
            continue
        # В скобках даётся расшифровка эпизодов, поэтому для счёта её отбрасываем:
        # иначе итог и его расшифровка сложились бы дважды.
        outside = re.sub(r"\([^)]*\)", "", text)
        total = re.search(r"совершен\w*\s+(\d+)\s+преступлени", outside)
        episodes = re.findall(r"(\d+)\s+(?:кражи|краж|факт)", outside)
        details = re.search(r"\(([^)]*)\)", text) or re.search(r"совершен\w*\s+(.+?)(?:[.,](?:\s|$))", text)
        hotspots.append(
            {
                "number": len(hotspots) + 1,
                "object": label,
                "count": int(total.group(1)) if total else sum(int(n) for n in episodes) or None,
                "types": details.group(1).strip() if details else "",
                "note": text,
            }
        )
    return hotspots


def narrative(section: int, sections: dict[int, dict], paragraphs: list[str]) -> dict | None:
    text = " ".join(paragraphs).strip()
    if not text:
        return None
    return {"section": section, "title": sections.get(section, {}).get("title", ""), "text": text}


def digitize() -> dict:
    header, sections = split_sections(read_blocks(Document(SOURCE)))

    def table(number: int, index: int = 0) -> list[list[str]]:
        tables = sections.get(number, {}).get("tables", [])
        return tables[index] if index < len(tables) else []

    def paragraphs(number: int) -> list[str]:
        return list(sections.get(number, {}).get("paragraphs", []))

    general = {row[0]: row[1] for row in table(1)[1:] if len(row) > 1}

    # Раздел 7 вобрал в себя таблицы разделов 11-16 и текст раздела 8:
    # собственные таблицы есть только у опорных пунктов.
    section7 = paragraphs(7)
    admin_rows, section7 = take_text_table(section7, "Показатель Сведения", ADMIN_ROW_RE)

    section9 = paragraphs(9)
    factor_rows, section9 = take_labelled_rows(section9, "Показатель Сведения", FACTOR_LABELS)

    section10 = paragraphs(10)
    cause_rows, section10 = take_labelled_rows(section10, "Показатель Сведения Примеры", CAUSE_LABELS)
    if cause_rows and section10 and section10[0].startswith("ул."):
        # Колонка «Примеры» инфраструктурных причин разорвана на два абзаца.
        cause_rows[-1] = (cause_rows[-1][0], f"{cause_rows[-1][1]} {section10.pop(0)}")

    crimes = parse_pair(general.get("Зарегистрировано уголовных правонарушений", ""))
    crime_structure = [dynamics_row(row) for row in kv_rows(table(4), ("indicator", "value", "comment"))]
    if crime_structure:
        total = crime_structure[0]
        crimes.setdefault("previous", total.get("previous"))

    return {
        "id": "otegen_batyr",
        "name": "с. Отеген батыр",
        "title": "Криминологический паспорт — с. Отеген батыр",
        "district": clean(header[2]) if len(header) > 2 else "",
        "year": to_number(header[3]) if len(header) > 3 else None,
        "passport_status": "full",
        "source_document": SOURCE.name,
        "summary": {
            "settlement": general.get("Населённый пункт", ""),
            "district": general.get("Район", ""),
            "rural_okrug": general.get("Сельский округ", ""),
            "population": to_number(general.get("Численность населения", "")),
            "crimes": crimes,
            "rate_per_10k": to_number(general.get("Уровень преступности на 10 тыс. населения", "")),
            "description": general.get("Краткая характеристика", ""),
        },
        "socio": kv_rows(table(2), ("indicator", "value", "meaning")),
        "characteristic": " ".join(paragraphs(3)),
        "crime_structure": crime_structure,
        "offender_profile": kv_rows(table(5), ("indicator", "value")),
        "victim_profile": kv_rows(table(6), ("indicator", "value")),
        "time_of_day": [
            {"period": period, "count": int(match.group(1))}
            for period, pattern in TIME_PERIODS
            if (match := re.search(pattern, " ".join(paragraphs(7)), re.IGNORECASE))
        ],
        "hotspots": parse_hotspots(paragraphs(7)),
        "support_points": kv_rows(table(7), ("location", "staff", "registered")),
        "admin_practice": [
            {"indicator": indicator, "count": to_number(count), "raw": f"{clean(count)} ({share}%)"}
            for indicator, count, share in admin_rows
        ],
        "factors": [{"factor": factor, "details": details} for factor, details in factor_rows],
        "causes": [
            {"type": kind, "details": parts[0].strip(), "examples": parts[1].strip() if len(parts) > 1 else ""}
            for kind, text in cause_rows
            for parts in [text.split(". ", 1)]
        ],
        "registry": [
            {"category": row["category"], "count": to_number(row["value"]), "raw": row["value"]}
            for row in kv_rows(table(11), ("category", "value"))
        ],
        "criminogenic_objects": kv_rows(table(12), ("object", "details")),
        "domestic_crime": [dynamics_row(row) for row in kv_rows(table(13), ("indicator", "value", "comment"))],
        "minors": [dynamics_row(row) for row in kv_rows(table(14), ("indicator", "value", "comment"))],
        "cattle_theft": kv_rows(table(15), ("indicator", "value", "comment")),
        "special": {
            "title": sections.get(16, {}).get("title", "Маятниковая миграция и промышленная зона"),
            "rows": kv_rows(table(16), ("indicator", "value")),
        },
        "measures": [
            {
                "number": number,
                "title": row["title"].split(":", 1)[0].strip(),
                "object": row["title"].split(":", 1)[1].strip() if ":" in row["title"] else "",
                "executors": row["executors"],
                "term": row["term"],
                "criterion": row["criterion"],
                "rationale": "",
            }
            for number, row in enumerate(kv_rows(table(17), ("title", "executors", "term", "criterion")), start=1)
        ],
        "expected_results": paragraphs(18),
        "narrative_blocks": [
            block
            for block in (
                narrative(5, sections, paragraphs(5)),
                narrative(6, sections, paragraphs(6)),
                narrative(7, sections, section7),
                narrative(10, sections, section10),
                narrative(12, sections, paragraphs(12)),
            )
            if block
        ],
        "data_quality": {
            "completeness": "full",
            "as_of": "2026-08-28",
            "verified_by": "криминологический паспорт ОП Илийского района от 28.08.2026",
        },
    }


def main() -> None:
    passport = digitize()
    OUT.write_text(json.dumps(passport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT}")
    print(
        f"  социально-экономических {len(passport['socio'])}, "
        f"структура преступности {len(passport['crime_structure'])}, "
        f"время суток {len(passport['time_of_day'])}, "
        f"точек концентрации {len(passport['hotspots'])}, "
        f"адм. практика {len(passport['admin_practice'])}, "
        f"факторов {len(passport['factors'])}, "
        f"причин {len(passport['causes'])}, "
        f"профучёт {len(passport['registry'])}, "
        f"объектов {len(passport['criminogenic_objects'])}, "
        f"мероприятий {len(passport['measures'])}, "
        f"ожидаемых результатов {len(passport['expected_results'])}"
    )


if __name__ == "__main__":
    main()
