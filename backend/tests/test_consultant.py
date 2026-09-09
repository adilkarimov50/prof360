"""Tests for legal search point extraction and citation validation."""
from app.ai.consultant import _validate_point_citations
from app.legal.search import _articles, _points


def test_extract_article():
    assert "ст.73" in _articles("Как реагировать по ст.73 КоАП?")


def test_extract_point():
    assert "3" in _points("п.3 ст.73 КоАП")
    assert "12" in _points("пункт 12 приказа №32")


def test_validate_unknown_point():
    norms = [{"norm_id": 1, "article": "ст.73", "point": "1"}]
    warns = _validate_point_citations("Согласно п.99 ст.73 КоАП...", norms)
    assert warns
    assert "п.99" in warns[0]


def test_validate_known_point_ok():
    norms = [{"norm_id": 1, "article": "ст.73", "point": "3"}]
    assert _validate_point_citations("Применяется п.3 ст.73", norms) == []
