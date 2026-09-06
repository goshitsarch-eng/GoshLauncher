# Fedora RPM packaging

`goshlauncher.spec` builds the native GoshLauncher package with Fedora's Python
pyproject macros. The package intentionally retains the `ulauncher` Python
distribution, commands, user systemd unit, and user-data paths for extension and
rollback compatibility. It does not contain a Flatpak host bridge.

## Dependencies

The spec uses Fedora packages for PySide6, KDE Kirigami, the KDE desktop
QtQuick Controls style, Qt Declarative QML modules, and python-xlib. No Python
wheel is downloaded or bundled during the RPM build.

## Reproducible source archive

Commit the candidate first, then create the archive from that exact Git object:

```sh
packaging/fedora/make-source-archive.sh HEAD "$PWD/dist"
```

The script resolves the ref to an immutable commit, uses `git archive`, strips
the gzip timestamp with `gzip -n`, and prints the source commit, tree, and
SHA-256. Running it twice for the same commit produces identical bytes.

## Fedora 44 build and qualification

On an x86_64 Fedora 44 builder with the spec's BuildRequires installed:

```sh
rpm_stage=a
rpmbuild "-b${rpm_stage}" \
  --define "_sourcedir $PWD/dist" \
  --define "_specdir $PWD/packaging/fedora" \
  --define "_topdir $PWD/.rpmbuild" \
  packaging/fedora/goshlauncher.spec

packaging/fedora/verify-rpm.py \
  .rpmbuild/RPMS/noarch/goshlauncher-6.0.2-1.fc44.noarch.rpm
```

The verifier checks identity, version, license, vendor, runtime dependencies,
exact payload boundaries, extracted payload bytes, scriptlets, file capabilities,
setuid/setgid/world-writable bits, host bridge markers, and unsigned status. It
requires `rpm`, `rpm2cpio`, and `cpio`. Build artifacts belong outside Git and
must not be committed.
