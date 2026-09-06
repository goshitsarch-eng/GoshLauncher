# 6.0.2 audit and fixes

This review followed the Qt/QML entry points through their Python backends, core effects,
settings persistence, desktop integration, and packaging.

| Finding | Fix |
|---|---|
| Normal activation hid the popup before extensions could return another page or query | Core effect semantics now decide when to close |
| Programmatic input updates did not trigger a search | App query setter updates both input and core |
| About labels assigned nonexistent accessibility properties | Uses the Qt Accessible attached property |
| Multiline extension preferences used a nonexistent editing-finished handler | Text changes populate pending preferences |
| New shortcut saves kept an empty editor ID and created duplicates | Save returns and retains the stable ID |
| Editing shortcuts erased custom icons; unusable keywords were accepted | Preserve icons and validate trimmed, single-token keywords |
| Extension refresh selected by list position | Preserve selection by extension ID |
| Previously opened preference controls showed stale values | Refresh when the window is reopened |
| Space capture could store a blank key; function keys were lowercased | Convert Qt key names and modifier values correctly |
| Plasma capture saved settings without changing the desktop binding | Route users to Plasma keyboard settings |
| Tray and monitor controls did not affect the application | Apply tray changes and select the requested X11 display |
| Popup width included shadows outside its placement calculation | Account for full width and bound size to the work area |
| Lock/sleep watcher existed but was not attached to the popup | Start and stop the existing watcher with popup visibility |
| Preferences could not open without a persistent daemon or popup | Allow a standalone preferences window |
| Systemd failures could appear to save successfully | Check the resulting enabled state |
| Wayland socket creation errors escaped the unavailable-provider fallback | Treat creation failures like connection failures |
| No Flatpak manifest or ARM64 release build existed | Add native dual-architecture builds, host launch integration, QML checks and publication gates |

## Verification

`make check` covers Python lint, types, Markdown, spelling, and unit tests. New regression tests
exercise query execution, closing/nonclosing effects, shortcut capture and persistence, tray
changes, monitor selection, window ownership, and session watcher lifecycle. The QML smoke check
loads both windows and creates extension text controls using real Qt and Kirigami. It runs in
Fedora CI and inside each Flatpak release build.

A headless test does not establish interactive focus, compositor positioning, global shortcut
approval, window switching, or physical multi-monitor behavior. These remain desktop-dependent
manual checks. Legacy fallback-shortcut rows are intentionally absent from launcher search;
the unused editor toggle is hidden while existing saved values are preserved.
