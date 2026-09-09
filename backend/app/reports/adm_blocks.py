"""Разделение административной практики на блоки: «против личности и общества»
(ст. 73, 434, 440 и смежные составы) против «дорожной безопасности» (глава 30 КоАП).

Источник — выгрузка формы 1-АД по Уйгурскому району (с. Чунджа/Шонжы).
Квалификация составов сверена с фабулами дел («13.1 Фабула (новая)»),
поскольку выгрузка содержит только номера статей без наименований.

Используется как в CLI-скрипте, так и в API отчётов «Профилактика 360».
"""
from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import openpyxl

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

CHUNDZHA_RE = re.compile(r"чунджа|чунжа|шонжы|шоңжы", re.I)
ROUTE_RE = re.compile(r"трасса|а/д|автодорог", re.I)
ARTICLE_RE = re.compile(r"ст\.?\s*(\d+(?:-\d+)?)(?:\s*ч\.?\s*(\d+(?:-\d+)?))?", re.I)

# ---------------------------------------------------------------------------
# Блок «против личности и общества» — посягательства на личность, семью,
# несовершеннолетних и общественный порядок. Разбит на профильные группы.
# ---------------------------------------------------------------------------
PERSON_GROUPS: dict[str, tuple[str, ...]] = {
    "Семейно-бытовая сфера": ("73", "73-1", "73-2", "73-3", "461"),
    "Защита несовершеннолетних": ("127", "127-1", "127-2", "132", "423-1", "435", "442"),
    "Алкоголь в общественных местах": ("440", "440-1"),
    "Общественный порядок и нравственность": ("434", "434-1", "434-3", "437"),
    "Приставание и навязывание услуг": ("449",),
    "Профилактический (административный) надзор": ("480",),
}
PERSON_ARTICLES = {a for arts in PERSON_GROUPS.values() for a in arts}

# Блок «дорожная безопасность» — глава 30 КоАП и смежный состав ст. 230 (ОСАГО).
ROAD_ARTICLES = {
    "230",
    "590", "591", "592", "593", "594", "595", "596", "597", "598", "599",
    "600", "601", "602", "603", "604", "605", "606", "607", "608", "609",
    "610", "611", "612", "613", "614", "615", "616", "617", "618", "619",
    "620", "621", "622", "631", "667",
}

# Наименования сверены с фабулами дел выгрузки 1-АД.
ARTICLE_TITLES: dict[str, str] = {
    # против личности и общества
    "73": "Противоправные действия в сфере семейно-бытовых отношений",
    "73-3": "Нарушение неприкосновенности частной жизни",
    "127": "Невыполнение родителями обязанностей по воспитанию детей",
    "127-2": "Противоправные действия несовершеннолетних в отношении сверстников",
    "132": "Допуск несовершеннолетних в развлекательные заведения в ночное время",
    "423-1": "Продажа несовершеннолетним табачной и никотиносодержащей продукции",
    "434": "Мелкое хулиганство",
    "434-3": "Ношение в общественных местах одежды, препятствующей распознаванию лица",
    "435": "Нарушение общественного порядка несовершеннолетними",
    "437": "Нарушение тишины и покоя граждан",
    "440": "Распитие алкоголя либо появление в общественном месте в состоянии опьянения",
    "442": "Нахождение несовершеннолетних вне жилища в ночное время без сопровождения",
    "449": "Приставание в общественных местах с навязыванием услуг",
    "461": "Нарушение общественного порядка в семейно-бытовой сфере",
    "480": "Несоблюдение требований административного надзора",
    # дорожная безопасность
    "230": "Управление транспортным средством без договора ОСАГО",
    "590": "Нарушение правил дорожного движения",
    "591": "Пользование телефоном при управлении транспортным средством",
    "593": "Несоблюдение дистанции и бокового интервала",
    "594": "Нарушение правил проезда перекрёстков",
    "595": "Нарушение правил маневрирования (неподача сигнала поворота)",
    "596": "Нарушение правил расположения на проезжей части",
    "597": "Нарушение правил остановки и стоянки",
    "599": "Проезд на запрещающий сигнал светофора",
    "600": "Непредоставление преимущества пешеходам",
    "601": "Невыполнение требований дорожных знаков и разметки",
    "602": "Нарушение правил пользования внешними световыми приборами",
    "603": "Незаконная установка специальных световых приборов",
    "606": "Создание аварийной обстановки",
    "608": "Нарушение правил перевозки людей и грузов",
    "610": "Нарушение правил выезда с прилегающей территории",
    "612": "Управление транспортным средством без права управления",
    "613": "Передача управления лицу, не имеющему права управления",
    "615": "Нарушение правил дорожного движения пешеходами",
    "617": "Выпуск на линию технически неисправного транспортного средства",
    "620": "Нарушение правил проезда пересечений",
    "621": "Нарушение иных правил дорожного движения",
    "631": "Нарушение правил производства работ на дорогах",
    "667": "Эксплуатация транспортного средства без государственных номеров",
    # иные составы (для полноты таблиц)
    "197": "Нарушение ограничений оборота никотиносодержащей продукции",
    "200": "Нарушение правил реализации алкогольной продукции",
    "204": "Торговля в неустановленных местах",
    "364": "Нарушение правил рыболовства",
    "382": "Нарушение правил охоты",
    "407-2": "Нарушение правил содержания домашних животных",
    "408": "Нарушение правил выпаса сельскохозяйственных животных",
    "420": "Непринятие мер к уничтожению дикорастущей конопли",
    "434-2": "Загрязнение мест общего пользования",
    "441": "Курение в неустановленных местах",
    "484": "Нарушение правил хранения гражданского оружия",
    "486": "Нарушение сроков хранения гражданского оружия",
    "492": "Проживание без регистрации либо по недействительным документам",
    "505": "Нарушение правил благоустройства",
    "517": "Нарушение иностранцем срока пребывания в Республике Казахстан",
    "518": "Нарушение правил приёма и оформления иностранцев",
    "669": "Неуплата административного штрафа в срок",
    "80-1": "Нарушение законодательства о здравоохранении",
}

BLOCK_LABELS = {
    "person": "Против личности и общества",
    "road": "Дорожная безопасность",
    "other": "Иные составы",
}


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _article_base(article: str) -> str:
    m = ARTICLE_RE.search(article)
    return m.group(1) if m else ""


def _parse_article(raw: str) -> str:
    m = ARTICLE_RE.search(_s(raw))
    if not m:
        return _s(raw)
    base, part = m.group(1), m.group(2)
    return f"ст.{base} ч.{part}" if part else f"ст.{base}"


def _parse_date(s: str) -> datetime | None:
    try:
        return datetime.strptime(_s(s), "%d.%m.%Y")
    except ValueError:
        return None


def block_of(article: str) -> str:
    base = _article_base(article)
    if base in PERSON_ARTICLES:
        return "person"
    if base in ROAD_ARTICLES:
        return "road"
    return "other"


def group_of(article: str) -> str:
    base = _article_base(article)
    for group, arts in PERSON_GROUPS.items():
        if base in arts:
            return group
    return ""


def title_of(article: str) -> str:
    return ARTICLE_TITLES.get(_article_base(article), "—")


def default_source() -> Path:
    """Путь к выгрузке 1-АД: DATA_DIR в контейнере либо корень репозитория."""
    name = ("Группа отчетов об административных правонарушениях (ф.1-АД) "
            "данные к отчету 1-АД - 15 августа 2026 г. в 13_35_06.xlsx")
    candidate = Path(os.getenv("DATA_DIR", "/data")) / "Уйгур, Чунджа" / name
    if candidate.exists():
        return candidate
    return Path(__file__).resolve().parents[3] / "Уйгур, Чунджа" / name


def load_chundzha_rows(path: Path | None = None) -> list[dict]:
    src = Path(path) if path else default_source()
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = [_s(h) for h in next(it)]
    idx = {h: i for i, h in enumerate(header)}

    def get(row, col):
        i = idx.get(col)
        return _s(row[i]) if i is not None and i < len(row) else ""

    rows: list[dict] = []
    for raw in it:
        row = list(raw)
        place = get(row, COL_PLACE)
        if not CHUNDZHA_RE.search(place) or ROUTE_RE.search(place):
            continue
        article = _parse_article(get(row, COL_ARTICLE))
        fine = row[idx[COL_FINE]] if COL_FINE in idx else None
        fine_short = row[idx[COL_FINE_SHORT]] if COL_FINE_SHORT in idx else None
        dt = _parse_date(get(row, COL_DATE))
        rows.append({
            "article": article,
            "article_base": _article_base(article),
            "block": block_of(article),
            "group": group_of(article),
            "decision": get(row, COL_DECISION),
            "measure": get(row, COL_MEASURE),
            "month": dt.strftime("%Y-%m") if dt else "",
            "sex": get(row, COL_SEX),
            "age": get(row, COL_AGE),
            "unit": get(row, COL_UNIT),
            "fine": fine if isinstance(fine, (int, float)) and fine > 0 else 0,
            "fine_short": fine_short if isinstance(fine_short, (int, float)) and fine_short > 0 else 0,
        })
    wb.close()
    return rows


def _top(counter: Counter, n: int) -> list[dict]:
    return [{"name": k, "count": v} for k, v in counter.most_common(n) if k]


def article_count(rows: list[dict], base: str) -> int:
    """Точное количество дел по базовой статье (без захвата ст. 73-3 в ст. 73)."""
    return sum(1 for r in rows if r["article_base"] == base)


def block_stats(rows: list[dict], block: str) -> dict:
    rs = [r for r in rows if r["block"] == block]
    total = len(rs)
    if not total:
        return {"block": block, "label": BLOCK_LABELS[block], "total": 0,
                "articles": [], "by_month": {}, "decisions": [], "measures": [],
                "sex": [], "age": [], "units": [], "groups": [],
                "terminated": 0, "terminated_pct": 0.0, "imposed": 0, "fines_total": 0}

    decisions = Counter(r["decision"] for r in rs if r["decision"])
    terminated = sum(v for k, v in decisions.items() if "прекращ" in k.lower())
    imposed = sum(v for k, v in decisions.items() if "наложением" in k.lower())

    articles = Counter(r["article_base"] for r in rs)
    articles_detail = [
        {
            "article": f"ст.{base}",
            "title": ARTICLE_TITLES.get(base, "—"),
            "count": cnt,
            "share_pct": round(cnt / total * 100, 1),
        }
        for base, cnt in articles.most_common(15)
    ]

    groups = Counter(r["group"] for r in rs if r["group"])
    groups_detail = [
        {"name": g, "count": c, "share_pct": round(c / total * 100, 1)}
        for g, c in groups.most_common()
    ]

    return {
        "block": block,
        "label": BLOCK_LABELS[block],
        "total": total,
        "articles": articles_detail,
        "groups": groups_detail,
        "by_month": dict(sorted(Counter(r["month"] for r in rs if r["month"]).items())),
        "decisions": _top(decisions, 6),
        "measures": _top(Counter(r["measure"] for r in rs if r["measure"]), 8),
        "sex": _top(Counter(r["sex"] for r in rs), 3),
        "age": _top(Counter(r["age"] for r in rs), 8),
        "units": _top(Counter(r["unit"] for r in rs), 6),
        "terminated": terminated,
        "terminated_pct": round(terminated / total * 100, 1),
        "imposed": imposed,
        "fines_total": int(sum(r["fine"] for r in rs) + sum(r["fine_short"] for r in rs)),
    }


STRICT_MEASURES = ("арест", "общественные работы", "лишение спец.права")


def outcome_of(row: dict) -> str:
    """Фактический исход производства.

    Выгрузка 1-АД содержит записи разных стадий: «рассмотрен с наложением
    взыскания» (мера указана в графе 9.1) и «исполнение наказания: погашение
    штрафа» (мера не заполняется, но штраф наложен и погашен). Поэтому исход
    определяется по решению, а не по наличию меры взыскания.
    """
    decision = (row.get("decision") or "").lower()
    measure = row.get("measure") or ""
    if "прекращ" in decision or "освобожд" in decision:
        return "terminated"
    if "передан" in decision:
        return "transferred"
    if "сполнение" in decision:
        return "fine"
    if measure == "предупреждение":
        return "warning"
    if "штраф" in measure:
        return "fine"
    if measure in STRICT_MEASURES or "выдворен" in measure:
        return "strict"
    return "other"


def enforcement_by_article(rows: list[dict], block: str, min_count: int = 3) -> list[dict]:
    """Исходы производств по статьям блока.

    Позволяет отличить реальное взыскание (штраф, арест, общественные работы)
    от предупреждения и от прекращения производства.
    """
    out: list[dict] = []
    bases = Counter(r["article_base"] for r in rows if r["block"] == block)
    for base, cnt in bases.most_common():
        if cnt < min_count:
            continue
        rs = [r for r in rows if r["article_base"] == base]
        o = Counter(outcome_of(r) for r in rs)
        real = o["fine"] + o["strict"]
        out.append({
            "article": f"ст.{base}",
            "title": ARTICLE_TITLES.get(base, "—"),
            "total": cnt,
            "fine": o["fine"],
            "strict": o["strict"],
            "warning": o["warning"],
            "terminated": o["terminated"],
            "transferred": o["transferred"],
            "real_penalty": real,
            "real_pct": round(real / cnt * 100, 1),
            "warning_pct": round(o["warning"] / cnt * 100, 1),
            "terminated_pct": round(o["terminated"] / cnt * 100, 1),
        })
    return out


def outcome_summary(rows: list[dict], block: str) -> dict:
    rs = [r for r in rows if r["block"] == block]
    o = Counter(outcome_of(r) for r in rs)
    total = len(rs) or 1
    return {
        "fine": o["fine"], "strict": o["strict"], "warning": o["warning"],
        "terminated": o["terminated"], "transferred": o["transferred"],
        "real_penalty": o["fine"] + o["strict"],
        "real_pct": round((o["fine"] + o["strict"]) / total * 100, 1),
        "warning_pct": round(o["warning"] / total * 100, 1),
    }


def unit_load(rows: list[dict]) -> list[dict]:
    """Распределение нагрузки подразделений ОВД по блокам."""
    out: list[dict] = []
    for unit, cnt in Counter(r["unit"] for r in rows if r["unit"]).most_common(8):
        rs = [r for r in rows if r["unit"] == unit]
        by_block = Counter(r["block"] for r in rs)
        out.append({
            "unit": unit,
            "total": cnt,
            "person": by_block.get("person", 0),
            "road": by_block.get("road", 0),
            "other": by_block.get("other", 0),
            "person_pct": round(by_block.get("person", 0) / cnt * 100, 1),
        })
    return out


def build_analysis(path: Path | None = None) -> dict:
    rows = load_chundzha_rows(path)
    total = len(rows)
    blocks = {b: block_stats(rows, b) for b in ("person", "road", "other")}
    person, road = blocks["person"], blocks["road"]

    key_articles = {
        base: article_count(rows, base)
        for base in ("73", "73-3", "434", "440", "442", "127", "437", "449", "480", "612")
    }
    arrests = Counter(
        r["article_base"] for r in rows
        if r["measure"] == "арест" and r["block"] == "person"
    )

    return {
        "enforcement_person": enforcement_by_article(rows, "person"),
        "enforcement_road": enforcement_by_article(rows, "road"),
        "outcomes": {b: outcome_summary(rows, b) for b in ("person", "road", "other")},
        "unit_load": unit_load(rows),
        "person_arrests": [{"article": f"ст.{k}", "count": v} for k, v in arrests.most_common()],
        "arrests_total": sum(1 for r in rows if r["measure"] == "арест"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "locality": "с. Чунджа (Шонжы) Уйгурского района",
        "period": "01.01.2026 – 14.08.2026",
        "total": total,
        "blocks": blocks,
        "key_articles": key_articles,
        "ratio_road_to_person": round(road["total"] / person["total"], 1) if person["total"] else 0,
        "person_share_pct": round(person["total"] / total * 100, 1) if total else 0,
        "road_share_pct": round(road["total"] / total * 100, 1) if total else 0,
    }
