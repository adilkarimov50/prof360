"""Сверка данных скоринга «Туран» с выгрузками диспучёта, ВИЧ/ТБ и ЦПС.

Берёт ИИН из локальных Excel-выгрузок, ищет их в MongoDB `scoring-db`
и строит отчёт: кто из наблюдаемых групп есть в скоринге, с каким баллом,
уровнем риска и поведенческим портретом.

Запуск:  backend/.venv/bin/python scripts/crossmatch_turan.py
"""

from __future__ import annotations

import glob
import re
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parent.parent
DISP_DIR = ROOT / "dispanser_mkb_clean"
OUT = ROOT / "Туран_сверка_с_выгрузками.xlsx"

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "scoring-db"

# Расшифровка групп МКБ из имён файлов диспучёта.
MKB_LABELS = {
    "A15-19": "Туберкулёз органов дыхания",
    "B18-19": "Вирусные гепатиты",
    "B20-24": "ВИЧ",
    "С00-97": "Злокачественные новообразования",
    "D00-09": "Новообразования in situ",
    "D37-48": "Новообразования неопределённого характера",
    "G30-32": "Болезни нервной системы (Альцгеймер и др.)",
    "G35-37": "Рассеянный склероз и демиелинизирующие",
    "G40": "Эпилепсия",
    "I21-22": "Инфаркт миокарда",
    "I60-64": "Инсульт",
    "K74": "Цирроз печени",
    "Орф заб": "Орфанные заболевания",
}

# Поле person.riskLevel заполняется из суммы баллов ПОРТРЕТНОГО анализа
# (PersonPortraitService: RiskLevel.fromScore(analysis.getTotalScore())),
# а не из person.scoring. Пороги enum RiskLevel: 0-9 / 10-15 / 16-20 / 21+.
RISK_RU = {
    "GREEN": "Зелёный (низкий)",
    "YELLOW": "Жёлтый (средний)",
    "RED": "Красный (высокий)",
    "BURGUNDY": "Бордовый (завышенный)",
}

# Пороги из backend/docs/SCORING_CALCULATION_GUIDE.md — применяются к person.scoring.
def risk_by_doc(score) -> str | None:
    if score is None or pd.isna(score):
        return None
    if score < 3:
        return "Низкий (<3)"
    if score < 5:
        return "Средний (3–5)"
    if score < 8:
        return "Повышенный (5–8)"
    return "Критический (≥8)"

PORTRAIT_RU = {
    "SYSTEMATIC_TRAFFIC_VIOLATOR": "Системный нарушитель КоАП",
    "POTENTIAL_DOMESTIC_AGGRESSOR": "Потенциальный семейно-бытовой агрессор",
    "PRONE_TO_OFFENSES": "Склонен к правонарушениям",
    "SEXUAL_OFFENSE_RISK": "Риск преступлений против половой неприкосновенности",
    "NO_PORTRAIT": "Портрет не определён",
}


def norm_iin(value) -> str | None:
    """12 цифр или None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 12 else None


def load_dispensary() -> pd.DataFrame:
    rows = []
    for path in sorted(DISP_DIR.glob("*_clean.xlsx")):
        code = path.stem.removesuffix("_clean")
        df = pd.read_excel(path, dtype=str)
        if "ИИН" not in df.columns:
            continue
        for _, r in df.iterrows():
            iin = norm_iin(r.get("ИИН"))
            if iin:
                rows.append(
                    {
                        "iin": iin,
                        "источник": "Диспучёт",
                        "группа": f"{code} — {MKB_LABELS.get(code, code)}",
                        "фио_источник": r.get("ФИО"),
                        "организация": r.get("Организация"),
                    }
                )
    return pd.DataFrame(rows)


def load_vich_tub() -> pd.DataFrame:
    path = ROOT / "Вич, Туб получатели Алм облыс.xlsx"
    if not path.exists():
        return pd.DataFrame()
    rows = []
    for sheet, df in pd.read_excel(path, sheet_name=None, header=None, dtype=str).items():
        for _, r in df.iterrows():
            values = r.tolist()
            iin = next((norm_iin(v) for v in values if norm_iin(v)), None)
            if not iin:
                continue
            fio = next(
                (str(v) for v in values if isinstance(v, str) and len(str(v)) > 8 and not norm_iin(v)),
                None,
            )
            rows.append(
                {
                    "iin": iin,
                    "источник": "Получатели пособий ВИЧ/ТБ",
                    "группа": f"лист «{sheet}»",
                    "фио_источник": fio,
                    "организация": None,
                }
            )
    return pd.DataFrame(rows)


def load_cps() -> pd.DataFrame:
    matches = glob.glob(str(ROOT / "ЦПС" / "*ИПР*.xlsx"))
    if not matches:
        return pd.DataFrame()
    df = pd.read_excel(matches[0], header=2)
    col = next((c for c in df.columns if "Семья" in str(c)), None)
    if col is None:
        return pd.DataFrame()
    rows = []
    for value in df[col]:
        m = re.search(r"ИИН:\s*(\d{12})", str(value))
        if m:
            rows.append(
                {
                    "iin": m.group(1),
                    "источник": "ЦПС (ИПР семьи)",
                    "группа": "сопровождение ТЖС",
                    "фио_источник": str(value).split("ИИН:")[0].strip(" ,"),
                    "организация": None,
                }
            )
    return pd.DataFrame(rows)


def fetch_turan(iins: list[str]) -> pd.DataFrame:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    coll = client[DB_NAME]["persons"]
    found = []
    chunk = 20000
    fields = {
        "_id": 0,
        "iin": 1,
        "fullName": 1,
        "district": 1,
        "gender": 1,
        "birthDate": 1,
        "scoring": 1,
        "riskLevel": 1,
        "primaryPortrait": 1,
        "scoringDetails.type": 1,
    }
    for i in range(0, len(iins), chunk):
        batch = iins[i : i + chunk]
        for doc in coll.find({"iin": {"$in": batch}}, fields):
            details = doc.get("scoringDetails") or []
            found.append(
                {
                    "iin": doc.get("iin"),
                    "фио_туран": doc.get("fullName"),
                    "район": doc.get("district"),
                    "пол": doc.get("gender"),
                    "дата_рождения": doc.get("birthDate"),
                    "балл": doc.get("scoring"),
                    "риск_портрета": RISK_RU.get(doc.get("riskLevel"), doc.get("riskLevel")),
                    "риск_по_баллу": risk_by_doc(doc.get("scoring")),
                    "портрет": PORTRAIT_RU.get(
                        doc.get("primaryPortrait"), doc.get("primaryPortrait")
                    ),
                    "категорий_учёта": len(details),
                    "категории": ", ".join(
                        sorted({d.get("type", "") for d in details if d.get("type")})
                    ),
                }
            )
    client.close()
    return pd.DataFrame(found)


def main() -> None:
    sources = pd.concat(
        [load_dispensary(), load_vich_tub(), load_cps()], ignore_index=True
    )
    if sources.empty:
        raise SystemExit("не найдено ни одного ИИН в выгрузках")

    unique_iins = sorted(sources["iin"].unique())
    print(f"ИИН в выгрузках: {len(sources):,} строк, {len(unique_iins):,} уникальных")

    turan = fetch_turan(unique_iins)
    print(f"найдено в Туране: {len(turan):,}")

    merged = sources.merge(turan, on="iin", how="left")
    merged["в_туране"] = merged["фио_туран"].notna().map({True: "да", False: "нет"})

    # Сводка по источникам и группам.
    summary = (
        merged.groupby(["источник", "группа"], dropna=False)
        .agg(
            всего=("iin", "nunique"),
            в_туране=("фио_туран", lambda s: s.notna().sum()),
            средний_балл=("балл", "mean"),
        )
        .reset_index()
    )
    summary["покрытие_%"] = (summary["в_туране"] / summary["всего"] * 100).round(1)
    summary["средний_балл"] = summary["средний_балл"].round(2)
    summary = summary.sort_values("всего", ascending=False)

    # Риск среди тех, кто найден.
    hit = merged[merged["фио_туран"].notna()]
    risk_pivot = (
        pd.crosstab(hit["источник"], hit["риск_портрета"]).reset_index()
        if not hit.empty
        else pd.DataFrame()
    )
    risk_score_pivot = (
        pd.crosstab(hit["источник"], hit["риск_по_баллу"]).reset_index()
        if not hit.empty
        else pd.DataFrame()
    )
    portrait_pivot = (
        pd.crosstab(hit["источник"], hit["портрет"]).reset_index()
        if not hit.empty
        else pd.DataFrame()
    )

    # Пересечение медицинского наблюдения и высокого балла скоринга
    # (по методике из SCORING_CALCULATION_GUIDE.md — балл ≥ 5).
    critical = hit[hit["балл"] >= 5].sort_values("балл", ascending=False)

    # Портрет определён — самая адресная группа для профилактики.
    with_portrait = hit[
        ~hit["портрет"].isin(["Портрет не определён", None]) & hit["портрет"].notna()
    ].sort_values("балл", ascending=False)

    cols = [
        "источник", "группа", "iin", "фио_источник", "фио_туран", "район",
        "пол", "дата_рождения", "балл", "риск_по_баллу", "риск_портрета", "портрет",
        "категорий_учёта", "категории", "организация",
    ]

    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="Сводка", index=False)
        if not risk_score_pivot.empty:
            risk_score_pivot.to_excel(xw, sheet_name="Риск_по_баллу", index=False)
        if not risk_pivot.empty:
            risk_pivot.to_excel(xw, sheet_name="Риск_портрета", index=False)
        if not portrait_pivot.empty:
            portrait_pivot.to_excel(xw, sheet_name="Портреты_по_источникам", index=False)
        critical[cols].to_excel(xw, sheet_name="Высокий_риск", index=False)
        with_portrait[cols].to_excel(xw, sheet_name="С_портретом", index=False)
        merged[cols + ["в_туране"]].to_excel(xw, sheet_name="Все_записи", index=False)

        for ws in xw.book.worksheets:
            if ws.max_row > 1:
                ws.auto_filter.ref = ws.dimensions
                ws.freeze_panes = "A2"

    print(f"\nвысокий/критический риск: {len(critical):,}")
    print(f"с определённым портретом:  {len(with_portrait):,}")
    print(f"\nотчёт: {OUT}")


if __name__ == "__main__":
    main()
