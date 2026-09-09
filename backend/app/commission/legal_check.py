"""Проверка соответствия поручений комиссии законодательству (векторный поиск + LLM)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.consultant import _format_norms_block, _norm_source, _validate_point_citations
from app.legal.embeddings import using_local_model
from app.legal.search import hybrid_search

LEGAL_SYSTEM = (
    "Ты прокурор-аналитик. Проверяешь соответствие поручений комиссии по профилактике "
    "и исполнения должностными лицами требованиям законодательства. "
    "Отвечай строго в формате JSON без markdown. "
    "Цитируй ТОЛЬКО нормы из предоставленного списка с [Норма #ID]. "
    "Пункт (п.N) называй только если он указан в поле «пункт» нормы."
)


def _extract_assignments(stage1: dict) -> list[dict]:
    """Получить список поручений из результата этапа 1."""
    raw = stage1.get("assignments")
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        result.append({
            "text": text,
            "responsible": (item.get("responsible") or "").strip() or None,
            "deadline": (item.get("deadline") or "").strip() or None,
            "execution_status": (item.get("execution_status") or "").strip() or None,
        })
    return result


def _search_norms_for_assignment(db: Session, assignment_text: str, limit: int = 6) -> list[dict]:
    """Векторный + гибридный поиск норм по тексту поручения."""
    results = hybrid_search(db, assignment_text, limit=limit)
    seen: set[int] = set()
    norms: list[dict] = []
    for r in results:
        norm = r["norm"]
        if norm.id in seen:
            continue
        seen.add(norm.id)
        src = _norm_source(norm)
        dist = r.get("distance")
        src["similarity"] = round(max(0.0, 1.0 - dist), 3) if dist is not None else None
        norms.append(src)
    return norms


def _build_legal_prompt(
    doc_type: str,
    district: str,
    assignments_with_norms: list[dict],
    text_fragment: str,
) -> str:
    blocks: list[str] = []
    for i, a in enumerate(assignments_with_norms, 1):
        norms_text = _format_norms_block(a["matched_norms"])
        blocks.append(
            f"### Поручение {i}\n"
            f"Текст: {a['text']}\n"
            f"Ответственный: {a.get('responsible') or '—'}\n"
            f"Срок: {a.get('deadline') or '—'}\n"
            f"Исполнение: {a.get('execution_status') or 'не указано'}\n\n"
            f"Найденные нормы (векторный поиск):\n{norms_text}"
        )
    assignments_block = "\n\n".join(blocks)
    return f"""Проверь правовое соответствие поручений комиссии по профилактике правонарушений.
Документ: {doc_type}, район «{district}».

{assignments_block}

Фрагмент документа:
---
{text_fragment[:6000]}
---

Для КАЖДОГО поручения оцени:
- законность формулировки поручения;
- соответствие полномочиям ответственного должностного лица;
- соблюдение сроков и факт исполнения (если указано).

compliance: ok — соответствует; warning — риски/неполнота; violation — нарушение закона.

В matched_norm_ids указывай только norm_id из найденных норм выше.

Верни JSON:
{{
  "assignments": [
    {{
      "index": 1,
      "text": "...",
      "responsible": "...",
      "compliance": "ok|warning|violation",
      "matched_norm_ids": [1, 2],
      "issues": ["конкретные правовые замечания"],
      "recommendation": "рекомендация прокурора"
    }}
  ],
  "overall": "общий вывод по правовому соответствию документа",
  "compliance_score": 0-100,
  "violations_count": 0
}}"""


def _merge_results(
    assignments_with_norms: list[dict],
    llm_result: dict,
) -> dict:
    """Собрать финальный JSON с matched_norms из векторного поиска."""
    raw_list = llm_result.get("assignments") or []
    llm_by_index: dict[int, dict] = {}
    for i, a in enumerate(raw_list):
        if not isinstance(a, dict):
            continue
        idx = a.get("index", i + 1)
        if isinstance(idx, (int, float)):
            llm_by_index[int(idx)] = a

    merged: list[dict] = []
    violations = 0
    for i, a in enumerate(assignments_with_norms, 1):
        la = llm_by_index.get(i, {})
        compliance = la.get("compliance", "warning")
        if compliance not in ("ok", "warning", "violation"):
            compliance = "warning"
        if compliance == "violation":
            violations += 1

        norm_ids_raw = la.get("matched_norm_ids") or []
        id_set: set[int] = set()
        if isinstance(norm_ids_raw, list):
            for x in norm_ids_raw:
                try:
                    id_set.add(int(x))
                except (TypeError, ValueError):
                    pass

        matched = [n for n in a["matched_norms"] if n["norm_id"] in id_set]
        if not matched:
            matched = a["matched_norms"][:3]

        issues = la.get("issues")
        merged.append({
            "text": a["text"],
            "responsible": a.get("responsible"),
            "deadline": a.get("deadline"),
            "execution_status": a.get("execution_status"),
            "compliance": compliance,
            "matched_norms": matched,
            "issues": issues if isinstance(issues, list) else [],
            "recommendation": la.get("recommendation") or "",
        })

    score = llm_result.get("compliance_score")
    if isinstance(score, (int, float)):
        score = float(max(0, min(100, score)))
    else:
        score = None

    violations_count = llm_result.get("violations_count")
    if not isinstance(violations_count, int):
        violations_count = violations

    warnings: list[str] = []
    if not using_local_model():
        warnings.append(
            "Семантический поиск работает в офлайн-режиме (hash-fallback) — точность ниже."
        )

    return {
        "assignments": merged,
        "overall": llm_result.get("overall") or "",
        "compliance_score": score,
        "violations_count": violations_count,
        "warnings": warnings,
    }


def check_compliance(
    db: Session,
    *,
    doc_type: str,
    district: str,
    text: str,
    stage1: dict,
) -> tuple[dict, float | None]:
    """Проверка поручений через hybrid_search + LLM. Возвращает (analysis_legal, score)."""
    assignments = _extract_assignments(stage1)
    if not assignments:
        empty = {
            "assignments": [],
            "overall": "Поручения не извлечены из документа — правовая проверка не выполнена.",
            "compliance_score": None,
            "violations_count": 0,
            "warnings": [],
        }
        return empty, None

    assignments_with_norms: list[dict] = []
    all_norms: list[dict] = []
    for a in assignments:
        matched = _search_norms_for_assignment(db, a["text"])
        assignments_with_norms.append({**a, "matched_norms": matched})
        all_norms.extend(matched)

    prompt = _build_legal_prompt(doc_type, district, assignments_with_norms, text)
    raw = llm.generate(prompt, system=LEGAL_SYSTEM, temperature=0.15, max_tokens=4096)
    llm_result = llm.parse_json_from_llm(raw) or {
        "overall": raw or "Правовой анализ недоступен",
        "assignments": [],
    }

    result = _merge_results(assignments_with_norms, llm_result)

    if result.get("overall") and all_norms:
        cite_warnings = _validate_point_citations(result["overall"], all_norms)
        if cite_warnings:
            result["warnings"] = result.get("warnings", []) + cite_warnings

    return result, result.get("compliance_score")
