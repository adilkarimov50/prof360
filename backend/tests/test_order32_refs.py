"""Tests for Order 32 reference helpers."""
from app.prosecutor.order32_refs import fix_wrong_order32_points


def test_fix_representation_p1():
    bad = (
        "внести Представление (п.1 Приказа ГП РК №32 от 17.01.2023) "
        "в адрес начальника ОВД"
    )
    fixed, warns = fix_wrong_order32_points(bad)
    assert "п.1" not in fixed or "Утвердить" in fixed
    assert "Представление" in fixed
    assert warns


def test_st59_p9_unchanged():
    text = "основания по ст.59 п.9 Закона о профилактике"
    fixed, warns = fix_wrong_order32_points(text)
    assert fixed == text
    assert not warns
