from __future__ import annotations

from ulauncher.modes.launcher.calculator import evaluate_arithmetic, format_number


def test_bare_integer_is_not_math() -> None:
    assert evaluate_arithmetic("42", allow_bare=False) is None
    assert evaluate_arithmetic("42", allow_bare=True) == 42


def test_expression_evaluates() -> None:
    assert evaluate_arithmetic("1+2*3", allow_bare=False) == 7
    assert evaluate_arithmetic("sqrt(9)", allow_bare=False) == 3
    assert evaluate_arithmetic("sqrt 16", allow_bare=False) == 4
    assert evaluate_arithmetic("2^8", allow_bare=False) == 256
    assert evaluate_arithmetic("-2^2", allow_bare=False) == -4
    assert evaluate_arithmetic("50%", allow_bare=False) == 0.5
    assert evaluate_arithmetic("10%3", allow_bare=False) == 1
    assert evaluate_arithmetic("5!", allow_bare=False) == 120
    assert evaluate_arithmetic("sin 90", allow_bare=False) == 1
    assert evaluate_arithmetic("2(3+1)", allow_bare=False) == 8
    assert evaluate_arithmetic("1,000+2", allow_bare=False) == 1002
    assert evaluate_arithmetic("two plus two", allow_bare=False) == 4
    assert evaluate_arithmetic("2pi", allow_bare=False) == evaluate_arithmetic("2*pi", allow_bare=False)


def test_incomplete_tokens_are_not_math() -> None:
    assert evaluate_arithmetic("2foo", allow_bare=False) is None
    assert evaluate_arithmetic("0x", allow_bare=False) is None
    assert evaluate_arithmetic("1e", allow_bare=False) is None


def test_format_number_is_stable() -> None:
    assert format_number(4.0) == "4"
    assert format_number(0) == "0"
