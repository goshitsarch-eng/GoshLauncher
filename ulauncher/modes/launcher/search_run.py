"""Run a search plan against provider functions, ported from spotlight-goshos searchRun.js."""

from __future__ import annotations

from typing import Any, Callable


def safe_provider_results(run: Callable[[], Any]) -> list[Any]:
    try:
        rows = run()
    except Exception:
        return []
    return list(rows) if isinstance(rows, list) else []


def run_isolated(run: Callable[[], Any]) -> None:
    """goshos searchRun: a throwing provider must not hide later categories."""
    try:
        run()
    except Exception:
        return


def append_provider_results(
    results: list[Any],
    run: Callable[..., Any],
    query: str,
    max_results: int,
    settings: Any,
    mode: Any,
) -> None:
    results.extend(safe_provider_results(lambda: run(query, max_results, settings, mode)))


def collect_search_results(
    plan: dict[str, Any],
    max_results: int,
    providers: dict[str, Callable[..., Any]],
    settings: Any,
) -> list[Any]:
    results: list[Any] = []
    for name in plan.get("providers") or []:
        run = providers.get(name)
        if not run:
            continue
        append_provider_results(results, run, plan["query"], max_results, settings, plan.get("mode"))

    if not results and plan.get("web_fallback") and providers.get("web"):
        append_provider_results(results, providers["web"], plan["query"], max_results, settings, plan.get("mode"))

    return results
