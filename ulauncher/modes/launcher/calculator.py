"""Recursive-descent arithmetic, ported from spotlight-goshos calculator.js."""

from __future__ import annotations

import math
import re

from ulauncher.modes.launcher.number_words import replace_number_words, replace_ordinal_power

CONSTS = {"pi": math.pi, "e": math.e}


def _tan(n: float) -> float:
    rad = n * math.pi / 180
    if abs(math.cos(rad)) < 1e-10:
        return float("nan")
    return math.tan(rad)


def _cbrt(n: float) -> float:
    # math.cbrt is 3.11+; n ** (1/3) is complex for negatives on 3.8–3.10.
    cbrt = getattr(math, "cbrt", None)
    if cbrt is not None:
        return float(cbrt(n))
    return math.copysign(abs(n) ** (1 / 3), n)


FUNCS = {
    "sqrt": math.sqrt,
    "cbrt": _cbrt,
    "abs": abs,
    "log": math.log10,
    "log2": math.log2,
    "ln": math.log,
    "sin": lambda n: math.sin(n * math.pi / 180),
    "cos": lambda n: math.cos(n * math.pi / 180),
    "tan": _tan,
    "asin": lambda n: math.asin(n) * 180 / math.pi,
    "acos": lambda n: math.acos(n) * 180 / math.pi,
    "atan": lambda n: math.atan(n) * 180 / math.pi,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
}

_TOKEN_RE = re.compile(
    r"\s*(0x[0-9a-fA-F]+|0b[01]+|(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+\-]?[0-9]+)?|[a-zA-Z][a-zA-Z0-9]*|[+\-*/%()^!])"
)


def normalize_math(source: str) -> str:
    text = source
    text = re.sub(r"[\r\n]+", "", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[πΠ𝜋]", "pi", text)
    text = text.replace("²", "^2").replace("³", "^3")
    text = re.sub(r"\bsquared\b", "^2", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcubed\b", "^3", text, flags=re.IGNORECASE)
    text = text.replace("°", "")
    text = text.replace("×", "*").replace("÷", "/")
    text = re.sub(r"[−–—]", "-", text)
    text = re.sub(r"[⋅·]", "*", text)
    text = text.replace("**", "^")
    text = re.sub(r"\bplus\b", "+", text, flags=re.IGNORECASE)
    text = re.sub(r"\bminus\b", "-", text, flags=re.IGNORECASE)
    text = re.sub(r"\badd\b", "+", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsubtract\b", "-", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:times|multiplied\s+by)\b", "*", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdivided\s+by\b", "/", text, flags=re.IGNORECASE)
    text = re.sub(r"\bover\b", "/", text, flags=re.IGNORECASE)
    text = re.sub(r"\bto the power of\b", "^", text, flags=re.IGNORECASE)
    text = re.sub(r"\bto the\s+(\d+)(?:st|nd|rd|th)?(?:\s+power)?\b", r"^\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnegative\b", "-", text, flags=re.IGNORECASE)
    text = replace_ordinal_power(text)
    text = replace_number_words(text)
    text = re.sub(r"√\s*\(", "sqrt(", text)
    text = re.sub(r"√\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", text)
    text = re.sub(r"(\d)\s+[xX]\s+(\d)", r"\1*\2", text)
    text = re.sub(r"([1-9]\d*(?:\.\d+)?)[xX](\d)", r"\1*\2", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", r"(\1/100)*\2", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*percent\s+of\s*(\d+(?:\.\d+)?)", r"(\1/100)*\2", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhalf\s+of\s+(\d+(?:\.\d+)?)", r"(\1/2)", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsquare\s+root\s+of\s+(\d+(?:\.\d+)?)", r"sqrt(\1)", text, flags=re.IGNORECASE)
    text = re.sub(r"=([+\-]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[+\-]?\d+)?)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"=+\s*$", "", text)
    nxt = re.sub(r"(\d),(\d)", r"\1\2", text)
    while nxt != text:
        text = nxt
        nxt = re.sub(r"(\d),(\d)", r"\1\2", text)
    nxt = re.sub(r"(\d) (\d{3})\b", r"\1\2", text)
    while nxt != text:
        text = nxt
        nxt = re.sub(r"(\d) (\d{3})\b", r"\1\2", text)
    return text


def _has_evaluable_value(text: str, allow_bare: bool) -> bool:
    if re.search(r"\d", text) or re.search(r"\bpi\b", text, re.IGNORECASE):
        return True
    if not re.search(r"\be\b", text, re.IGNORECASE):
        return False
    return allow_bare or bool(re.search(r"[+\-*/%^!()]", text))


def _looks_like_math(text: str, allow_bare: bool) -> bool:
    if allow_bare:
        return True
    if re.search(r"[+\-*/%^!]", text):
        return True
    stripped = re.sub(r"0x[0-9a-fA-F]+", "0", text, flags=re.IGNORECASE)
    stripped = re.sub(r"0b[01]+", "0", stripped)
    stripped = re.sub(r"\d+(?:\.\d+)?[eE][+\-]?\d+", "0", stripped)
    return bool(re.search(r"[a-zA-Z]", stripped))


def _is_ident(tok: str | None) -> bool:
    return bool(tok and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9]*", tok))


def evaluate_arithmetic(source: str, allow_bare: bool = False) -> float | None:
    text = normalize_math(source)
    if not _has_evaluable_value(text, allow_bare) or not _looks_like_math(text, allow_bare):
        return None
    tokens = [m.group(1) for m in _TOKEN_RE.finditer(text)]
    if "".join(tokens) != re.sub(r"\s+", "", text) or not tokens:
        return None
    pos = 0

    def peek() -> str | None:
        return tokens[pos] if pos < len(tokens) else None

    def consume() -> str:
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def is_implicit_factor() -> bool:
        nxt = peek()
        if nxt == "(":
            return True
        if not _is_ident(nxt):
            return False
        return nxt.lower() != "e"  # type: ignore[union-attr]

    def factorial(n: float) -> float | None:
        if n != int(n) or n < 0 or n > 170:
            return None
        value = 1
        for i in range(2, int(n) + 1):
            value *= i
        return value

    def is_binary_modulo_percent() -> bool:
        if peek() != "%":
            return False
        nxt = tokens[pos + 1] if pos + 1 < len(tokens) else None
        if nxt is None:
            return False
        if nxt == "(" or _is_ident(nxt):
            return False
        if re.fullmatch(r"0x[0-9a-fA-F]+", nxt, re.IGNORECASE) or re.fullmatch(r"0b[01]+", nxt):
            return True
        return bool(re.fullmatch(r"[0-9.]+(?:[eE][+\-]?[0-9]+)?", nxt))

    def postfix_fact(value: float | None) -> float | None:
        if value is None or peek() != "!":
            return value
        consume()
        return factorial(value)

    def postfix_percent(value: float | None) -> float | None:
        if value is None or peek() != "%" or is_binary_modulo_percent():
            return value
        consume()
        return value / 100

    def finish_value(value: float | None) -> float | None:
        if value is None:
            return None
        return postfix_percent(postfix_fact(value))

    def apply_func(fn, v: float) -> float | None:  # type: ignore[no-untyped-def]
        try:
            out = fn(v)
        except (ValueError, OverflowError, ZeroDivisionError):
            return None
        if not math.isfinite(out):
            return None
        return float(out)

    def parse_expression() -> float | None:
        value = parse_term()
        if value is None:
            return None
        while peek() in {"+", "-"}:
            op = consume()
            right = parse_term()
            if right is None:
                return None
            value = value + right if op == "+" else value - right
        return value

    def parse_term() -> float | None:
        value = parse_unary()
        if value is None:
            return None
        while peek() in {"*", "/", "%"} or is_implicit_factor():
            if is_implicit_factor():
                right = parse_unary()
                if right is None:
                    return None
                value *= right
                continue
            op = consume()
            right = parse_unary()
            if right is None:
                return None
            if op == "*":
                value *= right
            elif right == 0:
                return None
            elif op == "/":
                value /= right
            else:
                value %= right
        return value

    def parse_unary() -> float | None:
        if peek() == "-":
            consume()
            v = parse_unary()
            return None if v is None else -v
        if peek() == "+":
            consume()
            return parse_unary()
        return parse_power()

    def parse_power() -> float | None:
        value = parse_primary()
        if value is None:
            return None
        if peek() != "^":
            return value
        consume()
        exp = parse_unary()
        if exp is None:
            return None
        try:
            return math.pow(value, exp)
        except (ValueError, OverflowError):
            return None

    def parse_primary() -> float | None:
        tok = peek()
        if tok is None:
            return None
        if tok == "(":
            consume()
            v = parse_expression()
            if v is None or peek() != ")":
                return None
            consume()
            return finish_value(v)
        if _is_ident(tok):
            name = tok.lower()
            consume()
            if name in FUNCS:
                if peek() == "(":
                    consume()
                    v = parse_expression()
                    if v is None or peek() != ")":
                        return None
                    consume()
                    return finish_value(apply_func(FUNCS[name], v))
                v = parse_unary()
                if v is None:
                    return None
                return finish_value(apply_func(FUNCS[name], v))
            if name in CONSTS:
                return finish_value(CONSTS[name])
            return None
        if re.fullmatch(r"0x[0-9a-fA-F]+", tok, re.IGNORECASE):
            consume()
            return finish_value(int(tok, 16))
        if re.fullmatch(r"0b[01]+", tok):
            consume()
            return finish_value(int(tok, 2))
        if re.fullmatch(r"[0-9.]+(?:[eE][+\-]?[0-9]+)?", tok):
            consume()
            return finish_value(float(tok))
        return None

    result = parse_expression()
    if result is None or pos != len(tokens) or not math.isfinite(result):
        return None
    return result


def format_hex(n: float) -> str:
    if n != int(n) or n < 0:
        return ""
    return f"0x{int(n):x}"


def calculator_description(n: float) -> str:
    hex_form = format_hex(n)
    if hex_form:
        return f"{hex_form} · press Enter to copy"
    return "Press Enter to copy to clipboard"


def format_number(n: float) -> str:
    if n == 0:
        return "0"
    if n == int(n) and abs(n) < 1e15:
        return str(int(n))
    rounded = float(f"{n:.12g}")
    if rounded == int(rounded) and abs(rounded) < 1e15:
        return str(int(rounded))
    return str(rounded)
