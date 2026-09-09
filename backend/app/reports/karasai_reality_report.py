"""Аналитическая справка: реальная картина Каскелен и Иргели (Карасайский район).

Для прокуратуры / комиссии по профилактике. Основана на bundle.json и karasai_crosscheck.
"""

from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.shared import Pt

from app.analytics.karasai_crosscheck import build_analysis
from app.reports.generator import _docx_base

LAW245 = "Закон РК «О профилактике правонарушений» от 30.12.2025 № 245-VIII"
ORDER32 = "Приказ Генерального Прокурора РК от 17.01.2023 № 32"


def _fmt(n) -> str:
    if n is None:
        return "—"
    if isinstance(n, float):
        return f"{n}".replace(".", ",")
    return f"{int(n):,}".replace(",", " ")


def _table(doc: Document, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for r in rows:
        cells = table.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = str(v)


def _bullets(doc: Document, items: tuple[str, ...]) -> None:
    for txt in items:
        doc.add_paragraph(txt, style="List Bullet")


def karasai_reality_docx(author: str = "", export_id: str = "") -> bytes:
    analysis = build_analysis()
    doc = _docx_base("Справка: реальная картина Карасайского района", author, export_id)

    title = doc.add_paragraph()
    run = title.add_run(
        "АНАЛИТИЧЕСКАЯ СПРАВКА\n"
        "о сопоставлении криминологических паспортов с фактическими данными\n"
        "г. Каскелен и Иргелинского сельского округа\n"
        "Карасайского района (7 месяцев 2026 года)"
    )
    run.bold = True
    run.font.size = Pt(14)

    doc.add_paragraph(
        f"Дата подготовки: {date.today().strftime('%d.%m.%Y')}. "
        f"Нормативная база: {LAW245}; Приказы МВД РК №662, №1008, №163; "
        f"Приказ Минздрава №814; {ORDER32}."
    )

    # 1. Предмет и метод
    doc.add_heading("1. Предмет и метод исследования", level=1)
    doc.add_paragraph(
        "Справка подготовлена путём перекрёстного сопоставления итоговых криминологических "
        "паспортов (_итог, ред. 31.08.2026), выгрузки ЕРДР (1 512 записей), формы 1-АД "
        f"({analysis['summary']['admin_total']} записей по району), списков наркологического "
        f"({analysis['summary']['narcology_total']} лиц) и психиатрического "
        f"({analysis['summary']['psychiatry_total']} лиц) учёта, протоколов комиссии "
        "при акимате района (Q1 — 23.02.2026, Q2 — 21.05.2026)."
    )
    _bullets(doc, (
        "Блок A — сверка KPI: паспорт / ЕРДР / 1-АД / медучёт, флаг расхождения >10 %.",
        "Блок B — геопривязка улиц и объектов (Абылай хана, Алтын Орда, Асыл Арман).",
        "Блок C — профучёт: ОВД vs наркология vs психиатрия vs ст.440/442.",
        "Блок D — поручения комиссии vs KPI исполнения.",
        "Блок E — правовая оценка по Закону №245-VIII и Приказу ГП №32.",
    ))

    # 2. Сводка расхождений
    doc.add_heading("2. Матрица расхождений «на бумаге vs в данных»", level=1)
    flagged = [g for g in analysis["gaps"] if g.get("flagged")]
    doc.add_paragraph(
        f"Выявлено {analysis['summary']['total_gaps']} сопоставлений, "
        f"из них {analysis['summary']['flagged_gaps']} с существенным расхождением."
    )
    rows = []
    for g in flagged[:20]:
        rows.append((
            g.get("label", ""),
            g.get("metric", ""),
            _fmt(g.get("passport_value")),
            _fmt(g.get("alt_value")),
            f"{g.get('delta_pct', '—')} %" if g.get("delta_pct") is not None else "—",
            g.get("note", "")[:80],
        ))
    _table(doc, ("НП", "Показатель", "Паспорт", "Данные", "Δ%", "Примечание"), rows)

    # 3. Каскелен
    doc.add_heading("3. г. Каскелен", level=1)
    doc.add_heading("3.1. Уголовная статистика и мошенничество", level=2)
    doc.add_paragraph(
        "554 факта в паспорте vs 592 записи ЕРДР (+6,9 %). "
        "500 записей только по ст.190 (294 ч.3 + 206 ч.2) — 53,6 % структуры. "
        "89,3 % совершивших не работают при охвате ЦЗН 11,3 % безработных."
    )
    doc.add_heading("3.2. Административная практика", level=2)
    kask_admin = analysis["kpi_strip"]["kaskelen"]
    doc.add_paragraph(
        f"По 1-АД с геофильтром: {kask_admin['admin_1ad']} записей по городу. "
        "Паспорт агрегирует по району: ст.440 — 825, ст.442 — 834, ст.73 — 215. "
        "Без геопривязки по улицам сравнение методологически некорректно."
    )
    doc.add_heading("3.3. Профилактический учёт", level=2)
    funnel = analysis["funnel"]["kaskelen"]
    _table(doc, ("Этап", "Численность"), [(f["stage"], _fmt(f["count"])) for f in funnel])
    doc.add_paragraph(
        "87 лиц на профучёте ОВД (алкоголь) при 333 F10 в наркологии и 825 ст.440 — "
        "критический индикатор формального характера индивидуальной профилактики (ст.59, приказ №163)."
    )

    # 4. Иргели
    doc.add_heading("4. Иргелинский сельский округ", level=1)
    doc.add_paragraph(
        "Численность: 63 152 в паспорте vs 43 100 (gov.kz) — реальный уровень ~51,0 на 10 тыс., "
        "а не 34,3. Дневной поток на рынке 80–90 тыс. не учитывается."
    )
    doc.add_paragraph(
        "УТК «Алтын Орда»: 88 фактов (раздел 7) vs 17 в ЕРДР; "
        "ЖК «Асыл Арман»: 46 vs 18. Требуется единая методика привязки."
    )
    doc.add_paragraph(
        "37 камер vs 226 в Каскелене; 51,7 % краж не раскрыто; "
        "16 алкозлоупотребляющих на учёте при 284 алкообъектах."
    )

    # 5. Комиссия
    doc.add_heading("5. Комиссия при акимате: поручения и исполнение", level=1)
    for sess in analysis.get("commission", []):
        doc.add_paragraph(f"Протокол {sess.get('id', '')}: {sess.get('assignments_count', 0)} поручений.")
        topics = sess.get("topics", {})
        topic_list = [k for k, v in topics.items() if v]
        if topic_list:
            doc.add_paragraph(f"Темы: {', '.join(topic_list)}.")
    doc.add_paragraph(
        "KPI исполнения в паспортах _итог (таблицы T36/T44) не заполнены — "
        "несоответствие ст.41–43 Закона о мониторинге эффективности мер."
    )

    # 6. Правовая оценка
    doc.add_heading("6. Правовая оценка и акты реагирования", level=1)
    legal_rows = []
    seen: set[str] = set()
    for g in flagged:
        leg = g.get("legal", {})
        key = leg.get("reaction_ref", "")
        if key in seen:
            continue
        seen.add(key)
        legal_rows.append((
            g.get("metric", "")[:40],
            leg.get("law", "")[:50],
            leg.get("subordinate", "")[:40],
            leg.get("reaction_title", ""),
        ))
    _table(doc, ("Разрыв", "Закон", "Подзаконный акт", "Акт по №32"), legal_rows[:12])

    # 7. Предложения прокурору
    doc.add_heading("7. Предложения прокурору района", level=1)
    _bullets(doc, (
        f"Внести представление ({ORDER32}) начальнику ОП о неполноте профилактического учёта "
        "и отсутствии взаимодействия с наркологией/психиатрией (ст.59, п.9; приказы №163, №814).",
        "Запросить у акима единую базу численности населения для расчёта уровня преступности.",
        "Потребовать заполнения KPI исполнения поручений комиссии (ст.41–43 Закона).",
        "Представление акимату о камерах и освещении в точках концентрации (ст.48–69).",
        "Контроль геопривязки 1-АД и ЕРДР к конкретным НП и объектам.",
    ))

    doc.add_paragraph("")
    doc.add_paragraph(analysis["conclusions"]["systemic"])

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
