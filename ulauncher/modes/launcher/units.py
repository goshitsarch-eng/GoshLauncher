"""Unit conversion, ported from spotlight-goshos unitMatch.js."""

from __future__ import annotations

import math
import re

from ulauncher.modes.launcher.number_words import replace_number_words

ALIASES = {
    "km": "km",
    "kms": "km",
    "kilometer": "km",
    "kilometers": "km",
    "kilometre": "km",
    "kilometres": "km",
    "m": "m",
    "meter": "m",
    "meters": "m",
    "metre": "m",
    "metres": "m",
    "cm": "cm",
    "centimeter": "cm",
    "centimeters": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "mm": "mm",
    "millimeter": "mm",
    "millimeters": "mm",
    "mi": "mi",
    "mile": "mi",
    "miles": "mi",
    "nmi": "nmi",
    "nautical": "nmi",
    "nauticalmile": "nmi",
    "nauticalmiles": "nmi",
    "yd": "yd",
    "yard": "yd",
    "yards": "yd",
    "ft": "ft",
    "foot": "ft",
    "feet": "ft",
    "in": "in",
    "inch": "in",
    "inches": "in",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "mg": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "t": "t",
    "tonne": "t",
    "tonnes": "t",
    "st": "st",
    "stone": "st",
    "stones": "st",
    "c": "c",
    "celsius": "c",
    "centigrade": "c",
    "f": "f",
    "fahrenheit": "f",
    "k": "k",
    "kelvin": "k",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "gal": "gal",
    "gallon": "gal",
    "gallons": "gal",
    "qt": "qt",
    "quart": "qt",
    "quarts": "qt",
    "pt": "pt",
    "pint": "pt",
    "pints": "pt",
    "cup": "cup",
    "cups": "cup",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "floz": "floz",
    "fluidounce": "floz",
    "fluidounces": "floz",
    "b": "b",
    "byte": "b",
    "bytes": "b",
    "kb": "kb",
    "kilobyte": "kb",
    "kilobytes": "kb",
    "mb": "mb",
    "megabyte": "mb",
    "megabytes": "mb",
    "gb": "gb",
    "gigabyte": "gb",
    "gigabytes": "gb",
    "tb": "tb",
    "terabyte": "tb",
    "terabytes": "tb",
    "kib": "kib",
    "mib": "mib",
    "gib": "gib",
    "tib": "tib",
    "s": "s",
    "sec": "s",
    "secs": "s",
    "second": "s",
    "seconds": "s",
    "min": "min",
    "mins": "min",
    "minute": "min",
    "minutes": "min",
    "h": "h",
    "hr": "h",
    "hrs": "h",
    "hour": "h",
    "hours": "h",
    "d": "d",
    "day": "d",
    "days": "d",
    "kph": "kph",
    "kmh": "kph",
    "kmph": "kph",
    "mph": "mph",
    "mps": "mps",
    "kn": "kn",
    "knot": "kn",
    "knots": "kn",
    "m3": "m3",
    "cubicmeter": "m3",
    "cubicmetre": "m3",
    "cm3": "cm3",
    "cc": "cm3",
    "ft3": "ft3",
    "cuft": "ft3",
    "m2": "m2",
    "sqm": "m2",
    "sqmeter": "m2",
    "sqmetre": "m2",
    "km2": "km2",
    "ha": "ha",
    "hectare": "ha",
    "hectares": "ha",
    "acre": "acre",
    "acres": "acre",
    "ft2": "ft2",
    "sqft": "ft2",
    "mi2": "mi2",
    "sqmi": "mi2",
    "pa": "pa",
    "pascal": "pa",
    "pascals": "pa",
    "kpa": "kpa",
    "bar": "bar",
    "bars": "bar",
    "atm": "atm",
    "atmosphere": "atm",
    "atmospheres": "atm",
    "psi": "psi",
    "mmhg": "mmhg",
    "torr": "mmhg",
    "j": "j",
    "joule": "j",
    "joules": "j",
    "kj": "kj",
    "kilojoule": "kj",
    "kilojoules": "kj",
    "cal": "cal",
    "kcal": "kcal",
    "kilocalorie": "kcal",
    "kilocalories": "kcal",
    "calorie": "kcal",
    "calories": "kcal",
    "wh": "wh",
    "watthour": "wh",
    "watthours": "wh",
    "kwh": "kwh",
    "kilowatthour": "kwh",
    "kilowatthours": "kwh",
    "btu": "btu",
    "w": "w",
    "watt": "w",
    "watts": "w",
    "kw": "kw",
    "kilowatt": "kw",
    "kilowatts": "kw",
    "hp": "hp",
    "horsepower": "hp",
    "deg": "deg",
    "degree": "deg",
    "degrees": "deg",
    "rad": "rad",
    "radian": "rad",
    "radians": "rad",
    "gon": "gon",
    "grad": "gon",
    "grads": "gon",
    "gradians": "gon",
}

UNITS: dict[str, dict[str, float | str]] = {
    "mm": {"dim": "length", "to_base": 0.001},
    "cm": {"dim": "length", "to_base": 0.01},
    "m": {"dim": "length", "to_base": 1},
    "km": {"dim": "length", "to_base": 1000},
    "in": {"dim": "length", "to_base": 0.0254},
    "ft": {"dim": "length", "to_base": 0.3048},
    "yd": {"dim": "length", "to_base": 0.9144},
    "mi": {"dim": "length", "to_base": 1609.344},
    "nmi": {"dim": "length", "to_base": 1852},
    "mg": {"dim": "mass", "to_base": 0.000001},
    "g": {"dim": "mass", "to_base": 0.001},
    "kg": {"dim": "mass", "to_base": 1},
    "t": {"dim": "mass", "to_base": 1000},
    "oz": {"dim": "mass", "to_base": 0.028349523125},
    "lb": {"dim": "mass", "to_base": 0.45359237},
    "st": {"dim": "mass", "to_base": 6.35029318},
    "ml": {"dim": "volume", "to_base": 0.001},
    "l": {"dim": "volume", "to_base": 1},
    "cup": {"dim": "volume", "to_base": 0.2365882365},
    "tbsp": {"dim": "volume", "to_base": 0.01478676478125},
    "tsp": {"dim": "volume", "to_base": 0.00492892159375},
    "floz": {"dim": "volume", "to_base": 0.0295735295625},
    "pt": {"dim": "volume", "to_base": 0.473176473},
    "qt": {"dim": "volume", "to_base": 0.946352946},
    "gal": {"dim": "volume", "to_base": 3.785411784},
    "m3": {"dim": "volume", "to_base": 1000},
    "cm3": {"dim": "volume", "to_base": 0.001},
    "ft3": {"dim": "volume", "to_base": 28.316846592},
    "b": {"dim": "data", "to_base": 1},
    "kb": {"dim": "data", "to_base": 1000},
    "mb": {"dim": "data", "to_base": 1e6},
    "gb": {"dim": "data", "to_base": 1e9},
    "tb": {"dim": "data", "to_base": 1e12},
    "kib": {"dim": "data", "to_base": 1024},
    "mib": {"dim": "data", "to_base": 1048576},
    "gib": {"dim": "data", "to_base": 1073741824},
    "tib": {"dim": "data", "to_base": 1099511627776},
    "c": {"dim": "temp", "to_base": 0},
    "f": {"dim": "temp", "to_base": 0},
    "k": {"dim": "temp", "to_base": 0},
    "s": {"dim": "duration", "to_base": 1},
    "min": {"dim": "duration", "to_base": 60},
    "h": {"dim": "duration", "to_base": 3600},
    "d": {"dim": "duration", "to_base": 86400},
    "m2": {"dim": "area", "to_base": 1},
    "km2": {"dim": "area", "to_base": 1e6},
    "ha": {"dim": "area", "to_base": 10000},
    "acre": {"dim": "area", "to_base": 4046.8564224},
    "ft2": {"dim": "area", "to_base": 0.09290304},
    "mi2": {"dim": "area", "to_base": 2589988.110336},
    "kph": {"dim": "speed", "to_base": 1000 / 3600},
    "mph": {"dim": "speed", "to_base": 1609.344 / 3600},
    "mps": {"dim": "speed", "to_base": 1},
    "kn": {"dim": "speed", "to_base": 1852 / 3600},
    "pa": {"dim": "pressure", "to_base": 1},
    "kpa": {"dim": "pressure", "to_base": 1000},
    "bar": {"dim": "pressure", "to_base": 1e5},
    "atm": {"dim": "pressure", "to_base": 101325},
    "psi": {"dim": "pressure", "to_base": 6894.757293168361},
    "mmhg": {"dim": "pressure", "to_base": 133.32236842105263},
    "j": {"dim": "energy", "to_base": 1},
    "kj": {"dim": "energy", "to_base": 1000},
    "cal": {"dim": "energy", "to_base": 4.184},
    "kcal": {"dim": "energy", "to_base": 4184},
    "wh": {"dim": "energy", "to_base": 3600},
    "kwh": {"dim": "energy", "to_base": 3.6e6},
    "btu": {"dim": "energy", "to_base": 1055.05585262},
    "w": {"dim": "power", "to_base": 1},
    "kw": {"dim": "power", "to_base": 1000},
    "hp": {"dim": "power", "to_base": 745.6998715822702},
    "deg": {"dim": "angle", "to_base": 1},
    "rad": {"dim": "angle", "to_base": 180 / math.pi},
    "gon": {"dim": "angle", "to_base": 0.9},
}

_NUMBER = r"(-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+\-]?\d+)?)"
_UNIT = r"([a-z][a-z0-9]*)"
QUERY_RE = re.compile(rf"^{_NUMBER}\s*{_UNIT}\s+(?:to|in|into|as)\s+{_UNIT}$", re.IGNORECASE)
HOW_MANY_RE = re.compile(
    rf"^how\s+many\s+{_UNIT}\s+(?:are\s+there\s+in|are\s+in|is|are|in)\s+{_NUMBER}\s*{_UNIT}$",
    re.IGNORECASE,
)


def resolve_unit(name: str) -> dict[str, float | str] | None:
    unit_id = ALIASES.get(name.lower())
    if not unit_id:
        return None
    unit = UNITS[unit_id]
    return {"id": unit_id, "dim": unit["dim"], "to_base": unit["to_base"]}


def normalize_unit_query(query: str) -> str:
    text = replace_number_words(query)
    text = re.sub(r"(\d)\s*°\s*(to|in|into|as)\b", r"\1 deg \2", text, flags=re.IGNORECASE)
    text = text.replace("²", "2").replace("³", "3")
    text = re.sub(r"km\s*/\s*h(?:r)?", "kph", text, flags=re.IGNORECASE)
    text = re.sub(r"mi\s*/\s*h", "mph", text, flags=re.IGNORECASE)
    text = re.sub(r"(^|[^a-z])m\s*/\s*s\b", r"\1mps", text, flags=re.IGNORECASE)

    def fraction(match: re.Match[str]) -> str:
        divisor = float(match.group(2))
        if not divisor:
            return match.group(0)
        return str(float(match.group(1)) / divisor)

    text = re.sub(r"\b(\d+)\s*/\s*(\d+)(?=\s)", fraction, text)
    text = re.sub(r"\bfluid\s+ounces?\b", "floz", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfl(?:uid)?\s*ozs?\b", "floz", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*degrees?\s+(f|c|k|fahrenheit|celsius|kelvin|centigrade)\b", r" \1", text, flags=re.IGNORECASE)
    text = text.replace("°", " ")
    nxt = re.sub(r"(\d),(\d)", r"\1\2", text)
    while nxt != text:
        text = nxt
        nxt = re.sub(r"(\d),(\d)", r"\1\2", text)
    nxt = re.sub(r"(\d) (\d{3})\b", r"\1\2", text)
    while nxt != text:
        text = nxt
        nxt = re.sub(r"(\d) (\d{3})\b", r"\1\2", text)
    text = re.sub(r"\b(to|into|as)\s+an?\s+", r"\1 ", text, flags=re.IGNORECASE)

    def article_unit(match: re.Match[str]) -> str:
        word = match.group(1)
        if word.lower() in ALIASES:
            return f"1 {word}"
        return match.group(0)

    return re.sub(r"\ban?\s+([a-z][a-z0-9]*)\b", article_unit, text, flags=re.IGNORECASE)


def parse_unit_query(query: str) -> dict[str, float | str] | None:
    text = normalize_unit_query(query).strip()
    match = QUERY_RE.match(text)
    if match:
        return {"value": float(match.group(1)), "from": match.group(2), "to": match.group(3)}
    spoken = HOW_MANY_RE.match(text)
    if not spoken:
        return None
    return {"value": float(spoken.group(2)), "from": spoken.group(3), "to": spoken.group(1)}


def _convert_temp(value: float, from_id: str, to_id: str) -> float:
    celsius = value
    if from_id == "f":
        celsius = (value - 32) * (5 / 9)
    elif from_id == "k":
        celsius = value - 273.15
    if to_id == "c":
        return celsius
    if to_id == "f":
        return celsius * (9 / 5) + 32
    return celsius + 273.15


def convert_units(value: float, from_name: str, to_name: str) -> dict[str, float | str] | None:
    source = resolve_unit(from_name)
    dest = resolve_unit(to_name)
    if not source or not dest or source["dim"] != dest["dim"] or source["id"] == dest["id"]:
        return None
    if source["dim"] == "temp":
        converted = _convert_temp(value, str(source["id"]), str(dest["id"]))
        return {"value": converted, "from_id": source["id"], "to_id": dest["id"]}
    converted = value * float(source["to_base"]) / float(dest["to_base"])
    return {"value": converted, "from_id": source["id"], "to_id": dest["id"]}


def format_unit_value(n: float) -> str:
    if n == 0:
        return "0"
    if n == int(n) and abs(n) < 1e12:
        return str(int(n))
    rounded = float(f"{n:.8g}")
    if rounded == int(rounded) and abs(rounded) < 1e12:
        return str(int(rounded))
    return str(rounded)


def convert_query(query: str) -> dict[str, str] | None:
    parsed = parse_unit_query(query)
    if not parsed:
        return None
    converted = convert_units(float(parsed["value"]), str(parsed["from"]), str(parsed["to"]))
    if not converted:
        return None
    return {
        "title": f"{format_unit_value(float(converted['value']))} {converted['to_id']}",
        "description": f"{format_unit_value(float(parsed['value']))} {converted['from_id']}",
        "copy_text": format_unit_value(float(converted["value"])),
    }
