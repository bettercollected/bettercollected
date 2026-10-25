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

## Postgres versions

The test jobs run against PostgreSQL 15 (`POSTGRES_IMAGE` in `ci.yml`, used by
`.github/scripts/test-dbs.sh`): the oldest major version supported, since
self-hosted deployments may run 15 while the compose files ship 16, and a
feature new in 16 would otherwise pass CI and fail there. One more backend job
("postgres, newest server: migrations and roles") runs the tests of the
migration chains and of the database role scripts (`tests/admin`,
`tests/app/db`, `tests/app/migrate`) against `POSTGRES_IMAGE_NEWEST` (16), where
a behaviour change between major versions (role membership, privileges) would
show. Locally, start the same server with `POSTGRES_IMAGE=postgres:15
.github/scripts/test-dbs.sh start postgres`.

## Postgres mode without Mongo

In the Postgres mode every repository group reads from and writes to Postgres
only, and the services then start and serve without MongoDB
(`common/common/db/mongo.py`). CI checks that: the Postgres backend shards and
the Postgres auth and Google jobs run with no Mongo server and `MONGO_URI` on
a closed port, and each service's suite boots its app factory (the backend
also its job worker) in a fresh process that way
(`tests/**/test_startup_without_mongo.py`), with a mixed configuration still
refusing to start on an unreachable Mongo.

A few tests drive Mongo themselves whatever the flags (store parity, the
migration CLI, store-wide tasks and scripts). They carry the `mongo` marker,
assigned by the `MONGO_DRIVEN` list in the suite's `tests/conftest.py`; the
Mongo-less runs pass `-m "not mongo"`, and they run with Mongo in one more
backend job ("postgres, Mongo-driven tests") and in a second step of the
Google and auth jobs. A new test that needs a Mongo server goes on that list, or it
fails in the Mongo-less shards. Locally, the same run:

```sh
DB_READ_SOURCE=postgres DB_WRITE_MODE=postgres \
  MONGO_URI="mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=2000" \
  uv run pytest -n 4 --dist loadgroup -m "not mongo"
```

## Backend shards

The backend suite runs in 12 parallel jobs on a pull request (8 in the full
runs, plus the one for the tests that drive Mongo; the count is set in `ci-plan.sh`, and a manual run can try another one
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
