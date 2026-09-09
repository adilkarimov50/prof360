"""Гибридный поиск по НПА: ключевые слова + вектор + reranking; поиск редакции на дату."""
import re
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.legal.embeddings import embed_query
from app.models.legal import LegalAct, LegalNorm

_ARTICLE_RE = re.compile(r"ст(?:ать[яеи])?\.?\s*(\d+(?:-\d+)?)", re.IGNORECASE)
_POINT_RE = re.compile(
    r"(?:^|\s)(?:п\.?\s*|пункт\s+)(\d+)\b",
    re.IGNORECASE,
)

_ACT_HINTS: list[tuple[str, str]] = [
    ("коап", "административных правонарушениях"),
    ("административн", "административных правонарушениях"),
    ("аппк", "Административный процедурно-процессуальный"),
    ("адм. проц", "Административный процедурно-процессуальный"),
    ("упк", "Уголовно-процессуальный"),
    ("уик", "Уголовно-исполнительный"),
    ("уголовно-процесс", "Уголовно-процессуальный"),
    ("уголовно-исполн", "Уголовно-исполнительный"),
    ("гпк", "Гражданский процессуальный"),
    ("налог", "Налоговый"),
    ("брак", "браке"),
    ("семь", "браке"),
    ("труд", "Трудовой"),
    ("эколог", "Экологический"),
    ("предприним", "Предпринимательский"),
    ("социальн", "Социальный"),
    ("здоров", "здоровье народа"),
    ("приказ", "Прокурор"),
    ("№32", "Прокурор"),
    ("профилактик", "профилактике"),
    ("прокуратур", "прокуратуре"),
    ("овд", "внутренних дел"),
    ("полици", "внутренних дел"),
    ("уголовн", "Уголовный кодекс"),
]

_STOPWORDS = {
    "как", "что", "это", "для", "при", "под", "над", "или", "the", "как-то", "так",
    "по", "на", "из", "от", "до", "за", "об", "обо", "про", "не", "ни", "же", "ли",
    "можно", "нужно", "если", "есть", "был", "была", "быть", "его", "ему", "они", "она",
    "дела", "дело", "делу", "вопрос", "вопросу", "также", "чтобы", "када", "сколько",
}


def _articles(query: str) -> list[str]:
    return [f"ст.{m.group(1)}" for m in _ARTICLE_RE.finditer(query)]


def _points(query: str) -> list[str]:
    return list(dict.fromkeys(m.group(1) for m in _POINT_RE.finditer(query)))


def _act_hint(query: str) -> str | None:
    low = query.lower()
    for needle, title_part in _ACT_HINTS:
        if needle in low:
            return title_part
    return None


def _terms(query: str) -> list[str]:
    words = re.findall(r"[А-Яа-яЁёA-Za-z0-9]{3,}", query.lower())
    return [w for w in words if w not in _STOPWORDS][:10]


def _dedup_key(norm: LegalNorm) -> tuple:
    """Дедупликация: одна лучшая норма на (акт, статья)."""
    return (norm.act_id, norm.article or "", norm.point or "")


def _chunk_text(norm: LegalNorm, max_len: int = 900) -> str:
    """Для RAG-контекста длинные нормы обрезаем с указанием пункта."""
    text = norm.text_ru or norm.title or ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "… [текст сокращён; полная редакция в карточке нормы]"


def article_bundle_search(db: Session, query: str, max_norms: int = 24) -> list[LegalNorm]:
    """Все пункты упомянутой статьи — чтобы ИИ не выдумывал номера пунктов."""
    articles = _articles(query)
    if not articles:
        return []
    q = db.query(LegalNorm).join(LegalAct).filter(LegalNorm.article.in_(articles))
    rows = q.order_by(LegalNorm.point.nullsfirst(), LegalNorm.point).all()
    hint = _act_hint(query)
    if hint:
        filtered = [n for n in rows if hint.lower() in (n.act.title or "").lower()]
        if filtered:
            rows = filtered
    pts = _points(query)
    if pts:
        filtered = [n for n in rows if n.point in pts]
        if filtered:
            rows = filtered
    return rows[:max_norms]


def exact_article_search(db: Session, query: str) -> list[LegalNorm]:
    """Точное совпадение статьи/пункта (используется в hybrid_search)."""
    return article_bundle_search(db, query)


def keyword_search(db: Session, query: str, limit: int = 12) -> list[LegalNorm]:
    terms = _terms(query)
    if not terms:
        return []
    conds = []
    for t in terms:
        like = f"%{t}%"
        conds.append(LegalNorm.title.ilike(like))
        conds.append(LegalNorm.text_ru.ilike(like))
        conds.append(LegalNorm.keywords.ilike(like))
        conds.append(LegalNorm.category.ilike(like))
    return db.query(LegalNorm).filter(or_(*conds)).limit(limit).all()


def vector_search(db: Session, query: str, limit: int = 15) -> list[tuple[LegalNorm, float]]:
    vec = embed_query(query)
    rows = (
        db.query(LegalNorm, LegalNorm.embedding.cosine_distance(vec).label("dist"))
        .filter(LegalNorm.embedding.is_not(None))
        .order_by("dist")
        .limit(limit)
        .all()
    )
    return [(r[0], float(r[1])) for r in rows]


def _dedup_results(items: list[dict]) -> list[dict]:
    """Оставляет лучший score на (act, article, point)."""
    best: dict[tuple, dict] = {}
    for item in items:
        key = _dedup_key(item["norm"])
        if key not in best or item["score"] > best[key]["score"]:
            best[key] = item
    return list(best.values())


def hybrid_search(db: Session, query: str, limit: int = 10) -> list[dict]:
    """Объединяет точные статьи, BM25-подобный keyword и вектор с fusion reranking."""
    articles = _articles(query)
    # Если в вопросе есть статья — подтягиваем все её пункты из базы (анти-галлюцинации)
    effective_limit = max(limit, 16) if articles else limit
    scored: dict[int, dict] = {}
    fetch_limit = effective_limit * 3

    for norm in exact_article_search(db, query):
        scored.setdefault(norm.id, {"norm": norm, "score": 0.0})
        scored[norm.id]["score"] += 2000.0
        if norm.point and norm.point in _points(query):
            scored[norm.id]["score"] += 500.0

    for rank, (norm, dist) in enumerate(vector_search(db, query, fetch_limit)):
        scored.setdefault(norm.id, {"norm": norm, "score": 0.0})
        # cosine distance -> similarity bonus
        sim = max(0.0, 1.0 - dist)
        scored[norm.id]["score"] += sim * 50.0 + (fetch_limit - rank) * 0.5
        scored[norm.id]["distance"] = dist

    for rank, norm in enumerate(keyword_search(db, query, fetch_limit)):
        scored.setdefault(norm.id, {"norm": norm, "score": 0.0})
        scored[norm.id]["score"] += (fetch_limit - rank) * 1.2

    hint = _act_hint(query)
    if hint:
        for item in scored.values():
            if hint.lower() in (item["norm"].act.title or "").lower():
                item["score"] += 8.0

    articles = _articles(query)
    for item in scored.values():
        norm = item["norm"]
        if norm.status != "действует":
            item["score"] -= 50.0
        if norm.point and norm.article in articles:
            item["score"] += 15.0
        if norm.keywords and articles:
            for a in articles:
                if a in (norm.keywords or ""):
                    item["score"] += 3.0

    merged = _dedup_results(list(scored.values()))
    return sorted(merged, key=lambda x: -x["score"])[:effective_limit]


def norm_context_text(norm: LegalNorm) -> str:
    """Текст нормы для промпта: явно указываем пункт, чтобы модель не путала."""
    header = norm.ref or "норма"
    body = _chunk_text(norm)
    if norm.point:
        return f"[{header}] пункт {norm.point}: {body}"
    return f"[{header}] (без выделенного пункта): {body}"


def norm_on_date(db: Session, article: str, on: date) -> LegalNorm | None:
    q = db.query(LegalNorm).filter(LegalNorm.article == article)
    for norm in q.all():
        start_ok = (norm.edition_start is None) or (norm.edition_start <= on)
        end_ok = (norm.edition_end is None) or (on <= norm.edition_end)
        if start_ok and end_ok:
            return norm
    return q.first()
