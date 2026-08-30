#!/bin/sh
# Qt 6 runtime for GitHub Actions. PySide6 comes from pip (requirements.txt);
# these are the native libraries its wheels link against, plus xvfb for any
# test that needs a display server.
set -eu
apt-get update
apt-get install -y --no-install-recommends \
    python3-venv \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-xlib \
    libegl1 \
    libgl1 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libxcb-cursor0 \
    libfontconfig1 \
    libdbus-1-3 \
    xvfb
