"""Update criminological passport for s. Chundzha with admin/commission/law sections."""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from koap_titles_fallback import title_for  # noqa: E402

PASSPORT_IN = ROOT / "Уйгур, Чунджа" / "Криминологическии: паспорт Чунджа.docx"
PASSPORT_OUT = ROOT / "Уйгур, Чунджа" / "Криминологический_паспорт_Чунджа_2026.docx"
STATS_PATH = ROOT / "Уйгур, Чунджа" / "chundzha_adm_stats.json"


def load_stats() -> dict:
    return json.loads(STATS_PATH.read_text(encoding="utf-8"))


def replace_blanks(text: str, value: str) -> str:
    if "_____" in text or text.strip() in ("—", "-", ""):
        return value
    return text


def set_cell_if_blank(cell, value: str) -> None:
    t = cell.text.strip()
    if "_____" in t or t in ("—", "-", ""):
        cell.text = value


def fill_socio_tables(doc: Document, stats: dict) -> None:
    """Fill section 2 blanks and tables 22–27 where data exists."""
    for table in doc.tables:
        for row in table.rows:
            label = row.cells[0].text.strip()
            if len(row.cells) < 2:
                continue
            val_cell = row.cells[1]

            if "Количество субъектов предпринимательства" in label:
                set_cell_if_blank(val_cell, "25 субъектов (защищены права прокуратурой района); "
                                         "3 инвестора (37 млрд тенге) — данные КРАС за 1 кв. 2026")
            elif "Количество получателей АСП" in label:
                set_cell_if_blank(val_cell, "подлежит запросу в управлении координации занятости "
                                         "и социальных программ акимата")
            elif "Количество организаций образования" in label:
                set_cell_if_blank(val_cell, "31 школа; 7 006 учащихся (нарушены права — КРАС); "
                                         "10 школ с 10 клубами (268 детей)")
            elif "NEET" in label or "не учится и не работ" in label.lower():
                set_cell_if_blank(val_cell, "подлежит запросу (ЦЗН, акимат)")
            elif "Среднемесячная заработная плата по с. Чунджа" in label:
                set_cell_if_blank(val_cell, "подлежит запросу в управлении статистики")
            elif "Камеры, подключенные к системе ОВД" in label:
                set_cell_if_blank(val_cell, "подлежит установлению (≈70 частных камер не интегрированы)")
            elif "Камеры на УДС" in label:
                set_cell_if_blank(val_cell, "подлежит запросу в акимате")
            elif "Освещение улиц" in label:
                set_cell_if_blank(val_cell, "подлежит запросу в акимате (ул. Онгарова, окраины)")
            elif "Иные спортивные секции" in label:
                set_cell_if_blank(val_cell, "подлежит запросу в отделе физкультуры и спорта")

            # Table 22 — profilakticheskiy uchet
            if "Ранее судимые" in label:
                set_cell_if_blank(val_cell, "подлежит запросу (ОВД)")
            elif "Под пробацией" in label:
                set_cell_if_blank(val_cell, "подлежит запросу (СИ)")
            elif "Семейные дебоширы" in label:
                set_cell_if_blank(val_cell, "подлежит запросу (ОВД, центр поддержки семьи)")
            elif label.startswith("Несовершеннолетние") and "15." not in label:
                set_cell_if_blank(val_cell, "8 фактов в отношении н/л (2026); 1 лицо — совершившее")
            elif "алкогольной зависимостью" in label.lower():
                set_cell_if_blank(val_cell, "19 % эпизодов преступлений в состоянии опьянения (угол.)")
            elif "наркотической зависимостью" in label.lower():
                set_cell_if_blank(val_cell, "1 факт наркопреступления (2026)")

            # Table 23 — objects
            if "Объекты реализации алкоголя" in label:
                set_cell_if_blank(val_cell, "подлежит запросу (ОВД); выявлено 3 нарушения в "
                                         "развлекательных/торговых объектах (КРАС)")
            elif "Увеселительные заведения" in label:
                set_cell_if_blank(val_cell, "16 объектов общепита без санразрешений (КРАС)")
            elif "Гостиницы" in label:
                set_cell_if_blank(val_cell, "«Алма Парк», «Уют» — места концентрации преступлений")
            elif "Места стоянки грузового транспорта" in label:
                set_cell_if_blank(val_cell, "ул. Онгарова — 2 кражи")

            # Table 24 — family violence
            if "Количество преступлений" in label and len(row.cells) == 3:
                hdr = table.rows[0].cells[0].text
                if "Семейно-бытовая" in hdr or "семейно-быт" in str(table.rows[0].cells[0].text).lower():
                    if "2025" in label or "2026" in label or "Количество" in label:
                        pass
            if "Защитные предписания" in label:
                set_cell_if_blank(val_cell, "подлежит запросу (ОВД)")
            elif "Особые требования" in label:
                set_cell_if_blank(val_cell, "подлежит запросу (суд, ОВД)")
            elif "Семьи риска" in label:
                set_cell_if_blank(val_cell, "1 176 семей (мобильная группа); 177 семей FSM Social")
            elif "доставленных в центр" in label.lower():
                set_cell_if_blank(val_cell, "подлежит запросу (центр поддержки семьи)")

            # Table 27 — livestock
            if "Количество крестьянских хозяйств" in label:
                set_cell_if_blank(val_cell, "подлежит запросу (акимат)")
            elif "Зарегистрировано фактов" in label and "скот" in str(table.rows[0].cells[0].text).lower():
                set_cell_if_blank(val_cell, "подлежит запросу (нет данных в источниках)")


def _insert_paragraph_after(paragraph, text: str, style: str = "Normal") -> None:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    from docx.text.paragraph import Paragraph
    p = Paragraph(new_p, paragraph._parent)
    p.style = style
    p.text = text
    return p


def build_section_17_admin(stats: dict) -> list[str]:
    n = stats["chundzha_count"]
    share = stats["chundzha_share_pct"]
    lines = [
        f"За период {stats['period']} по данным формы 1-АД зарегистрировано {n} административных "
        f"правонарушений, совершённых на территории с. Чунджа (Шонжы), что составляет {share} % "
        f"от всех дел по Уйгурскому району ({stats['district_total']}).",
        "Структура по основным статьям КоАП (топ-10):",
    ]
    for i, item in enumerate(stats["articles_top"][:10], 1):
        tit = title_for(item["name"])
        pct = round(item["count"] / n * 100, 1)
        lines.append(f"{i}. {item['name']} ({tit}) — {item['count']} ({pct} %).")
    m = stats["measures"]
    warn = next((x["count"] for x in m if "предупреждение" in x["name"]), 0)
    arrest = next((x["count"] for x in m if "арест" in x["name"]), 0)
    fine = sum(x["count"] for x in m if "штраф" in x["name"])
    lines += [
        f"По решениям: с наложением взыскания — "
        f"{next(x['count'] for x in stats['decisions'] if 'наложением' in x['name'])}; "
        f"погашение штрафа — "
        f"{next(x['count'] for x in stats['decisions'] if 'погашение' in x['name'])}.",
        f"Меры: предупреждение — {warn}; штраф/сокращённое — {fine}; арест — {arrest}. "
        f"Сумма штрафов (где указана): {stats['fines']['sum_total']:,} тенге.",
        "Портрет нарушителя (адм.): мужчины — 82,8 %; доминирует возраст 30–49 лет (50,4 %). "
        "Основные подразделения: ДПП и УИП МПС Уйгурского РОВД.",
        "Криминологический вывод: административная практика концентрируется на дорожно-транспортных "
        "и санитарных нарушениях; доля дел по управлению в состоянии опьянения (ст.612) — 10,5 %.",
    ]
    return lines


def build_section_18_commission() -> list[str]:
    return [
        "По исполнению поручений областной межведомственной комиссии по профилактике правонарушений "
        "(протокол №1 от 12.02.2026) акимат района представил отчёт (исх. № 02-27 от 26.03.2026).",
        "За 1 квартал 2026 г. в районе зарегистрировано 34 уголовных правонарушения "
        "(−33,3 % к АППГ); уровень на 10 тыс. населения — 22 (один из минимальных в области).",
        "Выполнено: утверждён план совместных мероприятий с ОВД; установлено 14 билбордов "
        "по профилактике интернет-мошенничества; проведено 11 профилактических мероприятий "
        "с молодёжью; проекты «Бақытты отбасы», «Салауатты сана», «Ана – медиатор».",
        "Проблемные направления (рост к АППГ): преступления в состоянии опьянения (8→16), "
        "мошенничество (48→58), интернет-мошенничество (43→46). По протоколу №1/1 (26.02.2026) "
        "работа по разъяснению Закона № 245-VIII и мониторингу безопасности дорог — в процессе.",
        "Прокуратура района (КРАС): проведено 2 проверки, 25 анализов (67 АППГ), 18 представлений, "
        "36 протестов; по линии профилактики — 1 анализ, 3 нарушения, 2 акта надзора.",
        "Криминологический вывод: формально отчётность по поручениям МВК исполняется, однако "
        "количество анализов сократилось в 2,7 раза; данные по профилактическому учёту, "
        "защитным предписаниям и заседаниям районной комиссии в первичных материалах отсутствуют.",
    ]


def build_section_19_zoi() -> list[str]:
    return [
        "За 6 месяцев 2026 г. (КРАС прокуратуры области по Уйгурскому району): выявлено 92 "
        "нарушения (210 АППГ), устранено 73; внесено 18 представлений и 36 протестов.",
        "Финансовый результат: взыскано в доход государства 48 931 424 тенге; возвращено "
        "имущества на 29 097 750 тенге; административные штрафы — 501 700 тенге; "
        "предотвращено необоснованное расходование 9 649 999 тенге.",
        "К административной ответственности привлечено 31 лицо, к дисциплинарной — 132 "
        "(рост с 26). Защищены права 4 182 граждан, в т.ч. 4 155 детей.",
        "Системные проблемы: некачественное исполнение поручений по «Мобильному прокурору» "
        "(3 из 6 инвесторов), монополиям, бюджетному надзору (бюджет 8,1 млрд тенге), "
        "поливной воде, акции «Таза Қазақстан» (результаты по АПН — нулевые).",
        "Социальная сфера: нарушены права 7 006 учащихся; привлечены 65 педагогов (5 директоров).",
        "Криминологический вывод: надзорная работа по защите социальных прав эффективна по "
        "количественным показателям, но не компенсирует дефицит профилактики на местах "
        "(мусор, связь, интернет, поливная вода).",
    ]


def build_section_20_law() -> list[str]:
    return [
        "С 2 марта 2026 г. действует Закон РК «О профилактике правонарушений» от 30.12.2025 "
        "№ 245-VIII ЗРК (отменяет Закон 2010 г. № 271-IV и 4 смежных акта).",
        "Обязанности акимата с. Чунджа / Уйгурского района (ст. 9 п. 2): общая профилактика, "
        "создание организаций помощи, кабинетов помощи детям-жертвам насилия, официальные "
        "предостережения, социальная инфраструктура для несовершеннолетних.",
        "Межведомственная комиссия (ст. 38): координация субъектов; оценка эффективности мер "
        "по бытовому насилию, опьянению и правонарушениям в общественных местах — на заседаниях "
        "региональной комиссии (ст. 72 п. 4 — раз в полугодие по семьям в ТЖС).",
        "Индивидуальная профилактика (ст. 48–61): профилактическая беседа, официальное "
        "предостережение (30 суток, контроль 2 раза/мес.), защитное предписание (30 суток, "
        "проверка 1 раз/7 дней), профилактический учёт (ст. 59).",
        "Специальные меры (ст. 75): установка камер видеонаблюдения, патрулирование, контроль "
        "«горячих точек» — соответствует выявленным криминогенным объектам паспорта (Заготзерно, "
        "ул. Онгарова, гостиницы).",
        "Оценка соответствия для с. Чунджа: частичное — мероприятия по МВК и мобильная группа "
        "реализуются; пробелы — интеграция ≈70 частных камер (0 меморандумов), профучёт, "
        "территориальные программы по семьям в ТЖС, камеры/освещение на УДС (ст. 75 п. 4).",
    ]


def renumber_old_sections(doc: Document) -> None:
    for p in doc.paragraphs:
        if p.text.strip().startswith("17. Приоритетные"):
            p.text = "21. Приоритетные профилактические мероприятия"
        elif p.text.strip().startswith("18. Ожидаемые"):
            p.text = "22. Ожидаемые результаты"


def insert_new_sections(doc: Document, stats: dict) -> None:
    target = None
    for p in doc.paragraphs:
        if p.text.strip().startswith("17. Приоритетные") or p.text.strip().startswith("21. Приоритетные"):
            target = p
            break
    if target is None:
        raise RuntimeError("Section 17/21 not found")

    sections = [
        ("17. Административная практика (форма 1-АД)", build_section_17_admin(stats)),
        ("18. Работа комиссии по профилактике правонарушений", build_section_18_commission()),
        ("19. Надзорная деятельность прокуратуры (ЗОИ)", build_section_19_zoi()),
        ("20. Соответствие Закону «О профилактике правонарушений» № 245-VIII", build_section_20_law()),
    ]

    for heading, body_lines in sections:
        for line in reversed(body_lines):
            bp = target.insert_paragraph_before(line)
            bp.style = "Normal"
        hp = target.insert_paragraph_before(heading)
        hp.style = "Heading 1"
        target.insert_paragraph_before("")

    renumber_old_sections(doc)


def add_admin_measures(doc: Document) -> None:
    extras = [
        "Провести адресный анализ административных правонарушений по ст.612 (управление в "
        "состоянии опьянения) с сопоставлением уголовной алкогольной статистики.",
        "Обеспечить учёт и отчётность по защитным предписаниям и официальным предостережениям "
        "в соответствии со ст. 51, 60 Закона № 245-VIII.",
        "Довести до населения с. Чунджа порядок работы «Мобильного прокурора» и механизмы "
        "обращения по инфраструктурным проблемам (связь, мусор, поливная вода).",
        "Организовать информационную кампанию по профилактике интернет-мошенничества "
        "(продолжение работы 14 билбордов, WhatsApp-группы участковых).",
    ]
    in_list = False
    for p in doc.paragraphs:
        if p.text.strip().startswith("22. Ожидаемые"):
            break
        if "Обеспечить взаимодействие с ЦЗН" in p.text:
            in_list = True
            continue
        if in_list and p.style.name == "List Paragraph" and "ЦЗН" in p.text:
            parent = p._element.getparent()
            idx = list(parent).index(p._element)
            for i, txt in enumerate(extras):
                new_p = deepcopy(p._element)
                parent.insert(idx + 1 + i, new_p)
                from docx.text.paragraph import Paragraph
                np = Paragraph(new_p, p._parent)
                np.text = txt
                np.style = "List Paragraph"
            break

    expected = [
        "Снижение административных правонарушений по ст.612 и ст.590 на территории с. Чунджа.",
        "Повышение доли исполненных поручений районной комиссии по профилактике правонарушений.",
        "Налаживание учёта мер индивидуальной профилактики по Закону № 245-VIII.",
    ]
    for p in doc.paragraphs:
        if p.text.strip().startswith("22. Ожидаемые"):
            anchor = p
            for txt in reversed(expected):
                ap = anchor._element
                parent = ap.getparent()
                from docx.text.paragraph import Paragraph
                new_el = OxmlElement("w:p")
                ap.addnext(new_el)
                np = Paragraph(new_el, anchor._parent)
                np.text = txt
                np.style = "List Paragraph"
            break


def update_abbreviations(doc: Document) -> None:
    for table in doc.tables:
        if table.rows and "КоАП" in table.rows[-1].cells[0].text:
            return
        if table.rows and table.rows[0].cells[0].text.strip() == "Сокращение":
            row = table.add_row()
            row.cells[0].text = "КоАП"
            row.cells[1].text = "Кодекс об административных правонарушениях"
            row = table.add_row()
            row.cells[0].text = "МВК"
            row.cells[1].text = "Межведомственная комиссия по профилактике правонарушений"
            row = table.add_row()
            row.cells[0].text = "ЗОИ"
            row.cells[1].text = "Защита общественных интересов (надзор прокуратуры)"
            row = table.add_row()
            row.cells[0].text = "ТЖС"
            row.cells[1].text = "Трудная жизненная ситуация"
            break


def add_admin_articles_table(doc: Document, stats: dict) -> None:
    """Insert admin articles table after section 17 heading."""
    target = None
    for p in doc.paragraphs:
        if p.text.strip().startswith("17. Административная"):
            target = p
            break
    if not target:
        return

    table = doc.add_table(rows=1, cols=4)
    hdr = table.rows[0].cells
    hdr[0].text = "Статья КоАП"
    hdr[1].text = "Содержание"
    hdr[2].text = "Кол-во"
    hdr[3].text = "Доля, %"
    n = stats["chundzha_count"]
    for item in stats["articles_top"][:12]:
        row = table.add_row().cells
        row[0].text = item["name"]
        row[1].text = title_for(item["name"])
        row[2].text = str(item["count"])
        row[3].text = f"{round(item['count'] / n * 100, 1)} %"
    # Place table immediately after section 17 intro paragraphs (before section 18)
    sec18 = None
    for p in doc.paragraphs:
        if p.text.strip().startswith("18. Работа комиссии"):
            sec18 = p
            break
    if sec18:
        sec18._element.addprevious(table._tbl)
    else:
        target._element.addnext(table._tbl)


def main() -> None:
    stats = load_stats()
    doc = Document(str(PASSPORT_IN))
    fill_socio_tables(doc, stats)
    insert_new_sections(doc, stats)
    add_admin_articles_table(doc, stats)
    add_admin_measures(doc)
    update_abbreviations(doc)
    doc.save(str(PASSPORT_OUT))
    print(f"Saved: {PASSPORT_OUT}")


if __name__ == "__main__":
    main()
