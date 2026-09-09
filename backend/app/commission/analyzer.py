"""Двухэтапный ИИ-анализ документов комиссии."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.ai import llm
from app.analytics import insights
from app.commission import legal_check

DOC_TYPE_LABELS = {
    "protocol": "протокол заседания комиссии",
    "report": "доклад",
    "execution_plan": "план исполнения",
}

STAGE1_SYSTEM = (
    "Ты прокурор-аналитик, проверяющий документы комиссии по профилактике правонарушений. "
    "Отвечай строго в формате JSON без markdown."
)

STAGE2_SYSTEM = (
    "Ты прокурор-аналитик Алматинской области. Оцениваешь исполнение и целесообразность мер профилактики "
    "с учётом реальной криминогенной обстановки района. "
    "Актуальные приоритеты МВК по профилактике: интернет-мошенничество (рост 16,4% в 2025 г.), "
    "вымогательство (рост в Талгарском +14,5 раза), преступность несовершеннолетних (рост 31,6%), "
    "незаконный оборот вейпов (ст.301-1 УК), алкогольная преступность. "
    "Отвечай строго в формате JSON без markdown."
)


def _stage1_prompt(doc_type: str, district: str, period: str, text: str) -> str:
    label = DOC_TYPE_LABELS.get(doc_type, doc_type)
    return f"""Проанализируй документ комиссии ({label}) для района «{district}», период {period}.

Текст документа:
---
{text[:12000]}
---

Верни JSON:
{{
  "detected_type": "protocol|report|execution_plan|other",
  "title_guess": "краткое название",
  "requisites": {{
    "date": {{"present": true/false, "value": "...", "comment": "..."}},
    "commission_composition": {{"present": true/false, "comment": "..."}},
    "agenda": {{"present": true/false, "comment": "..."}},
    "decisions": {{"present": true/false, "comment": "..."}},
    "deadlines": {{"present": true/false, "comment": "..."}},
    "responsible_persons": {{"present": true/false, "comment": "..."}},
    "signatures": {{"present": true/false, "comment": "..."}}
  }},
  "assignments": [
    {{"text": "формулировка поручения", "responsible": "должностное лицо/орган", "deadline": "срок", "execution_status": "исполнено|не исполнено|частично|не указано"}}
  ],
  "assignments_quality": "оценка конкретности и измеримости поручений",
  "deficiencies": ["список недостатков"],
  "quality_score": 0-100,
  "summary": "краткий вывод по качеству документа"
}}"""


def _stage2_prompt(
    doc_type: str,
    district: str,
    period: str,
    text: str,
    stage1: dict,
    district_context: dict,
    articles: list[dict],
) -> str:
    label = DOC_TYPE_LABELS.get(doc_type, doc_type)
    ctx = json.dumps(district_context, ensure_ascii=False, indent=2)
    arts = json.dumps(articles[:10], ensure_ascii=False)
    s1 = json.dumps(stage1, ensure_ascii=False)[:4000]
    return f"""Документ: {label}, район «{district}», период {period}.

Результат этапа 1 (качество документа):
{s1}

Данные по району из системы «Профилактика 360»:
{ctx}

Топ статей административной практики в районе:
{arts}

Текст документа (фрагмент):
---
{text[:10000]}
---

Оцени исполнение, целесообразность и эффективность мер. Верни JSON:
{{
  "execution_assessment": "исполнимость и факт исполнения поручений",
  "execution_score": 0-100,
  "feasibility": "целесообразность мер относительно обстановки района",
  "feasibility_score": 0-100,
  "effectiveness": "реальный эффект vs формальность",
  "effectiveness_score": 0-100,
  "district_alignment": "насколько меры соответствуют рискам района",
  "include_recommendation": "yes|revise|no",
  "include_recommendation_label": "да|с доработкой|нет",
  "justification": "обоснование рекомендации",
  "suggestions": ["конкретные предложения"],
  "summary": "итоговый вывод"
}}

include_recommendation: yes = включать в протокол, revise = с доработкой, no = не включать."""


def analyze_document(
    db: Session,
    *,
    doc_type: str,
    district: str,
    period: str,
    text: str,
    file_bytes: bytes | None = None,
    mime_type: str | None = None,
) -> tuple[dict, dict, dict, float | None, float | None, float | None, str | None]:
    """Трёхэтапный анализ. Возвращает (stage1, stage2, legal, quality, effectiveness, legal_score, recommendation)."""
    p1 = _stage1_prompt(doc_type, district, period, text)
    raw1 = llm.analyze_multimodal(
        p1,
        file_bytes=file_bytes,
        mime_type=mime_type,
        system=STAGE1_SYSTEM,
        temperature=0.15,
        max_tokens=4096,
    )
    stage1 = llm.parse_json_from_llm(raw1) or {
        "summary": raw1 or "Анализ недоступен",
        "quality_score": None,
        "deficiencies": [],
        "assignments": [],
    }

    stage_legal, legal_score = legal_check.check_compliance(
        db,
        doc_type=doc_type,
        district=district,
        text=text,
        stage1=stage1,
    )

    counters = insights.overview_counters(db, district)
    articles = insights.article_stats(db, limit=10, district_filter=district)
    p2 = _stage2_prompt(doc_type, district, period, text, stage1, counters, articles)
    raw2 = llm.analyze_multimodal(
        p2,
        system=STAGE2_SYSTEM,
        temperature=0.15,
        max_tokens=4096,
    )
    stage2 = llm.parse_json_from_llm(raw2) or {
        "summary": raw2 or "Анализ недоступен",
        "include_recommendation": "revise",
        "include_recommendation_label": "с доработкой",
    }

    quality = stage1.get("quality_score")
    if isinstance(quality, (int, float)):
        quality = float(max(0, min(100, quality)))
    else:
        quality = None

    eff = stage2.get("effectiveness_score")
    if isinstance(eff, (int, float)):
        eff = float(max(0, min(100, eff)))
    else:
        eff = None

    rec = stage2.get("include_recommendation") or stage2.get("include_recommendation_label")
    if rec in ("yes", "revise", "no"):
        pass
    elif rec in ("да", "с доработкой"):
        rec = {"да": "yes", "с доработкой": "revise"}.get(rec, "revise")
    elif rec == "нет":
        rec = "no"
    else:
        rec = "revise"

    return stage1, stage2, stage_legal, quality, eff, legal_score, rec
