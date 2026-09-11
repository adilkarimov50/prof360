#!/usr/bin/env python3
"""Полный анализ ЦПС Карасайского района по выгрузкам FSM Social."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CPS = ROOT / "ЦПС"
OUT = CPS / "ЦПС_полный_анализ.xlsx"
SUICIDE_X = ROOT / "Суицид_F00-99_ЦПС_сверка.xlsx"

NORMATIVE = pd.DataFrame(
    [
        (
            "Учёт обращений по стандарту ТЖС",
            "405 из 457 обращений в ТЖС без ИИН (89%)",
            "Приказ МКИ РК №256-НҚ (Правила ЦПС), журнал по стандарту ТЖС; "
            "п.13–14 — первичная оценка и учёт",
        ),
        (
            "Координация межведомственной помощи",
            "632 из 650 мер ИПР исполняет сам ЦПС (97%); образование 0 исполнено; "
            "соцзащита 0",
            "Кодекс «О браке и семье» ст.5-1 п.2 пп.2; Правила ЦПС п.6 пп.2, п.15, п.18; "
            "Закон о профилактике правонарушений ст.10",
        ),
        (
            "Мобильные группы",
            "271 из 276 выездов без времени приезда; в протоколе — только сотрудники ЦПС",
            "Правила ЦПС п.20–22; ст.11 Закона о профилактике — состав МГ (ОВД, "
            "здравоохранение, образование)",
        ),
        (
            "Содержание ИПР",
            '428 мер (66%) указаны как «Иные» без конкретизации; 37 семей с несколькими '
            "родительскими заданиями",
            "Правила ЦПС п.16–17 — мероприятия со сроками и видами поддержки",
        ),
        (
            "Результат «консультация / не нуждается»",
            "244 итога с одной консультацией; 66 — «не нуждается»; 66 — «бордовая зона ЦКС»",
            "Правила ЦПС п.11–13 — всесторонняя поддержка, не сводящаяся к разовой беседе",
        ),
        (
            "Направления от пробации",
            "218 направлений; 181 (83%) закрыты консультацией/отказом в помощи",
            "Правила ЦПС п.12 пп.4; интегрированная модель (п.2 Правил)",
        ),
        (
            "Спецсоциальные услуги и убежище",
            "0 оказано спецуслуг; 0 временного проживания (по отчёту о работе)",
            "Правила ЦПС п.23–25; ст.5-1 Кодекса о браке п.2 пп.4",
        ),
        (
            "Достоверность отчётности",
            "Строки-шаблоны (37) в журнале; «пробация» 7 взято / 310 «исполнено»",
            "Требования к ведению ИС и служебная дисциплина",
        ),
        (
            "Охват лиц группы риска (суицид)",
            "596 из 598 лиц с суицидом без обращения в ЦПС; 14 F00–99+суицид — 0 в ЦПС",
            "Правила ЦПС п.12 пп.3–5; ст.54, ст.72 Закона о профилактике; взаимодействие с ОЗ",
        ),
    ],
    columns=["Нарушение / риск", "Факт по данным", "Норма"],
)


def clean_journal(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, header=2)
    df.columns = [str(c).strip().replace("\n", " ") for c in df.columns]
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")], errors="ignore")
    df = df[pd.to_numeric(df["№ обращения"], errors="coerce").notna()].copy()
    df["№ обращения"] = df["№ обращения"].astype(int)
    df["dt"] = pd.to_datetime(df["Дата"], dayfirst=True, errors="coerce")
    df["iin"] = df["ИИН"].apply(
        lambda x: re.sub(r"\D", "", str(x)) if pd.notna(x) else None
    )
    df.loc[df["iin"].astype(str).str.len() != 12, "iin"] = None
    return df


def extract_iin(text) -> str | None:
    if pd.isna(text):
        return None
    m = re.search(r"ИИН:\s*(\d{12})", str(text))
    if m:
        return m.group(1)
    m = re.search(r"(\d{12})", str(text))
    return m.group(1) if m else None


def micro_district(row) -> str:
    kato = str(row.get("КАТО (район)", "") or "")
    addr = str(row.get("Адрес проживания", "") or "")
    s = f"{kato} {addr}".lower()
    if re.search(r"каскелен|195220", s):
        return "г. Каскелен"
    if re.search(r"отеген", s):
        return "с. Отеген батыра"
    if re.search(r"иргел", s):
        return "с. Иргели"
    if re.search(r"карасай|195200", s):
        return "Карасайский р-н (прочие НП)"
    return "Адрес не детализирован"


def load_ipr() -> pd.DataFrame:
    df = pd.read_excel(
        CPS / "ИПР семьи' от 09.09.2026 12;29;30 (с 01.01.25 по 09.09.26).xlsx",
        header=2,
    )
    df.columns = [str(c).strip().replace("\n", " ") for c in df.columns]
    df = df[df["Номер родительского задания"].notna()].copy()
    df["iin"] = df["Семья"].apply(extract_iin)
    df["parent_task"] = pd.to_numeric(df["Номер родительского задания"], errors="coerce")
    return df


def load_work_report() -> pd.DataFrame:
    raw = pd.read_excel(
        CPS
        / "Отчет 'Отчет о проделанной работе' от 09.09.2026 12;36;20 (с 01.01.26 по 09.09.26).xlsx",
        header=None,
    )
    rows: list[dict] = []
    for i in range(len(raw)):
        name = raw.iloc[i, 1]
        taken = raw.iloc[i, 4]
        done = raw.iloc[i, 5]
        if not isinstance(name, str) or len(name) < 8 or name == "Наименование работ":
            continue
        if pd.isna(taken) and pd.isna(done):
            continue
        rows.append({"Показатель": name.strip(), "Взято": taken, "Выполнено": done})
    return pd.DataFrame(rows)


def sender_bucket(org: str) -> str:
    s = str(org or "")
    for pat, label in [
        (r"пробац", "Служба пробации"),
        (r"Прокур", "Прокуратура"),
        (r"полици", "Полиция (ОВД)"),
        (r"Центр поддержки|Отбасын", "Сам ЦПС"),
        (r"больниц|амбулатор|здрав", "Здравоохранение"),
        (r"образован|школ", "Образование"),
    ]:
        if re.search(pat, s, re.I):
            return label
    return "Прочие"


def main() -> Path:
    j = clean_journal(
        CPS
        / "Отчет 'Журнал регистрации обращений' от 09.09.2026 12;27;30 (с 01.01.26 по 09.09.26).xlsx"
    )
    ipr = load_ipr()
    proto = pd.read_excel(
        CPS
        / "Отчет 'Протокол выезда' от 09.09.2026 12;28;57 (с 01.01.26 00;00 по 09.09.26 12;28).xlsx",
        header=2,
    )
    proto = proto[pd.to_numeric(proto["№ пп"], errors="coerce").notna()]
    work = load_work_report()

    j["micro"] = j.apply(micro_district, axis=1)
    j["отправитель_группа"] = j["Наименование организации отправителя"].apply(sender_bucket)
    tzs_mask = j["Тип обращения"].astype(str).str.contains("ТЖС|выявление", case=False, na=False)

    summary = [
        ("Период обращений", "01.01.2026 – 09.09.2026"),
        ("Период ИПР", "01.01.2025 – 09.09.2026"),
        ("Обращений (уник. №)", j["№ обращения"].nunique()),
        ("Строк в журнале (с дублями шаблона)", len(j)),
        ("ТЖС / выявление", int(tzs_mask.sum())),
        ("ТЖС без ИИН", int(j[tzs_mask]["iin"].isna().sum())),
        ("ИПР: семей (ИИН)", ipr["iin"].nunique()),
        ("ИПР: строк мер", len(ipr)),
        ("ИПР: мера «Иные»", int((ipr["Мера поддержки"] == "Иные").sum())),
        ("Выезды мобгруппы", len(proto)),
        ("Выезды без времени приезда", int(proto["Дата/время приезда"].isna().sum())),
    ]
    if SUICIDE_X.exists():
        sv = pd.read_excel(SUICIDE_X, sheet_name="Сводка")
        for _, r in sv.dropna(subset=["Показатель"]).iterrows():
            if "ЛИЦА: НЕ в ЦПС" in str(r["Показатель"]):
                summary.append(("Суицид: лиц без ЦПС", r["Значение"]))
            if "ЛИЦА: обращались" in str(r["Показатель"]):
                summary.append(("Суицид: лиц с ЦПС", r["Значение"]))

    summary_df = pd.DataFrame(summary, columns=["Показатель", "Значение"])

    by_micro = (
        j.groupby("micro")
        .agg(
            обращений=("№ обращения", "count"),
            уник_номеров=("№ обращения", "nunique"),
            с_ИИН=("iin", lambda s: s.notna().sum()),
            комплексных=("Признак обращения", lambda s: s.astype(str).str.contains("Комплекс").sum()),
        )
        .reset_index()
        .sort_values("обращений", ascending=False)
    )

    by_source = j["Источник информации:Организация/физ лицо/ само лицо в ТЖС"].value_counts().reset_index()
    by_source.columns = ["Источник", "Кол-во"]

    by_sender = (
        j.groupby("отправитель_группа")
        .size()
        .reset_index(name="обращений")
        .sort_values("обращений", ascending=False)
    )

    staff = (
        j.groupby(["Принял обращение: ФИО", "Принял обращение: Должность"])
        .size()
        .reset_index(name="обращений")
        .sort_values("обращений", ascending=False)
    )

    ipr_org = ipr["Организация исполнитель"].astype(str).str[:80].value_counts().reset_index()
    ipr_org.columns = ["Организация", "мер"]

    ipr_meas = ipr["Мера поддержки"].value_counts().reset_index()
    ipr_meas.columns = ["Мера", "Кол-во"]

    ipr_resp = (
        ipr["Ответственный по сопровождению\u00a0семьи"]
        .value_counts()
        .reset_index()
    )
    ipr_resp.columns = ["Ответственный", "мер"]

    proto_staff = (
        proto["ФИО исполнителя (из моб группы)"].value_counts().reset_index()
    )
    proto_staff.columns = ["Исполнитель выезда", "выездов"]

    res = j["Результат"].fillna("").astype(str)
    flags = pd.DataFrame(
        {
            "№ обращения": j["№ обращения"],
            "Дата": j["Дата"],
            "ФИО": j["ФИО (при его наличии)"],
            "micro": j["micro"],
            "отправитель": j["отправитель_группа"],
            "Причина": j["Причина обращения"],
            "Результат": j["Результат"],
            "консультация_или_отказ": res.str.contains(
                "консультац|кеңес|не нужда", case=False, regex=True
            ),
            "бордовая_зона_ЦКС": res.str.contains("бордов", case=False),
        }
    )

    sheets = {
        "Сводка": summary_df,
        "Нарушения_и_нормы": NORMATIVE,
        "По_населенным_пунктам": by_micro,
        "Источники_обращений": by_source,
        "Кто_направил": by_sender,
        "Кто_принял": staff,
        "ИПР_организации": ipr_org,
        "ИПР_меры": ipr_meas,
        "ИПР_ответственные": ipr_resp,
        "Мобгруппа_исполнители": proto_staff,
        "Отчет_работа_ЦПС": work,
        "Рисковые_итоги": flags[flags["консультация_или_отказ"] | flags["бордовая_зона_ЦКС"]],
        "Все_обращения": j,
        "ИПР_строки": ipr,
        "Протоколы_выезда": proto,
    }

    if SUICIDE_X.exists():
        for sh in ("Сводка", "Без обращения в ЦПС", "Детали ЦПС (найденные)"):
            try:
                sheets[f"Суицид_{sh[:20]}"] = pd.read_excel(SUICIDE_X, sheet_name=sh)
            except Exception:
                pass

    with pd.ExcelWriter(OUT, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name[:31], index=False)

    print(f"Записано: {OUT}")
    print(summary_df.to_string(index=False))
    return OUT


if __name__ == "__main__":
    main()
