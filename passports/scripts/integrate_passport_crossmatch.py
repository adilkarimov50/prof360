#!/usr/bin/env python3
"""Интеграция кримпаспортов Каскелен/Иргели со сверкой профучёта — новые связи и выводы."""

from __future__ import annotations

import io
import json
from datetime import date
from html import escape
from pathlib import Path

from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KARASAI = DATA / "karasai"
OUT_JSON = KARASAI / "integrated_analysis.json"
OUT_DIR = ROOT.parent / "Карасайский район"
OUT_HTML = OUT_DIR / "Справка_интегрированная_Каскелен_Иргели.html"
OUT_DOCX = OUT_DIR / "Справка_интегрированная_Каскелен_Иргели.docx"


def esc(t) -> str:
    return escape(str(t or ""))


def fmt(n) -> str:
    if isinstance(n, int):
        return f"{n:,}".replace(",", " ")
    return str(n)


def pct(part: int, whole: int) -> str:
    if not whole:
        return "0%"
    return f"{100 * part / whole:.1f}%"


def load(name: str) -> dict:
    return json.loads((KARASAI / name).read_text(encoding="utf-8"))


def build_integrated() -> dict:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from crossmatch_registry import classify_locality

    kask = json.loads((DATA / "kaskelen.json").read_text(encoding="utf-8"))
    irg = json.loads((DATA / "irgeli.json").read_text(encoding="utf-8"))
    report = load("report_ru.json")
    bundle = load("bundle.json")
    analysis = load("analysis.json")
    cross = load("registry_crossmatch.json")
    loc = cross["localities"]
    table = cross["table"]
    summary = cross["summary"]

    fk = report["prevention_funnel"]["kaskelen"]
    fi = report["prevention_funnel"]["irgeli"]

    # OVD типы по НП
    def ovd_types_for(locality_key: str) -> dict[str, int]:
        from collections import Counter
        c: Counter = Counter()
        for r in table:
            if not r.get("police_types") or r["police_types"] == "—":
                continue
            text = f"{r.get('settlement', '')} {r.get('address_residence', '')}"
            if classify_locality(text) == locality_key:
                for t in r["police_types"].split(", "):
                    c[t] += 1
        return dict(c.most_common())

    fraud_no_ovd = sum(1 for s in cross.get("suspect_no_police", []) if "190" in s.get("qual", ""))

    connections = [
        {
            "id": 1,
            "title": "Профучёт отстаёт от криминогенности",
            "kaskelen": f"Доля преступлений (место совершения) — {loc['crime_location']['kaskelen']['share']}, доля профучёта ОВД (проживание) — {loc['ovd_residence']['kaskelen']['share']}",
            "irgeli": f"Преступления — {loc['crime_location']['irgeli']['share']}, профучёт — {loc['ovd_residence']['irgeli']['share']}",
            "conclusion": "Каскелен генерирует в 2 раза большую долю преступлений, чем имеет долю в профучёте. Патрули и реестры «не догоняют» фактическую нагрузку.",
        },
        {
            "id": 2,
            "title": "Воронка профилактики «переворачивается» на админ. уровне",
            "kaskelen": f"Психиатрия {fk[0]['count']} → наркология {fk[1]['count']} → ОВД {fk[2]['count']} → ст.440 {fk[3]['count']}",
            "irgeli": f"Психиатрия {fi[0]['count']} → наркология {fi[1]['count']} → ОВД {fi[2]['count']} → ст.440 {fi[3]['count']}",
            "conclusion": "После ОВД число адм. правонарушений (ст.440) многократно превышает число состоящих на учёте. Сверка подтверждает: 2 106 мед. без ОВД, 414 подозреваемых без ОВД — учёт не «фильтрует» поток.",
        },
        {
            "id": 3,
            "title": "Мошенничество vs профучёт",
            "kaskelen": f"Паспорт: {kask['crime_structure'][0]['current'] if kask.get('crime_structure') else 554} преступлений, мошенничество ~54%; ЕРДР ст.190 — {bundle['erdr'].get('fraud_190', 617)}",
            "irgeli": "Иргели — кражи и объекты (Алтын Орда, Асыл Арман), не мошенничество",
            "conclusion": f"Из {summary['gap_crime_no_police']} подозреваемых вне профучёта — {fraud_no_ovd} по ст.190. Профучёт ОВД не охватывает «цифровую» преступность, хотя комиссия Q2 2026 сфокусирована на мошенничестве.",
        },
        {
            "id": 4,
            "title": "Hotspot ≠ адрес проживания",
            "kaskelen": f"ЕРДР: Abylai Khan {bundle['erdr'].get('hotspots_erdr', {}).get('abylay', 48)}; паспорт — алкообъекты и улица Абая",
            "irgeli": f"Алтын Орда: паспорт 88 vs ЕРДР {bundle['erdr'].get('hotspots_erdr', {}).get('altyn_orda', 26)}; дневной поток 80–90 тыс.",
            "conclusion": "Преступления концентрируются на объектах и в часы потока населения. Профучёт и особое требование привязаны к проживанию — «чужие» для рынка и ТЦ лица в реестрах не видны.",
        },
        {
            "id": 5,
            "title": "Наркологический учёт ОВД без медподтверждения",
            "kaskelen": f"Паспорт: {fk[2]['count']} на ОВД vs {fk[1]['count']} в наркологии; сверка: 14 с типом «нарк. ОВД» проживают в Каскелене",
            "irgeli": f"16 на ОВД vs 27 в наркологии; 284 алкообъекта",
            "conclusion": f"62 человека на «нарк. учёте ОВД» без записи в мед. списках (район). В Каскелене только {ovd_types_for('kaskelen').get('Наркологический учёт ОВД', 0)} — формальный учёт при массовых ст.440.",
        },
        {
            "id": 6,
            "title": "Тройной разрыв KPI",
            "kaskelen": "KPI комиссии: 0 из 10 заполнено",
            "irgeli": "KPI: 0; раскрываемость краж 48,3%",
            "conclusion": "Паспорт → комиссия → профучёт → KPI не замкнуты. Сверка 0 лиц с полным пересечением ОВД+мед+УД — системная, не локальная проблема.",
        },
        {
            "id": 7,
            "title": "Иргели: заниженный уровень преступности",
            "kaskelen": "—",
            "irgeli": f"Население паспорт {report['irgeli']['facts'][1]['value']} → реальный уровень ~51/10 тыс. (+46%)",
            "conclusion": "При дневном потоке 80–90 тыс. и 70,9% вечерних преступлений расчёт «на постоянное население» недооценивает риск. Профучёт 16 алкозлоупотребляющих vs 93 ст.440 — аналогичный разрыв, что и в Каскелене.",
        },
        {
            "id": 8,
            "title": "Несовершеннолетние: ст.442 vs учёт",
            "kaskelen": f"ст.442: {fk[4]['count']}; паспорт — 12 несовершеннолетних на учёте",
            "irgeli": f"ст.442: {fi[4]['count']}",
            "conclusion": "Массовые ночные нарушения (ст.442) не конвертируются в профучёт. Комиссия Q1/Q2 требует раннего учёта — данных об исполнении нет.",
        },
    ]

    locality_compare = []
    for source_key, label in (
        ("ovd_residence", "Профучёт ОВД (проживание)"),
        ("med_narco_residence", "Наркология (проживание)"),
        ("med_psych_residence", "Психиатрия (проживание)"),
        ("crime_location", "ЕРДР (место совершения)"),
        ("order_residence", "Особое треб./защитка"),
    ):
        for lk in ("kaskelen", "irgeli"):
            item = loc[source_key][lk]
            locality_compare.append({
                "source": label,
                "locality": item["label"],
                "count": item["count"],
                "district_total": item["district_total"],
                "share": item["share"],
            })

    passport_vs_data = [
        ["г. Каскелен", "Уголовные (паспорт / ЕРДР)", f"{kask['summary']['crimes']['current']} / {bundle['erdr']['kaskelen']}", "+28% в ЕРДР"],
        ["г. Каскелен", "ст.440 / профучёт ОВД", f"{fk[3]['count']} / {fk[2]['count']}", f"{fk[3]['count'] // max(fk[2]['count'], 1)}× больше нарушений, чем лиц на учёте"],
        ["г. Каскелен", "Мошенничество", f"~54% структуры / {bundle['erdr'].get('fraud_190', 617)} в ЕРДР", "Профучёт не охватывает"],
        ["Иргели", "Население / уровень", "63 152 → 34,3 vs 43 100 → 51,0", "+46% занижение уровня"],
        ["Иргели", "ст.440 / профучёт", f"{fi[3]['count']} / {fi[2]['count']}", "5,8×"],
        ["Иргели", "Алтын Орда (паспорт / ЕРДР)", "88 / 26", "Разные методики + поток населения"],
        ["Район", "ОВД + мед (сверка)", f"{summary['match_ovd_med']} из {summary['unique_persons']}", "1% пересечения"],
        ["Район", "ОВД + мед + УД", str(summary["match_all_three"]), "Полный разрыв цепочки"],
    ]

    conclusions = [
        "Кримпаспорт, комиссия и профучёт описывают одну проблему (алкоголь, несовершеннолетние, мошенничество), но данные не сходятся в единую цепочку «лицо → учёт → мера → результат».",
        f"Каскелен: {loc['crime_location']['kaskelen']['share']} преступлений района vs {loc['ovd_residence']['kaskelen']['share']} профучёта — профилактика недопокрывает главный генератор криминогенности.",
        "Иргели: заниженный уровень преступности из‑за базы населения и неучтённого дневного потока; объекты (Алтын Орда, Асыл Арман) — зоны риска без адресного профучёта посетителей.",
        "Сверка 3 236 лиц подтверждает паспортную воронку: медучёт → ОВД «обрывается» (93–99% разрыв), подозреваемые (96,7%) и мошенники вне реестров.",
        "Адресная логика: проживание (ОВД, мед) ≠ место преступления (ЕРДР) ≠ фабула. Без учёта мобильности и объектов патрулирование по маршрутам не закрывает фактические точки концентрации.",
        "KPI комиссии (0/10) + 0 полных пересечений ОВД+мед+УД = нарушение логики Закона 245-VIII ст.41–43: мониторинг есть на бумаге, контроля исполнения нет.",
    ]

    recommendations = [
        "Унифицировать базу населения (Каскелен: 87 023 / 84 199 / 89 000; Иргели: 63 152 vs 43 100 + модель дневного потока) до расчёта уровня и KPI.",
        "Ввести обязательный обмен ИИН: мед → ОВД (приказ №814 ↔ №163) и ЕРДР → профучёт — 414 подозреваемых вне учёта недопустимы.",
        "Каскелен: отдельный блок профилактики мошенничества (ст.190) — не только LED-экраны (комиссия Q2), но и учёт повторных потерпевших/подозреваемых.",
        "Иргели: объектный профучёт на Алтын Орде и Асыл Арман (рейды + видео + ст.440) с привязкой к месту, а не только к проживанию.",
        "Заполнить KPI комиссии количественными показателями: % снятых с медучёта, поставленных на ОВД; % раскрытия на объектах; число семей группы риска.",
        "Сопоставлять маршруты патрулей с ERDR hotspots (abylay 48, altyn_orda 26) и COVERAGE_GAPS — расширить вечернее покрытие под 74,7% ночных преступлений (Каскелен).",
    ]

    return {
        "meta": {
            "generated": date.today().isoformat(),
            "title": "Интегрированная справка: кримпаспорт + сверка профучёта",
            "localities": ["г. Каскелен", "Иргелинский с.о."],
            "sources_merged": [
                "kaskelen.json / irgeli.json",
                "report_ru.json / analysis.json / bundle.json",
                "registry_crossmatch.json",
            ],
        },
        "executive_summary": (
            "Объединение криминологических паспортов и person-level сверки 3 236 лиц выявило системный разрыв: "
            "паспорт фиксирует рост и концентрацию (мошенничество в Каскелене, объекты в Иргели), "
            "комиссия принимает решения без KPI, профучёт ОВД охватывает 3–15% тех, кто уже в медсписках и ЕРДР. "
            "Каскелен даёт 30,5% преступлений района при 15,4% профучёта. "
            "Иргели при реальной численности 43 100 имеет уровень ~51/10 тыс., а не 34,3. "
            "Ни одного лица с полным пересечением ОВД + мед + УД."
        ),
        "connections": connections,
        "locality_compare": locality_compare,
        "passport_vs_data": passport_vs_data,
        "funnel": {"kaskelen": fk, "irgeli": fi},
        "crossmatch_summary": summary,
        "conclusions": conclusions,
        "recommendations": recommendations,
    }


def table_html(headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def build_html(data: dict) -> str:
    today = date.today().strftime("%d.%m.%Y")
    conn_rows = [
        [str(c["id"]), esc(c["title"]), esc(c["kaskelen"]), esc(c["irgeli"]), esc(c["conclusion"])]
        for c in data["connections"]
    ]
    loc_rows = [
        [esc(r["source"]), esc(r["locality"]), fmt(r["count"]), fmt(r["district_total"]), esc(r["share"])]
        for r in data["locality_compare"]
    ]
    pvd_rows = [[esc(r[0]), esc(r[1]), esc(r[2]), esc(r[3])] for r in data["passport_vs_data"]]

    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Интегрированная справка · Каскелен и Иргели · 2026</title>
<link href="https://fonts.googleapis.com/css2?family=Literata:wght@400;600;700&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
<style>
body{{font-family:'Source Sans 3',sans-serif;background:#fafbfc;color:#1a1f2e;line-height:1.65;margin:0}}
.wrap{{max-width:920px;margin:0 auto;padding:40px 24px 80px}}
header{{background:linear-gradient(160deg,#0f1f3d,#1b4d8c);color:#fff;padding:48px 24px;margin:-40px -24px 32px}}
header h1{{font-family:Literata,serif;font-size:1.55rem;margin:0 0 8px}}
.lead{{background:#eef3fa;border-left:4px solid #1b4d8c;padding:16px 20px;margin:20px 0}}
h2{{font-family:Literata,serif;color:#1b4d8c;border-bottom:2px solid #dde2ea;padding-bottom:8px;margin:36px 0 16px}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin:16px 0}}
th,td{{padding:9px 11px;border-bottom:1px solid #dde2ea;text-align:left;vertical-align:top}}
th{{background:#f4f6f9;font-size:11px;text-transform:uppercase;color:#5c6578}}
.scroll{{overflow-x:auto}}
ol li{{margin:8px 0}}
.footer{{margin-top:40px;padding-top:20px;border-top:1px solid #dde2ea;font-size:14px}}
.footer a{{color:#1b4d8c}}
</style></head><body>
<div class="wrap">
<header>
  <div class="eyebrow" style="opacity:.8;font-size:12px;text-transform:uppercase">Карасайский район · интеграция данных</div>
  <h1>Интегрированная справка: криминологический паспорт + сверка профучёта</h1>
  <p style="opacity:.9;margin:0">г. Каскелен и Иргелинский с.о. · {today}</p>
</header>

<p class="lead">{esc(data['executive_summary'])}</p>

<h2>1. Скрытые логические связи (8 блоков)</h2>
<div class="scroll">{table_html(['№','Связь','Каскелен','Иргели','Вывод'], conn_rows)}</div>

<h2>2. Каскелен и Иргели — доли от районного числа</h2>
<p>Сравнение долей по источникам (проживание vs место преступления).</p>
<div class="scroll">{table_html(['Источник','Населённый пункт','Число','Всего','Доля'], loc_rows)}</div>

<h2>3. Паспорт «на бумаге» vs оперативные данные</h2>
<div class="scroll">{table_html(['НП','Показатель','Паспорт / данные','Эффект'], pvd_rows)}</div>

<h2>4. Воронка профилактики (из паспорта)</h2>
<h3>Каскелен</h3>
{table_html(['Этап','Число'], [[esc(x['stage']), fmt(x['count'])] for x in data['funnel']['kaskelen']])}
<h3>Иргели</h3>
{table_html(['Этап','Число'], [[esc(x['stage']), fmt(x['count'])] for x in data['funnel']['irgeli']])}

<h2>5. Сверка профучёта (район, person-level)</h2>
{table_html(['Показатель','Значение'], [
    ['Уникальных лиц', fmt(data['crossmatch_summary']['unique_persons'])],
    ['ОВД + мед', fmt(data['crossmatch_summary']['match_ovd_med'])],
    ['ОВД + УД', fmt(data['crossmatch_summary']['match_ovd_crime'])],
    ['ОВД + мед + УД', fmt(data['crossmatch_summary']['match_all_three'])],
    ['Мед без ОВД', fmt(data['crossmatch_summary']['gap_med_no_police'])],
    ['УД без ОВД', fmt(data['crossmatch_summary']['gap_crime_no_police'])],
])}

<h2>6. Выводы</h2>
<ol>{"".join(f"<li>{esc(c)}</li>" for c in data['conclusions'])}</ol>

<h2>7. Рекомендации</h2>
<ol>{"".join(f"<li>{esc(r)}</li>" for r in data['recommendations'])}</ol>

<div class="footer">
  <a href="Справка_сверка_профучета_ОВД.html">← Сверка профучёта ОВД</a> ·
  <a href="index_sverka_profueta.html">Оглавление</a>
</div>
</div></body></html>"""


def build_docx(data: dict) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    t = doc.add_paragraph()
    r = t.add_run(data["meta"]["title"])
    r.bold = True
    r.font.size = Pt(14)
    doc.add_paragraph(data["executive_summary"])
    doc.add_heading("1. Скрытые логические связи", level=1)
    tbl = doc.add_table(rows=1, cols=3)
    tbl.style = "Table Grid"
    for i, h in enumerate(("Связь", "Каскелен / Иргели", "Вывод")):
        tbl.rows[0].cells[i].text = h
    for c in data["connections"]:
        row = tbl.add_row().cells
        row[0].text = c["title"]
        row[1].text = f"К: {c['kaskelen']}\nИ: {c['irgeli']}"
        row[2].text = c["conclusion"]

    doc.add_heading("2. Доли Каскелен и Иргели", level=1)
    t2 = doc.add_table(rows=1, cols=5)
    t2.style = "Table Grid"
    for i, h in enumerate(("Источник", "НП", "Число", "Всего", "Доля")):
        t2.rows[0].cells[i].text = h
    for row in data["locality_compare"]:
        cells = t2.add_row().cells
        cells[0].text = row["source"]
        cells[1].text = row["locality"]
        cells[2].text = str(row["count"])
        cells[3].text = str(row["district_total"])
        cells[4].text = row["share"]

    doc.add_heading("3. Паспорт vs данные", level=1)
    t3 = doc.add_table(rows=1, cols=4)
    t3.style = "Table Grid"
    for i, h in enumerate(("НП", "Показатель", "Значения", "Эффект")):
        t3.rows[0].cells[i].text = h
    for row in data["passport_vs_data"]:
        cells = t3.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)

    doc.add_heading("4. Выводы", level=1)
    for c in data["conclusions"]:
        doc.add_paragraph(c, style="List Number")
    doc.add_heading("5. Рекомендации", level=1)
    for r in data["recommendations"]:
        doc.add_paragraph(r, style="List Number")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def main() -> None:
    data = build_integrated()
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(data), encoding="utf-8")
    docx = build_docx(data)
    OUT_DOCX.write_bytes(docx)
    print(f"Written {OUT_JSON}")
    print(f"Written {OUT_HTML}")
    print(f"Written {OUT_DOCX}")


if __name__ == "__main__":
    main()
