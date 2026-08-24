"""Empty-search copy, ported from spotlight-goshos noResults.js."""

from __future__ import annotations


def no_results_title() -> str:
    return "No Results"


def no_results_detail(query: str) -> str:
    return f'No results for "{query}"'


def should_show_no_results(query: str, result_count: int) -> bool:
    return bool(query.strip()) and result_count == 0
