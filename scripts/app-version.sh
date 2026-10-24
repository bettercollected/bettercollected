#!/bin/sh
# Prints the version a webapp image built from this checkout should show in the
# dashboard sidebar: the release tag when HEAD is exactly on one (v4.0.2), else
# the short commit (b3a8cee, shown as "build · b3a8cee"), else nothing (not a
# git checkout). Pass it to the build:
#
#   docker build --build-arg "NEXT_PUBLIC_APP_VERSION=$(scripts/app-version.sh)" \
#     -f webapp/Dockerfile .
#
# CI computes the same value in .github/workflows/deploy.yml.
set -eu

cd "$(dirname "$0")/.." || exit 0

tag=$(git describe --tags --exact-match 2>/dev/null || true)
if printf '%s\n' "$tag" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$'; then
  printf '%s\n' "$tag"
  exit 0
fi

git rev-parse --short=7 HEAD 2>/dev/null || true
