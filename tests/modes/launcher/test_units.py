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
    there = convert_query("how many miles are there in 10 km")
    assert there is not None
    assert "mi" in there["title"]
    assert there["copy_text"] == there["title"]
    thirteen = convert_query("thirteen km to mi")
    assert thirteen is not None
    assert round(float(thirteen["title"].split()[0]) * 1000) / 1000 == 8.078
    nmi = convert_query("1 nmi to km")
    assert nmi is not None
    assert nmi["title"] == "1.852 km"
    acre = convert_query("1 acre to m2")
    assert acre is not None
    assert round(float(acre["title"].split()[0])) == 4047
    mib = convert_query("1 gb to mib")
    assert mib is not None
    assert "mib" in mib["title"]
    kph = convert_query("100 kph to mph")
    assert kph is not None
    assert round(float(kph["title"].split()[0])) == 62


def test_cal_is_not_food_calorie() -> None:
    cal = convert_query("1 cal to j")
    kcal = convert_query("1 kcal to j")
    assert cal is not None
    assert kcal is not None
    assert cal["copy_text"] != kcal["copy_text"]


def test_goshos_unit_conversion_battery() -> None:
    from ulauncher.modes.launcher.units import parse_unit_query

    ten = convert_query("ten km to mi")
    assert ten is not None
    assert round(float(ten["title"].split()[0]) * 1000) / 1000 == 6.214
    half = convert_query("1/2 cup to ml")
    assert half is not None
    assert half["description"] == "0.5 cup"
    assert parse_unit_query("three thousand km to mi")["value"] == 3000
    assert parse_unit_query("how many miles in 10 km")["from"] == "km"
    assert parse_unit_query("how many miles in 10 km")["to"] == "miles"
    assert parse_unit_query("how many km in a mile")["value"] == 1
    assert parse_unit_query("a cup to ml")["value"] == 1
    assert parse_unit_query("32°f to c")["from"] == "f"
    assert convert_query("32°f to c")["title"] == "0 c"
    assert convert_query("chrome") is None
    assert convert_query("1e-3 km to m")["title"] == "1 m"
    assert convert_query("1024 bytes to kib")["title"] == "1 kib"
    assert convert_query("2 hours to min")["title"] == "120 min"
    assert convert_query("1 day to h")["title"] == "24 h"
    assert convert_query(".5 km to m")["title"] == "500 m"
    assert convert_query("1 ha to m2")["title"] == "10000 m2"
    assert convert_query("2 hrs to min")["title"] == "120 min"
    assert convert_query("60 secs to min")["title"] == "1 min"
    assert convert_query("1 m3 to l")["title"] == "1000 l"
    assert convert_query("1 m³ to l")["title"] == "1000 l"
    assert convert_query("1 cc to ml")["title"] == "1 ml"
    assert convert_query("200 kcal to kj")["title"] == "836.8 kj"
    assert convert_query("1 kwh to kj")["title"] == "3600 kj"
    assert convert_query("100 w to kw")["title"] == "0.1 kw"
    hp_kw = convert_query("1 hp to kw")
    assert hp_kw is not None
    assert hp_kw["title"].split()[1] == "kw"
    assert abs(float(hp_kw["title"].split()[0]) - 0.746) < 0.001
    assert convert_query("1 cup to tbsp")["title"] == "16 tbsp"
    assert convert_query("3 tsp to tbsp")["title"] == "1 tbsp"
    assert round(float(convert_query("1 floz to ml")["title"].split()[0])) == 30
    assert convert_query("5 km to km") is None
    assert convert_query("1 kg to km") is None
    assert convert_query("1 min to m") is None


def test_goshos_pressure_energy_and_angle() -> None:
    import math

    from ulauncher.modes.launcher.units import convert_units, parse_unit_query

    assert convert_query("32 psi to bar")["title"].split()[1] == "bar"
    assert convert_query("760 mmhg to atm")["title"].split()[1] == "atm"
    assert convert_query("10 m/s to kph")["title"].split()[1] == "kph"
    assert parse_unit_query("1 m² to ft2")["from"] == "m2"
    assert convert_query("1 m² to ft2") is not None
    assert convert_query("200 calories to kj")["title"] == "836.8 kj"
    cal = convert_units(1, "cal", "j")
    assert cal is not None
    assert cal["value"] == 4.184
    hp = convert_units(1, "hp", "w")
    assert hp is not None
    assert round(hp["value"]) == 746
    deg = convert_units(180, "deg", "rad")
    assert deg is not None
    assert abs(deg["value"] - math.pi) < 1e-10
    nmi = convert_units(1, "nmi", "m")
    assert nmi is not None
    assert nmi["value"] == 1852
    stone = convert_units(1, "st", "kg")
    assert stone is not None
    assert round(stone["value"] * 1000) / 1000 == 6.35
    assert parse_unit_query("180° to rad")["from"] == "deg"
    assert parse_unit_query("180 degrees to rad")["from"] == "degrees"
    assert parse_unit_query("1 fl oz to ml")["from"] == "floz"


def test_goshos_unit_as_how_many_and_articles() -> None:
    from ulauncher.modes.launcher.units import parse_unit_query

    assert parse_unit_query("10 km as miles")["to"] == "miles"
    assert parse_unit_query("how many miles is 10 km")["to"] == "miles"
    assert parse_unit_query("how many miles are in 10 km")["to"] == "miles"
    assert parse_unit_query("how many miles are 10 km")["from"] == "km"
    assert parse_unit_query("an inch to cm")["value"] == 1
    assert parse_unit_query("10 km to a mile")["from"] == "km"
    assert parse_unit_query("10 km to a mile")["to"] == "mile"
    assert parse_unit_query("1.5e2 f to c")["value"] == 150
    assert parse_unit_query("how many km are in a mile")["value"] == 1
    assert parse_unit_query("a mile to km")["value"] == 1
    assert parse_unit_query("180° into rad")["from"] == "deg"
