#!/usr/bin/env bash
# Decides what a CI run covers; writes step outputs to $GITHUB_OUTPUT (or stdout).
#
# Pull requests: the Postgres persistence mode only, and only the suites the
# changed files can affect. Push to develop, the nightly schedule and a manual
# run (scope "full"): every suite in every mode.
#
# Path rules are deliberately conservative: a file that is not known to be
# prose or to belong to one service runs everything. Tests read files across
# the repository (workflow env, compose files, deploy scripts, docs/spec cases,
# the settings inventory, webapp sources), so those are listed explicitly.
#
# Inputs (env): EVENT (github.event_name), SCOPE (workflow_dispatch input),
# CHANGED_FILES (optional, newline separated; default: the PR merge commit's
# diff against its base, HEAD^1..HEAD).
set -euo pipefail

BACKEND_SHARDS=8 # see docs/ci.md: ~1 min per shard on a hosted runner
SIDE_SHARDS=2    # mongo and dual on develop/nightly, without the admin suite

full=false
case "${EVENT:-pull_request}" in
pull_request) ;;
workflow_dispatch) [ "${SCOPE:-full}" = full ] && full=true ;;
*) full=true ;;
esac

backend=false auth=false google=false common=false webapp=false
everything() { backend=true auth=true google=true common=true webapp=true; }

if [ "$full" = true ] || [ "${EVENT:-pull_request}" != pull_request ]; then
    everything
else
    if [ -z "${CHANGED_FILES+x}" ]; then
        # HEAD is the PR merge commit; its first parent is the base branch.
        CHANGED_FILES=$(git diff --name-only HEAD^1 HEAD) || CHANGED_FILES="(unknown)"
    fi
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        case "$f" in
        docs/spec/* | docs/settings-inventory.md) everything ;; # read by the test suites
        docs/*) ;;                                              # prose
        webapp/src/constants/theme.ts) webapp=true common=true backend=true ;;
        webapp/*) webapp=true common=true ;; # common scans the webapp for settings names
        backend/backend/app/constants/themes.py) backend=true common=true webapp=true ;;
        backend/*) backend=true common=true ;;
        auth/*) auth=true common=true ;;
        integrations/google/*) google=true common=true ;;
        common/*) backend=true auth=true google=true common=true ;;
        temporal/*) backend=true common=true ;;
        */*) everything ;; # .github, postgres, deploy, scripts, other integrations, ...
        *.md) ;;           # top-level prose: README, CHANGELOG, ...
        *) everything ;;   # top-level config the tests read (compose, deploy.sh, .env examples, .nvmrc)
        esac
    done <<<"$CHANGED_FILES"
fi

# Backend matrix: Postgres in shards always; Mongo and dual (without the admin
# suite, which does not depend on the mode) only on full runs.
entries=()
for g in $(seq 1 "$BACKEND_SHARDS"); do
    entries+=("{\"mode\":\"postgres\",\"read_source\":\"postgres\",\"write_mode\":\"postgres\",\"group\":$g,\"splits\":$BACKEND_SHARDS,\"ignore\":\"\"}")
done
modes='["postgres"]'
if [ "$full" = true ]; then
    for mode in mongo dual; do
        write=""
        [ "$mode" = dual ] && write=dual
        for g in $(seq 1 "$SIDE_SHARDS"); do
            entries+=("{\"mode\":\"$mode\",\"read_source\":\"\",\"write_mode\":\"$write\",\"group\":$g,\"splits\":$SIDE_SHARDS,\"ignore\":\"--ignore=tests/admin\"}")
        done
    done
    modes='["mongo","dual","postgres"]'
fi
matrix="{\"include\":[$(
    IFS=,
    echo "${entries[*]}"
)]}"

out=${GITHUB_OUTPUT:-/dev/stdout}
{
    echo "full=$full"
    echo "backend=$backend"
    echo "auth=$auth"
    echo "google=$google"
    echo "common=$common"
    echo "webapp=$webapp"
    echo "modes=$modes"
    echo "backend_matrix=$matrix"
} >>"$out"
echo "full=$full backend=$backend auth=$auth google=$google common=$common webapp=$webapp modes=$modes" >&2
