#!/usr/bin/env python3
"""Генерация HTML-справки по ЦПС Карасайского района."""

from __future__ import annotations

import html as h
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CPS = ROOT / "ЦПС"
OUT_DIR = ROOT / "passports" / "docs" / "spravka_cps"
OUT_HTML = OUT_DIR / "spravka.html"
SUICIDE_X = ROOT / "Суицид_F00-99_ЦПС_сверка.xlsx"

LAWS = [
    (
        "Правила осуществления деятельности Центров поддержки семьи",
        "Приказ МКИ РК от 14.06.2024 № 256-НҚ (реестр № 34499)",
        "https://adilet.zan.kz/rus/docs/V2400034499",
        "п. 6, 11–17, 20–25 — функции, сроки, ИПР, мобгруппы, насилие",
    ),
    (
        "Кодекс «О браке (супружестве) и семье»",
        "Статья 5-1 — Центры поддержки семьи (K1400000235)",
        "https://adilkarimov50.github.io/krim-passport/legal_read.html?doc=K1400000235",
        "создание ЦПС, координация, временное проживание при бытовом насилии",
    ),
    (
        "Закон «О профилактике правонарушений»",
        "Z2500000245 (ред. 2026)",
        "https://adilkarimov50.github.io/krim-passport/legal_read.html?doc=Z2500000245",
        "ст. 10–11 — ЦПС и мобильные группы; ст. 1239 — учёт ТЖС; "
        "полугодовая оценка на МВК «Закон и порядок»",
    ),
    (
        "Социальный кодекс",
        "Основания трудной жизненной ситуации",
        "https://adilet.zan.kz/rus/docs/K2300000224",
        "признание ТЖС, меры поддержки",
    ),
]

FILES = [
    ("Журнал регистрации обращений", "01.01.2026 – 09.09.2026"),
    ("Журнал регистрации обращений по стандарту ТЖС", "01.01.2026 – 09.09.2026"),
    ("ИПР семьи", "01.01.2025 – 09.09.2026"),
    ("Протокол выезда (мобильная группа)", "01.01.2026 – 09.09.2026"),
    ("Отчёт о проделанной работе", "01.01.2026 – 09.09.2026"),
    ("Суицид_F00-99_ЦПС_сверка.xlsx", "сверка с реестром суицидов"),
]


def esc(x) -> str:
    if pd.isna(x):
        return "—"
    return h.escape(str(x))


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


def table_from_df(df: pd.DataFrame, cols: list[str]) -> str:
    sub = df[cols].head(20) if all(c in df.columns for c in cols) else df.head(20)
    rows = []
    rows.append("<thead><tr>" + "".join(f"<th>{h.escape(c)}</th>" for c in sub.columns) + "</tr></thead>")
    rows.append("<tbody>")
    for _, r in sub.iterrows():
        rows.append(
            "<tr>"
            + "".join(f"<td>{esc(r[c])[:200]}</td>" for c in sub.columns)
            + "</tr>"
        )
    rows.append("</tbody>")
    return '<table class="data">' + "".join(rows) + "</table>"


def main() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    j = clean_journal()
    res = j["Результат"].fillna("").astype(str)

    summary = pd.read_excel(CPS / "ЦПС_полный_анализ.xlsx", sheet_name="Сводка")
    by_micro = pd.read_excel(CPS / "ЦПС_полный_анализ.xlsx", sheet_name="По_населенным_пунктам")
    by_sender = pd.read_excel(CPS / "ЦПС_полный_анализ.xlsx", sheet_name="Кто_направил")
    violations = pd.read_excel(CPS / "ЦПС_полный_анализ.xlsx", sheet_name="Нарушения_и_нормы")
    work = pd.read_excel(CPS / "ЦПС_полный_анализ.xlsx", sheet_name="Отчет_работа_ЦПС")

    # Example blocks
    ex_prob = j[
        j["Наименование организации отправителя"].astype(str).str.contains("пробац", case=False)
    ].head(8)
    ex_red = j[res.str.contains("бордов", case=False)].head(8)
    ex_no_iin = j[
        j["Тип обращения"].astype(str).str.contains("ТЖС", case=False) & j["ИИН"].isna()
    ].head(8)
    ex_pol = j[
        j["Наименование организации отправителя"].astype(str).str.contains("POLVANOVA|141832", case=False)
        | (j["№ обращения"] == 141832)
    ]
    if ex_pol.empty:
        ex_pol = j[j["Причина обращения"].astype(str).str.contains("алкогол|злоупотреб", case=False)].head(3)

    ex_violence = j[
        j["Причина обращения"].astype(str).str.contains("насил|алкогол|злоупотреб|суицид", case=False, regex=True)
    ].head(6)

    suicide_found = pd.DataFrame()
    suicide_none = pd.DataFrame()
    if SUICIDE_X.exists():
        suicide_found = pd.read_excel(SUICIDE_X, sheet_name="Детали ЦПС (найденные)")
        suicide_none = pd.read_excel(SUICIDE_X, sheet_name="Без обращения в ЦПС").head(12)

    proto = pd.read_excel(
        CPS
        / "Отчет 'Протокол выезда' от 09.09.2026 12;28;57 (с 01.01.26 00;00 по 09.09.26 12;28).xlsx",
        header=2,
    )
    proto = proto[pd.to_numeric(proto["№ пп"], errors="coerce").notna()]
    ex_proto = proto[proto["Дата/время приезда"].isna()].head(6)

    laws_html = "".join(
        f'<div class="card"><h3>{h.escape(t)}</h3>'
        f'<p class="mono">{h.escape(sub)}</p>'
        f'<p><a href="{h.escape(url)}" target="_blank" rel="noopener">{h.escape(url)}</a></p>'
        f"<p>{h.escape(note)}</p></div>"
        for t, sub, url, note in LAWS
    )

    files_html = "".join(
        f"<tr><td>{h.escape(n)}</td><td>{h.escape(p)}</td>"
        f'<td><code>prof/ЦПС/</code> (исходная выгрузка)</td></tr>'
        for n, p in FILES
    )

    body = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Справка: деятельность ЦПС Карасайского района</title>
<link href="https://fonts.googleapis.com/css2?family=Literata:opsz,wght@7..72,600;7..72,700&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--ink:#1a1f2e;--muted:#5c6578;--line:#dde2ea;--paper:#fafbfc;--accent:#1b4d8c;--warn:#b33f26;--max:960px}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Source Sans 3',system-ui,sans-serif;background:var(--paper);color:var(--ink);line-height:1.65;font-size:16px}}
.doc-header{{background:linear-gradient(160deg,#0f1f3d,#1b4d8c);color:#fff;padding:48px 24px}}
.doc-header .inner{{max-width:var(--max);margin:0 auto}}
.doc-header h1{{font-family:Literata,Georgia,serif;font-size:clamp(1.35rem,4vw,1.9rem);margin:12px 0}}
.doc-header .meta{{display:flex;flex-wrap:wrap;gap:8px;font-size:13px;margin-top:16px}}
.doc-header .meta span{{background:rgba(255,255,255,.12);padding:4px 10px;border-radius:4px}}
nav.toc{{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);padding:8px 24px;z-index:5;overflow-x:auto}}
nav.toc a{{font-size:13px;color:var(--accent);margin-right:12px;text-decoration:none}}
main{{max-width:var(--max);margin:0 auto;padding:32px 24px 64px}}
section{{margin-bottom:40px}}
h2{{font-family:Literata,Georgia,serif;color:var(--accent);font-size:1.35rem;border-bottom:2px solid var(--line);padding-bottom:8px;margin-bottom:16px}}
h3{{font-size:1.05rem;margin:20px 0 10px}}
.lead{{background:#eef3fa;border-left:4px solid var(--accent);padding:14px 18px;margin-bottom:20px;color:var(--muted)}}
.card{{background:#fff;border:1px solid var(--line);border-radius:8px;padding:16px 20px;margin-bottom:14px}}
.card-warn{{border-left:4px solid var(--warn)}}
table.data{{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}}
table.data th,table.data td{{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}}
table.data th{{background:#f4f6f9;font-size:11px;text-transform:uppercase;color:var(--muted)}}
.scroll{{overflow-x:auto}}
.warn{{color:var(--warn);font-weight:600}}
.num{{font-variant-numeric:tabular-nums;font-weight:600}}
.footer{{margin-top:32px;padding-top:20px;border-top:1px solid var(--line);font-size:14px}}
.footer a{{color:var(--accent)}}
@media print{{nav.toc{{display:none}}}}
</style>
</head>
<body>
<header class="doc-header">
<div class="inner">
<div style="font-size:12px;text-transform:uppercase;letter-spacing:.1em;opacity:.8">Прокуратура · Карасайский район</div>
<h1>Аналитическая справка о деятельности КГУ «Центр поддержки семьи»</h1>
<p style="opacity:.92;margin-top:8px">Проверка по выгрузкам ИС FSM Social, с примерами конкретных лиц, таблицами и ссылками на нормы права</p>
<div class="meta">
<span>Дата справки: 10.09.2026</span>
<span>Обращений: 497</span>
<span>ИПР (семей): 577</span>
<span>Источников: 5 + сверка суицид</span>
</div>
</div>
</header>
<nav class="toc">
<a href="#sources">Источники</a>
<a href="#summary">Сводка</a>
<a href="#geo">Территория</a>
<a href="#examples">Примеры лиц</a>
<a href="#violations">Нарушения</a>
<a href="#suicide">Суицид</a>
<a href="#laws">Законы</a>
<a href="#files">Файлы</a>
</nav>
<main>

<section id="sources">
<h2>1. Источники данных</h2>
<p class="lead">Анализ выполнен по пяти официальным отчётам ЦПС Карасайского района и сводной таблице
<code>ЦПС_полный_анализ.xlsx</code>, сопоставлению с реестром случаев суицida (598 лиц).</p>
<table class="data">
<thead><tr><th>Отчёт</th><th>Период</th><th>Расположение</th></tr></thead>
<tbody>{files_html}</tbody>
</table>
</section>

<section id="summary">
<h2>2. Сводные показатели</h2>
<div class="scroll">{table_from_df(summary, ['Показатель','Значение'])}</div>
<h3>Отчёт ЦПС «о проделанной работе» (фрагмент)</h3>
<div class="scroll">{table_from_df(work, ['Показатель','Взято','Выполнено'])}</div>
<p class="warn">Примечание: строка «Служба пробации — 7 взято / 310 выполнено» математически несостоятельна и ставит под сомнение достоверность отчётности ИС.</p>
</section>

<section id="geo">
<h2>3. Кому помогают и откуда (территория, направившие органы)</h2>
<h3>3.1. Населённые пункты / адреса</h3>
<div class="scroll">{table_from_df(by_micro, list(by_micro.columns))}</div>
<h3>3.2. Кто направил в ЦПС</h3>
<div class="scroll">{table_from_df(by_sender, list(by_sender.columns))}</div>
<p>Фактически ЦПС обрабатывает поток от <strong>службы пробации</strong> (218 обращений, 83% закрыты консультацией или отказом в помощи),
<strong>прокуратуры</strong> (107), <strong>полиции</strong> (25); собственные повторные карточки — 115.</p>
</section>

<section id="examples">
<h2>4. Примеры конкретных лиц (иллюстрация системных проблем)</h2>

<div class="card card-warn">
<h3>4.1. Направления службы пробации — закрытие без реальной помощи</h3>
<p>Норма: Правила ЦПС п. 12 п. 4, п. 15–17 — первичная оценка, ИПР, межведомственная поддержка.</p>
<div class="scroll">{table_from_df(ex_prob, ['№ обращения','Дата','ФИО (при его наличии)','Причина обращения','Результат','Наименование организации отправителя'])}</div>
<p><strong>Пример:</strong> № <span class="num">171537</span> — <strong>КОРНЕВ ЕВГЕНИЙ АЛЕКСАНДРОВИЧ</strong>, причина «медицинская помощь» (пробация),
результат: «<em>в помощи не нуждается</em>». № <span class="num">171503</span> — <strong>СЫДЫКБЕК АЯН ТУРГАНУЛЫ</strong>, запрос на трудоустройство — отказ в поддержке.</p>
</div>

<div class="card card-warn">
<h3>4.2. «Бордовая зона» ЦКС — итог дублирует формулировку причины</h3>
<p>Норма: интегрированная модель (Правила п. 6 п. 2); учёт семей в ТЖС (Закон о профилактике ст. 1239).</p>
<div class="scroll">{table_from_df(ex_red, ['№ обращения','ФИО (при его наличии)','Причина обращения','Результат','Принял обращение: ФИО'])}</div>
<p><strong>Примеры:</strong> № <span class="num">141878</span> — <strong>ДАУЛЕМБАЕВА ВЕНЕРА ДУЙСЕНБАЕВНА</strong>; № <span class="num">141895</span> — <strong>НУРЫМБЕТОВА ГУЛЬЖАЙНА ШАТТЫКОВНА</strong>;
№ <span class="num">142466</span> — <strong>КАРАБАЕВА ЛЯЗЗАТ ЖАНАБАЕВНА</strong>. В результате — повтор «семья в бордовой зоне» без перечня мер ОВД, здравоохранения, соцзащиты.</p>
</div>

<div class="card card-warn">
<h3>4.3. Обращения в ТЖС без ИИН (учёт нарушен)</h3>
<p>Норма: Правила ЦПС п. 13 — сведения по лицу/семье; стандарт журнала ТЖС.</p>
<div class="scroll">{table_from_df(ex_no_iin, ['№ обращения','ФИО (при его наличии)','Причина обращения','Адрес проживания','Результат'])}</div>
<p><strong>Пример:</strong> № <span class="num">140712</span> — <strong>ERIMBETOVA JANAR</strong> (многодетная семья, 5 детей) — ИИН в журнале не указан.
№ <span class="num">141832</span> — <strong>POLVANOVA AZIZA MANSURKIZI</strong> — «муж злоупотребляет алкоголем»; результат в карточке не заполнен.</p>
</div>

<div class="card card-warn">
<h3>4.4. Домашнее насилие / алкоголь / риск — без комплексного плана</h3>
<div class="scroll">{table_from_df(ex_violence, ['№ обращения','ФИО (при его наличии)','Причина обращения','Результат','Наименование организации отправителя'])}</div>
<p>Норма: Правила ЦПС п. 22–25 (мобгруппа, спецуслуги, временное проживание до 1 мес.); ст. 5-1 Кодекса о браке п. 2 п. 4.</p>
</div>

<div class="card card-warn">
<h3>4.5. Протоколы выезда мобильной группы — нет времени приезда</h3>
<p>Норма: Правила ЦПС п. 20–22 — состав МГ (ОВД, здравоохранение, образование); документирование выезда.</p>
<div class="scroll">{table_from_df(ex_proto, ['Номер родительского задания','ФИО исполнителя (из моб группы)','Дата/время приезда','Дата/время отъезда', ex_proto.columns[-1]] if len(ex_proto.columns) else ex_proto.columns)}</div>
<p><strong>Пример:</strong> к семье <strong>ТОКУЛИЕВА АКМАРАЛ КОНУРБАЕВНА</strong> (ИИН 760301401088) — два выезда (задания 337412), у одного исполнителя время приезда пустое, у другого указан только отъезд.</p>
</div>
</section>

<section id="violations">
<h2>5. Выявленные нарушения и риски (таблица)</h2>
<div class="scroll">{table_from_df(violations, list(violations.columns))}</div>
</section>

<section id="suicide">
<h2>6. Суицидальный регистр vs ЦПС</h2>
<p class="lead warn">Из 598 лиц с зарегистрированными случаями суицида в ЦПС по ИИН/ФИО найдены только <strong>2</strong>.
596 человек в выгрузках ЦПС за период не отражены. Это ключевой показатель неэффективности раннего выявления.</p>
<h3>6.1. Лица, которым ЦПС всё же оказывал помощь (полная трассировка)</h3>
<div class="scroll">{table_from_df(suicide_found, ['ИИН','ФИО_суицид','Дата','Источник_ЦПС','Причина','Помощь_оказана','№_обращения']) if len(suicide_found) else '<p>—</p>'}</div>
<p><strong>Кейс КОВАЛЕВА АНАСТАСИЯ ВАЛЕРЬЕВНА</strong> (ИИН 840121401037): суицид, ребёнок без присмотра — есть обращения № 329548, 346091, психологическая консультация в ИПР, выезды мобгруппы; требуется проверить уведомление опеки (24 ч, п. 26 Правил) и участие не только сотрудников ЦПС в МГ.</p>
<p><strong>Кейс СУЙЕУБАЕВ НУРЛАН СМЕТУЛЛАЕВИЧ</strong> (ИИН 880701301754): направление пробации после смерти 31.03.2026 — формальная регистрация, мера ИПР «Иные».</p>
<h3>6.2. Примеры лиц из реестра суицида без обращения в ЦПС</h3>
<div class="scroll">{table_from_df(suicide_none, ['ИИН','ФИО','Случаев_суицида','Специфика','Тип_суицида']) if len(suicide_none) else ''}</div>
</section>

<section id="laws">
<h2>7. Нормативная база (ссылки)</h2>
{laws_html}
</section>

<section id="files">
<h2>8. Приложения на диске</h2>
<ul>
<li><a href="ЦПС_полный_анализ.xlsx">ЦПС_полный_анализ.xlsx</a> — все таблицы для проверки (также <code>prof/ЦПС/</code>)</li>
<li><code>prof/Суицид_F00-99_ЦПС_сверка.xlsx</code> — перекрёстная сверка</li>
<li><code>prof/scripts/analyze_cps_karasai.py</code> — пересчёт аналитики</li>
<li><code>prof/scripts/build_cps_spravka.py</code> — пересборка настоящей справки</li>
</ul>
<div class="footer">
<p>Для обновления после новых выгрузок:</p>
<p><code>python scripts/analyze_cps_karasai.py && python scripts/build_cps_spravka.py</code></p>
<p>Библиотека НПА на сайте: <a href="https://adilkarimov50.github.io/krim-passport/prokuror_zakon.html">prokuror_zakon.html</a>
· Закон о профилактике: <a href="https://adilkarimov50.github.io/krim-passport/legal_read.html?doc=Z2500000245">Z2500000245</a></p>
</div>
</section>

</main>
</body>
</html>"""

    OUT_HTML.write_text(body, encoding="utf-8")
    print(f"Written: {OUT_HTML}")
    return OUT_HTML


if __name__ == "__main__":
    main()
