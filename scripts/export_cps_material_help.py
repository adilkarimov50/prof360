#!/usr/bin/env python3
"""Выгрузка спонсорской и материальной (гос/натуральной) помощи из ИПР ЦПС."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CPS = ROOT / "ЦПС"
IPR_PATH = CPS / "ИПР семьи' от 09.09.2026 12;29;30 (с 01.01.25 по 09.09.26).xlsx"
OUT = CPS / "ЦПС_спонсорская_и_материальная_помощь.xlsx"
OUT_DOCS = ROOT / "passports" / "docs" / "spravka_cps" / OUT.name

BASKET_RE = re.compile(
    r"продуктов(?:ой|ая|ого|ые)?\s*(?:корзин|набор)|"
    r"продовольственн(?:ая|ую|ой)\s*корзин|"
    r"корзин(?:а|ы)?\s*продукт|"
    r"(?:спонсорск|сплнсорск).{0,40}в\s+виде\s+продукт|"
    r"оказана\s+спонсорская\s+помощь\s+в\s+виде\s+продукт|"
    r"переданы\s+продукты",
    re.I,
)

STATE_ITEM_MEASURES = {
    "Материальная помощь в виде конкретных вещей",
    "Социальная помощь в натуральной форме",
    "Назначение государственной адресной социальной помощи",
    "Социальная помощь в натуральной форме",
    "Материальная помощь в виде конкретных вещей",
}

SPONSOR_MEASURE = "Спонсорская помощь"


def extract_iin_family(row) -> tuple[str | None, str]:
    fam = str(row.get("Семья", "") or "")
    m = re.search(r"ИИН:\s*(\d{12})", fam)
    iin = m.group(1) if m else None
    m2 = re.search(r"ФИО:\s*([^\n]+)", fam)
    fio_fam = m2.group(1).strip() if m2 else ""
    member = str(row.get("Члены семьи", "") or "").strip()
    return iin, member or fio_fam


def clean(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none") else s


def classify_row(row) -> dict:
    measure = clean(row.get("Мера поддержки"))
    result = clean(row.get("Результат"))
    combined = f"{measure} {result}"
    is_basket = bool(BASKET_RE.search(combined))
    is_sponsor_measure = measure == SPONSOR_MEASURE or "спонсор" in combined.lower()
    is_sponsor_not_basket = is_sponsor_measure and not is_basket

    # спонсор в тексте «Иные» с конкретикой
    if measure == "Иные" and re.search(r"спонсор|благотворит|foundation|фонд", combined, re.I):
        if not is_basket:
            is_sponsor_not_basket = True

    is_state_items = measure in STATE_ITEM_MEASURES
    is_state_natural = measure == "Социальная помощь в натуральной форме"
    is_state_material = measure == "Материальная помощь в виде конкретных вещей"
    is_state_asp = measure == "Назначение государственной адресной социальной помощи"

    # материальная помощь в тексте результата (продукты, подгузники, но не только корзина)
    material_in_text = bool(
        re.search(
            r"материальн(?:ая|ую)\s+помощ|приобретен[аы].*продукт|подгузник|коляск|одежд|"
            r"единоразов(?:ого|ая)\s+соц|натуральн",
            combined,
            re.I,
        )
    )

    org = clean(row.get("Организация исполнитель"))
    is_sobez_like = bool(
        re.search(
            r"отдел.*социаль|занятост|соц(?:иаль)?.*програм|управлен.*социаль|"
            r"социальн.*защит|карьерный",
            org,
            re.I,
        )
    )

    category = []
    if is_basket:
        category.append("продуктовая_корзина")
    if is_sponsor_not_basket:
        category.append("спонсорская_не_корзина")
    if is_state_material:
        category.append("гос_материальная_вещи")
    if is_state_natural:
        category.append("гос_соц_натуральная")
    if is_state_asp:
        category.append("гос_АСП")
    if material_in_text and not is_basket:
        category.append("материальная_в_результате")

    return {
        "is_basket": is_basket,
        "is_sponsor_not_basket": is_sponsor_not_basket,
        "is_state_items": is_state_items or is_state_material or is_state_natural,
        "is_sobez_like_org": is_sobez_like,
        "category": "; ".join(category) if category else "",
        "material_in_text": material_in_text,
    }


def load_ipr() -> pd.DataFrame:
    df = pd.read_excel(IPR_PATH, header=2)
    df.columns = [str(c).strip().replace("\n", " ") for c in df.columns]
    df = df[df["Номер родительского задания"].notna()].copy()
    return df


def build_detail(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for _, r in df.iterrows():
        iin, fio = extract_iin_family(r)
        cl = classify_row(r)
        if not cl["category"]:
            continue
        rows.append(
            {
                "Категория": cl["category"],
                "ИИН": iin or "",
                "ФИО (член семьи)": fio,
                "Мера поддержки": clean(r.get("Мера поддержки")),
                "Результат (что выдано/оказано)": clean(r.get("Результат")),
                "Организация-исполнитель": clean(r.get("Организация исполнитель")),
                "Исполнитель гос/соц?": "да" if cl["is_sobez_like_org"] else "нет",
                "Статус": clean(r.get("Статус")),
                "Срок исполнения": clean(r.get("Срок исполнения")),
                "Дата утверждения ИПР": clean(r.get("Дата утверждения")),
                "Номер род. задания": clean(r.get("Номер родительского задания")),
                "Номер задачи": clean(r.get("Номер  задачи")),
                "Ответственный ЦПС": clean(r.get("Ответственный по сопровождению\u00a0семьи")),
                "Выявитель": clean(r.get("Выявитель")),
            }
        )
    return pd.DataFrame(rows)


def main() -> Path:
    df = load_ipr()
    detail = build_detail(df)

    sponsor_all = df[df["Мера поддержки"] == SPONSOR_MEASURE].copy()
    sponsor_all["_cls"] = sponsor_all.apply(classify_row, axis=1)
    basket_rows = detail[detail["Категория"].str.contains("продуктовая_корзина", na=False)]
    sponsor_other = detail[detail["Категория"].str.contains("спонсорская_не_корзина", na=False)]
    state_items = detail[
        detail["Категория"].str.contains(
            "гос_материальная|гос_соц_натуральная|гос_АСП|материальная_в_результате", na=False, regex=True
        )
    ]

    # уникальные лица (по ИИН или ФИО)
    def uniq_persons(sub: pd.DataFrame) -> pd.DataFrame:
        sub = sub.copy()
        sub["key"] = sub.apply(
            lambda r: r["ИИН"] if r["ИИН"] else r["ФИО (член семьи)"], axis=1
        )
        return sub.drop_duplicates(subset=["key"], keep="first").drop(columns=["key"])

    u_basket = uniq_persons(basket_rows)
    u_sponsor_other = uniq_persons(sponsor_other)
    u_state = uniq_persons(state_items)

    summary = pd.DataFrame(
        [
            ("Период ИПР", "01.01.2025 – 09.09.2026"),
            ("Строк ИПР всего", len(df)),
            ("Строк «Спонсорская помощь» (мера)", len(sponsor_all)),
            ("Строк с продуктовой корзиной", len(basket_rows)),
            ("Уник. лиц с продуктовой корзиной", len(u_basket)),
            ("Строк спонсорской помощи БЕЗ корзины", len(sponsor_other)),
            ("Уник. лиц — спонсорская БЕЗ корзины", len(u_sponsor_other)),
            ("Строк гос/материальной (вещи, натура, АСП, текст)", len(state_items)),
            ("Уник. лиц — гос/материальная", len(u_state)),
            ("", ""),
            (
                "Примечание",
                "«Собез» в выгрузке ЦПС — через ГУ Отдел занятости и социальных программ / ЦПС; "
                "отдельного реестра выдачи вещей отделом соцзащиты в файле нет — только ИПР.",
            ),
        ],
        columns=["Показатель", "Значение"],
    )

    sheets = {
        "Сводка": summary,
        "Спонсор_без_корзины": sponsor_other.sort_values(["ИИН", "ФИО (член семьи)"]),
        "Уник_лица_спонсор_не_корзина": u_sponsor_other,
        "Продуктовая_корзина": basket_rows,
        "Уник_лица_корзина": u_basket,
        "Гос_материальная_и_натуральная": state_items.sort_values(["Категория", "ИИН"]),
        "Уник_лица_гос_материальная": u_state,
        "Все_категории": detail.sort_values(["Категория", "ИИН"]),
    }

    for path in (OUT, OUT_DOCS):
        path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            for name, tab in sheets.items():
                tab.to_excel(w, sheet_name=name[:31], index=False)

    print(f"Записано: {OUT}")
    print(summary.to_string(index=False))
    print(f"\nСпонсор без корзины (уник. лиц): {len(u_sponsor_other)}")
    print(f"Гос/материальная (уник. лиц): {len(u_state)}")
    return OUT


if __name__ == "__main__":
    main()
