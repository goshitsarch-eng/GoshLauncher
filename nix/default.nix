# based off https://github.com/NixOS/nixpkgs/blob/e44462d6021bfe23dfb24b775cc7c390844f773d/pkgs/applications/misc/ulauncher/default.nix#L4-L4
{ lib
, buildEnv
, git
, gnumake
, kdePackages
, libX11
, nix-update-script
, procps
, python3Packages
, pyrefly
, setuptools ? python3Packages.setuptools
, setuptools-scm ? python3Packages.setuptools-scm
, ruff
, stdenv
, systemd
, typos
, xdg-utils
, xvfb-run
, withXorg ? true
}:
let
  pname = "ulauncher";

  # nixpkgs' pythonMetadataCheckHook compares this to the built dist-info metadata.
  # Therefore the version string is extracted from _version.py.
  versionFile = builtins.readFile ../ulauncher/_version.py;
  versionMatch =
    builtins.match ''
      .*version = "([0-9]+\.[0-9]+\..*)".*
    '' versionFile;
  version =
    if versionMatch == null then
      throw "Failed to parse version"
    else builtins.elemAt versionMatch 0;
  src.python = ../.;

  packages.tests.python = pp: (with pp; [
    mock
    pytest
    pytest-mock
  ]);
  packages.tests.system = [
    pyrefly
    ruff
    typos
    xvfb-run
  ];

  packages.tests.all = pp: packages.tests.python pp ++ packages.tests.system;

  # QML modules the UI imports at runtime
  qmlDeps = [
    kdePackages.kirigami
    kdePackages.qqc2-desktop-style
    kdePackages.qtdeclarative
  ];

  self = python3Packages.buildPythonPackage {
    inherit version pname;
    src = src.python;

    pyproject = true;
    build-system = [ setuptools ];

    nativeBuildInputs = [
      setuptools-scm
      kdePackages.wrapQtAppsHook
    ];

    buildInputs = qmlDeps;

    # runtime dependencies / binaries prepended to PATH
    propagatedBuildInputs = with python3Packages; [
      levenshtein
      mock
      pyside6
    ] ++ lib.optionals withXorg [
      xlib
    ] ++ [
      git
      xdg-utils
    ];

    nativeCheckInputs = packages.tests.all python3Packages;

    postPatch = ''
      patchShebangs bin/ulauncher bin/ulauncher-toggle

      substituteInPlace \
          ulauncher/modes/extensions/extension_service.py \
        --replace-fail 'paths.APPLICATION,' '":".join(sys.path),'

      substituteInPlace \
          ulauncher.service \
          io.ulauncher.Ulauncher.service \
        --replace-fail "/usr" "$out"

      substituteInPlace \
          tests/modes/shortcuts/test_run_script.py \
        --replace-fail '#!/bin/bash' '#!${stdenv.shell}'
    '';

    dontWrapQtApps = true;
    preFixup = ''
      makeWrapperArgs+=(
        "''${qtWrapperArgs[@]}"
        ${lib.optionalString withXorg ''--prefix LD_LIBRARY_PATH : "${lib.makeLibraryPath [ libX11 ]}"''}
        --prefix QML2_IMPORT_PATH : "${lib.makeSearchPath "lib/qt-6/qml" qmlDeps}"
        --set-default ULAUNCHER_SYSTEM_PREFIX "$out"
      )
    '';

    # bin/ulauncher is a shell script, so wrapPythonPrograms skips it.
    # Wrap it manually to inject PYTHONPATH (so `python3 -m ulauncher` finds PySide6)
    # plus the same Qt/X11/prefix args python scripts would get.
    postFixup = ''
      wrapProgram $out/bin/ulauncher \
        --prefix PYTHONPATH : "$program_PYTHONPATH" \
        --prefix PATH : "$program_PATH" \
        "''${makeWrapperArgs[@]}"
    '';

    doCheck = true;
    installCheckPhase = ''
      test_dir="$PWD/.test-tmp"
      (
        export PATH="${lib.makeBinPath [ procps ]}:$PATH"
        trap "echo killing $BASHPID && pkill -P $BASHPID" EXIT

        mkdir -p "$test_dir"
        logfile="$test_dir/log.txt"
        env -i HOME="$test_dir" QT_QPA_PLATFORM=offscreen \
          $out/bin/ulauncher start --verbose &>"$logfile" &
        ulauncher_pid=$!

        while IFS= read -r line; do
          # lowercase each line for matching
          case "''${line,,}" in
            *error*)
              echo "ERROR: ulauncher failed to start"
              exit 1
            ;;
            *info*)
              # exits successfully as soon as it sees the first info message
              echo "OK: ulauncher started properly"
              exit 0
            ;;
          esac
        done < <(tail --pid=$ulauncher_pid -f "$logfile" | tee /dev/stderr)
      )
    '';

    passthru = {
      # won't be updateable until release?
      # updateScript = nix-update-script { };
      env = buildEnv {
        name = "${pname}-${version}-development";
        paths = [
          # python environment
          (self.passthru.pythonModule.withPackages (pp:
            [ self ]
              ++ packages.tests.python pp
              ++ (with pp; [ ]
              # debugging
              ++ [ ipdb ]
              # present in requirements.txt
              ++ [ build ]
              # Jetbrains IDEs don't like it without setuptools/pip installed
              ++ [ setuptools pip ]
            )
          ))
        ]
        ++ packages.tests.system
        ++ qmlDeps;
      };
    };

    meta = with lib; {
      description = "A Qt 6 + Kirigami application launcher for Linux, a fork of Ulauncher";
      homepage = "https://github.com/goshitsarch-eng/GoshLauncher";
      license = licenses.gpl3;
      platforms = platforms.linux;
      mainProgram = "ulauncher";
      maintainers = with maintainers; [ nazarewk ];
    };
  };
in
self
