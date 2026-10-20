# CI

`.github/workflows/ci.yml` runs on pull requests, on every push to `develop`,
nightly, and by hand (Actions → CI → Run workflow).

| Run | Suites | Persistence modes |
|---|---|---|
| Pull request | those the changed files can affect | Postgres |
| Push to `develop`, nightly, manual (`scope: full`) | all | Mongo, dual and Postgres |
| Manual, `scope: pr` | all | Postgres (what a pull request runs) |

The **Plan** job decides (`.github/scripts/ci-plan.sh`). Its path rules are
conservative: prose (`docs/`, top-level `*.md`) runs nothing, a change inside one
service runs that service (plus the common suite, which scans every service for
settings names), `common/` runs every Python suite, and anything else
(workflows, compose files, `deploy.sh`, `postgres/`, `docs/spec/`, the settings
inventory, ...) runs everything, because tests read those files. **CI ok**
fails when any job failed or was cancelled; use it as the one required check.

The webapp Docker image (`pr-checks.yml`) is built only when its Dockerfile,
dependencies or the files it copies by name change; the CI webapp job builds the
app on every webapp change.

## Backend shards

The backend suite runs in 12 parallel jobs on a pull request (8 in the full
runs; the count is set in `ci-plan.sh`, and a manual run can try another one
with its `shards` input). [pytest-split] gives each job a
share of the tests with about the same total time, from the per-test durations
recorded in `backend/.test_durations` (tests missing from the file count as the
average, so new tests are fine until the next refresh). In the full runs the
Mongo and dual modes take 2 jobs each and skip `tests/admin` (the admin service
always uses Postgres; its tests do not depend on the mode) and the permission
matrix (authorization, not storage; it runs in the Postgres mode).

Refresh the durations when the shards drift apart (a shard much slower than the
others in the CI log), from `backend/` with the test databases running:

```sh
DB_READ_SOURCE=postgres DB_WRITE_MODE=postgres \
  uv run pytest -n 4 --dist loadgroup --store-durations --clean-durations
```

and commit `backend/.test_durations`. The file holds every test id, so a
parametrized test must not put its values in its id: give it `ids=` that name
the case (`tests/test_durations_file.py` fails when an id looks like a key or
token). Running one shard locally:

```sh
uv run pytest -n 4 --dist loadgroup --splits 12 --group 3 --splitting-algorithm least_duration
```

[pytest-split]: https://github.com/jerry-git/pytest-split
