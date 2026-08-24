"""GNOME-style word prefix matching, ported from spotlight-goshos wordMatch.js."""

from __future__ import annotations

import re

SUBSTRING_MIN = 3
_WORD_SPLIT = re.compile(r"\s+")


def word_prefix_match(name_lower: str, query_lower: str) -> bool:
    length = len(query_lower)
    if length == 0 or length > len(name_lower):
        return False
    # goshos wordMatch.js: match at 0 or after a delimiter, inclusive end index
    for i in range(len(name_lower) - length + 1):
        if name_lower[i : i + length] == query_lower and (i == 0 or name_lower[i - 1] in " -_./"):
            return True
    return False


def text_matches_query(text: str, query: str) -> bool:
    if not query:
        return False
    t = text.lower()
    q = query.lower()
    if t.startswith(q) or word_prefix_match(t, q):
        return True
    return len(q) >= SUBSTRING_MIN and q in t


def text_matches_all_words(text: str, query: str) -> bool:
    words = [word for word in _WORD_SPLIT.split(query.lower()) if word]
    if len(words) < 2:
        return False
    return all(text_matches_query(text, word) for word in words)


def keyword_matches_query(keyword: str, query: str) -> bool:
    if not keyword or not query:
        return False
    kw = keyword.lower()
    q = query.lower()
    if kw.startswith(q) or kw == q or word_prefix_match(kw, q):
        return True
    nkw = kw.replace("-", "").replace("_", "").replace(" ", "")
    nq = q.replace("-", "").replace("_", "").replace(" ", "")
    return bool(nq) and nkw.startswith(nq)


def path_matches_query(path: str, query: str) -> bool:
    if not path or not query:
        return False
    p = path.lower()
    q = query.lower()
    return p.startswith(q) or word_prefix_match(p, q)


def label_matches_query(text: str, query: str) -> bool:
    if not text or not query:
        return False
    t = text.lower()
    q = query.lower()
    return t.startswith(q) or word_prefix_match(t, q)


def id_matches_query(identifier: str, query: str) -> bool:
    if not identifier or not query:
        return False
    q = query.lower()
    if len(q) < SUBSTRING_MIN:
        return False
    for token in identifier.lower().split():
        if not token:
            continue
        if word_prefix_match(token, q):
            return True
        last = token.split(".")[-1]
        if last.startswith(q):
            return True
    return False
