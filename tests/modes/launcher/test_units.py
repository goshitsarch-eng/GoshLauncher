from __future__ import annotations

from ulauncher.modes.launcher.units import convert_query


def test_spoken_and_readme_unit_phrases() -> None:
    miles = convert_query("how many miles in 10 km")
    assert miles is not None
    assert "mi" in miles["title"]
    assert convert_query("ten km to mi") is not None
    assert convert_query("32°f to c") is not None
    assert convert_query("32 f in c") is not None
    floz = convert_query("1 fl oz to ml")
    assert floz is not None
    assert "ml" in floz["title"]
    cup = convert_query("a cup to ml")
    assert cup is not None
    mile = convert_query("how many km in a mile")
    assert mile is not None
    assert "km" in mile["title"]
    assert convert_query("1/2 cup to ml") is not None
    assert convert_query("1,000 km to mi") is not None
    assert convert_query("100 km/h to mph") is not None
    assert convert_query("1 stone to kg") is not None
    assert convert_query("180° to rad") is not None


def test_cal_is_not_food_calorie() -> None:
    cal = convert_query("1 cal to j")
    kcal = convert_query("1 kcal to j")
    assert cal is not None
    assert kcal is not None
    assert cal["copy_text"] != kcal["copy_text"]
