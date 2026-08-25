"""Adwaita 1.1-safe preference rows (no SwitchRow/SpinRow — those need libadwaita 1.4)."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from gi.repository import Adw, Gtk

from ulauncher.modes.launcher.prefs_combo import combo_selected_index


def plain_action_row(title: str, subtitle: str = "") -> Adw.ActionRow:
    """Subtitles can contain & from goshos copy; do not parse them as Pango markup."""
    row = Adw.ActionRow(title=title)
    set_markup = getattr(row, "set_use_markup", None)
    if callable(set_markup):
        set_markup(False)
    if subtitle:
        row.set_subtitle(subtitle)
    return row


def combo_item_label(item: Any) -> str:
    if isinstance(item, dict):
        if "label" in item:
            return str(item["label"])
        return str(item["title"])
    return str(getattr(item, "label", None) or getattr(item, "title", item))


def string_list(labels: Sequence[str]) -> Gtk.StringList:
    model = Gtk.StringList()
    for label in labels:
        model.append(label)
    return model


def add_switch_row(
    group: Adw.PreferencesGroup,
    title: str,
    subtitle: str,
    active: bool,
    on_toggle: Callable[..., Any],
) -> Gtk.Switch:
    row = plain_action_row(title, subtitle)
    switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=active)
    row.add_suffix(switch)
    row.set_activatable_widget(switch)
    switch.connect("notify::active", on_toggle)
    group.add(row)
    return switch


def add_spin_row(
    group: Adw.PreferencesGroup,
    title: str,
    subtitle: str,
    adjustment: Gtk.Adjustment,
    on_changed: Callable[..., Any],
) -> Gtk.SpinButton:
    row = plain_action_row(title, subtitle)
    spin = Gtk.SpinButton(adjustment=adjustment, valign=Gtk.Align.CENTER, numeric=True)
    spin.set_width_chars(5)
    spin.connect("value-changed", on_changed)
    row.add_suffix(spin)
    group.add(row)
    return spin


def add_combo_row(
    group: Adw.PreferencesGroup,
    title: str,
    subtitle: str,
    items: Sequence[Any],
    current_id: str | None,
) -> Adw.ComboRow:
    model = string_list([combo_item_label(item) for item in items])
    row = Adw.ComboRow(title=title, model=model)
    set_markup = getattr(row, "set_use_markup", None)
    if callable(set_markup):
        set_markup(False)
    if subtitle:
        row.set_subtitle(subtitle)
    index = combo_selected_index(items, current_id)
    if index >= 0:
        row.set_selected(index)
    group.add(row)
    return row


def add_button_row(
    group: Adw.PreferencesGroup,
    title: str,
    subtitle: str,
    button_label: str,
    on_clicked: Callable[..., Any],
) -> Gtk.Button:
    row = plain_action_row(title, subtitle)
    button = Gtk.Button(label=button_label, valign=Gtk.Align.CENTER)
    button.connect("clicked", on_clicked)
    row.add_suffix(button)
    group.add(row)
    return button


def add_entry_row(
    group: Adw.PreferencesGroup,
    title: str,
    subtitle: str,
    text: str,
    on_changed: Callable[..., Any],
) -> Gtk.Entry:
    row = plain_action_row(title, subtitle)
    entry = Gtk.Entry(text=text, valign=Gtk.Align.CENTER, hexpand=True)
    entry.set_width_chars(18)
    entry.connect("changed", on_changed)
    row.add_suffix(entry)
    group.add(row)
    return entry


def wrap_custom_view(title: str, icon_name: str, view: Gtk.Widget) -> Adw.PreferencesPage:
    page = Adw.PreferencesPage(title=title, icon_name=icon_name)
    group = Adw.PreferencesGroup()
    view.set_hexpand(True)
    view.set_vexpand(True)
    group.add(view)
    page.add(group)
    return page
