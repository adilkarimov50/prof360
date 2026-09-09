"""Импорт папки документов МВК: извлечение протоколов, поручений и ответов органов."""
from __future__ import annotations

import io
import logging
import os
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai import llm
from app.commission.extract import extract_docx_text
from app.models.commission_session import CommissionAssignment, CommissionExecution, CommissionSession

logger = logging.getLogger("prof360.session_ingestor")

# Паттерны определения типа файла
_PROTOCOL_PATTERNS = [
    r"хатта?ма",
    r"прот[оа]кол",
    r"Күн тәртібі",
    r"повест",
]
_RESPONSE_PATTERNS = [
    r"жауап",
    r"ответ",
    r"орындалуы",
    r"баяндама",
    r"доклад",
    r"справ",
    r"анықтам",
    r"план",
    r"таблиц",
    r"информ",
    r"акп\.к",
    r"ИМ ",
]

_SESSION_NUM_RE = re.compile(r"[хх]аттама\s*[№#]?\s*(\d+[/\-]\d+|\d+)", re.I)
_DATE_RU_RE = re.compile(r"(\d{1,2})[.\s]+([а-яёА-ЯЁ]+)[.\s]+(\d{4})")
_DATE_NUM_RE = re.compile(r"(\d{2})[.\-](\d{2})[.\-](\d{4})")
_MONTHS_KZ = {
    "қаңтар": 1, "ақпан": 2, "наурыз": 3, "сәуір": 4, "мамыр": 5, "маусым": 6,
    "шілде": 7, "тамыз": 8, "қыркүйек": 9, "қазан": 10, "қараша": 11, "желтоқсан": 12,
}
_MONTHS_RU = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "май": 5, "июн": 6,
    "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}

# Ключевые слова тематики поручений
_TOPIC_KEYWORDS = {
    "cyber": ["интернет", "алаяқт", "мошенни", "кибер", "онлайн"],
    "extortion": ["вымогател", "бопсалау", "шантаж"],
    "juvenile": ["кәмелетке", "несовершеннолетн", "жасөспірім", "балалар"],
    "vape": ["вейп", "электронды темекі", "электрон темек", "301-1"],
    "alcohol": ["алкогол", "масаң", "детоксикац", "УБДБ", "ЦВАД"],
    "road": ["жол қауіпсіздіг", "дорожн", "жаяу жүргінші", "ПДД"],
    "law": ["жаңа заң", "профилактика туралы заң", "Заң күшіне"],
}


def _read_docx_bytes(path: str) -> str:
    try:
        with open(path, "rb") as f:
            b = f.read()
        return extract_docx_text(b)
    except Exception as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return ""


def _detect_type(filename: str, text: str) -> str:
    """Определить: протокол или ответ органа."""
    combined = (filename + " " + text[:500]).lower()
    if any(re.search(p, combined, re.I) for p in _PROTOCOL_PATTERNS):
        return "protocol"
    if any(re.search(p, combined, re.I) for p in _RESPONSE_PATTERNS):
        return "response"
    return "unknown"


def _extract_date(text: str) -> tuple[int | None, int | None, int | None]:
    """Возвращает (день, месяц, год)."""
    m = _DATE_NUM_RE.search(text[:1000])
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 2020 <= y <= 2030:
            return d, mo, y
    m = _DATE_RU_RE.search(text[:1000])
    if m:
        day = int(m.group(1))
        mon_word = m.group(2).lower()[:6]
        year = int(m.group(3))
        mon = _MONTHS_KZ.get(mon_word) or _MONTHS_RU.get(mon_word)
        if mon and 2020 <= year <= 2030:
            return day, mon, year
    return None, None, None


def _detect_topic(text: str) -> str:
    low = text.lower()
    for topic, kws in _TOPIC_KEYWORDS.items():
        if any(kw in low for kw in kws):
            return topic
    return "other"


def _detect_organ(filename: str, text: str) -> tuple[str, str]:
    """Определить имя органа и тип из файла/текста."""
    combined = (filename + " " + text[:800]).lower()
    organ_map = [
        ("Кеген ауданы", "akimat", ["кеген"]),
        ("Балхаш ауданы", "akimat", ["балқаш", "балхаш"]),
        ("Талгар ауданы", "akimat", ["талғар", "талгар"]),
        ("Конаев қаласы", "akimat", ["конаев"]),
        ("Алатау қаласы", "akimat", ["алатау қаласы", "алатау қала"]),
        ("Жамбыл ауданы", "akimat", ["жамбыл аудан"]),
        ("Еңбекшіқазақ ауданы", "akimat", ["еңбекшіқазақ", "енбекшиказах"]),
        ("Уйгур ауданы", "akimat", ["ұйғыр", "уйгур"]),
        ("Іле ауданы", "akimat", ["іле аудан", "иле аудан"]),
        ("Карасай ауданы", "akimat", ["қарасай", "карасай"]),
        ("Білім басқармасы", "education", ["білім басқармас", "образования"]),
        ("ПД ҚҚБ", "pd", ["қоғамдық қауіпсіздік басқармас", "тасыбаев", "уоб"]),
        ("ПД УБОП", "pd", ["ұйымдасқан қылмыс", "сатылғанов", "убоп"]),
        ("ПД бастығы", "pd", ["ашимов", "пд басш", "бірінші орынбасары"]),
        ("Денсаулық сақтау басқармасы", "dsb", ["денсаулық сақтау", "жүнісова", "дсб"]),
        ("Жастар саясаты басқармасы", "other", ["жастар саясаты"]),
    ]
    for name, otype, keywords in organ_map:
        if any(kw in combined for kw in keywords):
            return name, otype
    return "Белгісіз орган", "other"


def _extract_session_number(filename: str, text: str) -> str:
    combined = filename + " " + text[:800]
    m = re.search(r"№\s*(\d+/\d+|\d+)", combined)
    if m:
        return m.group(1)
    m = _SESSION_NUM_RE.search(combined)
    if m:
        return m.group(1)
    return "?"


def _extract_point_numbers(text: str) -> list[str]:
    """Вытащить упоминаемые пункты поручений из текста ответа."""
    pts = re.findall(r"\b(\d+\.\d+(?:\.\d+)?)\b", text[:3000])
    seen, result = set(), []
    for p in pts:
        if p not in seen and re.match(r"^\d\.\d", p):
            seen.add(p)
            result.append(p)
    return result[:10]


AI_EXTRACT_SYSTEM = (
    "Ты прокурор-аналитик. Анализируешь документы заседания МВК по профилактике правонарушений. "
    "Отвечай строго в JSON без markdown."
)


def _ai_extract_assignments(session_text: str, session_num: str) -> list[dict]:
    """AI-извлечение структурированных поручений из текста повестки/протокола."""
    if not llm.is_available():
        return []
    prompt = f"""Из текста заседания МВК №{session_num} извлеки все поручения председателя.

Текст:
---
{session_text[:8000]}
---

Верни JSON-массив:
[
  {{
    "point_number": "2.1",
    "text": "полный текст поручения",
    "responsible_organs": "кому адресовано",
    "deadline": "срок (если указан)",
    "topic": "cyber|extortion|juvenile|vape|alcohol|road|law|other"
  }}
]

Если поручений нет — верни [].
"""
    raw = llm.generate(prompt, system=AI_EXTRACT_SYSTEM, temperature=0.1, max_tokens=4096)
    data = llm.parse_json_from_llm(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "assignments" in data:
        return data["assignments"]
    return []


def _ai_assess_execution(assignment_text: str, response_text: str, organ: str) -> dict:
    """AI-оценка качества исполнения поручения органом."""
    if not llm.is_available():
        return {"execution_status": "unknown", "quality_score": None, "ai_assessment": "", "issues": []}
    prompt = f"""Оцени исполнение поручения МВК органом.

Поручение:
{assignment_text[:1000]}

Орган: {organ}
Ответ органа:
{response_text[:3000]}

Верни JSON:
{{
  "execution_status": "executed|partial|formal|not_executed",
  "quality_score": 0-100,
  "ai_assessment": "краткая оценка в 1-2 предложения",
  "issues": ["список конкретных замечаний если есть"]
}}

executed = полностью исполнено с реальными результатами
partial = исполнено частично
formal = формальный ответ без реальных действий
not_executed = не исполнено
"""
    raw = llm.generate(prompt, system=AI_EXTRACT_SYSTEM, temperature=0.15, max_tokens=1024)
    result = llm.parse_json_from_llm(raw) or {}
    status = result.get("execution_status", "unknown")
    if status not in ("executed", "partial", "formal", "not_executed"):
        status = "unknown"
    return {
        "execution_status": status,
        "quality_score": float(result["quality_score"]) if isinstance(result.get("quality_score"), (int, float)) else None,
        "ai_assessment": str(result.get("ai_assessment") or ""),
        "issues": result.get("issues") if isinstance(result.get("issues"), list) else [],
    }


def ingest_folder(
    db: Session,
    folder_path: str,
    session_number: str | None = None,
    session_date_str: str | None = None,
    session_type: str = "ordinary",
    force: bool = False,
) -> dict:
    """
    Сканирует папку с документами МВК.
    Создаёт CommissionSession + CommissionAssignment + CommissionExecution.
    Возвращает сводку.
    """
    if not os.path.isdir(folder_path):
        return {"error": f"Папка не найдена: {folder_path}"}

    files = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith((".docx", ".doc"))
    ]
    if not files:
        return {"error": "Нет .docx файлов в папке"}

    # Читаем все файлы
    file_data: list[dict] = []
    for fname in files:
        path = os.path.join(folder_path, fname)
        text = _read_docx_bytes(path)
        ftype = _detect_type(fname, text)
        file_data.append({"filename": fname, "path": path, "text": text, "type": ftype})

    # Определяем заседания: одно или несколько
    sessions_texts: dict[str, list[dict]] = {}
    for fd in file_data:
        snum = _extract_session_number(fd["filename"], fd["text"])
        sessions_texts.setdefault(snum, []).append(fd)

    created_sessions = []
    for snum, docs in sessions_texts.items():
        if session_number and snum != session_number and session_number != "auto":
            continue

        # Определяем дату из первого документа
        date_obj = None
        for doc in docs:
            d, m, y = _extract_date(doc["text"])
            if d and m and y:
                try:
                    from datetime import date
                    date_obj = date(y, m, d)
                except Exception:
                    pass
                break

        if session_date_str:
            try:
                date_obj = datetime.strptime(session_date_str, "%Y-%m-%d").date()
            except Exception:
                pass

        year = date_obj.year if date_obj else None
        quarter = ((date_obj.month - 1) // 3 + 1) if date_obj else None

        # Проверка дубликата
        existing = db.query(CommissionSession).filter(
            CommissionSession.session_number == snum,
            CommissionSession.year == year,
        ).first()
        if existing and not force:
            created_sessions.append({
                "session_number": snum, "status": "exists", "id": existing.id
            })
            continue

        # Собираем текст повестки/протоколов для извлечения поручений
        agenda_text = ""
        for doc in docs:
            if doc["type"] == "protocol" or "Күн тәртібі" in doc["filename"]:
                agenda_text += "\n\n" + doc["text"]
        if not agenda_text:
            agenda_text = "\n\n".join(d["text"] for d in docs[:3])

        # AI-извлечение поручений
        assignments_raw = _ai_extract_assignments(agenda_text, snum)

        session = CommissionSession(
            session_number=snum,
            session_date=date_obj,
            session_type=session_type,
            quarter=quarter,
            year=year,
            agenda_raw=agenda_text[:5000],
        )
        db.add(session)
        db.flush()

        assignments_map: dict[str, CommissionAssignment] = {}
        if assignments_raw:
            for a in assignments_raw:
                if not isinstance(a, dict):
                    continue
                pt = str(a.get("point_number") or "?").strip()
                assignment = CommissionAssignment(
                    session_id=session.id,
                    point_number=pt,
                    text=str(a.get("text") or ""),
                    responsible_organs=str(a.get("responsible_organs") or ""),
                    deadline=str(a.get("deadline") or ""),
                    topic=str(a.get("topic") or _detect_topic(str(a.get("text") or ""))),
                    priority="high" if a.get("topic") in ("cyber", "juvenile", "extortion") else "medium",
                )
                db.add(assignment)
                db.flush()
                assignments_map[pt] = assignment

        # Если AI не вернул поручения — создаём по пунктам из ответов
        if not assignments_map:
            all_points: set[str] = set()
            for doc in docs:
                if doc["type"] == "response":
                    for pt in _extract_point_numbers(doc["text"]):
                        all_points.add(pt)
            for pt in sorted(all_points):
                assignment = CommissionAssignment(
                    session_id=session.id,
                    point_number=pt,
                    text=f"Поручение по пункту {pt} (текст не извлечён из протокола)",
                    topic=_detect_topic(agenda_text),
                )
                db.add(assignment)
                db.flush()
                assignments_map[pt] = assignment

        # Обрабатываем ответы органов
        executions_created = 0
        for doc in docs:
            if doc["type"] != "response" or not doc["text"].strip():
                continue
            organ_name, organ_type = _detect_organ(doc["filename"], doc["text"])
            mentioned_points = _extract_point_numbers(doc["text"])

            # Если ни одного пункта не нашли — привязываем ко всем поручениям сессии
            target_points = mentioned_points if mentioned_points else list(assignments_map.keys())[:3]

            for pt in target_points:
                if pt not in assignments_map:
                    continue
                assignment = assignments_map[pt]
                # Проверка дубликата
                dup = db.query(CommissionExecution).filter(
                    CommissionExecution.assignment_id == assignment.id,
                    CommissionExecution.organ_name == organ_name,
                ).first()
                if dup:
                    continue
                execution = CommissionExecution(
                    assignment_id=assignment.id,
                    organ_name=organ_name,
                    organ_type=organ_type,
                    source_file=doc["filename"],
                    response_text=doc["text"][:5000],
                    execution_status="unknown",
                )
                db.add(execution)
                db.flush()
                executions_created += 1

        db.commit()
        created_sessions.append({
            "session_number": snum,
            "status": "created",
            "id": session.id,
            "assignments": len(assignments_map),
            "executions": executions_created,
            "files_processed": len(docs),
        })

    return {"sessions": created_sessions, "total_files": len(files)}


def assess_session_executions(db: Session, session_id: int) -> dict:
    """AI-оценка качества исполнения каждого поручения каждым органом."""
    session = db.query(CommissionSession).filter(CommissionSession.id == session_id).first()
    if not session:
        return {"error": "Заседание не найдено"}

    assessed = 0
    for assignment in session.assignments:
        for execution in assignment.executions:
            if execution.execution_status not in ("unknown", None) and not True:
                continue
            result = _ai_assess_execution(
                assignment_text=assignment.text,
                response_text=execution.response_text or "",
                organ=execution.organ_name,
            )
            execution.execution_status = result["execution_status"]
            execution.quality_score = result["quality_score"]
            execution.ai_assessment = result["ai_assessment"]
            execution.issues = result["issues"]
            execution.analyzed_at = datetime.utcnow()
            assessed += 1

    db.commit()
    return {"assessed": assessed, "session_id": session_id}
