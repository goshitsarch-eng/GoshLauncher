import gi

# pin gi versions for all use inside the ui directory tree
gi.require_versions(
    {
        "Gdk": "4.0",
        "GdkPixbuf": "2.0",
        "Gtk": "4.0",
        "Adw": "1",
        "Pango": "1.0",
    }
)
try:
    gi.require_version("GdkX11", "4.0")
except ValueError:
    pass

from gi.repository import Adw  # noqa: E402

Adw.init()

from ulauncher.ui.gtk4 import install_compat  # noqa: E402

install_compat()
