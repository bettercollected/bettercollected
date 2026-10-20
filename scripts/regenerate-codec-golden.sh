#!/usr/bin/env bash
# Rewrite the golden fixtures of the Postgres ``doc`` codec (common/common/db/codec_golden.py).
#
#   scripts/regenerate-codec-golden.sh [common|backend|auth|google ...]
#
# The fixtures pin the exact JSON each mirrored document is stored as, and its
# checksum. Regenerate them only on purpose: after adding a document class or a
# field (new cases appear), or after changing the synthetic test values. Then
# review the diff: a changed `doc` or `checksum` of an EXISTING case means rows
# already stored would encode differently, which needs a migration plan, not a
# fixture update. CI never regenerates.
#
# Run it in the environment you run each suite's tests in: the backend suite
# needs its MONGO_URI, DATABASE_URL (a *_test database) and secrets; the google
# suite a reachable MONGO_URI; auth and common need nothing extra.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=(common backend auth google)

for target in "${targets[@]}"; do
  case "$target" in
    common) dir=common test=tests/test_codec_golden.py ;;
    backend) dir=backend test=tests/app/db/test_codec_golden.py ;;
    auth) dir=auth test=tests/integration/app/test_codec_golden.py ;;
    google) dir=integrations/google test=tests/integration/app/repository/test_codec_golden.py ;;
    *) echo "unknown suite: $target (common, backend, auth or google)" >&2; exit 2 ;;
  esac
  echo "== $target"
  (cd "$root/$dir" && BC_CODEC_GOLDEN_WRITE=1 uv run --frozen pytest -q -p no:randomly "$test")
done

echo
echo "Review before committing:"
git -C "$root" status --short -- '*/fixtures/codec_golden/*'
git -C "$root" diff --stat -- '*/fixtures/codec_golden/*'
