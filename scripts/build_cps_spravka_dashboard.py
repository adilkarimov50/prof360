#!/usr/bin/env python3
"""Интерактивная справка ЦПС: дашборд, нормы с диспозицией, списки лиц, вопросы."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CPS = ROOT / "ЦПС"
OUT_DIR = ROOT / "passports" / "docs" / "spravka_cps"
OUT_HTML = OUT_DIR / "spravka.html"
SUICIDE_X = ROOT / "Суицид_F00-99_ЦПС_сверка.xlsx"
ANALYSIS = CPS / "ЦПС_полный_анализ.xlsx"

# Проверенные ссылки (doc_id из локальной библиотеки / adilet)
LINKS = {
    "Z2500000245": "https://adilkarimov50.github.io/krim-passport/legal_read.html?doc=Z2500000245",
    "K1100000518": "https://adilkarimov50.github.io/krim-passport/legal_read.html?doc=K1100000518",
    "V2400034499": "https://adilet.zan.kz/rus/docs/V2400034499",
    "K2300000224": "https://adilet.zan.kz/rus/docs/K2300000224",
}

VIOLATIONS = [
    {
        "id": "accounting",
        "title": "Ненадлежащий учёт лиц в ТЖС",
        "fact": "405 из 457 обращений по ТЖС без ИИН; 37 строк-шаблонов в журнале.",
        "norms": [
            {
                "cite": "Закон РК «О профилактике правонарушений» (Z2500000245), ст. 54, п. 1",
                "url": LINKS["Z2500000245"],
                "text": "Учет лиц (семей), находящихся в трудной жизненной ситуации, осуществляется центрами поддержки семьи для информационного обеспечения деятельности заинтересованных государственных органов.",
            },
            {
                "cite": "Правила деятельности ЦПС (приказ №256-НҚ, V2400034499), п. 13, пп. 2–3",
                "url": LINKS["V2400034499"],
                "text": "Первичная оценка лица (семьи) для определения трудной жизненной ситуации и выработки мер реагирования — в течение трёх рабочих дней (при угрозе жизни и здоровью — один рабочий день). "
                "Определяются потребности для составления индивидуального плана работы для лиц, признанных находящимися в ТЖС.",
            },
        ],
        "people_key": "no_iin",
    },
    {
        "id": "coordination",
        "title": "Подмена координации «самообслуживанием» ЦПС",
        "fact": "97% мер ИПР исполняет сам ЦПС; образование 0 исполнено; соцзащита 0.",
        "norms": [
            {
                "cite": "Кодекс «О браке (супружестве) и семье» (K1100000518), ст. 5-1, п. 2, пп. 2 и 8",
                "url": LINKS["K1100000518"],
                "text": "Центры поддержки семьи осуществляют координацию работы по охвату поддержкой лиц (семей), оказавшихся в трудной жизненной ситуации, государственными органами в пределах своей компетенции, "
                "в том числе посредством интегрированной модели; организуют работу мобильных групп при участии органов образования, здравоохранения, внутренних дел.",
            },
            {
                "cite": "Закон о профилактике правонарушений, ст. 10, п. 2, пп. 2 и 8",
                "url": LINKS["Z2500000245"],
                "text": "Аналогичная компетенция ЦПС: координация поддержки и организация мобильных групп с участием образования, здравоохранения, внутренних дел.",
            },
            {
                "cite": "Правила ЦПС, п. 15 и 18",
                "url": LINKS["V2400034499"],
                "text": "К разработке индивидуального плана привлекаются юристы, психологи, медработники, социальные работники, сотрудники местных полицейских служб, НПО. "
                "Координация охвата поддержкой осуществляется согласно Социальному кодексу.",
            },
        ],
        "people_key": "ipr_inye",
    },
    {
        "id": "ipr_formal",
        "title": "Формальный ИПР без конкретных мер",
        "fact": "428 из 650 строк ИПР — мера «Иные» без расшифровки; 37 семей с несколькими родительскими заданиями.",
        "norms": [
            {
                "cite": "Закон о профилактике правонарушений, ст. 55, п. 1",
                "url": LINKS["Z2500000245"],
                "text": "Организация социальной адаптации и реабилитации лиц (семей), находящихся в трудной жизненной ситуации, осуществляется в соответствии с индивидуальным планом помощи "
                "лицу (семье), находящемуся (находящейся) в трудной жизненной ситуации, уполномоченными субъектами профилактики правонарушений.",
            },
            {
                "cite": "Правила ЦПС, п. 16–17",
                "url": LINKS["V2400034499"],
                "text": "Мероприятия ИПР указываются раздельно по каждому виду государственной поддержки; каждое мероприятие содержит сроки. ИПР подписывается сотрудником Центра и семьёй и утверждается руководителем.",
            },
        ],
        "people_key": "ipr_inye",
    },
    {
        "id": "probation",
        "title": "Свод помощи к консультации по направлениям пробации",
        "fact": "218 направлений от службы пробации; 181 (83%) закрыты консультацией или отказом «не нуждается».",
        "norms": [
            {
                "cite": "Правила ЦПС, п. 12, пп. 4 и п. 14",
                "url": LINKS["V2400034499"],
                "text": "Помощь оказывается при получении информации от государственных органов. Проводится первичная оценка и определение потребностей для ИПР — не ограничивается разовой консультацией.",
            },
            {
                "cite": "Закон о профилактике, ст. 55, п. 1",
                "url": LINKS["Z2500000245"],
                "text": "Социальная адаптация и реабилитация — по индивидуальному плану с участием уполномоченных субъектов профилактики.",
            },
        ],
        "people_key": "probation",
    },
    {
        "id": "red_cks",
        "title": "Семьи «бордовой зоны» ЦКС без комплексного плана",
        "fact": "66 обращений: в результате повторяется формулировка причины без перечня межведомственных мер.",
        "norms": [
            {
                "cite": "Закон о профилактике, ст. 72, п. 2 (абзац 2–3)",
                "url": LINKS["Z2500000245"],
                "text": "Сведения о лицах (семьях) в ТЖС направляются в центры поддержки семьи, где им оказывается содействие в оказании социальной, юридической и психологической поддержки. "
                "Потерпевшим от бытового насилия предоставляется возможность получения специальных социальных услуг или психологической помощи, в том числе временного проживания до одного месяца.",
            },
            {
                "cite": "Кодекс о браке, ст. 5-1, п. 2, п. 4",
                "url": LINKS["K1100000518"],
                "text": "Оказание поддержки лицам с признаками бытового насилия с возможностью их временного проживания сроком до одного месяца.",
            },
        ],
        "people_key": "red_cks",
    },
    {
        "id": "mobile",
        "title": "Мобильная группа: состав и протоколы",
        "fact": "271 из 276 выездов без времени приезда; в протоколах — только сотрудники ЦПС.",
        "norms": [
            {
                "cite": "Закон о профилактике, ст. 11, п. 1–2",
                "url": LINKS["Z2500000245"],
                "text": "Мобильные группы осуществляют меры по раннему выявлению и организации поддержки; информируют правоохранительные органы о фактах насилия.",
            },
            {
                "cite": "Правила ЦПС, п. 21–22",
                "url": LINKS["V2400034499"],
                "text": "В состав мобильных групп входят представители органов образования, здравоохранения, внутренних дел; состав утверждается распоряжением акима. "
                "При угрозе жизни и здоровью Центры привлекают МГ для мер незамедлительного реагирования с указанием ответственных органов.",
            },
        ],
        "people_key": "mobile",
    },
    {
        "id": "violence",
        "title": "Насилие / алкоголь / риск — без спецуслуг",
        "fact": "По отчёту ЦПС: 0 спецсоциальных услуг, 0 временного проживания; пример: POLVANOVA — пустой результат.",
        "norms": [
            {
                "cite": "Правила ЦПС, п. 23–25",
                "url": LINKS["V2400034499"],
                "text": "Меры поддержки при бытовом насилии: информационная, юридическая, психологическая помощь, медпомощь, временное проживание до одного месяца.",
            },
            {
                "cite": "Закон о профилактике, ст. 72, п. 3, п. 1",
                "url": LINKS["Z2500000245"],
                "text": "Органы внутренних дел принимают правовые меры оперативного реагирования по каждому сообщению о факте бытового насилия.",
            },
        ],
        "people_key": "violence",
    },
    {
        "id": "suicide",
        "title": "Неохват лиц группы суицидального риска",
        "fact": "596 из 598 лиц с суицидом не отражены в ЦПС; 14 с F00–99 + суицид — 0 обращений.",
        "norms": [
            {
                "cite": "Закон о профилактике, ст. 54, п. 1",
                "url": LINKS["Z2500000245"],
                "text": "Учёт лиц (семей) в ТЖС — в центрах поддержки семьи для информационного обеспечения заинтересованных органов.",
            },
            {
                "cite": "Закон о профилактике, ст. 72, п. 4",
                "url": LINKS["Z2500000245"],
                "text": "Раз в полугодие на МВК «Закон и порядок» даётся оценка эффективности раннего выявления и организации поддержки лиц (семей) в ТЖС.",
            },
        ],
        "people_key": "suicide_no",
    },
    {
        "id": "reporting",
        "title": "Достоверность отчётности ИС",
        "fact": "Отчёт: служба пробации — 7 «взято» / 310 «исполнено»; 59 ТЖС не закрыты при 456 «взято».",
        "norms": [
            {
                "cite": "Правила ЦПС, п. 9 (подразделение по методологии)",
                "url": LINKS["V2400034499"],
                "text": "Осуществляется составление аналитических записок и отчётов, мониторинг эффективности оказываемой помощи.",
            },
        ],
        "people_key": None,
    },
]

QUESTIONS = [
    "Почему 405 обращений в ТЖС зарегистрированы без ИИН и как обеспечивается учёт по ст. 54 Закона о профилактике?",
    "Какими документами (приказ/распоряжение акима) утверждён состав мобильной группы с участием ОВД, здравоохранения и образования? Почему в протоколах выезда 98% записей без времени приезда?",
    "Почему 97% мер ИПР исполняет сам ЦПС без привлечения карьерного центра, ОВД, медорганизаций — в нарушение ст. 5-1 Кодекса о браке и ст. 10 Закона о профилактике?",
    "По какому основанию 181 из 218 направлений службы пробации закрыты формулировкой «консультация / не нуждается» без ИПР?",
    "Что конкретно сделано по 66 семьям «бордовой зоны» ЦКС? Где акты выезда МГ, направления в спецуслуги, уведомления ОВД?",
    "Почему по отчёту за 2026 год — 0 спецсоциальных услуг и 0 случаев временного проживания при п. 23–25 Правил ЦПС?",
    "Как объяснить отсутствие в ЦПС 596 лиц из реестра суицида? Какие меры взаимодействия с ОВД и ПН-службами?",
    "Как согласовать показатель «пробация 310 исполнено» при «7 взято»? Кто ответственен за достоверность FSM Social?",
    "Когда последний раз на МВК «Закон и порядок» докладывалась эффективность раннего выявления (ст. 72, п. 4)? Какие решения приняты по Карасайскому району?",
    "По семье КОВАЛЕВОЙ А.В. (суицид, ребёнок): направлены ли извещения в органы опеки в течение 24 часов (Правила ЦПС, п. 26)?",
]


def clean_field(val, default: str = "") -> str:
    """Пустые ячейки Excel/pandas → читаемый текст, не «nan»."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "<na>", "nat"):
        return default
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def clean_journal() -> pd.DataFrame:
    df = pd.read_excel(
        CPS
        / "Отчет 'Журнал регистрации обращений' от 09.09.2026 12;27;30 (с 01.01.26 по 09.09.26).xlsx",
        header=2,
    )
    df.columns = [str(c).strip().replace("\n", " ") for c in df.columns]
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")], errors="ignore")
    df = df[pd.to_numeric(df["№ обращения"], errors="coerce").notna()].copy()
    df["№ обращения"] = df["№ обращения"].astype(int)
    return df


def row_person(r, extra=None) -> dict:
    iin_raw = r.get("ИИН")
    iin = clean_field(iin_raw, "не указан")
    if iin != "не указан" and len(re.sub(r"\D", "", iin)) != 12:
        iin = "не указан"
    result = clean_field(r.get("Результат"), "не заполнено")
    d = {
        "id": int(r["№ обращения"]) if "№ обращения" in r and pd.notna(r["№ обращения"]) else None,
        "fio": clean_field(r.get("ФИО (при его наличии)"), "—")[:120],
        "date": clean_field(r.get("Дата"), "—")[:20],
        "reason": clean_field(r.get("Причина обращения"), "—")[:300],
        "result": result[:300],
        "sender": clean_field(r.get("Наименование организации отправителя"), "—")[:120],
        "address": clean_field(r.get("Адрес проживания"), "—")[:120],
        "iin": iin[:12],
    }
    if extra:
        d.update(extra)
    return d


def collect_people(j: pd.DataFrame) -> dict:
    res = j["Результат"].fillna("").astype(str)
    tzs = j["Тип обращения"].astype(str).str.contains("ТЖС|выявление", case=False, na=False)

    people = {
        "probation": [
            row_person(r)
            for _, r in j[
                j["Наименование организации отправителя"].astype(str).str.contains("пробац", case=False)
            ].head(80).iterrows()
        ],
        "red_cks": [row_person(r) for _, r in j[res.str.contains("бордов", case=False)].head(80).iterrows()],
        "no_iin": [row_person(r) for _, r in j[tzs & j["ИИН"].isna()].head(80).iterrows()],
        "violence": [
            row_person(r)
            for _, r in j[
                j["Причина обращения"].astype(str).str.contains(
                    "насил|алкогол|злоупотреб|суицид|угроз", case=False, regex=True
                )
            ].head(40).iterrows()
        ],
        "consult_only": [
            row_person(r)
            for _, r in j[res.str.contains("консультац|кеңес|не нужда", case=False, regex=True)].head(60).iterrows()
        ],
    }

    proto = pd.read_excel(
        CPS
        / "Отчет 'Протокол выезда' от 09.09.2026 12;28;57 (с 01.01.26 00;00 по 09.09.26 12;28).xlsx",
        header=2,
    )
    proto = proto[pd.to_numeric(proto["№ пп"], errors="coerce").notna()]
    people["mobile"] = [
        {
            "id": clean_field(r.get("Номер родительского задания"), "—"),
            "fio": clean_field(r.iloc[-1], "—")[:120],
            "date": clean_field(r.get("Дата/время отъезда"), "—")[:24],
            "reason": clean_field(r.get("ФИО исполнителя (из моб группы)", ""), "—")[:80],
            "result": "Нет времени приезда" if pd.isna(r.get("Дата/время приезда")) else "Есть приезд",
            "sender": clean_field(r.get("Организация исполнителя (из моб группы)"), "—")[:80],
            "address": "",
            "iin": "—",
        }
        for _, r in proto[proto["Дата/время приезда"].isna()].head(60).iterrows()
    ]

    ipr = pd.read_excel(
        CPS / "ИПР семьи' от 09.09.2026 12;29;30 (с 01.01.25 по 09.09.26).xlsx",
        header=2,
    )
    ipr = ipr[ipr["Мера поддержки"] == "Иные"].head(60)
    people["ipr_inye"] = [
        {
            "id": str(r.get("Номер родительского задания", "")),
            "fio": str(r.get("Члены семьи", ""))[:80],
            "date": str(r.get("Дата утверждения", ""))[:20],
            "reason": "ИПР: мера «Иные»",
            "result": str(r.get("Результат", ""))[:200],
            "sender": str(r.get("Организация исполнитель", ""))[:80],
            "address": str(r.get("Ответственный по сопровождению\u00a0семьи", ""))[:60],
            "iin": "",
        }
        for _, r in ipr.iterrows()
    ]

    if SUICIDE_X.exists():
        no = pd.read_excel(SUICIDE_X, sheet_name="Без обращения в ЦПС").head(100)
        people["suicide_no"] = [
            {
                "id": None,
                "fio": str(r.get("ФИО", ""))[:80],
                "date": "",
                "reason": str(r.get("Специфика", ""))[:120],
                "result": f"Случаев: {r.get('Случаев_суицида', '')}",
                "sender": str(r.get("Тип_суицида", ""))[:40],
                "address": "",
                "iin": str(r.get("ИИН", "")).replace(".0", "")[:12],
            }
            for _, r in no.iterrows()
        ]
        found = pd.read_excel(SUICIDE_X, sheet_name="Детали ЦПС (найденные)")
        people["suicide_found"] = [
            {
                "id": r.get("№_обращения"),
                "fio": str(r.get("ФИО_суицид", ""))[:80],
                "date": str(r.get("Дата", ""))[:20],
                "reason": str(r.get("Причина", ""))[:200],
                "result": str(r.get("Помощь_оказана", ""))[:120],
                "sender": str(r.get("Источник_инфо", ""))[:80],
                "address": "",
                "iin": str(r.get("ИИН", "")).replace(".0", "")[:12],
            }
            for _, r in found.iterrows()
        ]
    return people


def kpi() -> dict:
    summary = pd.read_excel(ANALYSIS, sheet_name="Сводка")
    d = dict(zip(summary["Показатель"], summary["Значение"]))
    out: dict = {}
    for k in d:
        v = d[k]
        if pd.isna(v):
            continue
        if isinstance(v, float) and v == int(v):
            v = int(v)
        out[str(k)] = v
    return out


def render_html(kpi_data: dict, people: dict, violations: list, questions: list) -> str:
    data_json = json.dumps(
        {"kpi": kpi_data, "people": people, "violations": violations, "questions": questions},
        ensure_ascii=False,
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Справка ЦПС Карасайский район — дашборд</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Literata:opsz,wght@7..72,600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#f0f3f8;--card:#fff;--ink:#1a2332;--muted:#5a6578;--line:#d8dee8;--accent:#164a8c;--warn:#b83220;--ok:#18794e;--sidebar:260px}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Source Sans 3',system-ui,sans-serif;background:var(--bg);color:var(--ink);line-height:1.55;font-size:15px}}
.layout{{display:flex;min-height:100vh}}
aside{{width:var(--sidebar);background:#0f1f3d;color:#fff;padding:20px 16px;flex:none;position:sticky;top:0;height:100vh;overflow-y:auto}}
aside h1{{font-family:Literata,Georgia,serif;font-size:1.05rem;line-height:1.35;margin-bottom:16px;font-weight:600}}
aside nav button{{display:block;width:100%;text-align:left;background:transparent;border:none;color:rgba(255,255,255,.85);padding:10px 12px;border-radius:6px;cursor:pointer;font-size:14px;margin-bottom:4px}}
aside nav button:hover,aside nav button.active{{background:rgba(255,255,255,.12);color:#fff}}
main{{flex:1;padding:24px 28px 48px;max-width:1100px}}
.panel{{display:none}}
.panel.active{{display:block}}
.hero{{background:linear-gradient(135deg,#164a8c,#2a6cb8);color:#fff;border-radius:12px;padding:24px 28px;margin-bottom:24px}}
.hero p{{opacity:.92;margin-top:8px;font-size:14px}}
.kpi{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin:20px 0}}
.kpi .c{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;text-align:center}}
.kpi .v{{font-size:1.5rem;font-weight:700;color:var(--accent)}}
.kpi .l{{font-size:11px;color:var(--muted);text-transform:uppercase;margin-top:4px}}
h2{{font-family:Literata,Georgia,serif;font-size:1.35rem;color:var(--accent);margin:28px 0 14px}}
h3{{font-size:1.05rem;margin:18px 0 10px}}
.conclusion{{background:#fff8e6;border:1px solid #e8d4a8;border-radius:10px;padding:20px 22px;margin:20px 0}}
.conclusion ol{{margin:12px 0 0 20px}}
.violation{{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:20px;overflow:hidden}}
.violation-head{{padding:16px 20px;background:#f8fafc;border-bottom:1px solid var(--line);cursor:pointer;display:flex;justify-content:space-between;align-items:flex-start;gap:12px}}
.violation-head h3{{margin:0;font-size:1rem;color:var(--warn)}}
.violation-body{{padding:16px 20px;display:none}}
.violation.open .violation-body{{display:block}}
.norm{{background:#f4f8fc;border-left:4px solid var(--accent);padding:12px 16px;margin:12px 0;border-radius:0 8px 8px 0;font-size:14px}}
.norm cite{{display:block;font-weight:600;font-style:normal;margin-bottom:6px;font-size:13px}}
.norm a{{color:var(--accent);font-size:13px}}
.norm blockquote{{margin:8px 0 0;color:var(--ink)}}
.fact{{font-size:14px;color:var(--muted);margin-bottom:12px}}
.toolbar{{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 16px;align-items:center}}
.toolbar input{{padding:8px 12px;border:1px solid var(--line);border-radius:8px;min-width:220px;font-size:14px}}
.toolbar select{{padding:8px 12px;border:1px solid var(--line);border-radius:8px;font-size:14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);border-radius:8px;overflow:hidden;border:1px solid var(--line)}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:#eef2f7;font-size:11px;text-transform:uppercase;color:var(--muted);position:sticky;top:0}}
.scroll{{max-height:420px;overflow:auto;border-radius:8px;border:1px solid var(--line)}}
.q{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 18px;margin-bottom:10px;font-size:15px}}
.q strong{{color:var(--accent)}}
.note{{font-size:13px;color:var(--muted);margin-top:16px}}
@media(max-width:900px){{.layout{{flex-direction:column}}aside{{width:100%;height:auto;position:relative}}}}
</style>
</head>
<body>
<div class="layout">
<aside>
<h1>ЦПС Карасайский район<br><span style="font-weight:400;font-size:13px;opacity:.8">аналитическая справка</span></h1>
<nav id="nav"></nav>
<p style="font-size:12px;opacity:.7;margin-top:20px">10.09.2026 · FSM Social</p>
</aside>
<main>
<section id="panel-summary" class="panel active"></section>
<section id="panel-violations" class="panel"></section>
<section id="panel-people" class="panel"></section>
<section id="panel-conclusion" class="panel"></section>
<section id="panel-questions" class="panel"></section>
<section id="panel-laws" class="panel"></section>
</main>
</div>
<script id="cps-data" type="application/json">{data_json}</script>
<script>
const DATA = JSON.parse(document.getElementById('cps-data').textContent);
const NAV = [
  {{id:'summary', label:'Сводка и KPI'}},
  {{id:'violations', label:'Нарушения и нормы'}},
  {{id:'people', label:'Реестр лиц'}},
  {{id:'conclusion', label:'Заключение'}},
  {{id:'questions', label:'Вопросы руководителю'}},
  {{id:'laws', label:'Ссылки на НПА'}},
];
const navEl = document.getElementById('nav');
NAV.forEach((n,i) => {{
  const b = document.createElement('button');
  b.textContent = n.label;
  b.dataset.panel = n.id;
  if(i===0) b.classList.add('active');
  b.onclick = () => showPanel(n.id, b);
  navEl.appendChild(b);
}});
function showPanel(id, btn) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-'+id).classList.add('active');
  document.querySelectorAll('aside nav button').forEach(b => b.classList.remove('active'));
  if(btn) btn.classList.add('active');
}}
function esc(s) {{
  if (s === null || s === undefined) return '—';
  const t = String(s).trim();
  if (!t || t.toLowerCase() === 'nan' || t === 'None') return '—';
  const d=document.createElement('div'); d.textContent=t; return d.innerHTML;
}}
function renderSummary() {{
  const k = DATA.kpi;
  const keys = ['Обращений (уник. №)','ТЖС без ИИН','ИПР: мера «Иные»','Выезды без времени приезда','Суицид: лиц без ЦПС','Суицид: лиц с ЦПС'];
  let cards = keys.map(key => {{
    const v = k[key] ?? '—';
    return `<div class="c"><div class="v">${{esc(String(v))}}</div><div class="l">${{esc(key)}}</div></div>`;
  }}).join('');
  document.getElementById('panel-summary').innerHTML = `
    <div class="hero"><h2 style="color:#fff;margin:0;font-family:Literata,serif">КГУ «Центр поддержки семьи»</h2>
    <p>Карасайский район · период обращений 01.01–09.09.2026 · ИПР с 01.01.2025</p></div>
    <div class="kpi">${{cards}}</div>
    <p class="note">Примечание: ранее ошибочно указывалась «ст. 1239» — в Законе о профилактике учёт ТЖС закреплён в <strong>ст. 54, п. 1</strong> (в тексте закона это строка 1239 файла, не номер статьи).</p>
    <h2>Источники</h2>
    <ul><li>Журнал обращений и журнал ТЖС (497 уник. №)</li><li>ИПР семей (577 ИИН)</li><li>Протоколы выезда (276)</li><li>Отчёт о работе</li><li><a href="ЦПС_полный_анализ.xlsx">ЦПС_полный_анализ.xlsx</a></li></ul>`;
}}
function renderViolations() {{
  let html = '<h2>Нарушения с диспозицией норм</h2><p class="note">Нажмите на блок — откроется список лиц по этой категории.</p>';
  DATA.violations.forEach(v => {{
    const norms = v.norms.map(n => `
      <div class="norm">
        <cite>${{esc(n.cite)}} — <a href="${{n.url}}" target="_blank" rel="noopener">открыть текст</a></cite>
        <blockquote>${{esc(n.text)}}</blockquote>
      </div>`).join('');
    const pk = v.people_key;
    const cnt = pk && DATA.people[pk] ? DATA.people[pk].length : 0;
    html += `<div class="violation" data-key="${{v.id}}">
      <div class="violation-head" onclick="this.parentElement.classList.toggle('open')">
        <h3>${{esc(v.title)}}</h3><span>${{cnt ? cnt+' пример(ов)' : '—'}}</span>
      </div>
      <div class="violation-body">
        <p class="fact"><strong>Факт:</strong> ${{esc(v.fact)}}</p>${{norms}}
        ${{pk ? renderPeopleTable(DATA.people[pk]||[], v.id) : ''}}
      </div></div>`;
  }});
  document.getElementById('panel-violations').innerHTML = html;
}}
function renderPeopleTable(rows, id) {{
  if(!rows.length) return '<p>Нет записей</p>';
  const head = '<tr><th>№/ID</th><th>ФИО</th><th>Дата</th><th>ИИН</th><th>Причина / источник</th><th>Результат</th></tr>';
  const body = rows.slice(0,40).map(r => `<tr>
    <td>${{esc(String(r.id||''))}}</td><td>${{esc(r.fio)}}</td><td>${{esc(r.date)}}</td><td>${{esc(r.iin)}}</td>
    <td>${{esc(r.reason)}}<br><small>${{esc(r.sender)}}</small></td><td>${{esc(r.result)}}</td></tr>`).join('');
  return `<div class="scroll"><table>${{head}}${{body}}</table></div>`;
}}
function renderPeople() {{
  const keys = Object.keys(DATA.people);
  let opts = keys.map(k => `<option value="${{k}}">${{k}} (${{DATA.people[k].length}})</option>`).join('');
  document.getElementById('panel-people').innerHTML = `
    <h2>Реестр лиц по категориям</h2>
    <div class="toolbar">
      <select id="cat">${{opts}}</select>
      <input id="search" placeholder="Поиск по ФИО, ИИН, причине…">
    </div>
    <div id="people-out"></div>`;
  const cat = document.getElementById('cat');
  const search = document.getElementById('search');
  function upd() {{
    const q = search.value.toLowerCase();
    let rows = DATA.people[cat.value]||[];
    if(q) rows = rows.filter(r => JSON.stringify(r).toLowerCase().includes(q));
    document.getElementById('people-out').innerHTML = renderPeopleTable(rows, 'all') + `<p class="note">Показано ${{Math.min(rows.length,40)}} из ${{rows.length}}</p>`;
  }}
  cat.onchange = upd; search.oninput = upd; upd();
}}
function renderConclusion() {{
  document.getElementById('panel-conclusion').innerHTML = `
    <h2>Заключение</h2>
    <div class="conclusion">
    <p>Деятельность КГУ «Центр поддержки семьи» Карасайского района по данным ИС FSM Social <strong>не обеспечивает</strong> закреплённую законом координацию межведомственной помощи лицам в трудной жизненной ситуации и не соответствует ряду требований Правил ЦПС (приказ №256-НҚ).</p>
    <ol>
      <li>Учёт ТЖС формальный: 89% карточек без ИИН (ст. 54, п. 1 Закона о профилактике).</li>
      <li>ИПР и «помощь» сводятся к консультации и мере «Иные» (ст. 55; Правила п. 15–16).</li>
      <li>Мобильная группа не документирована и фактически не межведомственна (ст. 11; Правила п. 21–22).</li>
      <li>Спецуслуги и временное проживание при насилии не оказывались (ст. 5-1 Кодекса о браке; ст. 72; Правила п. 23–25).</li>
      <li>Охват лиц суицидального риска — 2 из 598 (ст. 54; ст. 72, п. 4).</li>
      <li>Отчётность ИС содержит несостыковки (пробация 7/310).</li>
    </ol>
    <p style="margin-top:14px"><strong>Рекомендуется:</strong> прокурорская проверка, запрос распоряжения акима о составе МГ, материалов МВК «Закон и порядок», актов сверки с ОВД, ПН-службой и службой пробации; оценка служебной дисциплины руководства ЦПС.</p>
    </div>`;
}}
function renderQuestions() {{
  document.getElementById('panel-questions').innerHTML = '<h2>Вопросы руководителю ЦПС</h2>' +
    DATA.questions.map((q,i) => `<div class="q"><strong>${{i+1}}.</strong> ${{esc(q)}}</div>`).join('');
}}
function renderLaws() {{
  const seen = new Set();
  let blocks = '';
  DATA.violations.forEach(v => v.norms.forEach(n => {{
    if(seen.has(n.cite)) return;
    seen.add(n.cite);
    blocks += `<div class="norm"><cite>${{esc(n.cite)}}</cite><a href="${{n.url}}" target="_blank">${{n.url}}</a><blockquote>${{esc(n.text)}}</blockquote></div>`;
  }}));
  document.getElementById('panel-laws').innerHTML = '<h2>Нормативные акты (проверенные ссылки)</h2>' + blocks +
    `<div class="norm"><cite>Библиотека НПА (локальный сайт)</cite>
    <a href="https://adilkarimov50.github.io/krim-passport/prokuror_zakon.html">prokuror_zakon.html</a></div>`;
}}
renderSummary(); renderViolations(); renderPeople(); renderConclusion(); renderQuestions(); renderLaws();
</script>
</body>
</html>"""


def main() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    j = clean_journal()
    people = collect_people(j)
    html = render_html(kpi(), people, VIOLATIONS, QUESTIONS)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Written: {OUT_HTML}")
    return OUT_HTML


if __name__ == "__main__":
    main()
