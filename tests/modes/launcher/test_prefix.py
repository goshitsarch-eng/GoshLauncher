from __future__ import annotations

from ulauncher.modes.launcher.prefix import is_prefix_token, parse_query


def test_parse_query_strips_forced_prefixes() -> None:
    assert parse_query("= 1+2") == {"mode": "calculator", "query": "1+2"}
    assert parse_query("@ ulauncher") == {"mode": "web", "query": "ulauncher"}
    assert parse_query("! ls /tmp") == {"mode": "command", "query": "ls /tmp"}


def test_space_required_for_dot_dollar_hash() -> None:
    assert parse_query("$ firefox") == {"mode": "windows", "query": "firefox"}
    assert parse_query("$HOME")["mode"] == "all"
    assert parse_query("# wifi") == {"mode": "settings", "query": "wifi"}
    assert parse_query("#ff0000")["mode"] == "all"
    assert parse_query(". notes") == {"mode": "files", "query": "notes"}
    assert parse_query(".bashrc")["mode"] == "all"


def test_is_prefix_token() -> None:
    assert is_prefix_token("=2", "=")
    assert is_prefix_token("$", "$")
    assert is_prefix_token("$ foo", "$")
    assert not is_prefix_token("$HOME", "$")
    assert not is_prefix_token("#ff0000", "#")
