# Flatpak packages

GoshLauncher releases include `GoshLauncher-VERSION-x86_64.flatpak` and
`GoshLauncher-VERSION-aarch64.flatpak`. x86_64 is Intel/AMD x64; aarch64 is ARM64.
The separate source tar.gz is architecture independent.

## Install and run

Download your architecture's bundle and `SHA256SUMS` from
[GitHub Releases](https://github.com/goshitsarch-eng/GoshLauncher/releases).

```sh
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user ./GoshLauncher-6.0.2-x86_64.flatpak
flatpak run com.goshapps.GoshLauncher show
```

Substitute `aarch64` for ARM64. The bundle identifies its KDE runtime so Flatpak can install
that dependency from Flathub. This is a downloadable GitHub bundle, not a Flathub listing or
an automatic-update repository. Install the next release's bundle to upgrade.

To bind a compositor shortcut, use:

```sh
flatpak run com.goshapps.GoshLauncher toggle
```

The package requests the GlobalShortcuts portal where supported. On Plasma, the system keyboard
settings can bind the command above. Background mode keeps an already-started process running;
add this command to your desktop's autostart settings to start it at login:

```sh
flatpak run com.goshapps.GoshLauncher start
```

## Desktop integration

A launcher must see installed applications and start host programs. The manifest therefore grants
read access to host files, write access to the home directory, session bus access for desktop
integration, and access to logind/UPower system services. Application launches use
`flatpak-spawn --host`. The package reads host desktop entries and uses the established
`~/.config/ulauncher`, `~/.local/share/ulauncher`, and `~/.local/state/ulauncher` paths.
Native and Flatpak editions share the same application identity and should not run simultaneously.

Window search and system actions still depend on interfaces exposed by the desktop. Wayland
compositors control popup placement. Native RPM packaging remains available for the closest
integration with systemd and desktop-specific shortcut stores.

## Build locally

Install `flatpak` and `flatpak-builder`, then run from the repository root:

```sh
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak-builder --user --install-deps-from=flathub --force-clean --repo=repo \
  --default-branch=stable .flatpak-build packaging/flatpak/com.goshapps.GoshLauncher.json
flatpak-builder --run .flatpak-build packaging/flatpak/com.goshapps.GoshLauncher.json \
  env QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python3 /app/share/ulauncher/check-qml.py
flatpak build-bundle --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
  repo GoshLauncher.flatpak com.goshapps.GoshLauncher stable
```

The manifest uses matching KDE and [PySide BaseApp](https://github.com/flathub/io.qt.PySide.BaseApp)
6.11 branches and checksum-pinned Python dependencies. See the
[Flatpak build reference](https://docs.flatpak.org/en/latest/flatpak-builder-command-reference.html).
GitHub Actions builds each architecture on a native runner and publishes only when both bundles
and the source build have passed their checks.
