#!/bin/sh
# GTK 4 + libadwaita runtime for GitHub Actions. Ubuntu 22.04 matches the
# documented floor (GTK 4.6, Adwaita 1.1). Do not pull ulauncher/build-image:6.7;
# that published tag is the upstream GTK3-era image.
set -eu
apt-get update
apt-get install -y --no-install-recommends \
    python3-venv \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-gi \
    python3-gi-cairo \
    python3-xlib \
    gir1.2-glib-2.0 \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    gir1.2-gdkpixbuf-2.0 \
    libgtk-4-1 \
    libadwaita-1-0 \
    xvfb
