FROM ubuntu:22.04
# Run `make docker` to build this image

LABEL maintainer="Gosh"

# NOTE: Keep lines separate. One "RUN" per dependency/change
# https://stackoverflow.com/a/47451019/633921

ENV LANG=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_ROOT_USER_ACTION=ignore

RUN apt-get update --fix-missing
RUN apt-get install -y apt-utils
RUN apt-get install -y tzdata
RUN apt-get install -y keyboard-configuration

# CLI dependencies for building and testing
RUN apt-get install -y software-properties-common
RUN apt-get install -y git
RUN apt-get install -y vim
RUN apt-get install -y curl
RUN apt-get install -y wget
RUN apt-get install -y xvfb
RUN apt-get install -y help2man
RUN apt-get install -y python3-pip
RUN apt-get install -y python3-setuptools

# deb package build dependencies and helpers
RUN apt-get install -y debhelper
RUN apt-get install -y dh-python
RUN apt-get install -y devscripts
RUN apt-get install -y git-buildpackage

# ubuntu launchpad upload dependencies
RUN apt-get install -y dput
RUN apt-get install -y python3-paramiko

# Python runtime used by package and compatibility tests
RUN apt-get install -y python3-all

# Python 3.8 (the oldest version Ulauncher supports) for the test venv.
# The system python stays 3.10 for apt and the deb build tooling.
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get install -y python3.8
RUN apt-get install -y python3.8-venv
RUN apt-get install -y python3.8-dev

# Native-extension build tools used by test dependencies.
RUN apt-get install -y build-essential
RUN apt-get install -y pkg-config

# Debian disables ensurepip outside venvs, so bootstrap pip for 3.8 with get-pip
RUN curl -sS https://bootstrap.pypa.io/pip/3.8/get-pip.py | python3.8
RUN python3.8 -m pip install setuptools wheel
RUN python3.8 -m pip install python-xlib

# Make the venv in the makefile use 3.8
ENV PYTHON_BIN=python3.8

# Clean up
RUN apt-get autoremove -y
RUN apt-get clean

# Update /etc/dput.cf to use sftp for upload to ppa.launchpad.net
COPY [ "scripts/dput.cf", "/etc" ]

# Create container dir for the repo root dir to mount to
# This is needed because dpkg-buildpackage is stupid and outputs are hard coded to be the parent dir
RUN mkdir /src
RUN chmod 777 /src

# Create an unprivileged user to run as when testing and building locally (so generated files will not be owned by root on the host)
RUN useradd ulauncher --shell /bin/bash --home-dir /home/ulauncher --create-home --uid 1000 --user-group --comment Ulauncher

WORKDIR /src/ulauncher
