# MongoDB → PostgreSQL cutover runbook

Operator procedure for moving bettercollected's data from MongoDB (and its jobs from Temporal)
to the `app-postgres` PostgreSQL database, one repository group at a time, with rollback at every
step. Code conventions: `backend/AGENTS.md` "Persistence".

Everything below is driven by environment variables read at boot — **a flip is a restart**, never
a code change — and by the migration CLI, which runs out of band as a one-off process.

## The moving parts

| piece | where | what it does |
|---|---|---|
| `DB_READ_SOURCE`, `DB_WRITE_MODE` (+ `__<group>` overrides) | each service's env | per repository group: `mongo` → `dual` (write both, read Mongo) → `postgres_primary_dual` (write both, read Postgres) → `postgres` |
| `JOBS_BACKEND` (+ `__delete_user`, `__delete_response`, `__run_action`) | backend, actions-executor | `temporal` (default) or `postgres` (procrastinate) per job kind |
| `DB_SHADOW_READ_SAMPLE` | each service | fraction of reads also issued to the other store and compared |
| `GET /persistence/status` (admin) | backend | flags in effect, routing counters, outbox backlog, Postgres reachability |
| `python -m backend.migrate …` (also `auth.migrate`, `googleform.migrate`) | one-off container, service role | `preflight` · `backfill` · `verify` · `reconcile` · `status [--json]` · `jobs-sweep`; `--group <g>` or `--collections a,b` limit a run |
| outbox `mirror_write_failures` | Mongo collection + Postgres table, per service | mirror writes that failed; drained by a full `reconcile` |
| `store_migration` | Postgres table, per service schema | the "migration verified" marker and per-group verify records, written only by a clean `verify` (see "Verified marker") |
| `jobs-worker` service, actions-executor with `JOBS_BACKEND=postgres` | compose | consume the `default` and `actions` queues |
| `DB_AUTO_MIGRATE` (default `false`) | backend (+ jobs-worker), auth, google | `true`: each service runs `alembic upgrade head` for its own schema at startup (backend: plus procrastinate's `jobs` tables), under a per-schema Postgres advisory lock |

Groups (backend): `refdata`, `identity`, `forms`, `responses`, `actions`, `ai`, `analytics`.
Auth and google each have one group (`auth`, `google`). Which collections belong to which backend
group is declared in `backend/backend/db/groups.py` (`COLLECTION_GROUPS`); it matches the `group`
of the repository that serves each collection, so `--group g` on the migration CLI covers exactly
what `DB_READ_SOURCE__g` / `DB_WRITE_MODE__g` move. `--group` accepts several groups (repeated or
comma-separated); an unknown group stops the CLI with exit code 2 and the list of valid groups.
`--group` and `--collections` cannot be combined.

**Cutover-order rule, enforced at boot:** while a group still *reads* Mongo, the groups its Mongo
repositories join into must keep *writing* Mongo. In practice: never set `DB_WRITE_MODE=postgres`
for `forms` while `responses` reads Mongo, for `identity` while `forms` reads Mongo, or for
`actions` while `identity` reads Mongo. `postgres_primary_dual` is always allowed. A violation
fails the service at startup with the rule spelled out.

**Schema check at startup.** Whenever a service's flags put any group on Postgres (`dual` and
beyond, a Postgres read source or shadow reads), it compares its schema's Alembic revision with
the code's head before serving and **refuses to start** if the schema is behind or was never
migrated — the log names the schema, both revisions and the fix. A schema *ahead* of the code (a
newer release migrated it, then a rollback or reschedule brought the older image back) logs a
warning and starts: migrations are expand-only, so the older code still runs on it. The backend also
requires procrastinate's `jobs` tables when a job kind is on Postgres. With every flag at its
Mongo default nothing is checked and no database is needed. (Before this check a service on an
unmigrated database started "fine" and then answered every Postgres-backed request with 500
`UndefinedTable`.) An unreachable Postgres keeps its old rule: fatal only when a group *serves*
from it.

**Who runs the migrations.** `deploy.sh` runs them explicitly before the services roll (below).
A deployment that does not go through `deploy.sh` — the hosted deploys use Docker Swarm
(`.github/workflows/deploy.yml`, `mesudip/docker-stack`) with their own stack definition, and
nothing there migrates — must either run the same commands as a pre-deploy step or set
**`DB_AUTO_MIGRATE=true`** on backend, jobs-worker, auth and integrations-googleform. Then each
service migrates its own schema in-process at startup, before serving, as its own role; replicas
starting together serialise on a Postgres advisory lock (one per schema), the others wait and then
find the schema at head. Applied revisions are logged (`DB_AUTO_MIGRATE: schema 'app' migrated,
applied …`); a failed migration refuses to start. A waiting replica gives up after
`DB_AUTO_MIGRATE_LOCK_WAIT_SECONDS` (default 300) and the migration's DDL waits at most 60s for a
table lock, so a stuck migration fails and restarts instead of hanging. A newer schema than the
image knows (a rollback past a migration) is left alone with a warning — nothing is migrated
backwards automatically. Migrations run in a single transaction: one that needs non-transactional
DDL (`CREATE INDEX CONCURRENTLY`, an `autocommit_block`) can't go through `DB_AUTO_MIGRATE` and must
be run by hand before the release.

## R1 — release with everything still on Mongo

Prerequisites in the deployment (`deploy.sh` does these): the `app-postgres` service with the
five role passwords (`APP_POSTGRES_PASSWORD`, `BC_APP_PASSWORD`, `BC_AUTH_PASSWORD`,
`BC_GOOGLE_PASSWORD`, `BC_JOBS_EXEC_PASSWORD`), `DATABASE_URL` per service, `alembic upgrade head`
per service **as its own role**, and `python -m backend.jobs.schema` — or, instead of the last two,
`DB_AUTO_MIGRATE=true` (see "Schema check at startup" above). Note that with every flag on Mongo
the services skip the schema step entirely, so on R1 `DB_AUTO_MIGRATE` alone migrates nothing:
run the explicit commands once, or let the first restart with `DB_WRITE_MODE=dual` (Phase 1,
step 1) migrate.

1. Deploy with all flags at their defaults (`mongo` / `temporal`). Behaviour is unchanged; the only
   new thing running is the Postgres container and empty tables.
2. Check every service logs `persistence flags: {...}` at boot and `GET /persistence/status`
   (as an admin) shows `postgres.configured: true, reachable: true`.
3. Roll back: redeploy the previous images. Nothing depends on Postgres yet.

## Phase 1 — mirror, backfill, verify (Mongo stays authoritative)

Start on staging; repeat on production only after the staging gate.

1. **Mirror everything:** `DB_WRITE_MODE=dual` on backend, auth, google. Restart. Reads still
   come from Mongo; every write is also applied to Postgres, best-effort, bounded by
   `DB_MIRROR_TIMEOUT_MS` (2 s). A failing mirror never fails a request — it lands in the outbox.
   Watch `/persistence/status` → `metrics.<group>.mirror_failures` and `outbox`. Expected: zero.
2. **Preflight:** `python -m backend.migrate preflight` (and for auth/google). Non-zero exit means
   documents with non-ObjectId ids or duplicate unique keys (constraints *and* unique indexes;
   null and empty-string keys never collide); fix the data in Mongo first — backfill skips invalid
   ids and stops that collection on a duplicate (the others still run). Known from the
   2026-09-25 rehearsal on a production dump: two `forms` documents shared a `form_id` (a
   re-import made a second copy in 2023; the app always served the first). Keep the document
   `find_one` has always returned — the lowest `_id` — and remove the rest:

   ```js
   // mongosh, database bettercollected_backend
   db.forms.aggregate([{$group:{_id:"$form_id", ids:{$push:"$_id"}}},{$match:{"ids.1":{$exists:true}}}])
     .forEach(d => { const ids = d.ids.sort(); db.forms.deleteMany({_id:{$in: ids.slice(1)}}); });
   ```
3. **Backfill:** `python -m backend.migrate backfill --max-minutes 30` as many times as needed;
   each run resumes from its checkpoint (`status` shows per-collection state, rows copied,
   last id, and `stalled: true` if a run died mid-way). Use `--group g` or `--collections a,b` to
   order work, `--dry-run` to rehearse. Backfill never overwrites a row the application dual-wrote,
   and never writes the verified marker.
4. **Verify:** `python -m backend.migrate verify` — exit 0 only when no row is missing on either
   side, the per-row checksums match and the sampled round-trip agrees. For very large collections
   use `--sample-every 10` (a sampled run is never recorded as verified). A clean full run writes
   the verified marker; `--group g` records that group (see "Verified marker").
5. **Reconcile:** `python -m backend.migrate reconcile` copies whatever verify found (Mongo
   authoritative) and, when run over every collection, marks both outboxes resolved. Run `verify`
   again. Rows that exist on one side only are not deleted (see "Reconcile and deleted rows").
6. **Shadow reads:** `DB_SHADOW_READ_SAMPLE=0.05` for a week. `metrics.<group>.shadow_diffs`
   must stay at zero; a diff names the repository and method, never the payload.

Rehearsal numbers (production dump, 2026-09-25, laptop): backfill of the backend's 69k documents
(182 MB of responses) in ~30 s, `verify` in 14 s, auth and google in about a second each — all
clean once the two duplicate forms were removed. An offline shadow-read sweep over the same
dump (every identity/forms/responses/refdata read method, 50 workspaces, ~1,300 calls) found
one real divergence, fixed since: three responder groups carry a glob (`*@…`) where a regex was
expected, which made Mongo's `$regexMatch` fail the whole private-form listing for members of
those workspaces while the twin quietly skipped the group. Both sides now match the pattern in
Python and reject non-compiling patterns on save. Everything else was shape-only (absent vs
null fields, `_id` vs `id` on raw documents, list order), invisible after serialisation.

**Gate to Phase 2:** `verify` clean twice, 24 h apart; shadow diffs zero for 7 days; mirror
failures zero for 7 days; the CI matrix (which runs the whole suite served from Postgres) green.

Rollback at any point: `DB_WRITE_MODE=mongo` (stop mirroring) — one rolling restart; or simply
stop running the CLI. Nothing in Phase 1 changes what users read.

## Phase 2 — serve from Postgres, one group at a time

Order: `refdata` → `analytics` → `ai` → `actions` → `identity` → `forms` → `responses`, then
auth and google. For each group `g`:

1. `DB_READ_SOURCE__g=postgres`, `DB_WRITE_MODE__g=postgres_primary_dual`. Restart. Postgres is
   now authoritative for `g`; Mongo is kept current by the reverse mirror, so rollback stays
   instant.
2. Soak 48–72 h: `mirror_failures` for `g` zero, error rate at baseline, `verify --group g`
   clean (Mongo is now the copy, and it should still match).
3. Roll back: `DB_READ_SOURCE__g=mongo`, `DB_WRITE_MODE__g=dual`. One restart.

Jobs: `JOBS_BACKEND__delete_response=postgres` first (scheduled deletions; run
`python -m backend.migrate jobs-sweep --backend postgres` afterwards so every pending
expiration has a job regardless of which engine scheduled it; it reads the responses through the
routed repository, so from `DB_READ_SOURCE__responses`, and opens Mongo only while the `responses`
group still uses it), then `__delete_user`, then
`__run_action` with the actions-executor started with `JOBS_BACKEND=postgres`. Roll back a job
kind with `JOBS_BACKEND__<job>=temporal` and `jobs-sweep --backend temporal`.

## Verified marker

Each service schema (`app`, `auth`, `google`) has a `store_migration` table. Only `verify` writes
to it; `backfill`, `reconcile` and the services never do. A row is appended:

- **per group** (`scope = 'group'`) for every repository group whose collections were *all*
  verified in that run with nothing missing on either side, no checksum mismatch, no round-trip
  drift and the same count in both stores;
- **the marker** (`scope = 'service'`) when every group of the service was, either
  - in one run: `verify` without `--group`/`--collections`, or with `--group` naming every
    group; or
  - by combining group runs: after a `verify --group g`, the latest group row of *every* group is
    taken, and the marker is written when each of them covers all of its group's current
    collections, is at most 7 days old, and no backfill checkpoint of its collections was written
    after it. The marker then records the group runs it rests on (`based_on`) and, as
    `verified_at`, the oldest of them.

Not recorded: a sampled run (`--sample-every` > 1), a `--collections` run, and any run while a
backfill of one of the collections is in progress. Documents whose `_id` is not an ObjectId are
never copied, so their collection's counts differ and it is never recorded: remove or fix them
first (`preflight` counts them). A verify that finds differences writes nothing and does not
revoke an earlier marker: the marker says that a clean verify happened (when, by which run, with
which code version and counts), not that the stores still agree. Each row stores the service,
`verified_at`, the counts per collection, the code version (`<package version>+schema.<Alembic
head>`) and the verify run id.

Reading it: `status` prints it, `status --json` returns it under `marker` (with `last_verify` per
group and overall), and code uses `common.db.marker.migration_verified(conn, service)`, which
returns the latest marker or `None` (also when the table does not exist yet, or, given the
service's current collections, when a collection was added after the verify).

## Reconcile and deleted rows

`reconcile` never deletes anything, in either direction. It compares the stores collection by
collection: a document or row that exists on one side only is copied to the other side when that
side is the target of the direction, and otherwise left where it is.

| situation | `verify` reports | `reconcile` (mongo->postgres) | `reconcile --direction postgres->mongo` |
|---|---|---|---|
| deleted in Mongo (primary, `dual`), the Postgres delete failed: the row is only in Postgres | `missing_in_mongo` | leaves the row in Postgres | copies the row back into Mongo |
| deleted in Postgres (primary, `postgres_primary_dual`), the Mongo delete failed: the document is only in Mongo | `missing_in_postgres` | copies the document back into Postgres | leaves the document in Mongo |

So a failed mirror delete is not repaired by reconciling towards the mirror, and reconciling
towards the primary brings the deleted record back. A *full* reconcile (no `--group` or
`--collections`) then marks every unresolved outbox entry resolved, including the delete entries
it did not replay; a partial reconcile leaves the outboxes alone (their entries name a repository
and method, not a collection). Before reconciling, read the outbox (`status --json` →
`mirror_failures.<store>.unresolved_by_method`); for each unresolved delete, check the record's id
in both stores and delete the stray copy by hand from the store that is not authoritative for its
group, then run `verify` again. Also under `postgres_primary_dual`: a write replayed into Mongo is
saved with a fresh `updated_at`, so `verify` can report it as mismatched;
`reconcile --direction postgres->mongo` rewrites it from the row.

## Duplicate AI preference memories

Revision `0018` makes (`workspace_id`, `user_id`) unique in `app.ai_preference_memories`, as
Mongo's `workspace_user_unique` already is. It is a plain `CREATE UNIQUE INDEX` in the migration's
transaction (not `CONCURRENTLY`, which `DB_AUTO_MIGRATE` cannot run; the table is small), so it
goes through `deploy.sh` and `DB_AUTO_MIGRATE` alike. While Mongo is written first its unique index
keeps Postgres free of duplicates; only a stack that already wrote `postgres` or
`postgres_primary_dual` for the `ai` group could hold some. Then the migration refuses before
changing anything, naming only the counts, and the service does not start until they are resolved.
Nothing is merged automatically (two rows hold separate learned entries and consent times). List
them by id:

```sql
SELECT workspace_id, user_id, array_agg(id ORDER BY updated_at DESC) AS ids
FROM app.ai_preference_memories
GROUP BY workspace_id, user_id HAVING count(*) > 1;
```

Keep the row Mongo holds if Mongo is still written, else the most recently updated one, delete the
others (by `id`), and migrate again.

## Phase 3 — remove Mongo and Temporal

Only after two weeks fully on Postgres with everything at `postgres`/`postgres`:
`mongodump` archived and restore-tested; then the removal PRs (code, dependencies, compose,
env, docs). Keep the Mongo volume and dump for 30 days. Regression after removal: redeploy the
R2 images (they still know both stores) and `reconcile --direction postgres->mongo` to catch
Mongo up from the dump plus the outbox.

## Quick reference

```bash
# what is in effect, counters, outbox, reachability (admin cookie)
curl -b "$COOKIES" https://<backend>/api/v1/persistence/status

# schema migrations by hand (what deploy.sh runs; DB_AUTO_MIGRATE=true does the same at startup)
docker compose -f docker-compose.deployment.yml run --rm --no-deps backend \
  /api/backend/.venv/bin/alembic -c /api/backend/alembic.ini upgrade head
docker compose -f docker-compose.deployment.yml run --rm --no-deps backend \
  /api/backend/.venv/bin/python -m backend.jobs.schema
# … auth: /api/auth/.venv/bin/alembic -c /api/auth/alembic.ini upgrade head
# … integrations-googleform: alembic -c /api/integrations/google/alembic.ini upgrade head

# migration CLI, one-off container with DATABASE_URL (service role) + MONGO_URI
docker compose -f docker-compose.deployment.yml run --rm --no-deps backend \
  /api/backend/.venv/bin/python -m backend.migrate status
… status --json | preflight | backfill --max-minutes 30 | verify | reconcile | jobs-sweep --backend postgres
… --group refdata backfill | --group refdata verify | --group refdata,analytics reconcile
```

`status --json` prints one JSON document (`format: 1`): per collection its group, the counts in
Mongo and Postgres and the backfill checkpoint; per group the last clean verify; the outbox depth
per store; mirror failures per store (total, unresolved, unresolved per repository method); the
last clean verify of any kind; and the marker (`null` until one is written). Counts and names
only, never document contents. Plain `status` prints the same as a short summary.

Every command is idempotent and can be interrupted; a re-run continues where it stopped.
