#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
ref=${1:-HEAD}
out_dir=${2:-"$repo_root/dist"}
commit=$(git -C "$repo_root" rev-parse --verify "${ref}^{commit}")
version=$(git -C "$repo_root" show "${commit}:ulauncher/_version.py" | sed -n 's/^version = "\(.*\)"$/\1/p')

if [ -z "$version" ]; then
  printf 'Could not read the version from %s\n' "$commit" >&2
  exit 1
fi

archive="GoshLauncher-${version}.tar.gz"
mkdir -p "$out_dir"
tmp="$out_dir/.${archive}.tmp.$$"
trap 'rm -f "$tmp"' EXIT HUP INT TERM

git -C "$repo_root" archive \
  --format=tar \
  --prefix="GoshLauncher-${version}/" \
  "$commit" | gzip -n -9 > "$tmp"
mv -f "$tmp" "$out_dir/$archive"
trap - EXIT HUP INT TERM

printf 'source=%s\n' "$out_dir/$archive"
printf 'commit=%s\n' "$commit"
printf 'tree=%s\n' "$(git -C "$repo_root" rev-parse "${commit}^{tree}")"
printf 'sha256=%s\n' "$(sha256sum "$out_dir/$archive" | cut -d ' ' -f 1)"
