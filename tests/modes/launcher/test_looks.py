from __future__ import annotations

from ulauncher.modes.launcher.looks import LOOKS, get_look, look_ids


def test_seventeen_looks() -> None:
    ids = look_ids()
    assert len(ids) == 17
    assert "spotlight" in ids
    assert "popos" in ids
    assert get_look("missing")["id"] == LOOKS[0]["id"]
    pop = get_look("popos")
    assert pop["look"]["result_order"] == "windows-first"
    assert pop["look"]["show_numbers"] is True
