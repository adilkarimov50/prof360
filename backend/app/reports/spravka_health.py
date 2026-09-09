"""Аналитическая справка по линии здравоохранения (ДСБ области).

Охват: алкогольная преступность, сеть УБДБ, исполнение поручений МВК,
профилактика алкоголизма и детоксикация.
"""
import io

from docx import Document
from docx.shared import Pt
from sqlalchemy.orm import Session

from app.ai import spravka_writer
from app.analytics import insights
from app.models.commission_session import CommissionAssignment, CommissionExecution, CommissionSession
from app.reports.generator import _docx_base
from app.reports.spravka import _conclusion

ORGAN_NAMES = (
    "денсаулық сақтау",
    "здравоохран",
    "дсб",
)

STATUS_RU = {
    "executed": "исполнено",
    "partial": "частично",
    "formal": "формально",
    "not_executed": "не исполнено",
    "unknown": "не оценено",
}


def _is_dsb_organ(name: str | None, organ_type: str | None) -> bool:
    if organ_type == "dsb":
        return True
    if not name:
        return False
    low = name.lower()
    return any(m in low for m in ORGAN_NAMES)


def _dsb_executions(db: Session) -> list[dict]:
    rows = (
        db.query(CommissionExecution, CommissionAssignment, CommissionSession)
        .join(CommissionAssignment, CommissionAssignment.id == CommissionExecution.assignment_id)
        .join(CommissionSession, CommissionSession.id == CommissionAssignment.session_id)
        .order_by(CommissionSession.session_date, CommissionAssignment.point_number)
        .all()
    )
    out: list[dict] = []
    for ex, asn, sess in rows:
        if not _is_dsb_organ(ex.organ_name, ex.organ_type):
            if asn.topic != "alcohol" and "убдб" not in (asn.text or "").lower():
                continue
            if not _is_dsb_organ(ex.organ_name, ex.organ_type):
                continue
        out.append({
            "session_number": sess.session_number,
            "session_date": sess.session_date,
            "session_type": sess.session_type,
            "point_number": asn.point_number,
            "assignment_text": asn.text,
            "topic": asn.topic,
            "organ_name": ex.organ_name,
            "execution_status": ex.execution_status,
            "quality_score": ex.quality_score,
            "ai_assessment": ex.ai_assessment,
            "issues": ex.issues or [],
        })
    return out


def _dsb_assignments(db: Session) -> list[dict]:
    """Поручения МВК, относящиеся к зоне ответственности ДСБ."""
    keywords = ("убдб", "детокс", "алкогол", "нарколог", "тoxic", "токсик")
    rows = (
        db.query(CommissionAssignment, CommissionSession)
        .join(CommissionSession, CommissionSession.id == CommissionAssignment.session_id)
        .order_by(CommissionSession.session_date, CommissionAssignment.point_number)
        .all()
    )
    out: list[dict] = []
    for asn, sess in rows:
        text = (asn.text or "").lower()
        if asn.topic == "alcohol" or any(k in text for k in keywords):
            out.append({
                "session_number": sess.session_number,
                "session_date": sess.session_date,
                "session_type": sess.session_type,
                "point_number": asn.point_number,
                "text": asn.text,
                "topic": asn.topic,
                "responsible_organs": asn.responsible_organs,
                "executions_count": len(asn.executions),
                "completion_rate": (
                    sum(
                        1 for e in asn.executions
                        if e.execution_status in ("executed", "partial")
                    ) / len(asn.executions) * 100
                    if asn.executions else 0
                ),
            })
    return out


def _health_facts(db: Session, df: str | None) -> str:
    comm = insights.commission_stats(db, df)
    alc = insights.alcohol_correlation(db, df)
    executions = _dsb_executions(db)
    assignments = _dsb_assignments(db)

    exec_lines = []
    for i, e in enumerate(executions, 1):
        exec_lines.append(
            f"{i}) Протокол №{e['session_number']} от {e['session_date'] or '—'} "
            f"(п. {e['point_number']}): статус «{STATUS_RU.get(e['execution_status'], e['execution_status'])}», "
            f"балл {e['quality_score'] if e['quality_score'] is not None else '—'}. "
            f"{e['ai_assessment'] or 'Оценка отсутствует.'}"
        )

    asn_lines = []
    for i, a in enumerate(assignments, 1):
        asn_lines.append(
            f"{i}) Заседание №{a['session_number']} ({a['session_date'] or '—'}), "
            f"п. {a['point_number']}: {a['text'][:300]}{'…' if len(a['text'] or '') > 300 else ''} "
            f"(ответов: {a['executions_count']}, исполнение ~{a['completion_rate']:.0f}%)."
        )

    avg_score = (
        sum(e["quality_score"] or 0 for e in executions) / len(executions)
        if executions else None
    )
    avg_line = (
        f"Средний балл исполнения ДСБ: {avg_score:.0f}%.\n"
        if avg_score is not None
        else "Средний балл исполнения ДСБ: не определён (нет оценённых ответов).\n"
    )

    return (
        "Орган: Департамент санитарно-эпидемиологического контроля / Денсаулық сақтау басқармасы "
        "Алматинской области (далее — ДСБ).\n\n"
        "СПРАВОЧНО по протоколам МВК 2026 (официальная статистика):\n"
        "- Преступления, совершённые в состоянии опьянения, 2025 г.: 604 (7,1% от всех).\n"
        "- Алкогольная преступность остаётся системным фактором криминогенности области.\n\n"
        f"Данные системы «Профилактика 360»:\n"
        f"- Алкогольных административных правонарушений: {comm['alcohol_admin_cases']}.\n"
        f"- Нарушителей в состоянии опьянения (зафиксировано): {comm['alcohol_intoxicated_offenders']}.\n"
        f"- Дел с полем «опьянение»: {alc['cases_with_intox_field']}.\n"
        f"- СБ-составы с опьянением: {alc['sb_with_intoxication']}.\n"
        f"- Алкогольные статьи с опьянением: {alc['alcohol_articles_with_intoxication']}.\n\n"
        f"Поручений МВК по линии ДСБ/УБДБ: {len(assignments)}.\n"
        f"Ответов ДСБ по поручениям: {len(executions)}.\n"
        f"{avg_line}"
        "\nПоручения МВК (зона ответственности здравоохранения):\n"
        + ("\n".join(asn_lines) or "Поручения не выявлены.")
        + "\n\nИсполнение поручений ДСБ:\n"
        + ("\n".join(exec_lines) or "Ответы ДСБ не зафиксированы.")
        + "\n\nКлючевые выявленные проблемы:\n"
        "- Единственный действующий УБДБ в Талгарском районе — 25 коек; здания 1960–1971 гг. постройки.\n"
        "- Предложения по открытию центров детоксикации в г. Конаев, Карасайском и Енбекшиказахском "
        "районах не представлены (протокол №1, п. 5.1 — частичное исполнение).\n"
        "- По внеочередному протоколу №1/1 от 26.02.2026 (п. 3) ответ ДСБ отсутствует — поручение "
        "не исполнено.\n"
        "- Отсутствует финансово-организационное решение по капремонту и расширению сети УБДБ."
    )


def _add_assignments_table(doc: Document, db: Session) -> None:
    assignments = _dsb_assignments(db)
    if not assignments:
        return
    doc.add_heading("Реестр поручений МВК по линии здравоохранения", level=2)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Заседание"
    hdr[1].text = "Пункт"
    hdr[2].text = "Поручение"
    hdr[3].text = "Ответов"
    hdr[4].text = "Исполнение"
    for a in assignments:
        row = table.add_row().cells
        stype = "внеоч." if a["session_type"] == "extraordinary" else "очеред."
        row[0].text = f"№{a['session_number']} ({stype})\n{a['session_date'] or '—'}"
        row[1].text = f"п. {a['point_number']}"
        row[2].text = (a["text"] or "")[:500]
        row[3].text = str(a["executions_count"])
        row[4].text = f"{a['completion_rate']:.0f}%"


def spravka_health_docx(db: Session, df: str | None, username: str, export_id: str) -> bytes:
    title = "Аналитическая справка по линии здравоохранения (ДСБ области)"
    doc = _docx_base(title, username, export_id)

    area = df or "Алматинская область"
    doc.add_paragraph(
        f"Настоящая справка подготовлена службой по защите общественных интересов прокуратуры "
        f"по результатам анализа работы органов здравоохранения ({area}) в сфере профилактики "
        f"алкогольной преступности, функционирования учреждений безусловного доставления "
        f"больных (УБДБ) и исполнения поручений Межведомственной комиссии по профилактике "
        f"правонарушений (МВК)."
    )

    facts = _health_facts(db, df)
    doc.add_heading("Аналитическая часть", level=2)
    text, _ = spravka_writer.write_section("health", facts)
    for para in text.split("\n"):
        para = para.strip()
        if para:
            doc.add_paragraph(para)

    _add_assignments_table(doc, db)

    doc.add_heading("Выводы по исполнению поручений МВК", level=2)
    doc.add_paragraph(
        "1. ДСБ области не обеспечило полноценное исполнение поручений МВК по расширению сети УБДБ "
        "и подготовке конкретных предложений по открытию центров детоксикации в отдалённых районах."
    )
    doc.add_paragraph(
        "2. По протоколу очередного заседания №1 (п. 5.1) представлен лишь описательный анализ "
        "без решения ключевого вопроса — где и когда будут открыты дополнительные центры."
    )
    doc.add_paragraph(
        "3. По внеочередному протоколу №1/1 от 26.02.2026 (п. 3) ответ не представлен, что свидетельствует "
        "о формальном отношении к поручениям председателя комиссии."
    )
    doc.add_paragraph(
        "4. Сохраняющаяся нагрузка на единственный УБДБ (25 мест, изношенное здание) не соответствует "
        "масштабу алкогольной преступности в области (604 преступления в состоянии опьянения в 2025 г.)."
    )

    _conclusion(doc)

    doc.add_paragraph()
    note = doc.add_paragraph(
        "Документ носит аналитический характер, сформирован с использованием данных системы "
        "«Профилактика 360» и протоколов МВК; подлежит проверке и подписанию уполномоченным прокурором."
    )
    note.runs[0].font.size = Pt(9)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
