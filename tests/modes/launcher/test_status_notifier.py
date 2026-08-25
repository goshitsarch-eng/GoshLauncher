from __future__ import annotations

from types import SimpleNamespace

import pytest

from ulauncher.modes.launcher.status_notifier import (
    MENU_ABOUT,
    MENU_EXIT,
    MENU_IFACE,
    MENU_PATH,
    MENU_PREFERENCES,
    MENU_REVISION,
    MENU_SEPARATOR,
    MENU_SHOW,
    MENU_XML,
    SNI_IFACE,
    SNI_PATH,
    SNI_XML,
    dbusmenu_layout,
    filter_menu_props,
    menu_entries,
    menu_event_action,
    menu_group_properties,
    menu_props_for_id,
    pack_get_layout_result,
    pack_group_properties,
    preferred_tray_backend,
    register_item_argument,
    sni_bus_name,
    sni_method_action,
    sni_property_variant,
    sni_status,
    watcher_name_is_ours,
)


def test_sni_bus_name_and_status() -> None:
    assert sni_bus_name(4242) == "org.kde.StatusNotifierItem-4242-1"
    assert sni_bus_name(1, 2) == "org.kde.StatusNotifierItem-1-2"
    assert sni_status(True) == "Active"
    assert sni_status(False) == "Passive"


def test_register_item_argument_prefers_owned_well_known_name() -> None:
    assert (
        register_item_argument(
            well_known_name="org.kde.StatusNotifierItem-1-1",
            name_owned=True,
            object_path=SNI_PATH,
        )
        == "org.kde.StatusNotifierItem-1-1"
    )
    assert (
        register_item_argument(
            well_known_name="org.kde.StatusNotifierItem-1-1",
            name_owned=False,
            object_path=SNI_PATH,
        )
        == SNI_PATH
    )


def test_watcher_names_and_sni_clicks() -> None:
    assert watcher_name_is_ours("org.kde.StatusNotifierWatcher") is True
    assert watcher_name_is_ours("org.freedesktop.StatusNotifierWatcher") is True
    assert watcher_name_is_ours("org.gnome.Shell") is False
    assert sni_method_action("Activate") == "show"
    assert sni_method_action("SecondaryActivate") == "show"
    assert sni_method_action("ContextMenu") is None
    assert sni_method_action("Scroll") is None


def test_menu_click_actions_match_tray_commands() -> None:
    assert menu_event_action(MENU_SHOW, "clicked") == "show"
    assert menu_event_action(MENU_PREFERENCES, "clicked") == "preferences"
    assert menu_event_action(MENU_ABOUT, "clicked") == "about"
    assert menu_event_action(MENU_EXIT, "clicked") == "quit"
    assert menu_event_action(MENU_SEPARATOR, "clicked") is None
    assert menu_event_action(MENU_SHOW, "hovered") is None


def test_menu_layout_lists_all_entries_under_root() -> None:
    ids = [item_id for item_id, _props in menu_entries()]
    assert ids == [MENU_SHOW, MENU_PREFERENCES, MENU_ABOUT, MENU_SEPARATOR, MENU_EXIT]
    revision, node = dbusmenu_layout(0, -1, [])
    assert revision == MENU_REVISION
    node_id, props, children = node
    assert node_id == 0
    assert props["children-display"] == "submenu"
    child_ids = [child[0] for child in children]
    assert child_ids == ids
    labels = [child[1].get("label") for child in children if "label" in child[1]]
    assert "Show GoshLauncher" in labels
    assert "Exit" in labels


def test_menu_layout_filters_properties_and_depth() -> None:
    _revision, node = dbusmenu_layout(0, -1, ["label"])
    _node_id, props, children = node
    assert list(props) == ["label"]
    assert list(children[0][1]) == ["label"]
    _revision, shallow = dbusmenu_layout(0, 0, [])
    assert shallow[2] == []
    _revision, leaf = dbusmenu_layout(MENU_SHOW, 1, ["label"])
    assert leaf[0] == MENU_SHOW
    assert leaf[1] == {"label": "Show GoshLauncher"}
    assert leaf[2] == []


def test_menu_group_properties_skips_unknown_ids() -> None:
    rows = menu_group_properties([0, MENU_SHOW, 99], ["label"])
    assert rows[0][0] == 0
    assert rows[1] == (MENU_SHOW, {"label": "Show GoshLauncher"})
    assert all(item_id != 99 for item_id, _props in rows)
    assert filter_menu_props({"label": "a", "enabled": True}, []) == {"label": "a", "enabled": True}
    assert menu_props_for_id(99) is None


def test_preferred_tray_backend_uses_sni_without_gtk_menu() -> None:
    assert preferred_tray_backend("XApp", False) == "XApp"
    assert preferred_tray_backend("AyatanaIndicator", True) == "AyatanaIndicator"
    assert preferred_tray_backend("AyatanaIndicator", False) == "StatusNotifierItem"
    assert preferred_tray_backend(None, False) == "StatusNotifierItem"


def test_introspection_xml_exports_sni_and_dbusmenu() -> None:
    from ulauncher.gi import Gio

    sni = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
    menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML)
    sni_iface = sni.lookup_interface(SNI_IFACE)
    menu_iface = menu.lookup_interface(MENU_IFACE)
    assert sni_iface is not None
    assert menu_iface is not None
    sni_methods = {method.name for method in sni_iface.methods}
    menu_methods = {method.name for method in menu_iface.methods}
    assert {"Activate", "SecondaryActivate", "ContextMenu", "Scroll"} <= sni_methods
    assert {"GetLayout", "Event", "AboutToShow"} <= menu_methods


def test_packed_layout_and_sni_properties_have_spec_types() -> None:
    revision, node = dbusmenu_layout(0, -1, [])
    layout = pack_get_layout_result(revision, node)
    assert layout.get_type_string() == "(u(ia{sv}av))"
    unpacked = layout.unpack()
    assert unpacked[0] == MENU_REVISION
    assert unpacked[1][0] == 0
    rows = pack_group_properties(menu_group_properties([MENU_SHOW], ["label"]))
    assert rows.get_type_string() == "(a(ia{sv}))"
    status = sni_property_variant(
        "Status",
        status="Active",
        icon_name="ulauncher",
        icon_theme_path="",
        title="GoshLauncher",
        item_id="ulauncher",
    )
    assert status is not None
    assert status.unpack() == "Active"
    menu_path = sni_property_variant(
        "Menu",
        status="Active",
        icon_name="ulauncher",
        icon_theme_path="",
        title="GoshLauncher",
        item_id="ulauncher",
    )
    assert menu_path is not None
    assert menu_path.unpack() == MENU_PATH
    tooltip = sni_property_variant(
        "ToolTip",
        status="Active",
        icon_name="ulauncher",
        icon_theme_path="",
        title="GoshLauncher",
        item_id="ulauncher",
    )
    assert tooltip is not None
    assert tooltip.get_type_string() == "(sa(iiay)ss)"


def test_status_notifier_item_activate_invokes_show(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.status_notifier import StatusNotifierItem

    seen: list[str] = []
    item = StatusNotifierItem(seen.append)
    monkeypatch.setattr(
        "ulauncher.utils.scheduling.run_when_idle",
        lambda func, *args, **kwargs: func(*args, **kwargs),
    )
    invocation = SimpleNamespace(return_value=lambda _value: None)
    item._on_sni_method(None, "", SNI_PATH, SNI_IFACE, "Activate", None, invocation)
    assert seen == ["show"]
    item._on_menu_method(
        None,
        "",
        MENU_PATH,
        MENU_IFACE,
        "Event",
        SimpleNamespace(unpack=lambda: (MENU_PREFERENCES, "clicked", None, 0)),
        invocation,
    )
    assert seen == ["show", "preferences"]
