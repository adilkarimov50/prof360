"""Разбор областной выгрузки диспансерного учёта F00-F99 (Алматинская область).

Файл сгруппирован по медицинским организациям: строки-заголовки с названием
организации чередуются со строками пациентов. Скрипт восстанавливает привязку
пациента к организации и считает агрегаты по наркологическому (F11-F19)
и алкогольному (F10) учёту. Персональные данные наружу не выводятся.
"""

import re
import sys

import pandas as pd

SRC = "F00-99.xlsx"

# Районы/города Алматинской области по названию медорганизации
DISTRICT_PATTERNS = [
    ("Карасайский", r"карасай|каскелен"),
    ("Илийский", r"илий|отеген|байсерке"),
    ("Талгарский", r"талгар"),
    ("Енбекшиказахский", r"енбекшиказах|есик|иссык"),
    ("Жамбылский", r"жамбыл|узынагаш"),
    ("Райымбекский", r"райымбек|кеген"),
    ("Кегенский", r"кеген"),
    ("Уйгурский", r"уйгур|чунджа"),
    ("Балхашский", r"балхаш|баканас"),
    ("Кербулакский", r"кербулак|сарыозек"),
    ("г. Конаев", r"конаев|капшагай"),
    ("г. Алатау", r"алатау"),
    ("Областной уровень", r"рпб|областн|обласной|аймақ"),
]


def detect_district(org: str) -> str:
    low = org.lower()
    for name, pat in DISTRICT_PATTERNS:
        if re.search(pat, low):
            return name
    return "Не определён"


def load() -> pd.DataFrame:
    raw = pd.read_excel(SRC, sheet_name="spis_pac_sostoit", header=None)
    rows = []
    org = ""
    for _, r in raw.iterrows():
        c0, code = r[0], r[6]
        # строка-заголовок организации: текст в первой колонке, кода МКБ нет
        if pd.notna(c0) and pd.isna(code) and not str(c0).strip().isdigit():
            txt = str(c0).strip()
            if len(txt) > 12 and not txt.startswith(("№", "Всего", " Всего")):
                org = txt
            continue
        if pd.isna(code) or pd.isna(c0):
            continue
        if not str(c0).strip().replace(".0", "").isdigit():
            continue
        rows.append(
            {
                "org": org,
                "birth": r[3],
                "sex": str(r[5]).strip(),
                "code": str(code).strip().upper(),
                "diag": str(r[7]).strip() if pd.notna(r[7]) else "",
                "system": str(r[8]).strip() if pd.notna(r[8]) else "",
                "reg_date": r[9],
            }
        )
    d = pd.DataFrame(rows)
    d["block"] = d["code"].str.slice(0, 3)
    d["district"] = d["org"].map(detect_district)
    d["birth_dt"] = pd.to_datetime(d["birth"], errors="coerce", dayfirst=True)
    d["reg_dt"] = pd.to_datetime(d["reg_date"], errors="coerce", dayfirst=True)
    ref = pd.Timestamp("2026-09-08")
    d["age"] = ((ref - d["birth_dt"]).dt.days / 365.25).round(0)
    d["years_reg"] = ((ref - d["reg_dt"]).dt.days / 365.25).round(1)
    return d


def main() -> None:
    d = load()
    print(f"всего записей F00-F99 по области: {len(d)}")
    print(f"организаций распознано: {d['org'].nunique()}")

    sud = d[d["block"].str.match(r"F1[0-9]", na=False)].copy()
    print(f"\n=== Учёт по психоактивным веществам F10-F19: {len(sud)} чел. "
          f"({len(sud) / len(d) * 100:.1f}% всего F00-F99) ===")

    print("\n-- по блокам МКБ-10 --")
    for blk, n in sud["block"].value_counts().items():
        name = sud[sud["block"] == blk]["diag"].mode()
        print(f"  {blk}: {n:5d}  {str(name.iloc[0])[:62] if len(name) else ''}")

    alco = sud[sud["block"] == "F10"]
    narco = sud[sud["block"].isin([f"F1{i}" for i in range(1, 10)])]
    print(f"\n  алкогольный учёт (F10): {len(alco)}")
    print(f"  наркологический учёт (F11-F19): {len(narco)}")

    print("\n-- пол --")
    for grp, label in ((alco, "F10 алкоголь"), (narco, "F11-F19 наркотики")):
        vc = grp["sex"].value_counts()
        tot = vc.sum()
        parts = ", ".join(f"{k} {v} ({v / tot * 100:.0f}%)" for k, v in vc.items())
        print(f"  {label}: {parts}")

    print("\n-- возраст --")
    bins = [0, 18, 25, 30, 40, 50, 60, 200]
    labels = ["<18", "18-24", "25-29", "30-39", "40-49", "50-59", "60+"]
    for grp, label in ((alco, "F10 алкоголь"), (narco, "F11-F19 наркотики")):
        cut = pd.cut(grp["age"].dropna(), bins=bins, labels=labels, right=False)
        vc = cut.value_counts().reindex(labels)
        print(f"  {label}:")
        for k, v in vc.items():
            v = 0 if pd.isna(v) else int(v)
            print(f"    {k:>6}: {v:5d} ({v / len(grp) * 100:4.1f}%)")

    print("\n-- по районам (F10-F19) --")
    t = sud.groupby("district").agg(
        всего=("code", "size"),
        F10=("block", lambda s: (s == "F10").sum()),
        женщин=("sex", lambda s: s.str.startswith("Жен").sum()),
        до18=("age", lambda s: (s < 18).sum()),
        медиана_лет_на_учёте=("years_reg", "median"),
    ).sort_values("всего", ascending=False)
    t["F11_F19"] = t["всего"] - t["F10"]
    print(t.to_string())

    print("\n-- длительность нахождения на учёте (F10-F19) --")
    print(f"  медиана: {sud['years_reg'].median():.1f} лет")
    print(f"  свыше 5 лет: {(sud['years_reg'] > 5).sum()} "
          f"({(sud['years_reg'] > 5).sum() / len(sud) * 100:.1f}%)")
    print(f"  свыше 10 лет: {(sud['years_reg'] > 10).sum()} "
          f"({(sud['years_reg'] > 10).sum() / len(sud) * 100:.1f}%)")
    print(f"  поставлено на учёт в 2026 г.: {(sud['reg_dt'] >= '2026-01-01').sum()}")

    print("\n-- несовершеннолетние и молодёжь до 25 (F10-F19) --")
    print(f"  до 18 лет: {(sud['age'] < 18).sum()}")
    print(f"  18-24 года: {((sud['age'] >= 18) & (sud['age'] < 25)).sum()}")

    print("\n-- вся структура F00-F99 для контекста (топ-12 блоков) --")
    for blk, n in d["block"].value_counts().head(12).items():
        print(f"  {blk}: {n:6d} ({n / len(d) * 100:4.1f}%)")

    print("\n-- организации (топ-15 по числу F10-F19) --")
    for org, n in sud["org"].value_counts().head(15).items():
        print(f"  {n:5d}  {org[:88]}")


if __name__ == "__main__":
    sys.exit(main())
