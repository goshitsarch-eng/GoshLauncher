# Communication

> This guide is Ulauncher's, adapted for GoshLauncher. GoshLauncher is a fork
> ([Credits](README.md#credits)), so file issues and pull requests against
> [goshitsarch-eng/GoshLauncher](https://github.com/goshitsarch-eng/GoshLauncher) — not against Ulauncher.
> The links below that point at Ulauncher are upstream references kept on purpose.

Please read our General [communication guidelines](CODE_OF_CONDUCT.md).

## Code contributions

Thank you for your interest in contributing to GoshLauncher! We very much appreciate it.

Before you put the work in on anything large, open a
[discussion or issue](https://github.com/goshitsarch-eng/GoshLauncher/issues) so we can agree it is
something the project wants.

Much of this code base is Ulauncher's, so a bug you hit may already be fixed or discussed upstream:
check [Ulauncher's issues](https://github.com/Ulauncher/Ulauncher/issues) and
[v6 milestone](https://github.com/Ulauncher/Ulauncher/milestone/7) before writing a fix, and consider
sending fixes that are not GoshLauncher-specific to Ulauncher as well, so both projects get them.

### Set Up Development Environment

You need the following to set up the local build environment:

- Git
- python3-pip and python3-setuptools
- Application runtime dependencies (an installed GoshLauncher package already provides most of these)

#### Distro specific instructions

<details>
  <summary>Ubuntu/Debian</summary>

  Install the development dependencies:

  ```sh
  sudo apt update && sudo apt install git bash make sed python3-setuptools debhelper dh-python
  make venv
  ```

  If you don't have GoshLauncher installed already, install the runtime dependencies as well (requires universe repo):

  ```sh
  sudo add-apt-repository universe
  sudo apt install python3-{all,xlib} \
    libegl1 libxkbcommon0 qml6-module-org-kde-kirigami qml6-module-org-kde-qqc2-desktop-style
  ```

</details>

<details>
  <summary>Arch</summary>

  First, install your system updates:

  ```sh
  sudo pacman -Syu
  ```

  Install the development and testing dependencies:

  ```sh
  sudo pacman -Syu --needed git bash make sed python-{build,setuptools,lefthook}
  make venv
  ```

  If you don't have GoshLauncher installed already, install the runtime dependencies as well:

  ```sh
  sudo pacman -Syu --needed pyside6 kirigami qqc2-desktop-style python-xlib
  ```

</details>

<details>
  <summary>Nix package manager / NixOS</summary>

1. build your development interpreter with `make nix-build-dev`
2. use the development interpreter (`./nix/dev/bin/python`) by either of:
   - pointing your favorite IDE to use it, make sure it adds repository root to `PYTHONPATH`,
   - using it directly from repository root (otherwise you will use the version of code built with environment),
3. rebuild the interpreter when project dependencies change,

Alternatively you can run the current code directly `make nix-run ARGS="<arg1> <arg2...>"`, without any IDE completion.

PySide6 ships type stubs, so IDE completion works out of the box.

</details>

#### Running the app from the local repository

1. `git clone` the repository locally
1. Open a terminal window and cd into the GoshLauncher repository root directory.
1. Run `make run` to start the app. If GoshLauncher is already running, this command stops that instance first because only one launcher instance can own the D-Bus name.
1. When you are done testing or want to restart, press Ctrl+C. You can then start it normally again (`systemctl --user start ulauncher` if using systemd).

### How to contribute

Use the GoshLauncher main branch, and verify that the issue or feature has not already been fixed there.

1. Follow the steps above to set up and test locally, but fork the GoshLauncher repo and clone from that fork instead (or change/add the remote to your fork).
1. When you are ready to contribute code, create a new branch for your PR.
1. Commit and push your changes. When possible, try to make your changes so that each commit changes just one thing, and please use [Conventional Commits](https://www.conventionalcommits.org/) for your commit messages.
1. Create a pull request (provide the relevant information suggested by the template). Use the main branch as the base branch and target.

See the [Qt for Python docs](https://doc.qt.io/qtforpython-6/) and the [Kirigami docs](https://develop.kde.org/frameworks/kirigami/).

There are some more helpful developer and maintainer commands provided by using our `make` targets. Run `make` to list them all.

If you have questions, open an issue in the [GoshLauncher repository](https://github.com/goshitsarch-eng/GoshLauncher/issues).

## Project Structure

```
ulauncher/
├── api/          # Extension API (runs in separate process)
│   ├── client/   # Extension-side IPC client
│   └── shared/   # Shared types between Ulauncher and extensions
├── modes/        # Query handlers (apps, files, extensions, etc.)
├── ui/           # Qt/QML Kirigami components and windows
└── utils/        # Shared utilities (event bus, timers, IPC, etc.)
```

## Async

Ulauncher uses **callback patterns**, not Python's `async/await`:

- Avoid `threading.Thread` - use the event loop
- For delayed execution: `scheduling.timer`
- For main thread execution: `scheduling.run_when_idle`

## Architecture

Try to understand and follow these, when applicable.

### [EventBus](docs/architecture/eventbus.md)

For cross-module communication when modules can't directly reference each other (avoid circular imports, decouple core from UI).

### [Mode System](docs/architecture/mode-system.md)

Ulauncher's query handling architecture. Each mode handles specific types of queries (apps, files, calculator, extensions, etc.).

### Custom Data Structures

- **[BaseDataClass](docs/architecture/base_data_class.md)** - Lightweight dict-based dataclass alternative
- **[JsonConf](docs/architecture/json_conf.md)** - Config files with auto-deduplication and safe concurrent access

### [Extension IPC](docs/architecture/extension-ipc.md)

Multi-process architecture for extensions. Unix socket pairs with JSON-line protocol for communication between Ulauncher and extension processes.
