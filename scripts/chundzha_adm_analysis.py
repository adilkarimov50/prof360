"""Parse form 1-AD admin cases for s. Chundzha / Shonjy and export JSON stats."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "Уйгур, Чунджа" / (
    "Группа отчетов об административных правонарушениях (ф.1-АД) "
    "данные к отчету 1-АД - 15 августа 2026 г. в 13_35_06.xlsx"
)
OUT = ROOT / "Уйгур, Чунджа" / "chundzha_adm_stats.json"

COL_PLACE = "2.1 Место совершения правонарушения"
COL_ARTICLE = "9. Квалификация"
COL_DECISION = "7. Решение по материалу/протоколу"
COL_MEASURE = "9.1. Основная мера взыскания"
COL_DATE = "3. Дата заведения"
COL_SEX = "17. Пол"
COL_AGE = "18. Возраст"
COL_UNIT = "1. Подразделения ОВД выявившее правонарушение"
COL_FINE = "9.5. Размер наложенного штрафа"
COL_FINE_SHORT = "9.6. Размер наложенного штрафа в сокращенном порядке"
COL_RESIDENCE = "22. Место жительства Насел.пункт"

CHUNDZHA_RE = re.compile(r"чунджа|чунжа|шонжы|шоңжы", re.I)
ROUTE_RE = re.compile(r"трасса|а/д|автодорог", re.I)
ARTICLE_RE = re.compile(r"ст\.?\s*(\d+(?:-\d+)?)(?:\s*ч\.?\s*(\d+))?", re.I)


def _s(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def is_chundzha(place: str) -> bool:
    if not CHUNDZHA_RE.search(place):
        return False
    if ROUTE_RE.search(place):
        return False
    return True


def parse_date(s: str) -> datetime | None:
    s = _s(s)
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d.%m.%Y")
    except ValueError:
        return None


def parse_article(s: str) -> str:
    m = ARTICLE_RE.search(_s(s))
    if not m:
        return _s(s)
    base, part = m.group(1), m.group(2)
    return f"ст.{base} ч.{part}" if part else f"ст.{base}"


def load_rows() -> tuple[list[str], list[dict]]:
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = [_s(h) for h in next(it)]
    idx = {h: i for i, h in enumerate(header)}

    def get(row, col):
        i = idx.get(col)
        if i is None:
            return ""
        return _s(row[i]) if i < len(row) else ""

    rows = []
    for raw in it:
        row = list(raw)
        place = get(row, COL_PLACE)
        if not is_chundzha(place):
            continue
        fine = row[idx[COL_FINE]] if COL_FINE in idx else None
        fine_short = row[idx[COL_FINE_SHORT]] if COL_FINE_SHORT in idx else None
        rows.append({
            "place": place,
            "article_raw": get(row, COL_ARTICLE),
            "article": parse_article(get(row, COL_ARTICLE)),
            "decision": get(row, COL_DECISION),
            "measure": get(row, COL_MEASURE),
            "date": get(row, COL_DATE),
            "month": (parse_date(get(row, COL_DATE)).strftime("%Y-%m")
                      if parse_date(get(row, COL_DATE)) else ""),
            "sex": get(row, COL_SEX),
            "age": get(row, COL_AGE),
            "unit": get(row, COL_UNIT),
            "residence": get(row, COL_RESIDENCE),
            "fine": fine if isinstance(fine, (int, float)) and fine > 0 else 0,
            "fine_short": fine_short if isinstance(fine_short, (int, float)) and fine_short > 0 else 0,
        })
    wb.close()
    return header, rows


def top(counter: Counter, n=15) -> list[dict]:
    return [{"name": k, "count": v} for k, v in counter.most_common(n)]


def build_stats(rows: list[dict]) -> dict:
    articles = Counter(r["article"] for r in rows if r["article"])
    articles_base = Counter(parse_article(r["article_raw"]).split(" ч.")[0] for r in rows)
    months = Counter(r["month"] for r in rows if r["month"])
    decisions = Counter(r["decision"] for r in rows if r["decision"])
    measures = Counter(r["measure"] for r in rows if r["measure"])
    sex = Counter(r["sex"] for r in rows if r["sex"])
    age = Counter(r["age"] for r in rows if r["age"])
    units = Counter(r["unit"] for r in rows if r["unit"])

    fines = [r["fine"] for r in rows if r["fine"]]
    fines_short = [r["fine_short"] for r in rows if r["fine_short"]]

    district_total = 4040
    chundzha_count = len(rows)
    share = round(chundzha_count / district_total * 100, 1)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": str(XLSX.name),
        "period": "01.01.2026 – 14.08.2026",
        "district_total": district_total,
        "chundzha_count": chundzha_count,
        "chundzha_share_pct": share,
        "articles_top": top(articles, 20),
        "articles_base_top": top(articles_base, 15),
        "by_month": top(months, 12),
        "decisions": top(decisions, 10),
        "measures": top(measures, 10),
        "sex": top(sex, 5),
        "age": top(age, 10),
        "units": top(units, 10),
        "fines": {
            "count": len(fines) + len(fines_short),
            "sum_regular": int(sum(fines)),
            "sum_short": int(sum(fines_short)),
            "sum_total": int(sum(fines) + sum(fines_short)),
        },
    }


def main() -> None:
    _, rows = load_rows()
    stats = build_stats(rows)
    OUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Chundzha rows: {stats['chundzha_count']} ({stats['chundzha_share_pct']}%)")
    print(f"Written: {OUT}")


if __name__ == "__main__":
    main()
