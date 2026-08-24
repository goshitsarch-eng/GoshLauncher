from __future__ import annotations

import math

import pytest

from ulauncher.modes.launcher.calculator import (
    calculator_description,
    evaluate_arithmetic,
    format_hex,
    format_number,
)


def test_bare_integer_is_not_math() -> None:
    assert evaluate_arithmetic("42", allow_bare=False) is None
    assert evaluate_arithmetic("42", allow_bare=True) == 42
    assert evaluate_arithmetic("two", allow_bare=False) is None
    assert evaluate_arithmetic("1,000", allow_bare=True) == 1000
    assert evaluate_arithmetic("0.5", allow_bare=True) == 0.5


def test_goshos_arithmetic_battery() -> None:
    assert evaluate_arithmetic("12 * 8 + 3") == 99
    assert evaluate_arithmetic("2^8") == 256
    assert evaluate_arithmetic("2^3^2") == 512
    assert evaluate_arithmetic("-2^2") == -4
    assert evaluate_arithmetic("(-2)^2") == 4
    assert evaluate_arithmetic("2^-2") == 0.25
    assert evaluate_arithmetic("tan(90)") is None
    assert evaluate_arithmetic("0x") is None
    assert evaluate_arithmetic("2foo") is None
    assert evaluate_arithmetic(".5+1") == 1.5
    assert evaluate_arithmetic("1e") is None
    assert evaluate_arithmetic("2*e") == 2 * math.e
    assert evaluate_arithmetic("2π") == 2 * math.pi
    assert evaluate_arithmetic("5²") == 25
    assert evaluate_arithmetic("2³") == 8
    assert evaluate_arithmetic("sin(90°)") == 1
    assert evaluate_arithmetic("sin 90") == 1
    assert evaluate_arithmetic("sqrt 16") == 4
    assert evaluate_arithmetic("log2 8") == 3
    assert evaluate_arithmetic("sin 90 + 1") == 2
    assert evaluate_arithmetic("sin90") is None
    assert evaluate_arithmetic("1/0") is None
    assert evaluate_arithmetic("not math") is None
    assert evaluate_arithmetic("address") is None
    assert evaluate_arithmetic("sometimes") is None
    assert evaluate_arithmetic("plus") is None
    assert evaluate_arithmetic("leftover") is None
    assert evaluate_arithmetic("(1+2)*3") == 9
    assert evaluate_arithmetic("10 / 4") == 2.5
    assert evaluate_arithmetic("10 % 3") == 1
    assert evaluate_arithmetic("1+2=") == 3
    assert evaluate_arithmetic("1 000 + 2") == 1002
    assert evaluate_arithmetic("1 000 000 / 2") == 500000
    assert evaluate_arithmetic("1+2=3") == 3
    assert evaluate_arithmetic("50% of 80=40") == 40
    assert evaluate_arithmetic("1\u00a0+\u00a02") == 3
    assert evaluate_arithmetic("π²") == math.pi**2


def test_spoken_readme_phrases() -> None:
    assert evaluate_arithmetic("2 plus 2") == 4
    assert evaluate_arithmetic("two plus two") == 4
    assert evaluate_arithmetic("2 add 3") == 5
    assert evaluate_arithmetic("8 subtract 3") == 5
    assert evaluate_arithmetic("10 minus 3") == 7
    assert evaluate_arithmetic("4 times 5") == 20
    assert evaluate_arithmetic("3 multiplied by 3") == 9
    assert evaluate_arithmetic("8 divided by 2") == 4
    assert evaluate_arithmetic("8 over 2") == 4
    assert evaluate_arithmetic("5 squared") == 25
    assert evaluate_arithmetic("2 cubed") == 8
    assert evaluate_arithmetic("2 to the power of 8") == 256
    assert evaluate_arithmetic("2 to the 8th") == 256
    assert evaluate_arithmetic("2 to the 8th power") == 256
    assert evaluate_arithmetic("2 to the eighth") == 256
    assert evaluate_arithmetic("two to the eighth") == 256
    assert evaluate_arithmetic("two to the power of eight") == 256
    assert evaluate_arithmetic("half of 80") == 40
    assert evaluate_arithmetic("square root of 16") == 4
    assert evaluate_arithmetic("negative 3 plus 5") == 2
    assert evaluate_arithmetic("three thousand + 1") == 3001
    assert evaluate_arithmetic("twenty plus two") == 22
    assert evaluate_arithmetic("forty-five + 1") == 46
    assert evaluate_arithmetic("twenty one + 1") == 22
    assert evaluate_arithmetic("one hundred + 1") == 101
    assert evaluate_arithmetic("a hundred + 1") == 101
    assert evaluate_arithmetic("a thousand + 1") == 1001
    assert evaluate_arithmetic("one hundred and twenty + 1") == 121
    assert evaluate_arithmetic("one hundred twenty + 1") == 121
    assert evaluate_arithmetic("one hundred and twenty-one + 1") == 122
    assert evaluate_arithmetic("one thousand two hundred + 1") == 1201
    assert evaluate_arithmetic("two million + 1") == 2000001
    assert evaluate_arithmetic("a million + 1") == 1000001
    assert evaluate_arithmetic("five hundred million + 1") == 500000001
    assert evaluate_arithmetic("two million three hundred + 1") == 2000301
    assert evaluate_arithmetic("twenty thousand + 1") == 20001


def test_goshos_implicit_percent_factorial_and_hex() -> None:
    assert evaluate_arithmetic("2pi^2") == pytest.approx(2 * math.pi * math.pi)
    assert evaluate_arithmetic("2^3pi") == pytest.approx(8 * math.pi)
    assert evaluate_arithmetic("2(3)^2") == 18
    assert evaluate_arithmetic("2**8") == 256
    assert evaluate_arithmetic("2 x 3") == 6
    assert evaluate_arithmetic("2x3") == 6
    assert evaluate_arithmetic("2\u00d73") == 6
    assert evaluate_arithmetic("8\u00f72") == 4
    assert evaluate_arithmetic("1,000+2") == 1002
    assert evaluate_arithmetic("-(2+3)") == -5
    assert evaluate_arithmetic("5!") == 120
    assert evaluate_arithmetic("3!+1") == 7
    assert evaluate_arithmetic("50% of 80") == 40
    assert evaluate_arithmetic("25 percent of 200") == 50
    assert evaluate_arithmetic("50%") == 0.5
    assert evaluate_arithmetic("50% * 80") == 40
    assert evaluate_arithmetic("10%3") == 1
    assert evaluate_arithmetic("\u221a16") == 4
    assert evaluate_arithmetic("0x10") is None
    assert evaluate_arithmetic("0x10", True) == 16
    assert evaluate_arithmetic("0x10+1") == 17
    assert evaluate_arithmetic("0b1010", True) == 10
    assert evaluate_arithmetic("e") is None
    assert evaluate_arithmetic("e", True) == pytest.approx(math.e)
    assert evaluate_arithmetic("pi") == pytest.approx(math.pi)
    assert format_hex(255) == "0xff"
    assert format_hex(-1) == ""
    assert calculator_description(255) == "0xff · press Enter to copy"
    assert calculator_description(0.5) == "Press Enter to copy to clipboard"


def test_format_number_is_stable() -> None:
    assert format_number(4.0) == "4"
    assert format_number(0) == "0"
    assert format_number(0.1 + 0.2) == "0.3"
    assert format_number(-0.0) == "0"
    assert format_number(256) == "256"
