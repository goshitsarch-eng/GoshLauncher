"""StatusNotifierItem + DBusMenu tray for GTK4.

Ayatana indicators still need Gtk.Menu, which GTK4 removed. KDE, Unity, and the
GNOME AppIndicator extension speak this D-Bus protocol instead, so the tray
works without a GTK3 menu widget.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

from ulauncher import app_display_name, show_launcher_label

logger = logging.getLogger(__name__)

SNI_IFACE = "org.kde.StatusNotifierItem"
SNI_PATH = "/StatusNotifierItem"
MENU_IFACE = "com.canonical.dbusmenu"
MENU_PATH = "/StatusNotifierItem/Menu"
WATCHER_PATH = "/StatusNotifierWatcher"
WATCHER_IFACES = (
    ("org.kde.StatusNotifierWatcher", "org.kde.StatusNotifierWatcher"),
    ("org.freedesktop.StatusNotifierWatcher", "org.freedesktop.StatusNotifierWatcher"),
)

MENU_SHOW = 1
MENU_PREFERENCES = 2
MENU_ABOUT = 3
MENU_SEPARATOR = 4
MENU_EXIT = 5
MENU_REVISION = 1

_PROP_SIGS = {
    "label": "s",
    "type": "s",
    "enabled": "b",
    "visible": "b",
    "children-display": "s",
}

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <method name="ContextMenu">
      <arg direction="in" type="i" name="x"/>
      <arg direction="in" type="i" name="y"/>
    </method>
    <method name="Activate">
      <arg direction="in" type="i" name="x"/>
      <arg direction="in" type="i" name="y"/>
    </method>
    <method name="SecondaryActivate">
      <arg direction="in" type="i" name="x"/>
      <arg direction="in" type="i" name="y"/>
    </method>
    <method name="Scroll">
      <arg direction="in" type="i" name="delta"/>
      <arg direction="in" type="s" name="orientation"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
      <arg type="s" name="status"/>
    </signal>
    <signal name="NewIconThemePath">
      <arg type="s" name="icon_theme_path"/>
    </signal>
    <signal name="NewMenu"/>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg direction="in" type="i" name="parentId"/>
      <arg direction="in" type="i" name="recursionDepth"/>
      <arg direction="in" type="as" name="propertyNames"/>
      <arg direction="out" type="u" name="revision"/>
      <arg direction="out" type="(ia{sv}av)" name="layout"/>
    </method>
    <method name="GetGroupProperties">
      <arg direction="in" type="ai" name="ids"/>
      <arg direction="in" type="as" name="propertyNames"/>
      <arg direction="out" type="a(ia{sv})" name="properties"/>
    </method>
    <method name="GetProperty">
      <arg direction="in" type="i" name="id"/>
      <arg direction="in" type="s" name="name"/>
      <arg direction="out" type="v" name="value"/>
    </method>
    <method name="Event">
      <arg direction="in" type="i" name="id"/>
      <arg direction="in" type="s" name="eventId"/>
      <arg direction="in" type="v" name="data"/>
      <arg direction="in" type="u" name="timestamp"/>
    </method>
    <method name="AboutToShow">
      <arg direction="in" type="i" name="id"/>
      <arg direction="out" type="b" name="needsUpdate"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/>
      <arg type="a(ias)" name="removedProps"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
    <signal name="ItemActivationRequested">
      <arg type="i" name="id"/>
      <arg type="u" name="timestamp"/>
    </signal>
  </interface>
</node>
"""


def sni_bus_name(pid: int, index: int = 1) -> str:
    return f"org.kde.StatusNotifierItem-{pid}-{index}"


def sni_status(visible: bool) -> str:
    return "Active" if visible else "Passive"


def register_item_argument(*, well_known_name: str, name_owned: bool, object_path: str) -> str:
    if name_owned and well_known_name:
        return well_known_name
    return object_path


def watcher_name_is_ours(name: str) -> bool:
    return name in {bus for bus, _iface in WATCHER_IFACES}


def sni_method_action(method_name: str) -> str | None:
    if method_name in {"Activate", "SecondaryActivate"}:
        return "show"
    return None


def menu_entries() -> list[tuple[int, dict[str, Any]]]:
    return [
        (MENU_SHOW, {"label": show_launcher_label, "enabled": True, "visible": True}),
        (MENU_PREFERENCES, {"label": "Preferences", "enabled": True, "visible": True}),
        (MENU_ABOUT, {"label": "About", "enabled": True, "visible": True}),
        (MENU_SEPARATOR, {"type": "separator", "visible": True}),
        (MENU_EXIT, {"label": "Exit", "enabled": True, "visible": True}),
    ]


def menu_event_action(item_id: int, event_id: str) -> str | None:
    if event_id != "clicked":
        return None
    mapping = {
        MENU_SHOW: "show",
        MENU_PREFERENCES: "preferences",
        MENU_ABOUT: "about",
        MENU_EXIT: "quit",
    }
    return mapping.get(item_id)


def filter_menu_props(props: dict[str, Any], names: list[str]) -> dict[str, Any]:
    if not names:
        return dict(props)
    return {key: value for key, value in props.items() if key in names}


def menu_props_for_id(item_id: int) -> dict[str, Any] | None:
    if item_id == 0:
        return {"children-display": "submenu", "label": app_display_name}
    for mid, props in menu_entries():
        if mid == item_id:
            return dict(props)
    return None


def dbusmenu_layout(parent_id: int, recursion_depth: int, property_names: list[str]) -> tuple[int, Any]:
    """Return (revision, layout-node) for DBusMenu.GetLayout."""
    children: list[Any] = []
    if parent_id == 0 and recursion_depth != 0:
        children = [(item_id, filter_menu_props(props, property_names), []) for item_id, props in menu_entries()]
    root_props = filter_menu_props(menu_props_for_id(0) or {}, property_names)
    if parent_id == 0:
        return MENU_REVISION, (0, root_props, children)
    props = menu_props_for_id(parent_id)
    if props is None:
        return MENU_REVISION, (0, root_props, children)
    return MENU_REVISION, (parent_id, filter_menu_props(props, property_names), [])


def menu_group_properties(ids: list[int], property_names: list[str]) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    for item_id in ids:
        props = menu_props_for_id(item_id)
        if props is None:
            continue
        rows.append((item_id, filter_menu_props(props, property_names)))
    return rows


def preferred_tray_backend(lib: str | None, gtk_has_menu: bool) -> str:
    if lib == "XApp":
        return "XApp"
    if lib == "AyatanaIndicator" and gtk_has_menu:
        return "AyatanaIndicator"
    return "StatusNotifierItem"


def _session_connection() -> Any | None:
    try:
        from ulauncher.gi import Gio

        return Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except Exception:
        logger.debug("No session bus for StatusNotifierItem", exc_info=True)
        return None


def _variant(signature: str, value: Any) -> Any:
    from ulauncher.gi import GLib

    return GLib.Variant(signature, value)


def _pack_menu_props(props: dict[str, Any]) -> dict[str, Any]:
    packed: dict[str, Any] = {}
    for key, value in props.items():
        signature = _PROP_SIGS.get(key)
        if signature is None:
            continue
        packed[key] = _variant(signature, value)
    return packed


def pack_menu_node(node: Any) -> Any:
    node_id, props, children = node
    packed_children = [pack_menu_node(child) for child in children]
    return _variant("(ia{sv}av)", (node_id, _pack_menu_props(props), packed_children))


def pack_get_layout_result(revision: int, node: Any) -> Any:
    from ulauncher.gi import GLib

    return GLib.Variant.new_tuple(_variant("u", revision), pack_menu_node(node))


def pack_group_properties(rows: list[tuple[int, dict[str, Any]]]) -> Any:
    packed = [(item_id, _pack_menu_props(props)) for item_id, props in rows]
    return _variant("(a(ia{sv}))", (packed,))


def sni_property_variant(
    name: str,
    *,
    status: str,
    icon_name: str,
    icon_theme_path: str,
    title: str,
    item_id: str,
) -> Any | None:
    if name == "Category":
        return _variant("s", "ApplicationStatus")
    if name == "Id":
        return _variant("s", item_id)
    if name == "Title":
        return _variant("s", title)
    if name == "Status":
        return _variant("s", status)
    if name == "WindowId":
        return _variant("i", 0)
    if name == "IconName":
        return _variant("s", icon_name)
    if name == "IconThemePath":
        return _variant("s", icon_theme_path)
    if name in {"OverlayIconName", "AttentionIconName", "AttentionMovieName"}:
        return _variant("s", "")
    if name == "ToolTip":
        return _variant("(sa(iiay)ss)", (icon_name, [], title, show_launcher_label))
    if name == "ItemIsMenu":
        return _variant("b", False)
    if name == "Menu":
        return _variant("o", MENU_PATH)
    if name in {"IconPixmap", "AttentionIconPixmap", "OverlayIconPixmap"}:
        return _variant("a(iiay)", [])
    return None


def _menu_property_variant(item_id: int, name: str) -> Any:
    props = menu_props_for_id(item_id) or {}
    if name not in props:
        return _variant("b", True) if name in {"enabled", "visible"} else _variant("s", "")
    signature = _PROP_SIGS.get(name, "s")
    return _variant(signature, props[name])


def _request_name(connection: Any, name: str) -> bool:
    try:
        from ulauncher.gi import Gio, GLib

        result = connection.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "RequestName",
            GLib.Variant("(su)", (name, 0)),
            GLib.VariantType.new("(u)"),
            Gio.DBusCallFlags.NONE,
            1000,
            None,
        )
        code = result.unpack()[0]
        return int(code) in {1, 4}
    except Exception:
        logger.debug("RequestName %s failed", name, exc_info=True)
        return False


class StatusNotifierItem:
    """Export a tray item on the session bus and register with a watcher."""

    def __init__(
        self,
        on_action: Callable[[str], None],
        *,
        icon_name: str = "ulauncher-indicator-symbolic",
        icon_theme_path: str = "",
        title: str = app_display_name,
        item_id: str = "ulauncher",
    ) -> None:
        self._on_action = on_action
        self._icon_name = icon_name
        self._icon_theme_path = icon_theme_path
        self._title = title
        self._item_id = item_id
        self._connection: Any | None = None
        self._visible = False
        self._started = False
        self._name_owned = False
        self._bus_name = sni_bus_name(os.getpid())
        self._reg_ids: list[int] = []
        self._name_sub = 0

    def start(self, connection: Any | None = None) -> bool:
        if self._started:
            return True
        bus = connection if connection is not None else _session_connection()
        if bus is None:
            return False
        self._connection = bus
        if not self._export_objects(bus):
            return False
        self._name_owned = _request_name(bus, self._bus_name)
        self._register_with_watchers(bus)
        self._watch_watchers(bus)
        self._started = True
        return True

    def set_visible(self, visible: bool) -> None:
        if visible:
            self.start()
        self._visible = visible
        self._emit_new_status()

    def _export_objects(self, connection: Any) -> bool:
        from ulauncher.gi import Gio

        sni_node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
        menu_node = Gio.DBusNodeInfo.new_for_xml(MENU_XML)
        sni_iface = sni_node.lookup_interface(SNI_IFACE)
        menu_iface = menu_node.lookup_interface(MENU_IFACE)
        if sni_iface is None or menu_iface is None:
            return False
        try:
            sni_id = connection.register_object(
                SNI_PATH,
                sni_iface,
                self._on_sni_method,
                self._on_sni_get_property,
                None,
            )
            menu_id = connection.register_object(
                MENU_PATH,
                menu_iface,
                self._on_menu_method,
                self._on_menu_get_property,
                None,
            )
        except Exception:
            logger.debug("Could not export StatusNotifierItem objects", exc_info=True)
            return False
        if not sni_id or not menu_id:
            return False
        self._reg_ids = [int(sni_id), int(menu_id)]
        return True

    def _register_with_watchers(self, connection: Any) -> None:
        argument = register_item_argument(
            well_known_name=self._bus_name,
            name_owned=self._name_owned,
            object_path=SNI_PATH,
        )
        from ulauncher.gi import Gio, GLib

        payload = GLib.Variant("(s)", (argument,))
        for dest, iface in WATCHER_IFACES:
            try:
                connection.call(
                    dest,
                    WATCHER_PATH,
                    iface,
                    "RegisterStatusNotifierItem",
                    payload,
                    None,
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                    self._on_register_done,
                    dest,
                )
            except Exception:
                logger.debug("RegisterStatusNotifierItem dispatch failed on %s", dest, exc_info=True)

    def _on_register_done(self, connection: Any, result: Any, watcher_name: Any) -> None:
        try:
            connection.call_finish(result)
        except Exception:
            logger.debug("RegisterStatusNotifierItem failed on %s", watcher_name, exc_info=True)

    def _watch_watchers(self, connection: Any) -> None:
        from ulauncher.gi import Gio

        try:
            self._name_sub = int(
                connection.signal_subscribe(
                    "org.freedesktop.DBus",
                    "org.freedesktop.DBus",
                    "NameOwnerChanged",
                    "/org/freedesktop/DBus",
                    None,
                    Gio.DBusSignalFlags.NONE,
                    self._on_name_owner_changed,
                )
                or 0
            )
        except Exception:
            logger.debug("Could not watch StatusNotifierWatcher names", exc_info=True)

    def _on_name_owner_changed(
        self,
        _connection: Any,
        _sender: str,
        _path: str,
        _iface: str,
        _signal: str,
        parameters: Any,
        *_extra: object,
    ) -> None:
        payload = parameters.unpack() if hasattr(parameters, "unpack") else parameters
        name = payload[0] if isinstance(payload, (list, tuple)) and payload else ""
        new_owner = payload[2] if isinstance(payload, (list, tuple)) and len(payload) > 2 else ""
        if watcher_name_is_ours(str(name)) and new_owner and self._connection is not None:
            self._register_with_watchers(self._connection)

    def _emit_new_status(self) -> None:
        if self._connection is None or not self._started:
            return
        try:
            self._connection.emit_signal(
                None,
                SNI_PATH,
                SNI_IFACE,
                "NewStatus",
                _variant("(s)", (sni_status(self._visible),)),
            )
        except Exception:
            logger.debug("Could not emit NewStatus", exc_info=True)

    def _invoke(self, action: str | None) -> None:
        if not action:
            return
        from ulauncher.utils import scheduling

        scheduling.run_when_idle(self._on_action, action)

    def _on_sni_method(
        self,
        _connection: Any,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        method_name: str,
        _parameters: Any,
        invocation: Any,
        *_extra: object,
    ) -> None:
        self._invoke(sni_method_action(method_name))
        invocation.return_value(None)

    def _on_sni_get_property(
        self,
        _connection: Any,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        property_name: str,
        *_extra: object,
    ) -> Any:
        return sni_property_variant(
            property_name,
            status=sni_status(self._visible),
            icon_name=self._icon_name,
            icon_theme_path=self._icon_theme_path,
            title=self._title,
            item_id=self._item_id,
        )

    def _on_menu_method(
        self,
        _connection: Any,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        method_name: str,
        parameters: Any,
        invocation: Any,
        *_extra: object,
    ) -> None:
        args = parameters.unpack() if hasattr(parameters, "unpack") else parameters
        if method_name == "GetLayout":
            parent_id, recursion_depth, property_names = args
            revision, node = dbusmenu_layout(int(parent_id), int(recursion_depth), list(property_names))
            invocation.return_value(pack_get_layout_result(revision, node))
            return
        if method_name == "GetGroupProperties":
            ids, property_names = args
            rows = menu_group_properties([int(i) for i in ids], list(property_names))
            invocation.return_value(pack_group_properties(rows))
            return
        if method_name == "GetProperty":
            item_id, name = args
            invocation.return_value(_variant("(v)", (_menu_property_variant(int(item_id), str(name)),)))
            return
        if method_name == "Event":
            item_id, event_id, _data, _timestamp = args
            self._invoke(menu_event_action(int(item_id), str(event_id)))
            invocation.return_value(None)
            return
        if method_name == "AboutToShow":
            invocation.return_value(_variant("(b)", (False,)))
            return
        invocation.return_value(None)

    def _on_menu_get_property(
        self,
        _connection: Any,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        property_name: str,
        *_extra: object,
    ) -> Any:
        if property_name == "Version":
            return _variant("u", 3)
        if property_name == "TextDirection":
            return _variant("s", "ltr")
        if property_name == "Status":
            return _variant("s", "normal")
        if property_name == "IconThemePath":
            path = [self._icon_theme_path] if self._icon_theme_path else []
            return _variant("as", path)
        return None
