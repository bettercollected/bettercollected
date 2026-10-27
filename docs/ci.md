# CI

`.github/workflows/ci.yml` runs on pull requests, on every push to `develop`,
nightly, and by hand (Actions → CI → Run workflow).

| Run | Suites |
|---|---|
| Pull request | those the changed files can affect |
| Push to `develop`, nightly, manual (`scope: full`) | all |
| Manual, `scope: pr` | all (what a pull request would run, for every suite) |

There is one persistence mode: Postgres is the only store since 4.1, so there is no Mongo or dual run of the
suites. The runs differ only in which suites they run and in how many backend shards (12 on a pull request, 8 in
the full runs).

The **Plan** job decides (`.github/scripts/ci-plan.sh`). Its path rules are
conservative: prose (`docs/`, top-level `*.md`) runs nothing, a change inside one
service runs that service (plus the common suite, which scans every service for
settings names; a change in `temporal/actions-executor/` also runs its own tests), `common/` runs every Python suite, and anything else
(workflows, compose files, `deploy.sh`, `postgres/`, `docs/spec/`, the settings
inventory, ...) runs everything, because tests read those files. **CI ok**
fails when any job failed or was cancelled; use it as the one required check.

The webapp Docker image (`pr-checks.yml`) is built only when its Dockerfile,
dependencies or the files it copies by name change; the CI webapp job builds the
app on every webapp change.

A push to `develop` builds and pushes the images but deploys them only while the repository variable
`DEVELOP_DEPLOY_ENABLED` is `true` (Settings → Secrets and variables → Actions → Variables); unset, the
`deploy` job is skipped. `master` and tag deploys don't depend on it.

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

## Without Mongo

Every repository group of every service reads from and writes to Postgres only, and the services start and serve
without MongoDB: they never connect to it. CI checks that: the backend shards and the auth and Google jobs run with
no Mongo server (backend: `MONGO_URI` empty; auth and Google: `MONGO_URI` on a closed port), and each service's suite
boots its app factory (the backend also its job worker) in a fresh process that way
(`tests/**/test_startup_without_mongo.py`), with a set but unreachable `MONGO_URI` still refusing the backend's start
(the check for unimported 4.0 data). auth and Google refuse a stale `DB_READ_SOURCE` / `DB_WRITE_MODE` that names
another store (`auth/tests/test_startup_postgres_only.py`).

A few tests drive Mongo themselves: the import from 4.0 (`python -m <service>.migrate`: backfill, verify, reconcile,
the outbox, tombstones), the store-wide tasks and scripts. They plant 4.0 documents with the frozen Beanie classes of
`tests/app/db/beanie_originals.py` (Beanie is a test-only dependency: `common/tests/test_no_beanie_in_runtime.py`
keeps it out of the runtime). They carry the `mongo` marker, assigned by the `MONGO_DRIVEN` list in the suite's
`tests/conftest.py`; the Mongo-less runs pass `-m "not mongo"`, and they run with Mongo in one more backend job
("Mongo-driven tests") and in a second step of the Google and auth jobs. A new test that needs a Mongo server goes on
that list, or it fails in the Mongo-less shards. Locally, the same backend run:

```sh
MONGO_URI="" uv run pytest -n 4 --dist loadgroup -m "not mongo"
```

## Backend shards

The backend suite runs in 12 parallel jobs on a pull request (8 in the full
runs, plus the one for the tests that drive Mongo; the count is set in `ci-plan.sh`, and a manual run can try another one
with its `shards` input). [pytest-split] gives each job a
share of the tests with about the same total time, from the per-test durations
recorded in `backend/.test_durations` (tests missing from the file count as the
average, so new tests are fine until the next refresh).

Refresh the durations when the shards drift apart (a shard much slower than the
others in the CI log), from `backend/` with the test databases running:

```sh
MONGO_URI="" uv run pytest -n 4 --dist loadgroup -m "not mongo" --store-durations --clean-durations
```

and commit `backend/.test_durations`. The file holds every test id, so a
parametrized test must not put its values in its id: give it `ids=` that name
the case (`tests/test_durations_file.py` fails when an id looks like a key or
token). Running one shard locally:

```sh
uv run pytest -n 4 --dist loadgroup --splits 12 --group 3 --splitting-algorithm least_duration
```

[pytest-split]: https://github.com/jerry-git/pytest-split
