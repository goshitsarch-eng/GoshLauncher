# GoshLauncher

A GTK 4 + libadwaita application launcher for Linux. Open with **Ctrl+Space**. Search, looks, prefixes, and keyboard navigation follow [Spotlight-goshos](https://github.com/goshitsarch-eng/spotlight-goshos).

GoshLauncher is a fork of [Ulauncher](https://github.com/Ulauncher/Ulauncher) v6, whose core, extension API, and packaging it still builds on. The installed command is still `ulauncher`. See [Credits](#credits).

## Search order

Results appear under their own section header (unless you hide headers). Web search is last unless you use `@`.

1. **URLs** — `https://…`, `www.…`, bare domains, `host:port`, `localhost`, IPv4/IPv6, `*.local`, plus `sftp://`, `smb://`, `mailto:`, and `magnet:`. Names that look like files (`node.js`, `readme.md`) stay app and file searches. A trailing file-extension denylist keeps those out of URL matching.
2. **Paths** — `~/…`, `./…`, and absolute paths. Missing paths show “Path not found”. Directories also offer Open in Terminal.
3. **Folders** — XDG user folders (Home, Desktop, Documents, Downloads, Music, Pictures, Videos, Public, Templates).
4. **Bookmarks** — GTK 3 and GTK 4 bookmark files, including remote URIs.
5. **Applications** — Desktop entries by name, GenericName, Keywords, Comment, and id. Usage ranking, variant collapse, parental controls, and optional New window / desktop actions.
6. **Calculator** — Recursive-descent parser, not `eval`. Bare `42` is not math unless you type `=42`.
7. **Units** — Length, mass, temperature, volume, data sizes, duration, area, speed, pressure, energy, power, angle.
8. **Color** — Hash hex, `rgb` / `hsl` / `hwb`, and CSS names. `# wifi` stays the Settings prefix.
9. **Clock** — `time`, `now`, `date`, `today`, `tomorrow`, `yesterday`, `clock`.
10. **Windows** — Title, class, workspace number, close / force-quit.
11. **System actions** — Lock, suspend, restart, power off, log out, switch user, rotation lock, screenshot (when the session exposes them).
12. **GNOME Settings** — Control Center panels.
13. **Recent files** — `recently-used.xbel`.
14. **Web search** — Last-resort fallback, or immediately with `@`.

Before you type, the popup can show frequent apps and open windows. Windows-first looks (Pop!_OS) put windows above apps here too.

## Prefixes

Disable prefix modes in Features if you never want them. `!` stays off unless you turn the command runner on.

| Prefix | Provider |
|---|---|
| `=` | Calculator (`=2^8`) |
| `@` | Web search |
| `#` | Settings (`# wifi`, not `#ff0000`) |
| `$` | Windows (`$ term`, not `$HOME`) |
| `.` | Recent files (`. notes`, not `.bashrc`) |
| `!` | Argv command (off by default; not a shell) |

## Looks

Seventeen looks. A look owns colors and chrome (position, density, headers, number hints, icons, descriptions, icon size, windows-first). Width is not part of a look. There is no blur.

Spotlight, Omarchy, Pop!_OS, Ulauncher, KRunner, GNOME, Rofi, Raycast, Albert, Wofi, Fuzzel, Anyrun, Tofi, Light, PowerToys, Synapse, Onagre.

## Keyboard

| Action | Input |
|---|---|
| Open | `Ctrl+Space` |
| Traverse | `↑` / `↓`, `Tab`, `Page Up` / `Page Down`, `Ctrl+J` / `Ctrl+K`, `Ctrl+N` / `Ctrl+P` |
| Activate | Enter, click, or tap |
| Activate 1–9 | `Alt+1` … `Alt+9` when number hints are on. A pending Checking path slot does not fall through. |
| Dismiss | `Esc`, `Ctrl+Space`, or click / tap outside |

## Run

From a clone:

```
make venv
make run
```

If the package ships `ulauncher.service`:

```
systemctl --user enable --now ulauncher
```

Preferences: Shortcut, Appearance, Features, Web Search, About (Spotlight-goshos order), then Desktop, Shortcuts, and Extensions for this GTK host. Default size matches Spotlight-goshos (`680×720`).

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). `make check` runs lint and tests. Target Python 3.8+ with GTK 4.6 and libadwaita 1.1+.

## Credits

GoshLauncher stands on two projects and claims neither as its own.

**[Ulauncher](https://github.com/Ulauncher/Ulauncher)** — Copyright © 2015 Aleksandr Gornostal and the Ulauncher
contributors, GPL-3.0. Ulauncher v6 is the upstream code base: the mode system, extension API and extension IPC,
preferences, packaging, and most of what is under `ulauncher/` come from it. GoshLauncher keeps Ulauncher's extension
API (version 3.0), so extensions written for Ulauncher work here. Extension docs stay at
[docs.ulauncher.io](https://docs.ulauncher.io/).

**[Spotlight-goshos](https://github.com/goshitsarch-eng/spotlight-goshos)** — the design and behaviour reference. The
search order, the seventeen looks, the prefixes, the keyboard map, and the popup chrome are ported from it. Modules
under `ulauncher/modes/launcher/` name the goshos source file they follow.

Icons and look palettes quote the projects each look is named after (Rofi, KRunner, Raycast, Albert, Wofi, Fuzzel,
Anyrun, Tofi, PowerToys, Synapse, Onagre, Pop!_OS, GNOME). Those are visual homages; none of those projects are
affiliated with or endorse GoshLauncher.

## License

GNU GPL v3.0, inherited from Ulauncher. See [LICENSE](LICENSE) and [AUTHORS](AUTHORS).

This is a modified version of Ulauncher, not the original. Per GPL-3.0 section 5(a): the GTK 4 + libadwaita launcher
UI, the Spotlight-goshos search order and looks, and the rebrand to GoshLauncher were added in August 2026 by the
GoshLauncher contributors. Ulauncher is not responsible for, and does not endorse, these changes.
