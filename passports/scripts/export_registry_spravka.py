#!/usr/bin/env python3
"""Справка о сверке профучёта ОВД — HTML и Word в отдельную папку."""

from __future__ import annotations

import io
import json
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "karasai" / "registry_crossmatch.json"
OUT_DIR = ROOT.parent / "Карасайский район"
SPRAVKA = OUT_DIR / "Справка_сверка_профучета_ОВД.html"
INDEX = OUT_DIR / "index_sverka_profueta.html"
DOCX = OUT_DIR / "Справка_сверка_профучета_ОВД.docx"
DOCS_MIRROR = ROOT / "docs" / "spravka_sverka_profueta"


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


def table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def report_sections(data: dict) -> dict:
    s = data["summary"]
    table_rows = data["table"]
    addr_links = data.get("addr_links", [])
    suspect_no = data.get("suspect_no_police", [])
    multi = data.get("multi_registry", [])

    status_cnt = Counter(r["status"] for r in table_rows)
    ovd_med = [r for r in table_rows if r["status"] == "СОВПАДЕНИЕ: ОВД + мед"]
    ovd_crime = [r for r in table_rows if "ОВД + уголовное" in r["status"]]
    ovd_no_med = [r for r in table_rows if r["status"] == "РАСХОЖДЕНИЕ: ОВД без мед."]
    med_gap = [r for r in table_rows if "мед. без ОВД" in r["status"] or "мед + УД, нет ОВД" in r["status"]]

    narco_total = sum(1 for r in table_rows if r["narco"] == "да")
    narco_in_police = sum(1 for r in table_rows if r["narco"] == "да" and r["police_types"] != "—")
    psych_total = sum(1 for r in table_rows if r["psych"] == "да")
    psych_in_police = sum(1 for r in table_rows if r["psych"] == "да" and r["police_types"] != "—")
    suspect_total = sum(1 for r in table_rows if r["suspect"] == "да")
    suspect_in_police = sum(1 for r in table_rows if r["suspect"] == "да" and r["police_types"] != "—")

    addr_kaskelen = [a for a in addr_links if a.get("locality") in ("kaskelen", "irgeli")]
    ovd_no_med_by_type = Counter(r["police_types"] for r in ovd_no_med)
    locality_table = data.get("locality_table", [])
    address_legend = data.get("address_legend", {})

    return {
        "s": s,
        "status_cnt": status_cnt,
        "ovd_med": ovd_med,
        "ovd_crime": ovd_crime,
        "ovd_no_med_by_type": ovd_no_med_by_type,
        "narco_total": narco_total,
        "narco_in_police": narco_in_police,
        "psych_total": psych_total,
        "psych_in_police": psych_in_police,
        "suspect_total": suspect_total,
        "suspect_in_police": suspect_in_police,
        "addr_links": addr_links,
        "addr_kaskelen": addr_kaskelen,
        "suspect_no": suspect_no,
        "multi": multi,
        "today": date.today().strftime("%d.%m.%Y"),
        "sources_rows": [
            ["ОП (общий), август", fmt(s["police_types"]["ОП (общий)"]), "758 записей ОВД, 715 уник. ИИН"],
            ["Наркологический учёт ОВД", fmt(s["police_types"]["Наркологический учёт ОВД"]), ""],
            ["Ранее судимые", fmt(s["police_types"]["Ранее судимые"]), ""],
            ["Адм. надзор", fmt(s["police_types"]["Адм. надзор"]), ""],
            ["Особое требование (август)", fmt(s["police_types"]["Особое требование"]), ""],
            ["Защитное предписание (август)", fmt(s["police_types"]["Защитное предписание"]), ""],
            ["УДО", fmt(s["police_types"]["УДО"]), ""],
            ["Особое требование (область)", fmt(s["full_registry_types"]["Особое требование (область)"]), "проживание, без ИИН"],
            ["Защитное предписание (область)", fmt(s["full_registry_types"]["Защитное предписание (область)"]), "проживание, без ИИН"],
            ["Наркология (мед.)", fmt(s["narco_total"]), "мекенжай / адрес проживания"],
            ["Психиатрия (мед.)", fmt(s["psych_total"]), "мекенжай / адрес проживания"],
            ["Портрет подозреваемого", f"{s['suspects_total']} ({s['suspects_with_iin']} с ИИН)", "место совершения + фабула (не проживание)"],
        ],
        "matrix_rows": [
            ["СОВПАДЕНИЕ: ОВД + мед", fmt(status_cnt["СОВПАДЕНИЕ: ОВД + мед"]), pct(status_cnt["СОВПАДЕНИЕ: ОВД + мед"], s["unique_persons"]), "На профучёте ОВД и в медсписках"],
            ["СОВПАДЕНИЕ: ОВД + уголовное дело", fmt(status_cnt.get("СОВПАДЕНИЕ: ОВД + уголовное дело", 0)), pct(status_cnt.get("СОВПАДЕНИЕ: ОВД + уголовное дело", 0), s["unique_persons"]), "Подозреваемый и на учёте ОВД"],
            ["СОВПАДЕНИЕ: ОВД + мед + УД", fmt(s["match_all_three"]), "0%", "Полное пересечение — отсутствует"],
            ["РАСХОЖДЕНИЕ: мед. без ОВД", fmt(status_cnt["РАСХОЖДЕНИЕ: мед. без ОВД"]), pct(status_cnt["РАСХОЖДЕНИЕ: мед. без ОВД"], s["unique_persons"]), "Медучёт без профучёта ОВД"],
            ["РАСХОЖДЕНИЕ: мед + УД, нет ОВД", fmt(status_cnt.get("РАСХОЖДЕНИЕ: мед + УД, нет ОВД", 0)), pct(status_cnt.get("РАСХОЖДЕНИЕ: мед + УД, нет ОВД", 0), s["unique_persons"]), "Мед + уголовное дело, нет ОВД"],
            ["РАСХОЖДЕНИЕ: ОВД без мед.", fmt(status_cnt["РАСХОЖДЕНИЕ: ОВД без мед."]), pct(status_cnt["РАСХОЖДЕНИЕ: ОВД без мед."], s["unique_persons"]), "На учёте ОВД, не в медсписках"],
            ["РАСХОЖДЕНИЕ: УД без профучёта", fmt(status_cnt["РАСХОЖДЕНИЕ: УД без профучёта"]), pct(status_cnt["РАСХОЖДЕНИЕ: УД без профучёта"], s["unique_persons"]), "Подозреваемый вне августовского учёта"],
        ],
        "gap_rows": [
            ["Наркология", fmt(narco_total), fmt(narco_in_police), fmt(narco_total - narco_in_police), pct(narco_total - narco_in_police, narco_total)],
            ["Психиатрия", fmt(psych_total), fmt(psych_in_police), fmt(psych_total - psych_in_police), pct(psych_total - psych_in_police, psych_total)],
            ["Подозреваемые (УД)", fmt(suspect_total), fmt(suspect_in_police), fmt(suspect_total - suspect_in_police), pct(suspect_total - suspect_in_police, suspect_total)],
        ],
        "med_gap_breakdown": [
            ["Только наркология", fmt(sum(1 for r in med_gap if r["narco"] == "да" and r["psych"] == "нет"))],
            ["Только психиатрия", fmt(sum(1 for r in med_gap if r["psych"] == "да" and r["narco"] == "нет"))],
            ["Наркология + психиатрия", fmt(sum(1 for r in med_gap if r["narco"] == "да" and r["psych"] == "да"))],
        ],
        "ovd_no_med_rows": [[t, fmt(c)] for t, c in ovd_no_med_by_type.most_common()],
        "locality_table": locality_table,
        "address_legend": address_legend,
        "locality_rows": [
            [x["source"], x["locality"], fmt(x["count"]), fmt(x["district_total"]), x["share"]]
            for x in locality_table
        ],
        "legend_rows": [[k, v] for k, v in address_legend.items()],
    }


def docx_table(doc: Document, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = h
        for run in t.rows[0].cells[i].paragraphs[0].runs:
            run.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)


def build_docx(data: dict) -> bytes:
    r = report_sections(data)
    s = r["s"]
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    title = doc.add_paragraph()
    run = title.add_run("Аналитическая справка о сверке подучётных списков органов полиции")
    run.bold = True
    run.font.size = Pt(14)

    sub = doc.add_paragraph(
        "Сопоставление профучёта ОВД (август 2026) с областными реестрами, "
        "медицинскими списками и портретами подозреваемых"
    )
    sub.runs[0].italic = True

    doc.add_paragraph(
        f"Карасайский район, Алматинская область. Дата подготовки: {r['today']}. "
        f"Уникальных лиц: {fmt(s['unique_persons'])}. Источников: 12."
    )

    doc.add_heading("Краткое резюме", level=1)
    doc.add_paragraph(
        f"Проведена автоматизированная сверка {fmt(s['police_august_records'])} записей "
        f"августовского профучёта ОВД ({fmt(s['police_unique_iin'])} уникальных ИИН) "
        f"с {fmt(s['full_registry_records'])} записями областных реестров, "
        f"{fmt(s['narco_total'])} наркологическими и {fmt(s['psych_total'])} психиатрическими "
        f"пациентами, а также {fmt(s['suspects_total'])} портретами подозреваемых. "
        "Сопоставление выполнено по ИИН и по адресу (для реестров без ИИН)."
    )
    doc.add_paragraph(
        f"Ключевой вывод: из {fmt(r['narco_total'])} пациентов наркологии на профучёте ОВД только "
        f"{fmt(r['narco_in_police'])} ({pct(r['narco_in_police'], r['narco_total'])}); "
        f"из {fmt(r['psych_total'])} психиатрических — {fmt(r['psych_in_police'])} "
        f"({pct(r['psych_in_police'], r['psych_total'])}); "
        f"из {fmt(r['suspect_total'])} подозреваемых с ИИН — {fmt(r['suspect_in_police'])} "
        f"({pct(r['suspect_in_police'], r['suspect_total'])}). "
        "Полного пересечения ОВД + мед + УД не выявлено."
    )

    doc.add_heading("1. Источники данных", level=1)
    docx_table(doc, ("Источник", "Записей", "Примечание"), [tuple(x) for x in r["sources_rows"]])

    doc.add_heading("1а. Логика адресов в источниках", level=1)
    doc.add_paragraph(
        "Адреса разных источников не смешиваются. Сверка «совпадение/расхождение» выполняется "
        "только между адресами проживания (ОВД, медучёт, особое требование/защитка). "
        "Место совершения преступления из ЕРДР — отдельный показатель."
    )
    docx_table(doc, ("Тип адреса", "Источник"), [tuple(x) for x in r["legend_rows"]])

    doc.add_heading("2. Каскелен и Иргели: доля от районного числа", level=1)
    doc.add_paragraph(
        "Доля каждого населённого пункта от общего числа записей по району в данном источнике. "
        "Для ЕРДР знаменатель — дела с районом совершения «Карасайский»."
    )
    docx_table(
        doc,
        ("Источник", "Населённый пункт", "Число", "Всего по району", "Доля"),
        [tuple(x) for x in r["locality_rows"]],
    )

    doc.add_heading("3. Матрица совпадений и расхождений", level=1)
    doc.add_paragraph(f"Всего уникальных лиц в сводной таблице: {fmt(s['unique_persons'])}.")
    docx_table(doc, ("Категория", "Кол-во", "Доля", "Суть"), [tuple(x) for x in r["matrix_rows"]])

    doc.add_heading("4. Критические разрывы по направлениям", level=1)
    docx_table(
        doc,
        ("Направление", "Всего", "На учёте ОВД", "Не на учёте ОВД", "% разрыва"),
        [tuple(x) for x in r["gap_rows"]],
    )
    doc.add_paragraph(f"Структура медицинского разрыва ({fmt(s['gap_med_no_police'])} лиц):")
    docx_table(doc, ("Категория", "Кол-во"), [tuple(x) for x in r["med_gap_breakdown"]])

    doc.add_heading("5. Зафиксированные совпадения", level=1)
    doc.add_heading(f"5.1. ОВД + медицинский учёт ({len(r['ovd_med'])} лиц)", level=2)
    docx_table(
        doc,
        ("ФИО", "Учёт ОВД", "МКБ", "Населённый пункт", "ИИН"),
        [
            (x["fio"], x["police_types"], x.get("narco_mkb") or "—", x.get("settlement") or "—", x.get("iin") or "—")
            for x in r["ovd_med"]
        ],
    )
    doc.add_heading(f"5.2. ОВД + уголовное дело ({len(r['ovd_crime'])} лиц)", level=2)
    docx_table(
        doc,
        ("ФИО", "Учёт ОВД", "ЕРДР / статья", "ИИН"),
        [(x["fio"], x["police_types"], x["erdr"], x.get("iin") or "—") for x in r["ovd_crime"]],
    )
    doc.add_heading(f"5.3. Мультиучёт в списках ОВД ({len(r['multi'])} лиц в 2+ списках)", level=2)
    docx_table(
        doc,
        ("ФИО", "ИИН", "Списки"),
        [(x["fio"], x["iin"], ", ".join(x["types"])) for x in r["multi"][:20]],
    )

    doc.add_heading("6. Сверка адресов проживания (областные реестры)", level=1)
    doc.add_paragraph(
        "Областные файлы не содержат ИИН. Привязка к ОВД — только по адресу фактического проживания "
        f"(порог ≥ 82%). Связей по району: {fmt(s['addr_full_linked'])} "
        f"(из {fmt(s.get('karasai_full_registry', s['full_registry_records']))} записей области в Карасайском районе)."
    )
    doc.add_heading(f"6.1. Каскелен и Иргели ({len(r['addr_kaskelen'])} связей)", level=2)
    docx_table(
        doc,
        ("Реестр", "Населённый пункт", "ФИО (из ОВД)", "Учёт ОВД", "Схожесть"),
        [
            (
                a["full_registry"],
                a.get("settlement", ""),
                a.get("matched_fio", ""),
                a.get("matched_police_type", ""),
                f"{a.get('addr_score', 0):.0%}" if a.get("addr_score") else "—",
            )
            for a in r["addr_kaskelen"]
        ],
    )
    doc.add_heading("6.2. Топ-50 адресных связей проживания", level=2)
    docx_table(
        doc,
        ("Реестр", "Населённый пункт", "ФИО (из ОВД)", "Учёт ОВД"),
        [
            (a["full_registry"], a.get("settlement", ""), a.get("matched_fio", ""), a.get("matched_police_type", ""))
            for a in r["addr_links"][:50]
        ],
    )

    doc.add_heading("7. Расхождение: учёт ОВД без медицинского подтверждения", level=1)
    doc.add_paragraph(
        f"Особое внимание — {r['ovd_no_med_by_type'].get('Наркологический учёт ОВД', 0)} человек "
        "на «наркологическом учёте ОВД» без записи в мед. наркологии."
    )
    docx_table(doc, ("Тип учёта ОВД", "Без мед. учёта"), [tuple(x) for x in r["ovd_no_med_rows"]])

    doc.add_heading("8. Подозреваемые вне профучёта ОВД", level=1)
    doc.add_paragraph(
        f"Из {fmt(s['suspects_with_iin'])} подозреваемых с ИИН — {fmt(s['gap_crime_no_police'])} "
        "не состоят на августовском профучёте. Колонка «Место» — место совершения, не проживание."
    )
    docx_table(
        doc,
        ("ФИО", "ИИН", "ЕРДР", "Статья", "Место совершения", "Район"),
        [
            (x["fio"], x["iin"], x["erdr"], x["qual"], x.get("crime_settlement", ""), x.get("crime_district", ""))
            for x in r["suspect_no"]
        ],
    )

    doc.add_heading("9. Выводы и рекомендации", level=1)
    for text in (
        f"Мед ↔ ОВД: разрыв составляет {pct(r['narco_total'] - r['narco_in_police'], r['narco_total'])} "
        f"по наркологии и {pct(r['psych_total'] - r['psych_in_police'], r['psych_total'])} по психиатрии. "
        "Требуется регламент обмена данными между ОВД и медорганизациями.",
        f"УД ↔ ОВД: {pct(r['suspect_total'] - r['suspect_in_police'], r['suspect_total'])} подозреваемых "
        "не отражены в профучёте. Необходима автоматическая выгрузка из ЕРДР в подучётные списки.",
        f"Областные реестры: {fmt(s['addr_full_linked'])} адресных связей подтверждают частичное "
        "соотнесение с районным учётом; без ИИН точная идентификация невозможна.",
        f"Формальный учёт: {r['ovd_no_med_by_type'].get('Наркологический учёт ОВД', 0)} человек "
        "на «наркологическом учёте ОВД» без мед. подтверждения.",
        f"Мультиучёт: {len(r['multi'])} лиц одновременно в нескольких списках ОВД — "
        "требует проверки на дублирование и актуальность.",
    ):
        doc.add_paragraph(text, style="List Number")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_spravka(data: dict) -> str:
    r = report_sections(data)
    s = r["s"]
    ovd_med = r["ovd_med"]
    ovd_crime = r["ovd_crime"]
    multi = r["multi"]
    addr_links = r["addr_links"]
    addr_kaskelen = r["addr_kaskelen"]
    suspect_no = r["suspect_no"]
    today = r["today"]
    sources_rows = r["sources_rows"]
    matrix_rows = r["matrix_rows"]
    gap_rows = r["gap_rows"]
    med_gap_breakdown = r["med_gap_breakdown"]
    ovd_no_med_rows = r["ovd_no_med_rows"]
    ovd_no_med_by_type = r["ovd_no_med_by_type"]
    narco_total = r["narco_total"]
    narco_in_police = r["narco_in_police"]
    psych_total = r["psych_total"]
    psych_in_police = r["psych_in_police"]
    suspect_total = r["suspect_total"]
    suspect_in_police = r["suspect_in_police"]
    locality_rows = r["locality_rows"]
    legend_rows = [[esc(a), esc(b)] for a, b in r["legend_rows"]]

    ovd_med_rows = [
        [esc(x["fio"]), esc(x["police_types"]), esc(x.get("narco_mkb") or "—"), esc(x.get("locality") or x.get("settlement") or "—"), esc(x.get("iin") or "—")]
        for x in ovd_med
    ]
    ovd_crime_rows = [[esc(x["fio"]), esc(x["police_types"]), esc(x["erdr"]), esc(x.get("iin") or "—")] for x in ovd_crime]
    multi_rows = [[esc(x["fio"]), esc(x["iin"]), esc(", ".join(x["types"]))] for x in multi[:20]]
    addr_rows = [
        [esc(a["full_registry"]), esc(a.get("settlement", "")), esc(a.get("matched_fio", "")), esc(a.get("matched_police_type", "")), f'{a.get("addr_score", 0):.0%}' if a.get("addr_score") else "—"]
        for a in addr_kaskelen
    ]
    addr_all_rows = [[esc(a["full_registry"]), esc(a.get("settlement", "")), esc(a.get("matched_fio", "")), esc(a.get("matched_police_type", ""))] for a in addr_links[:50]]
    suspect_rows = [
        [esc(x["fio"]), f'<span class="mono">{esc(x["iin"])}</span>', esc(x["erdr"]), esc(x["qual"]), esc(x.get("crime_settlement", "")), esc(x.get("crime_district", ""))]
        for x in suspect_no[:50]
    ]

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Справка: сверка профучёта ОВД · Карасайский район · 2026</title>
<link href="https://fonts.googleapis.com/css2?family=Literata:opsz,wght@7..72,400;7..72,600;7..72,700&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{
  --ink:#1a1f2e;--muted:#5c6578;--line:#dde2ea;--paper:#fafbfc;--card:#fff;
  --accent:#1b4d8c;--warn:#b33f26;--ok:#1a7a4a;--gold:#9a7b2f;--max:900px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:'Source Sans 3',system-ui,sans-serif;background:var(--paper);color:var(--ink);line-height:1.65;font-size:16px}}
.doc-header{{background:linear-gradient(160deg,#0f1f3d 0%,#1b4d8c 100%);color:#fff;padding:56px 24px 48px}}
.doc-header .inner{{max-width:var(--max);margin:0 auto}}
.doc-header .eyebrow{{font-size:12px;text-transform:uppercase;letter-spacing:.12em;opacity:.75;margin-bottom:12px}}
.doc-header h1{{font-family:'Literata',Georgia,serif;font-size:clamp(1.4rem,4vw,2rem);font-weight:700;line-height:1.25;margin-bottom:10px}}
.doc-header .sub{{font-size:1.05rem;opacity:.9;margin-bottom:20px}}
.doc-header .meta{{display:flex;flex-wrap:wrap;gap:10px;font-size:13px}}
.doc-header .meta span{{background:rgba(255,255,255,.12);padding:5px 12px;border-radius:4px;border:1px solid rgba(255,255,255,.2)}}
nav.toc{{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid var(--line);padding:10px 24px;overflow-x:auto}}
nav.toc .inner{{max-width:var(--max);margin:0 auto;display:flex;gap:6px;flex-wrap:wrap}}
nav.toc a{{font-size:13px;color:var(--accent);text-decoration:none;padding:6px 12px;border-radius:4px;white-space:nowrap}}
nav.toc a:hover{{background:#eef3fa}}
main{{max-width:var(--max);margin:0 auto;padding:40px 24px 80px}}
section{{margin-bottom:48px}}
section h2{{font-family:'Literata',Georgia,serif;font-size:1.4rem;color:var(--accent);margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid var(--line)}}
section h3{{font-size:1.05rem;margin:24px 0 12px;color:var(--ink)}}
.lead{{font-size:1.06rem;color:var(--muted);background:#eef3fa;border-left:4px solid var(--accent);padding:16px 20px;border-radius:0 6px 6px 0;margin-bottom:24px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:20px 24px;margin-bottom:16px}}
.card-warn{{border-left:4px solid var(--warn)}}
.card-ok{{border-left:4px solid var(--ok)}}
.kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:20px 0}}
.kpi div{{background:#fff;border:1px solid var(--line);border-radius:8px;padding:14px;text-align:center}}
.kpi .v{{font-size:1.4rem;font-weight:700;color:var(--accent)}}
.kpi .l{{font-size:10px;color:var(--muted);text-transform:uppercase;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin:12px 0 20px}}
th,td{{padding:9px 11px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:#f4f6f9;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}}
tr:last-child td{{border-bottom:none}}
.num{{font-variant-numeric:tabular-nums;font-weight:600}}
.warn{{color:var(--warn);font-weight:600}}
.ok{{color:var(--ok);font-weight:600}}
.mono{{font-family:ui-monospace,monospace;font-size:12px}}
.note{{font-size:14px;color:var(--muted);font-style:italic;margin:8px 0 16px}}
.scroll{{overflow-x:auto}}
.footer-links{{display:flex;gap:10px;flex-wrap:wrap;margin-top:32px;padding-top:24px;border-top:1px solid var(--line)}}
.footer-links a{{display:inline-block;padding:10px 18px;background:var(--accent);color:#fff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500}}
.footer-links a.secondary{{background:#fff;color:var(--accent);border:1px solid var(--line)}}
@media print{{nav.toc,.footer-links{{display:none}}.doc-header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style>
</head>
<body>

<header class="doc-header">
  <div class="inner">
    <div class="eyebrow">Карасайский район · Алматинская область</div>
    <h1>Аналитическая справка о сверке подучётных списков органов полиции</h1>
    <p class="sub">Сопоставление профучёта ОВД (август 2026) с областными реестрами, медицинскими списками и портретами подозреваемых</p>
    <div class="meta">
      <span>Дата: {today}</span>
      <span>Уникальных лиц: {fmt(s["unique_persons"])}</span>
      <span>Источников: 12</span>
      <span>ЕРДР / мед / ОВД</span>
    </div>
  </div>
</header>

<nav class="toc">
  <div class="inner">
    <a href="#summary">Резюме</a>
    <a href="#sources">Источники</a>
    <a href="#addr-logic">Логика адресов</a>
    <a href="#locality">Каскелен / Иргели</a>
    <a href="#matrix">Матрица</a>
    <a href="#gaps">Разрывы</a>
    <a href="#matches">Совпадения</a>
    <a href="#addresses">Адреса</a>
    <a href="#ovd-no-med">ОВД без мед.</a>
    <a href="#crime">УД без ОВД</a>
    <a href="#conclusions">Выводы</a>
  </div>
</nav>

<main>

<section id="summary">
  <h2>Краткое резюме</h2>
  <p class="lead">
    Проведена автоматизированная сверка <strong>758 записей</strong> августовского профучёта ОВД
    ({fmt(s["police_unique_iin"])} уникальных ИИН) с <strong>3 302 записями</strong> областных реестров
    (особое требование и защитное предписание), <strong>381</strong> наркологическими и
    <strong>1 756</strong> психиатрическими пациентами, а также <strong>428</strong> портретами подозреваемых.
    Сопоставление по ИИН; адреса проживания сверяются отдельно от места совершения преступления.
  </p>
  <div class="kpi">
    <div><div class="v">{fmt(s["match_ovd_med"])}</div><div class="l">ОВД + мед</div></div>
    <div><div class="v">{fmt(s["match_ovd_crime"])}</div><div class="l">ОВД + УД</div></div>
    <div><div class="v warn">{fmt(s["match_all_three"])}</div><div class="l">ОВД+мед+УД</div></div>
    <div><div class="v warn">{fmt(s["gap_med_no_police"])}</div><div class="l">Мед без ОВД</div></div>
    <div><div class="v warn">{fmt(s["gap_crime_no_police"])}</div><div class="l">УД без ОВД</div></div>
    <div><div class="v">{fmt(s["addr_full_linked"])}</div><div class="l">Адрес. связей</div></div>
  </div>
  <div class="card card-warn">
    <strong>Ключевой вывод:</strong> из {fmt(narco_total)} пациентов наркологии на профучёте ОВД только
    <span class="ok">{fmt(narco_in_police)} ({pct(narco_in_police, narco_total)})</span>;
    из {fmt(psych_total)} психиатрических — <span class="ok">{fmt(psych_in_police)} ({pct(psych_in_police, psych_total)})</span>;
    из {fmt(suspect_total)} подозреваемых с ИИН — <span class="ok">{fmt(suspect_in_police)} ({pct(suspect_in_police, suspect_total)})</span>.
    Полного пересечения ОВД + мед + УД <strong>не выявлено</strong>.
  </div>
</section>

<section id="sources">
  <h2>1. Источники данных</h2>
  {table(["Источник", "Записей", "Примечание"], sources_rows)}
</section>

<section id="addr-logic">
  <h2>1а. Логика адресов</h2>
  <p class="note">Сверка «совпадение/расхождение» по адресу выполняется <strong>только между адресами проживания</strong>. Место совершения из ЕРДР и текст фабулы не сравниваются с проживанием.</p>
  {table(["Тип адреса", "Источник"], legend_rows)}
</section>

<section id="locality">
  <h2>2. Каскелен и Иргели — доля от районного числа</h2>
  <p class="note">Для каждого источника указано, сколько записей относится к г. Каскелен и с.о. Иргели (включая Казмис) и какова их доля от общего числа по району в этом источнике.</p>
  {table(["Источник", "Населённый пункт", "Число", "Всего по району", "Доля"], locality_rows)}
</section>

<section id="matrix">
  <h2>3. Матрица совпадений и расхождений</h2>
  <p class="note">Всего уникальных лиц в сводной таблице: {fmt(s["unique_persons"])}.</p>
  {table(["Категория", "Кол-во", "Доля", "Суть"], matrix_rows)}
</section>

<section id="gaps">
  <h2>4. Критические разрывы по направлениям</h2>
  {table(["Направление", "Всего", "На учёте ОВД", "Не на учёте ОВД", "% разрыва"], gap_rows)}

  <h3>Структура медицинского разрыва ({fmt(s["gap_med_no_police"])} лиц)</h3>
  {table(["Категория", "Кол-во"], med_gap_breakdown)}
</section>

<section id="matches">
  <h2>5. Зафиксированные совпадения</h2>

  <h3>5.1. ОВД + медицинский учёт ({len(ovd_med)} лиц)</h3>
  <div class="scroll">
  {table(["ФИО", "Учёт ОВД", "МКБ", "Населённый пункт", "ИИН"], ovd_med_rows)}
  </div>

  <h3>5.2. ОВД + уголовное дело ({len(ovd_crime)} лиц)</h3>
  <div class="scroll">
  {table(["ФИО", "Учёт ОВД", "ЕРДР / статья", "ИИН"], ovd_crime_rows)}
  </div>

  <h3>5.3. Мультиучёт в списках ОВД ({len(multi)} лиц в 2+ списках)</h3>
  <div class="scroll">
  {table(["ФИО", "ИИН", "Списки"], multi_rows) if multi_rows else "<p class='note'>—</p>"}
  </div>
</section>

<section id="addresses">
  <h2>6. Сверка адресов проживания (областные реестры)</h2>
  <p class="note">
    Привязка областных реестров к ОВД — только по <strong>адресу фактического проживания</strong> (порог ≥ 82%).
    Связей по Карасайскому району: <strong>{fmt(s["addr_full_linked"])}</strong>.
  </p>

  <h3>6.1. Каскелен и Иргели ({len(addr_kaskelen)} связей)</h3>
  <div class="scroll">
  {table(["Реестр", "Населённый пункт", "ФИО (из ОВД)", "Учёт ОВД", "Схожесть"], addr_rows) if addr_rows else "<p class='note'>Совпадений не найдено.</p>"}
  </div>

  <h3>6.2. Топ-50 связей проживания</h3>
  <div class="scroll">
  {table(["Реестр", "Населённый пункт", "ФИО (из ОВД)", "Учёт ОВД"], addr_all_rows)}
  </div>
</section>

<section id="ovd-no-med">
  <h2>7. Расхождение: учёт ОВД без медицинского подтверждения</h2>
  <p class="note">
    Лица на августовском профучёте ОВД, не найденные в списках наркологии и психиатрии.
    Особое внимание — <strong>{ovd_no_med_by_type.get("Наркологический учёт ОВД", 0)}</strong> человек
    на «наркологическом учёте ОВД» без записи в мед. наркологии.
  </p>
  {table(["Тип учёта ОВД", "Без мед. учёта"], ovd_no_med_rows)}
</section>

<section id="crime">
  <h2>8. Подозреваемые вне профучёта ОВД</h2>
  <p class="note">
    «Место совершения» — из ЕРДР (реквизит 31), это <strong>не адрес проживания</strong>.
  </p>
  <div class="scroll">
  {table(["ФИО", "ИИН", "ЕРДР", "Статья", "Место совершения", "Район"], suspect_rows)}
  </div>
</section>

<section id="conclusions">
  <h2>9. Выводы и рекомендации</h2>
  <div class="card">
    <ol style="padding-left:1.4em">
      <li><strong>Мед ↔ ОВД:</strong> разрыв составляет {pct(narco_total - narco_in_police, narco_total)} по наркологии и {pct(psych_total - psych_in_police, psych_total)} по психиатрии. Требуется регламент обмена данными между ОВД и медорганизациями.</li>
      <li><strong>УД ↔ ОВД:</strong> {pct(suspect_total - suspect_in_police, suspect_total)} подозреваемых не отражены в профучёте. Необходима автоматическая выгрузка из ЕРДР в подучётные списки.</li>
      <li><strong>Областные реестры:</strong> {fmt(s["addr_full_linked"])} адресных связей подтверждают, что часть записей области соотносится с районным учётом; однако без ИИН точная идентификация невозможна.</li>
      <li><strong>Формальный учёт:</strong> {ovd_no_med_by_type.get("Наркологический учёт ОВД", 0)} человек на «наркологическом учёте ОВД» без мед. подтверждения — признак учёта «на бумаге».</li>
      <li><strong>Мультиучёт:</strong> {len(multi)} лиц одновременно в нескольких списках ОВД — требует проверки на дублирование и актуальность.</li>
    </ol>
  </div>
</section>

<div class="footer-links">
  <a href="index_sverka_profueta.html">← Оглавление</a>
</div>

</main>
</body>
</html>"""


def build_index() -> str:
    today = date.today().strftime("%d.%m.%Y")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Сверка профучёта ОВД · Карасайский район</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>
body{{font-family:'Source Sans 3',system-ui,sans-serif;background:#f5f7fa;color:#1a1f2e;margin:0;padding:40px 24px 80px;line-height:1.6}}
.wrap{{max-width:640px;margin:0 auto}}
h1{{font-size:1.6rem;color:#1b4d8c;margin-bottom:8px}}
.sub{{color:#5c6578;margin-bottom:32px}}
.card{{display:block;background:#fff;border:1px solid #dde2ea;border-radius:10px;padding:24px 28px;margin-bottom:16px;text-decoration:none;color:inherit;transition:border-color .15s}}
.card:hover{{border-color:#1b4d8c}}
.card h2{{font-size:1.1rem;margin:0 0 8px;color:#1b4d8c}}
.card p{{margin:0;font-size:14px;color:#5c6578}}
.meta{{font-size:13px;color:#5c6578;margin-top:32px;padding-top:20px;border-top:1px solid #dde2ea}}
a.back{{color:#1b4d8c;font-size:14px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>Сверка подучётных списков ОВД</h1>
  <p class="sub">Карасайский район · Алматинская область · {today}</p>

  <a class="card" href="Справка_интегрированная_Каскелен_Иргели.html">
    <h2>Интегрированная справка (паспорт + профучёт)</h2>
    <p>Объединение кримпаспортов Каскелен/Иргели со сверкой 3 236 лиц: скрытые связи, доли НП, новые выводы.</p>
  </a>

  <a class="card" href="Справка_сверка_профучета_ОВД.html">
    <h2>Аналитическая справка (HTML)</h2>
    <p>Официальный документ с таблицами: источники, матрица совпадений/расхождений, адресные связи, выводы. Готов к печати.</p>
  </a>

  <a class="card" href="Справка_сверка_профучета_ОВД.docx">
    <h2>Аналитическая справка (Word)</h2>
    <p>Тот же документ в формате .docx для прокуратуры и комиссии — Times New Roman, таблицы, все разделы.</p>
  </a>
</div>
</body>
</html>"""


def main() -> None:
    if not DATA.exists():
        raise SystemExit(f"Нет данных: {DATA}. Сначала запустите crossmatch_registry.py")
    data = load()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = build_spravka(data)
    docx = build_docx(data)
    SPRAVKA.write_text(html, encoding="utf-8")
    INDEX.write_text(build_index(), encoding="utf-8")
    DOCX.write_bytes(docx)
    # копия в passports/docs для веб-навигации
    DOCS_MIRROR.mkdir(parents=True, exist_ok=True)
    (DOCS_MIRROR / SPRAVKA.name).write_text(html, encoding="utf-8")
    (DOCS_MIRROR / DOCX.name).write_bytes(docx)
    (DOCS_MIRROR / "index.html").write_text(build_index(), encoding="utf-8")
    print(f"Written {SPRAVKA}")
    print(f"Written {INDEX}")
    print(f"Written {DOCX}")
    print(f"Mirror  {DOCS_MIRROR}")


if __name__ == "__main__":
    main()
