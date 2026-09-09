"""Кэш полных текстов НПА с adilet.zan.kz (DOCX + plain text для чтения/скачивания)."""
from __future__ import annotations

import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from docx import Document

from app.legal.code_ingest import download_docx
from app.legal.codes_registry import ACTS, CODES_BY_DOC_ID, doc_url

_META = "cache_meta.json"


def cache_root() -> Path:
    root = Path(__file__).resolve().parents[2] / "data" / "legal" / "documents"
    root.mkdir(parents=True, exist_ok=True)
    return root


def docx_path(doc_id: str) -> Path:
    return cache_root() / f"{doc_id}.docx"


def text_path(doc_id: str) -> Path:
    return cache_root() / f"{doc_id}.txt"


def meta_path() -> Path:
    return cache_root() / _META


def _load_meta() -> dict:
    p = meta_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_meta(meta: dict) -> None:
    meta_path().write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_plain_text(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    lines: list[str] = []
    for para in doc.paragraphs:
        line = (para.text or "").replace("\xa0", " ").strip()
        if line:
            lines.append(line)
    return "\n\n".join(lines)


def is_cached(doc_id: str) -> bool:
    return docx_path(doc_id).is_file() and docx_path(doc_id).stat().st_size > 500


def cache_info(doc_id: str) -> dict | None:
    if not is_cached(doc_id):
        return None
    meta = _load_meta().get(doc_id, {})
    dx = docx_path(doc_id)
    return {
        "doc_id": doc_id,
        "cached_at": meta.get("cached_at"),
        "docx_bytes": dx.stat().st_size,
        "title": meta.get("title"),
    }


def ensure_cached(doc_id: str, force: bool = False) -> dict:
    """Скачивает DOCX с adilet, сохраняет .docx и .txt. Возвращает статус."""
    if doc_id not in CODES_BY_DOC_ID:
        raise KeyError(f"Неизвестный doc_id: {doc_id}")
    code = CODES_BY_DOC_ID[doc_id]
    path = docx_path(doc_id)
    if is_cached(doc_id) and not force:
        return {"doc_id": doc_id, "status": "cached", **(cache_info(doc_id) or {})}

    content = download_docx(doc_id)
    path.write_bytes(content)
    text = extract_plain_text(content)
    text_path(doc_id).write_text(text, encoding="utf-8")

    meta = _load_meta()
    meta[doc_id] = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "title": code["title"],
        "number": code.get("number"),
        "act_type": code.get("act_type"),
        "adilet_url": doc_url(doc_id),
    }
    _save_meta(meta)
    return {
        "doc_id": doc_id,
        "status": "downloaded",
        "docx_bytes": len(content),
        "text_chars": len(text),
        "title": code["title"],
    }


def get_plain_text(doc_id: str, fetch_if_missing: bool = True) -> str:
    if not text_path(doc_id).is_file() and fetch_if_missing:
        ensure_cached(doc_id)
    p = text_path(doc_id)
    if not p.is_file():
        raise FileNotFoundError(doc_id)
    return p.read_text(encoding="utf-8")


def download_all(doc_ids: list[str] | None = None, force: bool = False) -> list[dict]:
    ids = doc_ids or [c["doc_id"] for c in ACTS]
    results: list[dict] = []
    for i, doc_id in enumerate(ids):
        try:
            results.append(ensure_cached(doc_id, force=force))
        except Exception as exc:  # noqa: BLE001
            results.append({"doc_id": doc_id, "status": "error", "error": str(exc)})
        if i + 1 < len(ids):
            time.sleep(2.0)
    return results


def catalog(db=None) -> list[dict]:
    """Каталог всех НПА реестра + статус кэша и число норм в БД."""
    from app.models.legal import LegalAct, LegalNorm

    meta = _load_meta()
    out: list[dict] = []
    for code in ACTS:
        doc_id = code["doc_id"]
        act = None
        norms_count = 0
        act_id = None
        if db is not None:
            act = db.query(LegalAct).filter(LegalAct.number == code["number"]).first()
            if act:
                act_id = act.id
                norms_count = db.query(LegalNorm).filter(LegalNorm.act_id == act.id).count()
        cached = is_cached(doc_id)
        m = meta.get(doc_id, {})
        out.append({
            "doc_id": doc_id,
            "title": code["title"],
            "number": code.get("number"),
            "act_type": code.get("act_type"),
            "parse_mode": code.get("parse_mode"),
            "adilet_url": doc_url(doc_id),
            "cached": cached,
            "cached_at": m.get("cached_at"),
            "docx_bytes": docx_path(doc_id).stat().st_size if cached else None,
            "act_id": act_id,
            "norms_count": norms_count,
        })
    return out


def safe_filename(doc_id: str) -> str:
    code = CODES_BY_DOC_ID.get(doc_id, {})
    num = re.sub(r"[^\w\-]+", "_", str(code.get("number") or doc_id))
    return f"{num}_{doc_id}.docx"
