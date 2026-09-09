"""Локальные эмбеддинги для семантического поиска по НПА.

Приоритет — локальная модель sentence-transformers (данные не уходят наружу).
Если модель недоступна (нет интернета/пакета), используется детерминированный
офлайн-векторизатор на хеш-признаках, чтобы система оставалась работоспособной.
"""
import hashlib
import math
import re

from app.core.config import settings

_model = None
_model_tried = False


def _load_model():
    global _model, _model_tried
    if _model_tried:
        return _model
    _model_tried = True
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
    except Exception:
        _model = None
    return _model


def _hash_embed(text: str, dim: int) -> list[float]:
    """Офлайн-фолбэк: усреднённые хеш-векторы токенов (bag-of-words в dim измерений)."""
    vec = [0.0] * dim
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return vec
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 1) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _encode(texts: list[str], prefix: str) -> list[list[float]]:
    """Кодирует тексты. Для моделей e5 важны префиксы query:/passage:."""
    model = _load_model()
    if model is not None:
        prepared = [f"{prefix}{t}" for t in texts]
        vecs = model.encode(prepared, normalize_embeddings=True)
        return [v.tolist() for v in vecs]
    return [_hash_embed(t, settings.embedding_dim) for t in texts]


def _e5_prefix(kind: str) -> str:
    # Префиксы применимы только к семейству e5; для прочих моделей пустые.
    name = (settings.embedding_model or "").lower()
    if "e5" not in name:
        return ""
    return "query: " if kind == "query" else "passage: "


def embed_query(text: str) -> list[float]:
    """Вектор поискового запроса (e5: префикс query:)."""
    return _encode([text], _e5_prefix("query"))[0]


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Векторы документов/норм для хранения (e5: префикс passage:)."""
    return _encode(texts, _e5_prefix("passage"))


def embed_text(text: str) -> list[float]:
    """Совместимость: трактуется как поисковый запрос."""
    return embed_query(text)


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Совместимость: трактуется как набор документов (passage)."""
    return embed_passages(texts)


def using_local_model() -> bool:
    return _load_model() is not None
