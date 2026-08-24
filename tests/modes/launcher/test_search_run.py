from __future__ import annotations

from ulauncher.modes.launcher.search_run import collect_search_results, safe_provider_results


def test_collect_search_results_runs_providers_and_web_fallback() -> None:
    def apps(query: str, max_results: int, _settings: object, _mode: object) -> list[dict[str, object]]:
        return [{"title": "App", "n": max_results}] if query == "x" else []

    def web(query: str, _max_results: int, _settings: object, _mode: object) -> list[dict[str, str]]:
        return [{"title": f"web:{query}"}]

    providers = {"apps": apps, "web": web}
    planned = {"providers": ["apps"], "query": "x", "web_fallback": True}
    assert collect_search_results(planned, 4, providers, None)[0]["title"] == "App"
    assert collect_search_results(planned, 4, providers, None)[0]["n"] == 4
    fallback = {"providers": ["apps"], "query": "z", "web_fallback": True}
    assert collect_search_results(fallback, 3, providers, None)[0]["title"] == "web:z"
    off = {"providers": ["apps"], "query": "z", "web_fallback": False}
    assert collect_search_results(off, 3, providers, None) == []
    missing = {"providers": ["missing"], "query": "x", "web_fallback": False}
    assert collect_search_results(missing, 3, providers, None) == []


def test_throwing_provider_keeps_prior_rows() -> None:
    def apps(_query: str, _max_results: int, _settings: object, _mode: object) -> list[dict[str, str]]:
        return [{"title": "Kept"}]

    def windows(_query: str, _max_results: int, _settings: object, _mode: object) -> list[dict[str, str]]:
        message = "window vanished"
        raise RuntimeError(message)

    rows = collect_search_results(
        {"providers": ["apps", "windows"], "query": "x", "web_fallback": False},
        3,
        {"apps": apps, "windows": windows},
        None,
    )
    assert rows[0]["title"] == "Kept"


def test_safe_provider_results_rejects_non_lists() -> None:
    def boom() -> list:
        message = "windows"
        raise RuntimeError(message)

    assert safe_provider_results(boom) == []
    assert safe_provider_results(lambda: [{"title": "App"}])[0]["title"] == "App"
    assert safe_provider_results(lambda: None) == []
