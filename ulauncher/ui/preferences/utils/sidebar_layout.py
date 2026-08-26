from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from gi.repository import Gtk, Pango

from ulauncher.ui import gtk4
from ulauncher.ui.preferences.views import SIDEBAR_WIDTH, DataListBoxRow, styled


@dataclass
class SidebarItem:
    """Definition of a sidebar navigation entry."""

    id: str
    icon: Gtk.Widget
    name: str
    on_activate: Callable[[SidebarItem], None] | None = None
    description: str | None = None
    label: str | None = None
    label_style_classes: tuple[str, ...] = ()
    selectable: bool = True


class SidebarLayout(Gtk.Box):
    """Reusable layout with left sidebar navigation and right content area."""

    def __init__(
        self,
        *,
        footer_actions: list[tuple[str, str, Callable[[Gtk.Widget], None]]] | None = None,
    ) -> None:
        """Initialize the sidebar layout.

        Args:
            actions: List of (label, icon_name, callback) tuples for footer action rows
        """
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, halign=Gtk.Align.FILL)

        # Create left sidebar
        self.sidebar = styled(
            Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=0,
                hexpand=False,
                halign=Gtk.Align.START,
                width_request=SIDEBAR_WIDTH,
            ),
            "sidebar",
        )

        # Scrolled window for main list
        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-selected", self._on_sidebar_item_selected)
        scrolled.set_child(self.listbox)
        gtk4.pack_start(self.sidebar, scrolled, True, True, 0)

        # Add footer actions if provided
        if footer_actions:
            divider = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            gtk4.pack_start(self.sidebar, divider, False, False, 0)

            footer_listbox = self._create_footer_actions(footer_actions)
            gtk4.pack_start(self.sidebar, footer_listbox, False, False, 0)

        self._rows_by_id: dict[str, DataListBoxRow] = {}
        self._empty_placeholder_builder: Callable[[], Gtk.Widget] | None = None
        self._active_id: str | None = None
        self._replaying_selection = False

        gtk4.pack_start(self, self.sidebar, False, False, 0)

        # Vertical separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        gtk4.pack_start(self, separator, False, False, 0)

        # Right side - content view
        self.content_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, halign=Gtk.Align.FILL)
        gtk4.pack_start(self, self.content_view, True, True, 0)

    def set_items(self, items: Sequence[SidebarItem], active_item_id: str | None = None) -> None:
        """Render sidebar items inside the layout."""

        existing_children = list(gtk4.list_children(self.listbox))
        for child in existing_children:
            self.listbox.remove(child)

        self._rows_by_id.clear()
        has_items = False
        for item in items:
            row = self._create_sidebar_item_row(item)
            self.listbox.append(row)
            self._rows_by_id[item.id] = row
            has_items = True

        if not has_items and self._empty_placeholder_builder:
            placeholder_row = self._create_placeholder_row()
            self.listbox.append(placeholder_row)

        gtk4.show_all(self.listbox)

        if active_item_id:
            # set_items throws every row away, so re-selecting the item that was already active
            # emits row-selected again. Letting that reach on_activate re-ran the callback that
            # rebuilds the content pane, discarding whatever the user was editing in it - and
            # the extensions page rebuilds its list once a second.
            self._replaying_selection = active_item_id == self._active_id
            try:
                self.select_item(active_item_id)
            finally:
                self._replaying_selection = False
        else:
            self._active_id = None
            self.listbox.unselect_all()

    def select_item(self, item_id: str | None) -> None:
        """Select a sidebar item by its identifier."""

        if item_id is None:
            self.listbox.unselect_all()
            return

        row = self._rows_by_id.get(item_id)
        if row:
            self.listbox.select_row(row)

    def set_empty_placeholder_builder(self, builder: Callable[[], Gtk.Widget] | None) -> None:
        """Set a factory for the widget shown when no sidebar items exist."""

        self._empty_placeholder_builder = builder

    def _create_footer_actions(self, actions: list[tuple[str, str, Callable[[Gtk.Widget], None]]]) -> Gtk.ListBox:
        """Create footer action rows (full-width clickable items with icon and label)."""
        footer_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        footer_listbox.set_activate_on_single_click(True)
        footer_listbox.set_margin_top(6)
        footer_listbox.set_margin_bottom(6)

        for label, icon_name, callback in actions:
            row = self._create_action_row(label, icon_name)
            row.callback = callback  # type: ignore[attr-defined]
            footer_listbox.append(row)

        footer_listbox.connect("row-activated", self._on_footer_action_activated)
        gtk4.show_all(footer_listbox)

        return footer_listbox

    def _create_action_row(self, label: str, icon_name: str) -> DataListBoxRow:
        """Create a single footer action row."""
        row = DataListBoxRow(f"action-{label.lower().replace(' ', '-')}")
        row.set_selectable(False)
        row.set_can_focus(True)
        row.set_activatable(True)
        row.set_tooltip_text(label)

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_box.set_margin_top(2)
        action_box.set_margin_bottom(2)
        action_box.set_margin_start(8)
        action_box.set_margin_end(8)

        icon = Gtk.Image(icon_name=icon_name)
        icon.set_pixel_size(18)
        gtk4.pack_start(action_box, icon, False, False, 0)

        label_widget = styled(
            Gtk.Label(label=label, halign=Gtk.Align.START),
            "sidebar-item-name",
        )
        gtk4.pack_start(action_box, label_widget, True, True, 0)

        row.set_child(action_box)
        row.set_margin_bottom(2)
        row.set_margin_top(2)
        return row

    def _on_footer_action_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        """Handle footer action activation."""
        if hasattr(row, "callback"):
            row.callback(row)

    def _create_sidebar_item_row(self, item: SidebarItem) -> DataListBoxRow:
        row = DataListBoxRow(item.id)
        row.sidebar_item = item  # type: ignore[attr-defined]
        row.set_selectable(item.selectable)
        row.set_activatable(item.selectable)
        row.set_can_focus(item.selectable)

        content = self._build_sidebar_item_content(item)
        row.set_child(content)
        return row

    def _build_sidebar_item_content(self, item: SidebarItem) -> Gtk.Widget:
        content = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8,
        )
        item.icon.set_valign(Gtk.Align.CENTER)
        item.icon.set_halign(Gtk.Align.CENTER)
        gtk4.pack_start(content, item.icon, False, False, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        text_box.set_hexpand(True)
        name_label = Gtk.Label(
            label=item.name,
            halign=Gtk.Align.START,
            ellipsize=Pango.EllipsizeMode.END,
        )
        styled(name_label, "sidebar-item-name")
        gtk4.pack_start(text_box, name_label, False, False, 0)

        if item.description:
            description_label = Gtk.Label(
                label=item.description,
                halign=Gtk.Align.START,
                ellipsize=Pango.EllipsizeMode.END,
            )
            styled(description_label, "dim-label", "sidebar-item-description")
            gtk4.pack_start(text_box, description_label, False, False, 0)
            text_box.set_valign(Gtk.Align.START)
            name_label.set_valign(Gtk.Align.START)
        else:
            text_box.set_valign(Gtk.Align.CENTER)
            name_label.set_valign(Gtk.Align.CENTER)

        gtk4.pack_start(content, text_box, True, True, 0)

        if item.label:
            label_widget = Gtk.Label(label=item.label)
            label_widget.set_halign(Gtk.Align.CENTER)
            label_widget.set_valign(Gtk.Align.CENTER)
            class_names = ["status-badge"]
            if item.label_style_classes:
                class_names.extend(item.label_style_classes)
            else:
                class_names.append(item.label)
            styled(label_widget, *class_names)
            gtk4.pack_start(content, label_widget, False, False, 0)

        return content

    def _create_placeholder_row(self) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_can_focus(False)
        row.set_activatable(False)
        widget = self._empty_placeholder_builder() if self._empty_placeholder_builder else Gtk.Box()
        row.set_child(widget)
        return row

    def _on_sidebar_item_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if not row or not hasattr(row, "sidebar_item"):
            return

        item: SidebarItem = row.sidebar_item  # type: ignore[attr-defined]
        self._active_id = item.id
        if self._replaying_selection:
            return
        if item.on_activate and item.selectable:
            item.on_activate(item)

    def clear_content(self) -> None:
        """Clear the content view."""
        for child in gtk4.list_children(self.content_view):
            self.content_view.remove(child)

    def set_content(self, widget: Gtk.Widget) -> None:
        """Set the content view to display a widget.

        Args:
            widget: Widget to display in the content area
        """
        self.clear_content()
        gtk4.pack_start(self.content_view, widget, True, True, 0)
        gtk4.show_all(self.content_view)
