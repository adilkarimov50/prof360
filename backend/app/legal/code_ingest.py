"""Загрузка и структурирование полных кодексов/НПА РК с adilet.zan.kz."""
import io
import re
import time

import httpx
from docx import Document
from sqlalchemy.orm import Session

from app.legal.codes_registry import ACTS, CODES_BY_DOC_ID, doc_url, docx_url
from app.legal.embeddings import embed_passages
from app.legal.tags import auto_tags
from app.models.legal import LegalAct, LegalNorm

_ARTICLE_RE = re.compile(r"^Статья\s+(\d+(?:-\d+)?)\.?\s*(.*)$", re.IGNORECASE)
_POINT_HEAD_RE = re.compile(r"^(?:п\.?\s*)?(\d+)\.\s+(.+)$")
_POINT_PAREN_RE = re.compile(r"^(\d+)\)\s+(.+)$")
_CHAPTER_RE = re.compile(r"^(?:ГЛАВА|Глава|РАЗДЕЛ|Раздел|ПАРАГРАФ|Параграф)\s+", re.IGNORECASE)
_REPEALED_RE = re.compile(r"(исключен|утратил[аои]? силу)", re.IGNORECASE)
_POINT_BODY_RE = re.compile(r"^(\d+)\.\s")

_USER_AGENT = "Mozilla/5.0 (Prof360 LegalIngest)"
_MAX_TEXT = 12000
_EMBED_TRUNC = 1200
_EMBED_BATCH = 32
_RETRIES = 4
_RETRY_BACKOFF = 3.0
_SPLIT_THRESHOLD = 2500


def download_docx(doc_id: str) -> bytes:
    url = docx_url(doc_id)
    headers = {"User-Agent": _USER_AGENT}
    last_exc: Exception | None = None
    for attempt in range(_RETRIES):
        for verify in (True, False):
            try:
                with httpx.Client(follow_redirects=True, timeout=180.0,
                                  headers=headers, verify=verify) as client:
                    client.get(doc_url(doc_id))
                    r = client.get(url)
                    r.raise_for_status()
                    return r.content
            except (httpx.ConnectError, httpx.TransportError) as exc:
                last_exc = exc
                if verify:
                    continue
                break
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                break
        time.sleep(_RETRY_BACKOFF * (attempt + 1))
    raise last_exc or RuntimeError("download failed")


def _split_article_points(article: str, title: str, text: str, category: str | None,
                          status: str) -> list[dict]:
    """Длинные статьи режем на пункты для точных ссылок."""
    if len(text) < _SPLIT_THRESHOLD:
        return [{"article": article, "point": None, "title": title, "text": text,
                 "category": category, "status": status}]
    lines = text.split("\n")
    chunks: list[dict] = []
    cur_point: str | None = None
    cur_title = title
    body: list[str] = []

    def flush():
        nonlocal body, cur_point, cur_title
        if not body and not cur_point:
            return
        chunk_text = "\n".join(body).strip()
        if chunk_text or cur_point:
            chunks.append({
                "article": article, "point": cur_point, "title": cur_title[:512],
                "text": chunk_text[:_MAX_TEXT], "category": category, "status": status,
            })
        body = []

    for line in lines:
        m = _POINT_BODY_RE.match(line.strip())
        if m:
            flush()
            cur_point = m.group(1)
            cur_title = line.strip()[:512]
            body = []
        else:
            body.append(line)
    flush()
    return chunks if chunks else [{
        "article": article, "point": None, "title": title, "text": text,
        "category": category, "status": status,
    }]


def parse_docx(content: bytes, parse_mode: str = "article") -> list[dict]:
    doc = Document(io.BytesIO(content))
    if parse_mode == "point":
        return _parse_points(doc)
    return _parse_articles(doc)


def _parse_articles(doc: Document) -> list[dict]:
    raw: list[dict] = []
    current: dict | None = None
    chapter: str | None = None
    body: list[str] = []

    def flush():
        if current is None:
            return
        text = "\n".join(body).strip()
        status = "действует"
        if _REPEALED_RE.search(current["title"]) or (len(text) < 120 and _REPEALED_RE.search(text)):
            status = "утратил силу"
        raw.extend(_split_article_points(
            current["article"], current["title"], text, chapter, status))

    for para in doc.paragraphs:
        line = (para.text or "").replace("\xa0", " ").strip()
        if not line:
            continue
        if _CHAPTER_RE.match(line):
            chapter = line[:128]
            continue
        m = _ARTICLE_RE.match(line)
        if m:
            flush()
            current = {"article": f"ст.{m.group(1)}", "title": (m.group(2) or "").strip()}
            body = []
        elif current is not None:
            body.append(line)
    flush()
    return [a for a in raw if a.get("article")]


def _parse_points(doc: Document) -> list[dict]:
    """Приказы/инструкции: нумерованные пункты."""
    items: list[dict] = []
    current: dict | None = None
    section: str | None = None
    body: list[str] = []

    def flush():
        if current is None:
            return
        text = "\n".join(body).strip()
        status = "действует"
        if _REPEALED_RE.search(text):
            status = "утратил силу"
        items.append({**current, "text": text[:_MAX_TEXT], "status": status})

    for para in doc.paragraphs:
        line = (para.text or "").replace("\xa0", " ").strip()
        if not line:
            continue
        if _CHAPTER_RE.match(line):
            section = line[:128]
            continue
        m = _POINT_HEAD_RE.match(line) or _POINT_PAREN_RE.match(line)
        if m:
            flush()
            current = {
                "article": f"п.{m.group(1)}",
                "point": m.group(1),
                "title": m.group(2).strip()[:512],
                "category": section,
            }
            body = []
        elif current is not None:
            body.append(line)
    flush()
    return items


def _norm_key(article: str | None, point: str | None) -> str:
    return f"{article or ''}|{point or ''}"


def _get_or_create_act(db: Session, code: dict) -> LegalAct:
    act = db.query(LegalAct).filter(LegalAct.number == code["number"]).first()
    if act:
        return act
    act = LegalAct(
        title=code["title"], act_type=code["act_type"], number=code["number"],
        hierarchy_level=code.get("hierarchy_level", 2), source_url=doc_url(code["doc_id"]),
    )
    db.add(act)
    db.flush()
    return act


def ingest_code(db: Session, code: dict) -> dict:
    try:
        from app.legal.document_cache import docx_path, ensure_cached

        ensure_cached(code["doc_id"])
        content = docx_path(code["doc_id"]).read_bytes()
    except Exception as exc:  # noqa: BLE001
        return {"code": code["title"], "doc_id": code["doc_id"], "error": str(exc),
                "added": 0, "parsed": 0}

    mode = code.get("parse_mode", "article")
    parsed = parse_docx(content, mode)
    act = _get_or_create_act(db, code)

    existing = {
        _norm_key(a, p)
        for a, p in db.query(LegalNorm.article, LegalNorm.point).filter(LegalNorm.act_id == act.id).all()
    }
    pending: list[LegalNorm] = []
    texts: list[str] = []
    for art in parsed:
        key = _norm_key(art.get("article"), art.get("point"))
        if key in existing:
            continue
        tags = auto_tags(art.get("title"), art.get("text", ""), art.get("category"))
        norm = LegalNorm(
            act_id=act.id,
            article=art.get("article"),
            point=art.get("point"),
            title=art.get("title")[:512] if art.get("title") else None,
            text_ru=art.get("text") or art.get("title"),
            status=art.get("status", "действует"),
            edition_start=act.adopt_date,
            category=tags["category"],
            subject=tags["subject"],
            measure=tags["measure"],
            keywords=tags["keywords"],
            source_url=act.source_url,
        )
        db.add(norm)
        pending.append(norm)
        embed_src = f"{act.title} {art.get('article','')} {art.get('point','')} {art.get('title','')} {art.get('text','')}"
        texts.append(embed_src[:_EMBED_TRUNC])
        existing.add(key)

    for i in range(0, len(pending), _EMBED_BATCH):
        batch = pending[i:i + _EMBED_BATCH]
        vectors = embed_passages(texts[i:i + _EMBED_BATCH])
        for norm, vec in zip(batch, vectors):
            norm.embedding = vec
        db.commit()
    db.commit()
    return {"code": code["title"], "doc_id": code["doc_id"], "parsed": len(parsed),
            "added": len(pending)}


def tag_existing_norms(db: Session, limit: int | None = None) -> int:
    """Дозаполняет авто-теги у норм без subject/measure/keywords."""
    q = db.query(LegalNorm).filter(
        (LegalNorm.subject.is_(None)) | (LegalNorm.keywords.is_(None))
    )
    if limit:
        q = q.limit(limit)
    updated = 0
    for norm in q.all():
        tags = auto_tags(norm.title or "", norm.text_ru or "", norm.category)
        changed = False
        for field in ("category", "subject", "measure", "keywords"):
            if not getattr(norm, field) and tags.get(field):
                setattr(norm, field, tags[field])
                changed = True
        if changed:
            updated += 1
    db.commit()
    return updated


def ingest_all(db: Session, doc_ids: list[str] | None = None) -> list[dict]:
    codes = [CODES_BY_DOC_ID[d] for d in doc_ids if d in CODES_BY_DOC_ID] if doc_ids else ACTS
    results = []
    for i, code in enumerate(codes):
        results.append(ingest_code(db, code))
        if i + 1 < len(codes):
            time.sleep(2.0)
    return results
