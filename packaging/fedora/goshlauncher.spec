Name:           goshlauncher
Version:        6.0.1
Release:        1%{?dist}
Summary:        Qt 6 and KDE Kirigami application launcher

License:        GPL-3.0-or-later AND LGPL-3.0-only
URL:            https://github.com/goshitsarch-eng/GoshLauncher
Source0:        %{url}/archive/refs/tags/v%{version}/GoshLauncher-%{version}.tar.gz
Vendor:         Gosh
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3dist(setuptools)
BuildRequires:  python3dist(setuptools-scm)
BuildRequires:  python3dist(pytest)
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
BuildRequires:  systemd-rpm-macros
Requires:       python3-pyside6
Requires:       python3-xlib
Requires:       kf6-kirigami
Requires:       kf6-qqc2-desktop-style
Requires:       qt6-qtdeclarative
Requires:       xdg-utils
Requires:       python3-pip
Provides:       bundled(python3dist(ewmh))

%description
GoshLauncher is a native Qt 6 and KDE Kirigami launcher with application,
desktop action, file, command, window, calculation, and extension search.
It preserves the Ulauncher command names, extension API 3.0, and existing
configuration, data, state, and extension paths.

%prep
%autosetup -n GoshLauncher-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files ulauncher

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/com.goshapps.GoshLauncher.desktop
appstreamcli validate --no-net %{buildroot}%{_datadir}/metainfo/com.goshapps.GoshLauncher.metainfo.xml
%pytest -q tests/test_release_identity.py tests/test_fedora_packaging.py

%files -f %{pyproject_files}
%{_bindir}/ulauncher
%{_bindir}/ulauncher-toggle
%{_datadir}/applications/com.goshapps.GoshLauncher.desktop
%{_datadir}/dbus-1/services/com.goshapps.GoshLauncher.service
%{_datadir}/metainfo/com.goshapps.GoshLauncher.metainfo.xml
%{_userunitdir}/ulauncher.service
%{_datadir}/ulauncher/
%{_datadir}/icons/hicolor/scalable/apps/com.goshapps.GoshLauncher.svg
%{_datadir}/icons/hicolor/scalable/status/ulauncher-indicator-symbolic.svg
%{_datadir}/icons/hicolor/scalable/status/ulauncher-indicator-symbolic-dark.svg
%{_mandir}/man1/ulauncher.1*
%license %{_licensedir}/ulauncher/LICENSE
%license %{_licensedir}/ulauncher/AUTHORS
%license %{_licensedir}/ulauncher/copyright

%changelog
* Sun Aug 30 2026 Gosh - 6.0.1-1
- Add native Fedora packaging with distribution Qt, Kirigami, and Python dependencies.
- Preserve the canonical application identity and Ulauncher compatibility surfaces.
