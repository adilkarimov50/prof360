#!/usr/bin/env python3
"""Сверка списков A15-19, B20-24 и получателей ВИЧ/ТУБ по ИИН."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ВИЧ_ТБ_сверка_списков.xlsx"

# Нормализация районов/городов Алматинской области
DISTRICT_RULES: list[tuple[str, str]] = [
    (
        r"қонаев|конаев|г\.?\s*қ?онаев|"
        r"капшагай|id\s*senim|nova\s*invest|городская многопрофильная",
        "г. Конаев",
    ),
    (
        r"каскелен|karasai|карасай|жапек|отеген|узынагаш|узын|иргел|"
        r"врачебная амбулатория",
        "Карасайский р-н",
    ),
    (r"талгар", "г. Талгар / Талгарский р-н"),
    (r"балхаш", "г. Балхаш / Балхашский р-н"),
    (r"енбекшиказах|шелек", "Енбекшиказахский р-н"),
    (r"илий|иле\b|боралдай|районная больница", "Илийский р-н"),
    (r"уйгур|чундж", "Уйгурский р-н"),
    (r"жамбыл", "Жамбылский р-н"),
    (r"райымбек", "Райымбекский р-н"),
    (r"кеген", "Кегенский р-н"),
    (r"есик|иссык|issyk", "г. Есик"),
]


def canon_district(raw: str | None) -> str:
    if not raw or str(raw).strip() in ("", "nan", "None"):
        return "Не определён"
    s = str(raw).strip().lower()
    for pat, name in DISTRICT_RULES:
        if re.search(pat, s, re.I):
            return name
    title = str(raw).strip().title()
    if re.search(r"больниц|амбулатор|поликлин|медиц", s, re.I):
        return "Прочие МО (уточнить район)"
    return title


def district_from_org(org: str | None) -> str:
    if not org or str(org).strip() in ("", "nan"):
        return "Не определён"
    quoted = re.search(r'"([^"]+)"', str(org))
    text = quoted.group(1) if quoted else str(org)
    return canon_district(text)


def looks_like_fio(name: str) -> bool:
    parts = str(name).strip().split()
    if len(parts) >= 2 and str(name).upper() == str(name):
        return True
    return len(parts) >= 3


def norm_iin(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = re.sub(r"\D", "", str(v))
    return s if len(s) == 12 else None


def iin_from_masked(c2, c3, c4) -> str | None:
    for val in (c4, c2):
        if pd.isna(val):
            continue
        s = str(val).strip()
        m = re.search(r"(\d{6})\*+(\d{6})", s)
        if m:
            return m.group(1) + m.group(2)
        m2 = re.search(r"\*+(\d{6})", s)
        if m2 and pd.notna(c3):
            dm = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", str(c3).strip())
            if dm:
                d, mo, y = dm.groups()
                return f"{y[2:]}{mo}{d}{m2.group(1)}"
    return None


def parse_dispensary(path: Path, list_name: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, header=None)
    rows: list[dict] = []
    org = None
    for i in range(9, len(df)):
        r = df.iloc[i]
        c0, c1, c2, c3, c4 = r[0], r[1], r[2], r[3], r[4]
        if pd.notna(c0) and pd.isna(c1) and pd.isna(c2) and len(str(c0)) > 30:
            org = str(c0).strip()
            continue
        if pd.isna(c1) or str(c1).strip() in ("", "nan"):
            continue
        fio = str(c1).strip()
        if fio in ("№", "Т.А.Ә./Ф.И.О."):
            continue
        rows.append({
            "iin": iin_from_masked(c2, c3, c4),
            "fio_short": fio,
            "dob": r[3],
            "sex": r[5],
            "icd": r[6],
            "diagnosis": r[7],
            "org": org,
            "district_raw": district_from_org(org),
            "date_reg": r[9],
            "source_list": list_name,
            "source_file": path.name,
        })
    return pd.DataFrame(rows)


def parse_beneficiaries(path: Path) -> pd.DataFrame:
    frames: list[dict] = []
    for sh, list_name in (("ВИЧ", "VICH"), ("ТУБ", "TUB")):
        df = pd.read_excel(path, sheet_name=sh, header=None)
        district = None
        for i in range(2, len(df)):
            r = df.iloc[i]
            c1 = str(r[1]).strip() if pd.notna(r[1]) else ""
            # строка-заголовок района: «8 | Енбекшиказах | —»
            if c1 and pd.isna(r[2]) and not looks_like_fio(c1) and c1 not in ("Ф.И.О", "nan"):
                district = c1
                continue
            if pd.isna(r[1]):
                continue
            fio = c1
            if not fio or fio in ("Ф.И.О", "nan"):
                continue
            frames.append({
                "iin": norm_iin(r[2]),
                "fio_full": fio,
                "district_raw": canon_district(district),
                "source_list": list_name,
                "source_file": path.name,
            })
    return pd.DataFrame(frames)


def dedupe_by_iin(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    with_iin = df[df["iin"].notna()].drop_duplicates(subset=["iin"], keep="first")
    no_iin = df[df["iin"].isna()].copy()
    return with_iin, no_iin


def _pick_district(parts: list[str]) -> str:
    parts = [canon_district(p) for p in parts if p and p != "Не определён"]
    if not parts:
        return "Не определён"
    unique = list(dict.fromkeys(parts))
    return unique[0] if len(unique) == 1 else f"{unique[0]} (±{len(unique)-1})"


def resolve_district(ra, rb, rv, rt, in_a, in_b, in_v, in_t) -> str:
    # Для разбивки по области — район из списков получателей; иначе — по МО диспансера
    ben: list[str] = []
    if in_v and rv is not None:
        ben.append(rv["district_raw"])
    if in_t and rt is not None:
        ben.append(rt["district_raw"])
    if ben:
        return _pick_district(ben)
    disp: list[str] = []
    if in_a and ra is not None:
        disp.append(ra["district_raw"])
    if in_b and rb is not None:
        disp.append(rb["district_raw"])
    return _pick_district(disp)


DISTRICT_ORDER = [
    "г. Конаев",
    "г. Талгар / Талгарский р-н",
    "г. Балхаш / Балхашский р-н",
    "г. Есик",
    "Карасайский р-н",
    "Енбекшиказахский р-н",
    "Илийский р-н",
    "Жамбылский р-н",
    "Уйгурский р-н",
    "Райымбекский р-н",
    "Кегенский р-н",
    "Прочие МО (уточнить район)",
    "Не определён",
]


def _district_sort_key(name: str) -> tuple:
    base = name.split(" (±")[0]
    if base in DISTRICT_ORDER:
        return (0, DISTRICT_ORDER.index(base), name)
    return (1, name)


def build_district_summary(master: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for district in sorted(master["район"].unique(), key=_district_sort_key):
        sub = master[master["район"] == district]
        tb_d = sub[sub["A15-19_ТБ_дисп"] == "да"]
        vich_d = sub[sub["B20-24_ВИЧ_дисп"] == "да"]
        vich_b = sub[sub["ВИЧ_получатели"] == "да"]
        tub_b = sub[sub["ТУБ_получатели"] == "да"]
        rows.append({
            "Район / город": district,
            "Уник. ИИН всего": len(sub),
            "A15-19 ТБ дисп.": len(tb_d),
            "B20-24 ВИЧ дисп.": len(vich_d),
            "ВИЧ получатели": len(vich_b),
            "ТУБ получатели": len(tub_b),
            "ТБ дисп ∩ ТУБ получ.": len(sub[(sub["A15-19_ТБ_дисп"] == "да") & (sub["ТУБ_получатели"] == "да")]),
            "ВИЧ дисп ∩ ВИЧ получ.": len(sub[(sub["B20-24_ВИЧ_дисп"] == "да") & (sub["ВИЧ_получатели"] == "да")]),
            "ТБ дисп без получ.": len(sub[(sub["A15-19_ТБ_дисп"] == "да") & (sub["ТУБ_получатели"] != "да")]),
            "ВИЧ дисп без получ.": len(sub[(sub["B20-24_ВИЧ_дисп"] == "да") & (sub["ВИЧ_получатели"] != "да")]),
            "Только 1 список": len(sub[sub["списков_всего"] == 1]),
        })
    return pd.DataFrame(rows)


def presence_label(row) -> str:
    parts = []
    if row["A15-19_ТБ_дисп"] == "да":
        parts.append("A15-19")
    if row["B20-24_ВИЧ_дисп"] == "да":
        parts.append("B20-24")
    if row["ВИЧ_получатели"] == "да":
        parts.append("ВИЧ")
    if row["ТУБ_получатели"] == "да":
        parts.append("ТУБ")
    return " + ".join(parts) if parts else "—"


def main() -> Path:
    a15 = parse_dispensary(ROOT / "A15-19.xlsx", "A15-19_ТБ_дисп")
    b20 = parse_dispensary(ROOT / "B20-24.xlsx", "B20-24_ВИЧ_дисп")
    ben = parse_beneficiaries(ROOT / "Вич, Туб получатели Алм облыс.xlsx")

    a15_u, a15_no = dedupe_by_iin(a15)
    b20_u, b20_no = dedupe_by_iin(b20)
    v_u, v_no = dedupe_by_iin(ben[ben["source_list"] == "VICH"])
    t_u, t_no = dedupe_by_iin(ben[ben["source_list"] == "TUB"])

    all_iins = sorted(set(a15_u["iin"]) | set(b20_u["iin"]) | set(v_u["iin"]) | set(t_u["iin"]))

    records: list[dict] = []
    for iin in all_iins:
        in_a = iin in set(a15_u["iin"])
        in_b = iin in set(b20_u["iin"])
        in_v = iin in set(v_u["iin"])
        in_t = iin in set(t_u["iin"])
        ra = a15_u[a15_u["iin"] == iin].iloc[0] if in_a else None
        rb = b20_u[b20_u["iin"] == iin].iloc[0] if in_b else None
        rv = v_u[v_u["iin"] == iin].iloc[0] if in_v else None
        rt = t_u[t_u["iin"] == iin].iloc[0] if in_t else None
        district = resolve_district(ra, rb, rv, rt, in_a, in_b, in_v, in_t)
        records.append({
            "ИИН": iin,
            "район": district,
            "ФИО_получатели": rv["fio_full"] if in_v else (rt["fio_full"] if in_t else ""),
            "ФИО_диспансер": ra["fio_short"] if in_a else (rb["fio_short"] if in_b else ""),
            "A15-19_ТБ_дисп": "да" if in_a else "",
            "B20-24_ВИЧ_дисп": "да" if in_b else "",
            "ВИЧ_получатели": "да" if in_v else "",
            "ТУБ_получатели": "да" if in_t else "",
            "списков_всего": sum([in_a, in_b, in_v, in_t]),
            "МКБ_A15-19": ra["icd"] if in_a else "",
            "МКБ_B20-24": rb["icd"] if in_b else "",
            "диагноз_ТБ": ra["diagnosis"] if in_a else "",
            "диагноз_ВИЧ": rb["diagnosis"] if in_b else "",
            "район_ВИЧ_получ": rv["district_raw"] if in_v else "",
            "район_ТУБ_получ": rt["district_raw"] if in_t else "",
            "орган_диспансер": ra["org"] if in_a else (rb["org"] if in_b else ""),
            "дата_учёта_ТБ": ra["date_reg"] if in_a else "",
            "дата_учёта_ВИЧ": rb["date_reg"] if in_b else "",
        })

    master = pd.DataFrame(records)
    master["где_есть"] = master.apply(presence_label, axis=1)
    by_district = build_district_summary(master)

    def pick(df: pd.DataFrame) -> pd.DataFrame:
        return master.loc[df.index].copy()

    summary_rows = [
        ("A15-19 — дисп. учёт ТБ (МКБ A15–A19)", len(a15), len(a15_u), len(a15_no)),
        ("B20-24 — дисп. учёт ВИЧ (МКБ B20–B24)", len(b20), len(b20_u), len(b20_no)),
        ("ВИЧ — получатели (лист ВИЧ)", len(ben[ben["source_list"] == "VICH"]), len(v_u), len(v_no)),
        ("ТУБ — получатели (лист ТУБ)", len(ben[ben["source_list"] == "TUB"]), len(t_u), len(t_no)),
        ("Уникальных ИИН (объединение 4 списков)", len(master), len(master), 0),
        ("ТБ дисп. ∩ ТУБ получатели", len(master[(master["A15-19_ТБ_дисп"] == "да") & (master["ТУБ_получатели"] == "да")]), "", ""),
        ("ВИЧ дисп. ∩ ВИЧ получатели", len(master[(master["B20-24_ВИЧ_дисп"] == "да") & (master["ВИЧ_получатели"] == "да")]), "", ""),
        ("ТБ дисп. без ТУБ получателей", len(master[(master["A15-19_ТБ_дисп"] == "да") & (master["ТУБ_получатели"] != "да")]), "", ""),
        ("ВИЧ дисп. без ВИЧ получателей", len(master[(master["B20-24_ВИЧ_дисп"] == "да") & (master["ВИЧ_получатели"] != "да")]), "", ""),
        ("ТБ + ВИЧ (оба дисп. учёта)", len(master[(master["A15-19_ТБ_дисп"] == "да") & (master["B20-24_ВИЧ_дисп"] == "да")]), "", ""),
        ("Во всех 4 списках", len(master[master["списков_всего"] == 4]), "", ""),
    ]
    summary = pd.DataFrame(summary_rows, columns=["Показатель", "Строк в файле", "Уник. ИИН", "Без ИИН"])

    sheets = {
        "Сводка": summary,
        "По_районам": by_district,
        "По_районам_лица": master.sort_values(["район", "списков_всего", "ИИН"], ascending=[True, False, True]),
        "Все_лица_по_ИИН": master.sort_values(["списков_всего", "ИИН"], ascending=[False, True]),
        "ТБ_дисп_и_получатели": pick(master[(master["A15-19_ТБ_дисп"] == "да") & (master["ТУБ_получатели"] == "да")]),
        "ВИЧ_дисп_и_получатели": pick(master[(master["B20-24_ВИЧ_дисп"] == "да") & (master["ВИЧ_получатели"] == "да")]),
        "ТБ_дисп_без_получателей": pick(master[(master["A15-19_ТБ_дисп"] == "да") & (master["ТУБ_получатели"] != "да")]),
        "ВИЧ_дисп_без_получателей": pick(master[(master["B20-24_ВИЧ_дисп"] == "да") & (master["ВИЧ_получатели"] != "да")]),
        "ТБ_и_ВИЧ_оба_дисп": pick(master[(master["A15-19_ТБ_дисп"] == "да") & (master["B20-24_ВИЧ_дисп"] == "да")]),
        "Только_1_список": pick(master[master["списков_всего"] == 1]),
        "В_2_списках": pick(master[master["списков_всего"] == 2]),
        "В_3_и_4_списках": pick(master[master["списков_всего"] >= 3]),
        "Без_ИИН": pd.concat([
            a15_no.assign(источник="A15-19"),
            b20_no.assign(источник="B20-24"),
            v_no.assign(источник="ВИЧ"),
            t_no.assign(источник="ТУБ"),
        ], ignore_index=True),
        "Исход_A15-19": a15,
        "Исход_B20-24": b20,
        "Исход_получатели": ben,
    }

    with pd.ExcelWriter(OUT, engine="openpyxl") as w:
        for name, df in sheets.items():
            safe = name[:31]
            df.to_excel(w, sheet_name=safe, index=False)

    print(f"Записано: {OUT}")
    print(summary.to_string(index=False))
    return OUT


if __name__ == "__main__":
    main()
