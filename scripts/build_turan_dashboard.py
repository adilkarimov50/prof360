#!/usr/bin/env python3
"""Дашборд «Туран» для кримпаспорта: публичные агрегаты + локальный оперативный файл."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parent.parent
OUT_PUBLIC = ROOT / "passports" / "docs" / "turan.html"
OUT_PRIVATE_DIR = ROOT / "passports" / "private"
OUT_PRIVATE = OUT_PRIVATE_DIR / "turan_operativ.html"
CROSSMATCH_XLSX = ROOT / "Туран_сверка_с_выгрузками.xlsx"

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "scoring-db"

PORTRAIT_RU = {
    "SYSTEMATIC_TRAFFIC_VIOLATOR": "Системный нарушитель КоАП",
    "POTENTIAL_DOMESTIC_AGGRESSOR": "Потенциальный семейно-бытовой агрессор",
    "PRONE_TO_OFFENSES": "Склонен к правонарушениям",
    "SEXUAL_OFFENSE_RISK": "Риск преступлений против половой неприкосновенности",
    "NO_PORTRAIT": "Портрет не определён",
}

METHOD_WEIGHTS = [
    ("ADM_NADZOR", "Административный надзор", "+1.5"),
    ("UNEMPLOYED", "Безработные", "+1.5"),
    ("NO_INCOME", "Не имеющие дохода", "+1.5"),
    ("PROTECTIVE_ORDER", "Защитное предписание", "+3"),
    ("PROBATION", "Пробация", "+3"),
    ("JDN_ACCOUNTING", "Учёт ИДН", "+2"),
    ("PEDOPHILE_LIST", "Список педофилов", "+4"),
    ("BZ_LIST", "Список БЗ", "−1"),
    ("IPN / ОСМС / пенсия / соцотчисления", "Снижающие факторы", "−0.2 каждый"),
]

IIN_RE = re.compile(r"\b\d{12}\b")
# ФИО: три слова кириллицей, каждое ≥3 букв (грубая эвристика для guard).
FIO_RE = re.compile(
    r"\b[А-ЯЁA-Z][а-яёa-z]{2,}\s+[А-ЯЁA-Z][а-яёa-z]{2,}\s+[А-ЯЁA-Z][а-яёa-z]{2,}\b"
)


def mongo_coll():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    return client, client[DB_NAME]["persons"]


def aggregate_mongo() -> dict:
    client, coll = mongo_coll()
    total = coll.estimated_document_count()

    def count_field(field: str) -> int:
        q = {field: {"$nin": [None, ""]}}
        return coll.count_documents(q)

    coverage = {
        "total": total,
        "iin": count_field("iin"),
        "fullName": count_field("fullName"),
        "district": count_field("district"),
        "birthDate": count_field("birthDate"),
        "gender": count_field("gender"),
        "scoring": count_field("scoring"),
    }

    districts = []
    for row in coll.aggregate(
        [
            {"$group": {"_id": "$district", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
            {"$limit": 25},
        ]
    ):
        label = row["_id"] if row["_id"] else "без района"
        districts.append({"district": str(label), "count": row["n"]})

    portraits = []
    for row in coll.aggregate(
        [
            {"$group": {"_id": "$primaryPortrait", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
        ]
    ):
        key = row["_id"] or "null"
        portraits.append(
            {
                "key": key,
                "label": PORTRAIT_RU.get(key, str(key)),
                "count": row["n"],
            }
        )

    risk_overlap = []
    for row in coll.aggregate(
        [
            {
                "$group": {
                    "_id": "$riskLevel",
                    "n": {"$sum": 1},
                    "minScore": {"$min": "$scoring"},
                    "maxScore": {"$max": "$scoring"},
                    "avgScore": {"$avg": "$scoring"},
                }
            },
            {"$sort": {"n": -1}},
        ]
    ):
        risk_overlap.append(
            {
                "riskLevel": row["_id"] or "null",
                "count": row["n"],
                "minScore": round(row["minScore"], 2) if row["minScore"] is not None else None,
                "maxScore": round(row["maxScore"], 2) if row["maxScore"] is not None else None,
                "avgScore": round(row["avgScore"], 2) if row["avgScore"] is not None else None,
            }
        )

    score_buckets = []
    pipeline = [
        {
            "$bucket": {
                "groupBy": "$scoring",
                "boundaries": [-100, 0, 3, 5, 8, 100],
                "default": "other",
                "output": {"count": {"$sum": 1}},
            }
        }
    ]
    labels = {
        -100: "< 0",
        0: "0 – <3 (низкий)",
        3: "3 – <5 (средний)",
        5: "5 – <8 (повышенный)",
        8: "≥8 (критический)",
        "other": "прочее",
    }
    for row in coll.aggregate(pipeline):
        key = row["_id"]
        score_buckets.append(
            {"bucket": labels.get(key, str(key)), "count": row["count"]}
        )

    client.close()
    return {
        "generated": date.today().isoformat(),
        "coverage": coverage,
        "districts": districts,
        "portraits": portraits,
        "risk_overlap": risk_overlap,
        "score_buckets": score_buckets,
        "method_weights": [{"code": a, "name": b, "weight": c} for a, b, c in METHOD_WEIGHTS],
        "risk_note": {
            "doc_thresholds": "<3 низкий · 3–5 средний · 5–8 повышенный · ≥8 критический (поле scoring)",
            "enum_thresholds": "0–9 GREEN · 10–15 YELLOW · 16–20 RED · 21+ BURGUNDY (поле riskLevel от портретного анализа)",
        },
    }


def load_crossmatch_summary() -> list[dict]:
    if not CROSSMATCH_XLSX.exists():
        return []
    df = pd.read_excel(CROSSMATCH_XLSX, sheet_name="Сводка")
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "source": str(r.get("источник", "")),
                "group": str(r.get("группа", "")),
                "total": int(r.get("всего", 0) or 0),
                "in_turan": int(r.get("в_туране", 0) or 0),
                "coverage_pct": float(r.get("покрытие_%", 0) or 0),
                "avg_score": float(r.get("средний_балл", 0) or 0),
            }
        )
    return rows


def load_operative_lists() -> dict:
    if not CROSSMATCH_XLSX.exists():
        return {"high_score": [], "with_portrait": [], "cps_portrait": []}

    def df_to_records(sheet: str, limit: int | None = None) -> list[dict]:
        df = pd.read_excel(CROSSMATCH_XLSX, sheet_name=sheet)
        if limit:
            df = df.head(limit)
        records = []
        for _, r in df.iterrows():
            records.append(
                {
                    "source": str(r.get("источник", "")),
                    "group": str(r.get("группа", "")),
                    "iin": str(r.get("iin", "")),
                    "fio_source": str(r.get("фио_источник", "")),
                    "fio_turan": str(r.get("фио_туран", "")),
                    "district": str(r.get("район", "")),
                    "score": r.get("балл"),
                    "risk_score": str(r.get("риск_по_баллу", "")),
                    "portrait": str(r.get("портрет", "")),
                }
            )
        return records

    high = df_to_records("Высокий_риск")
    portrait = df_to_records("С_портретом")
    cps = [
        r
        for r in portrait
        if "ЦПС" in r.get("source", "")
        and "Склонен" in r.get("portrait", "")
    ]
    return {"high_score": high, "with_portrait": portrait, "cps_portrait": cps}


def assert_no_pii_in_public(payload: dict, html: str) -> None:
    blob = json.dumps(payload, ensure_ascii=False) + html
    iins = IIN_RE.findall(blob)
    if iins:
        raise SystemExit(f"PII guard: найдено {len(iins)} ИИН в публичном turan.html")
    if FIO_RE.search(blob):
        raise SystemExit("PII guard: возможное ФИО в публичном turan.html")


def render_html(data: dict, *, operative: bool) -> str:
    public_data = {k: v for k, v in data.items() if k != "operative"}
    if operative:
        embed = data
    else:
        embed = public_data

    data_json = json.dumps(embed, ensure_ascii=False)
    nav_extra = ""
    panels_extra = ""
    render_extra = ""

    if operative:
        nav_extra = "{id:'operative', label:'Оперативные списки'},"
        panels_extra = '<section id="panel-operative" class="panel"></section>'
        render_extra = """
function renderOperative() {
  const o = DATA.operative || {};
  const mk = (title, rows) => {
    if(!rows || !rows.length) return `<h3>${esc(title)}</h3><p>Нет записей</p>`;
    const head = '<tr><th>Источник</th><th>Группа</th><th>ИИН</th><th>ФИО (источник)</th><th>ФИО (Туран)</th><th>Район</th><th>Балл</th><th>Риск</th><th>Портрет</th></tr>';
    const body = rows.slice(0,500).map(r => `<tr>
      <td>${esc(r.source)}</td><td>${esc(r.group)}</td><td class="mono">${esc(r.iin)}</td>
      <td>${esc(r.fio_source)}</td><td>${esc(r.fio_turan)}</td><td>${esc(r.district)}</td>
      <td>${esc(r.score)}</td><td>${esc(r.risk_score)}</td><td>${esc(r.portrait)}</td></tr>`).join('');
    return `<h3>${esc(title)} (${rows.length})</h3><div class="scroll"><table>${head}${body}</table></div>`;
  };
  document.getElementById('panel-operative').innerHTML = `
    <h2>Оперативные списки (локально)</h2>
    <p class="note">Не для публикации. Полный поиск — в локальном интерфейсе Туран (localhost:4300) и Excel «Туран_сверка_с_выгрузками.xlsx».</p>
    ${mk('Балл ≥ 5 (методика scoring)', o.high_score)}
    ${mk('С определённым портретом', o.with_portrait)}
    ${mk('ЦПС + портрет «склонен к правонарушениям»', o.cps_portrait)}`;
}
"""

    title_suffix = " — оператив" if operative else ""
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Туран (скоринг) · Алматинская область{title_suffix}</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Literata:opsz,wght@7..72,600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#f0f3f8;--card:#fff;--ink:#1a2332;--muted:#5a6578;--line:#d8dee8;--accent:#1a5c42;--warn:#b83220;--sidebar:260px}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Source Sans 3',system-ui,sans-serif;background:var(--bg);color:var(--ink);line-height:1.55;font-size:15px}}
.layout{{display:flex;min-height:100vh}}
aside{{width:var(--sidebar);background:#0d3326;color:#fff;padding:20px 16px;flex:none;position:sticky;top:0;height:100vh;overflow-y:auto}}
aside h1{{font-family:Literata,Georgia,serif;font-size:1.05rem;line-height:1.35;margin-bottom:16px;font-weight:600}}
aside nav button{{display:block;width:100%;text-align:left;background:transparent;border:none;color:rgba(255,255,255,.85);padding:10px 12px;border-radius:6px;cursor:pointer;font-size:14px;margin-bottom:4px}}
aside nav button:hover,aside nav button.active{{background:rgba(255,255,255,.12);color:#fff}}
main{{flex:1;padding:24px 28px 48px;max-width:1100px}}
.panel{{display:none}} .panel.active{{display:block}}
.hero{{background:linear-gradient(135deg,#1a5c42,#2d8a66);color:#fff;border-radius:12px;padding:24px 28px;margin-bottom:24px}}
.kpi{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin:20px 0}}
.kpi .c{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;text-align:center}}
.kpi .v{{font-size:1.35rem;font-weight:700;color:var(--accent)}}
.kpi .l{{font-size:11px;color:var(--muted);text-transform:uppercase;margin-top:4px}}
h2{{font-family:Literata,Georgia,serif;font-size:1.35rem;color:var(--accent);margin:28px 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:#eef2f7;font-size:11px;text-transform:uppercase;color:var(--muted)}}
.scroll{{max-height:480px;overflow:auto;border:1px solid var(--line);border-radius:8px;margin:12px 0}}
.note{{font-size:13px;color:var(--muted);margin:12px 0}}
.warn{{background:#fff4f2;border:1px solid #f0c4bc;border-radius:10px;padding:16px 18px;margin:16px 0}}
.mono{{font-family:ui-monospace,monospace;font-size:12px}}
@media(max-width:900px){{.layout{{flex-direction:column}}aside{{width:100%;height:auto;position:relative}}}}
</style>
</head>
<body>
<div class="layout">
<aside>
<h1>Туран<br><span style="font-weight:400;font-size:13px;opacity:.8">скоринг · профилактика</span></h1>
<nav id="nav"></nav>
<p style="font-size:12px;opacity:.7;margin-top:20px">{data.get("generated","")}</p>
</aside>
<main>
<section id="panel-summary" class="panel active"></section>
<section id="panel-districts" class="panel"></section>
<section id="panel-method" class="panel"></section>
<section id="panel-portraits" class="panel"></section>
<section id="panel-crossmatch" class="panel"></section>
<section id="panel-scales" class="panel"></section>
{panels_extra}
</main>
</div>
<script id="turan-data" type="application/json">{data_json}</script>
<script>
const DATA = JSON.parse(document.getElementById('turan-data').textContent);
const NAV = [
  {{id:'summary', label:'Охват и KPI'}},
  {{id:'districts', label:'Районы'}},
  {{id:'method', label:'Методика баллов'}},
  {{id:'portraits', label:'Портреты'}},
  {{id:'crossmatch', label:'Сверка с медучётом'}},
  {{id:'scales', label:'Две шкалы риска'}},
  {nav_extra}
];
const navEl = document.getElementById('nav');
NAV.forEach((n,i) => {{
  const b = document.createElement('button');
  b.textContent = n.label;
  if(i===0) b.classList.add('active');
  b.onclick = () => {{
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById('panel-'+n.id).classList.add('active');
    document.querySelectorAll('aside nav button').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
  }};
  navEl.appendChild(b);
}});
function esc(s) {{
  if (s === null || s === undefined) return '—';
  const t = String(s).trim();
  if (!t || t.toLowerCase() === 'nan') return '—';
  const d=document.createElement('div'); d.textContent=t; return d.innerHTML;
}}
function fmt(n) {{ return Number(n).toLocaleString('ru-RU'); }}
function renderSummary() {{
  const c = DATA.coverage;
  document.getElementById('panel-summary').innerHTML = `
    <div class="hero"><h2 style="color:#fff;margin:0;font-family:Literata,serif">Система скоринга «Туран»</h2>
    <p>Алматинская область · агрегированные показатели без персональных данных</p></div>
    <div class="kpi">
      <div class="c"><div class="v">${{fmt(c.total)}}</div><div class="l">Человек в базе</div></div>
      <div class="c"><div class="v">${{fmt(c.district)}}</div><div class="l">С районом</div></div>
      <div class="c"><div class="v">${{fmt(c.birthDate)}}</div><div class="l">Дата рождения</div></div>
      <div class="c"><div class="v">${{fmt(c.gender)}}</div><div class="l">Пол</div></div>
    </div>
    <p class="note">Локальный полный интерфейс: <code>http://localhost:4300</code> (после <code>docker compose up</code> в каталоге turan).</p>`;
}}
function renderDistricts() {{
  const rows = (DATA.districts||[]).map(r => `<tr><td>${{esc(r.district)}}</td><td>${{fmt(r.count)}}</td></tr>`).join('');
  document.getElementById('panel-districts').innerHTML = `<h2>Распределение по районам</h2>
    <div class="scroll"><table><thead><tr><th>Район</th><th>Число</th></tr></thead><tbody>${{rows}}</tbody></table></div>`;
}}
function renderMethod() {{
  const w = (DATA.method_weights||[]).map(r => `<tr><td>${{esc(r.code)}}</td><td>${{esc(r.name)}}</td><td>${{esc(r.weight)}}</td></tr>`).join('');
  const b = (DATA.score_buckets||[]).map(r => `<tr><td>${{esc(r.bucket)}}</td><td>${{fmt(r.count)}}</td></tr>`).join('');
  document.getElementById('panel-method').innerHTML = `<h2>Методика (поле scoring)</h2>
    <p class="note">${{esc(DATA.risk_note.doc_thresholds)}}</p>
    <h3>Примеры весов категорий</h3>
    <table><thead><tr><th>Код</th><th>Категория</th><th>Вес</th></tr></thead><tbody>${{w}}</tbody></table>
    <h3>Распределение по баллу</h3>
    <table><thead><tr><th>Диапазон</th><th>Число</th></tr></thead><tbody>${{b}}</tbody></table>`;
}}
function renderPortraits() {{
  const rows = (DATA.portraits||[]).filter(p => p.key !== 'NO_PORTRAIT' && p.key !== 'null')
    .map(r => `<tr><td>${{esc(r.label)}}</td><td>${{fmt(r.count)}}</td></tr>`).join('');
  document.getElementById('panel-portraits').innerHTML = `<h2>Поведенческие портреты</h2>
    <div class="scroll"><table><thead><tr><th>Портрет</th><th>Число</th></tr></thead><tbody>${{rows}}</tbody></table></div>`;
}}
function renderCrossmatch() {{
  const rows = (DATA.crossmatch||[]).map(r => `<tr>
    <td>${{esc(r.source)}}</td><td>${{esc(r.group)}}</td><td>${{fmt(r.total)}}</td>
    <td>${{fmt(r.in_turan)}}</td><td>${{esc(r.coverage_pct)}}%</td><td>${{esc(r.avg_score)}}</td></tr>`).join('');
  document.getElementById('panel-crossmatch').innerHTML = `<h2>Сверка с выгрузками диспучёта, ВИЧ/ТБ и ЦПС</h2>
    <p class="note">Только агрегаты по группам МКБ и источникам. Детали — в Excel «Туран_сверка_с_выгрузками.xlsx».</p>
    <div class="scroll"><table><thead><tr><th>Источник</th><th>Группа</th><th>Всего ИИН</th><th>В Туране</th><th>%</th><th>Ср. балл</th></tr></thead><tbody>${{rows}}</tbody></table></div>`;
}}
function renderScales() {{
  const rows = (DATA.risk_overlap||[]).map(r => `<tr>
    <td>${{esc(r.riskLevel)}}</td><td>${{fmt(r.count)}}</td>
    <td>${{esc(r.minScore)}}</td><td>${{esc(r.maxScore)}}</td><td>${{esc(r.avgScore)}}</td></tr>`).join('');
  document.getElementById('panel-scales').innerHTML = `
    <h2>Две шкалы риска</h2>
    <div class="warn"><strong>Важно:</strong> поле <code>riskLevel</code> в БД считается от суммы баллов <em>портретного</em> анализа, а не от <code>scoring</code>.
    Пороги enum: ${{esc(DATA.risk_note.enum_thresholds)}}. Для отбора по методике используйте <code>scoring</code>.</div>
    <table><thead><tr><th>riskLevel</th><th>Число</th><th>min scoring</th><th>max scoring</th><th>avg scoring</th></tr></thead><tbody>${{rows}}</tbody></table>`;
}}
{render_extra}
renderSummary(); renderDistricts(); renderMethod(); renderPortraits(); renderCrossmatch(); renderScales();
{"renderOperative();" if operative else ""}
</script>
</body>
</html>"""


def main() -> None:
    agg = aggregate_mongo()
    agg["crossmatch"] = load_crossmatch_summary()
    operative = load_operative_lists()

    public_html = render_html(agg, operative=False)
    assert_no_pii_in_public(agg, public_html)
    OUT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    OUT_PUBLIC.write_text(public_html, encoding="utf-8")
    print(f"Public: {OUT_PUBLIC}")

    private_payload = {**agg, "operative": operative}
    OUT_PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    private_html = render_html(private_payload, operative=True)
    OUT_PRIVATE.write_text(private_html, encoding="utf-8")
    print(f"Private: {OUT_PRIVATE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
