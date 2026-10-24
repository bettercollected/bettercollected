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
be run by hand before the release. The whole cutover on such a stack, stage by stage, is in
"Running the cutover on an orchestrated (Docker Swarm) stack" below.

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
   After its mirror write, each write also reads back the rows it touched from both stores and
   copies the primary's version to the mirror where they differ: two writes to the same document
   at once can reach the mirror in the opposite order, which would leave the mirror with the older
   version. `metrics.<group>.mirror_repairs` counts the copies rewritten this way; a few under
   concurrent editing are expected. A document that still differs after three rounds, or when the
   mirror timeout has passed, counts as a mirror failure and lands in the outbox like one; a mirror
   copy of a document the primary no longer holds is deleted even then. A write that touched more
   than 500 documents (a bulk delete) is not read back (`metrics.<group>.mirror_converge_skipped`):
   `verify` covers it. Collections Mongo expires by a TTL index (sessions, rate-limit counters,
   idempotency keys, flow events) treat an expired copy as absent, so one store's expiry is never
   copied back from the other.
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
   again. A record deleted in one store whose copy survives in the other is deleted there, never
   copied back (see "Reconcile and deleted rows").
   Reconcile can run while the services write: each copy is stored only while the target still
   holds what reconcile read, so a document the application changed in the meantime is left as
   the application wrote it and counted under `skipped` (an update never re-inserts a row the
   application deleted meanwhile). A run with skipped copies leaves the outbox open. **Always run
   `verify` after a `reconcile`**: it is what shows that the stores agree. A record deleted while
   reconcile runs is not copied back: the Postgres insert checks for a newer tombstone in the same
   statement, and a Mongo insert is checked again after it lands and removed when the record was
   deleted meanwhile. Should anything still differ, `verify` shows it (a deleted record as
   `tombstoned`); then run `reconcile` again, then `verify` again. Collections Mongo expires by a TTL
   index (sessions, rate-limit counters, idempotency keys, SSO states, SCIM, flow events) treat an
   expired copy as absent: reconcile never copies one.
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

Every delete records a **tombstone** in the store that deletes, in every write mode: the
collection, the id and the time of the delete, nothing else (no document content, no personal
data). Postgres writes it to `<schema>.deletion_tombstones` in the same transaction as the delete
(app migration `0021`, auth and google `0004`), and Mongo writes it to the `deletion_tombstones`
collection just before the delete. A copy of a record is *deleted* when a tombstone for its id, from
either store, is newer than the copy's `updated_at`; a record written again under the same id after
the delete (ids derived from a relation are) is newer, so it is not.

| situation | `verify` reports | `reconcile`, either direction |
|---|---|---|
| deleted in Mongo (primary, `dual`), the Postgres delete failed: the row is only in Postgres | `missing_in_mongo`, `tombstoned` | deletes the row from Postgres |
| deleted in Postgres (primary, `postgres_primary_dual` or `postgres`), the Mongo delete failed or Mongo was no longer written: the document is only in Mongo | `missing_in_postgres`, `tombstoned` | deletes the document from Mongo |
| deleted, but copies older than the delete are in both stores (brought back by an earlier reconcile, or restored from a backup) | `tombstoned` | reports it (`tombstoned` in its result) and changes nothing: delete both copies by hand, by id, after checking them |

`reconcile` never copies a deleted record, in either direction, and deletes a surviving copy only
while it is still the copy it read (same `updated_at`). Its result per collection gives `deleted`
(surviving copies it deleted) and `tombstoned` (records left for an operator). A `verify` with any
`tombstoned` record is not clean and records no marker; its output names up to five such ids per
collection (`samples.tombstoned`).

Times are compared at millisecond precision (Mongo's), so a record deleted and written again in the
same write, such as a responder group's members when its emails are saved, is not a deleted
record.

Retention: tombstones are kept 120 days, enough for the cutover. Some ids are derived from personal
data (a responder group member's id is a hash of the group and the email), so they are not kept
longer. Mongo expires its tombstones with a TTL index (`deleted_at_ttl`). Each service prunes its
expired Postgres tombstones as it records deletes (a bounded batch every 200 deletes), and
`reconcile` prunes them at the end of each run. Drop the tables and the collection with the Mongo
decommission (below).

A *full* reconcile (no `--group` or `--collections`) then marks every unresolved outbox entry
resolved; a partial reconcile leaves the outboxes alone (their entries name a repository and method,
not a collection). Also under `postgres_primary_dual`: a write replayed into Mongo is saved with a
fresh `updated_at`, so `verify` can report it as mismatched; `reconcile --direction postgres->mongo`
rewrites it from the row.

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

## Running the cutover on an orchestrated (Docker Swarm) stack

A Swarm stack has no `deploy.sh`. The phases above still apply; on Swarm each step is one of three
things:

- **an edit to the stack definition**, deployed through whatever manages the stack
  (`docker stack deploy -c <stack file> <stack>` or your stack manager). Every flag here is
  environment-only (tier T5 in `docs/settings-inventory.md`): neither the settings store nor the
  admin portal can change it;
- **a one-off command** (the migration CLI), run in a container of the running service or as a
  one-off Swarm job on the stack's network;
- **an admin task** in the portal, where one exists (`responses.*`, `keyset.verify`). `verify` and
  `reconcile` are not tasks: they run from the CLI only.

The stages: **Stage 0** is Phase 1 plus a week of shadow reads. For each group, **A** (read
switch) and **B** (primary switch) split Phase 2 step 1 into two restarts, so each restart changes
one thing. **C**, **D** and **decommission** take Phase 3 in three steps. The jobs flips run
alongside A and B. Placeholders: `<stack>` is the stack name and `<g>` a group. Services have their
compose names (`backend`, `jobs-worker`, `auth`, `integrations-googleform`, `task-runner`, `admin`,
`mongodb`), plus `actions-executor` for the Temporal actions executor; use your own names if
they differ.

### Ground rules

- **The stored stack definition is the source of truth.** Make every change by editing it and
  deploying it, and note the values you replace: they are the rollback. Anything changed with
  `docker service update --env-add` (in an incident, say) is undone by the next deploy, including
  the image updates CI pushes, so copy it into the stored definition straight away. Before each
  stage, compare the flags the running services have with the stored ones:

  ```bash
  # DB_* and JOBS_BACKEND* only: flags, never credentials
  docker service inspect <stack>_backend \
    --format '{{json .Spec.TaskTemplate.ContainerSpec.Env}}' \
    | jq -r '.[] | select(startswith("DB_") or startswith("JOBS_BACKEND"))'
  ```
- **`backend` and `jobs-worker` carry identical `DB_*` and `JOBS_BACKEND*` flags.** The jobs worker
  runs the backend's repositories (deleting a user touches every group). Keep the flags in one block
  that both services read (a shared `env_file`, or a YAML anchor if your tooling supports merge
  keys), and always deploy the two together.
- **The task runner's `DB_WRITE_MODE`, `DB_WRITE_MODE__responses` and `DB_WRITE_MODE__google`
  follow the services' values** (the backend's for the default and `responses`, the Google
  integration's for `google`) and change in the same deploy. If they are unset, the responses and
  keyset tasks refuse with `write_mode_unknown` (docs/admin-service.md, "Task runner").
- **Migrations:** `DB_AUTO_MIGRATE=true` on `backend`, `jobs-worker`, `auth` and
  `integrations-googleform`, from Stage 0 on ("Who runs the migrations"). A release whose notes
  name a migration with non-transactional DDL is migrated by hand first (one-off commands below).
- **Let Swarm roll back a service that refuses to start.** A bad flag combination, a broken
  cutover-order rule or a schema behind the code stops the process at boot. With
  `update_config: {parallelism: 1, order: start-first, failure_action: rollback, monitor: 60s}`, the
  old tasks keep serving and Swarm puts the previous spec back. The stored definition still holds
  the rejected values: correct it before the next deploy.
- **Old and new flags run side by side while a service rolls.** Every transition below keeps both
  stores written during that window, so this is safe. Don't run `backfill`, `verify` or
  `reconcile` while a service is rolling, and don't redeploy a service while a long CLI run is
  going on inside one of its containers. (Every command resumes, but a verify cut off by a restart
  records nothing.)
- **Keyset freeze, from Stage 0 to decommission:** no `keyset.reencrypt` and no `keyset.drop_old`,
  neither as tasks nor through `scripts.rotate_response_keyset`. A re-encryption racing a store
  switch, or a dropped key that Mongo or its archive still needs, is how values become unreadable
  in the middle of the move. `responses.check_undecryptable` and `keyset.verify` are read-only and
  allowed. A compromised key overrides the freeze: rotate as in
  [response-keyset-rotation.md](response-keyset-rotation.md) with both stores configured, then take
  a fresh Mongo dump.

### One-off commands

Run the migration CLI inside a running task of the service. That task has the service's role,
flags, settings and networks, and runs the same image tag. That tag matters: the verified marker
records the code version, and the CLI checks the schema head it knows.

```bash
docker service ps <stack>_backend --filter desired-state=running   # which node runs a task
# on that node:
C=$(docker ps -q -f name=<stack>_backend. | head -n1)
docker exec "$C" /api/backend/.venv/bin/python -m backend.migrate status
docker exec "$C" /api/backend/.venv/bin/python -m backend.migrate --group refdata verify
docker exec "$C" /api/backend/.venv/bin/alembic -c /api/backend/alembic.ini current
# auth and the Google integration, the same way:
#   <stack>_auth                    /api/auth/.venv/bin/python -m auth.migrate …
#   <stack>_integrations-googleform /api/integrations/google/.venv/bin/python -m googleform.migrate …
```

A long `backfill` can run as a one-off Swarm job (Docker 20.10 or later), so a rolling service
does not cut it off:

```bash
docker service create --name bc-migrate --mode replicated-job --restart-condition none \
  --network <stack>_<network reaching Postgres and Mongo> --env-file <backend env, mode 0600> \
  <backend image>:<tag the service runs> \
  /api/backend/.venv/bin/python -m backend.migrate backfill --max-minutes 30
docker service logs -f bc-migrate
docker service rm bc-migrate     # then delete the env file
```

The env file holds the service's own environment (its `DATABASE_URL`, `MONGO_URI`/`MONGO_DB` or
the settings-store variables the service reads them through, and the `DB_*` flags).
`docker service inspect` shows those values for as long as the job exists, so remove it when it is
done.

### Watching a stage

- **Every replica restarted with the new flags.** `docker service ps <stack>_<service>` shows every
  task running on the new spec. `docker service logs --since <deploy time> <stack>_<service> 2>&1 |
  grep 'persistence flags'` prints one line per replica. As an admin,
  `GET /api/v1/persistence/status` → `flags` shows the backend's flags.
- **Portal → Health** (stacks that run the admin service and the settings store): every instance
  is "reporting" and nothing is behind or waiting for a restart. Instances replaced by the deploy
  show as "stopped" once they miss two minutes of reports. Each instance also reports which stores
  it writes. The page doesn't show that column; read it as the admin service's role or a superuser:

  ```sql
  SELECT service, instance, write_stores, now() - reported_at AS age
  FROM settings.service_state ORDER BY service, instance;
  ```

  `mongo,postgres` from Stage 0 through B, `postgres` after C.
- **Shadow diffs and mirror failures.** The counters in `/persistence/status` belong to the one
  backend replica that answered, and a restart resets them. To cover every replica, count the log
  lines on `backend`, `jobs-worker`, `auth` and `integrations-googleform`:

  ```bash
  docker service logs --since <stage start> <stack>_backend 2>&1 \
    | grep -cE 'shadow read differs|shadow read failed|mirror write failed'
  ```

  Each line names the group, repository and method, never a payload. The durable record is the
  outbox: `migrate status --json` → `outbox` and `mirror_failures.<store>.unresolved`, per service.
- **`verify --group <g>`** exits 0 (for `auth` and `google`, `auth.migrate verify` and
  `googleform.migrate verify`).
- **5xx rate and p95 latency**, from your proxy or APM, against a baseline taken before the stage.
  Watch Postgres connections against `max_connections` as well: shadow reads add load.

Exit criteria for every A and B: 0 unexplained shadow diffs, from at least 1000 shadow reads of the
group or the whole soak for a low-volume group; 5xx at baseline; p95 at most 1.2× baseline;
`verify --group <g>` clean; 0 mirror failures for the group.

### Stage 0 — mirror, backfill, verify, shadow

Before you start: a `mongodump --archive --gzip` of every Mongo database (backend, auth, the
Google integration, and Typeform's if you have one), encrypted, kept off the host, and its restore
tested by counts. On a stack with responses older than `workspace_id`, also run
`responses.backfill_workspaces` (dry run, then apply) and `responses.check_undecryptable` from the
portal.

| service | change |
|---|---|
| `backend`, `jobs-worker`, `auth`, `integrations-googleform` | `DB_WRITE_MODE=dual`, `DB_AUTO_MIGRATE=true` |
| `task-runner` | `DB_WRITE_MODE=dual`; its Mongo and Postgres connections configured |

1. Deploy all of these at once. Each service migrates its schema before it serves: look for
   `DB_AUTO_MIGRATE: schema '…' migrated` in the logs, or `alembic current` in a one-off.
2. For backend, auth and google, run Phase 1 steps 2–5 as one-off commands: `preflight` (fix
   duplicates as in step 2), `backfill`, `verify`, `reconcile`, then `verify` again. Repeat `verify`
   24 h later. Two clean runs write the marker (`status --json` → `marker` is not `null`).
3. Shadow reads: add `DB_SHADOW_READ_SAMPLE=0.1` (0.1 to 0.25) to `backend`, `jobs-worker`, `auth`
   and `integrations-googleform`. Deploy, then soak for 7 days.

Exit: `verify` clean twice, 24 h apart, on every service; 7 days of shadow reads with 0 diffs,
0 mirror failures and 0 unresolved outbox entries.
Rollback: `DB_WRITE_MODE=mongo` on all five services and `DB_SHADOW_READ_SAMPLE` removed, then
redeploy. `DB_AUTO_MIGRATE` can stay.
Stored definition: save it with Stage 0's values; it is the base for every group.

### Per group: A, then B

Order: `refdata`, `analytics`, `ai`, `actions`, `google`, `identity`, `auth`, `forms`,
`responses`. Take one group at a time, and start the next group's A only after the previous
group's B meets the exit criteria.

| group | services | A adds | B adds |
|---|---|---|---|
| `refdata`, `analytics`, `ai`, `actions`, `identity`, `forms` | `backend` + `jobs-worker` | `DB_READ_SOURCE__<g>=postgres` | `DB_WRITE_MODE__<g>=postgres_primary_dual` |
| `responses` | `backend` + `jobs-worker`; for B also `task-runner` | `DB_READ_SOURCE__responses=postgres` | `DB_WRITE_MODE__responses=postgres_primary_dual` |
| `google` | `integrations-googleform`; for B also `task-runner` | `DB_READ_SOURCE__google=postgres` | `DB_WRITE_MODE__google=postgres_primary_dual` |
| `auth` | `auth` | `DB_READ_SOURCE__auth=postgres` | `DB_WRITE_MODE__auth=postgres_primary_dual` |

**A, the read switch.** Add the read override and redeploy the service(s). Writes stay on `dual`,
so Mongo stays primary. Shadow reads stay on and now compare Postgres answers with Mongo's. Soak
at least 48 h, or 72 h for `identity`, `auth`, `forms` and `responses`. Before `auth`'s A, run a
full `auth.migrate reconcile` and a clean `auth.migrate verify`: before 4.0.2 some auth writes
skipped the mirror. Rollback: remove the override and redeploy.

**B, the primary switch.** Add the write override (and the `task-runner`'s for `responses` and
`google`), then redeploy. Postgres is now authoritative for the group, and the reverse mirror keeps
Mongo current: failures now land under `mirror_failures.mongo`. Soak at least 72 h. In `verify`, a
record replayed into Mongo can show as mismatched ("Reconcile and deleted rows"). Rollback: run
`reconcile --group <g> --direction postgres->mongo` (it deletes the Mongo copies of records deleted
in Postgres, see "Reconcile and deleted rows"). Then set `DB_WRITE_MODE__<g>=dual`, keep the read on Postgres,
and redeploy. Undo A afterwards if needed. Never move a group from `mongo` straight to `postgres`,
and never set `postgres` for a group at this stage.

A and B use only `dual` and `postgres_primary_dual`, so the cutover-order check at boot never
fires here; it matters at C. Stored definition: save it after every A and every B, so a routine
image deploy never reverts a group.

### Jobs flips (alongside A and B, done before D)

`jobs-worker` must run (at least one replica, the backend's flags). `DB_AUTO_MIGRATE` on the
backend creates procrastinate's `jobs` tables, or run `python -m backend.jobs.schema` once as a
one-off. Temporal and its worker stay in the stack: this cutover removes neither.

1. `JOBS_BACKEND__delete_response=postgres` on `backend` + `jobs-worker`. Deploy, then run
   `migrate jobs-sweep --backend postgres` as a one-off in a backend task.
2. `JOBS_BACKEND__delete_user=postgres` on `backend` + `jobs-worker`. Deploy.
3. `run_action`: add a second actions-executor service. Copy the existing one's definition and
   add `JOBS_BACKEND=postgres` and
   `DATABASE_URL=postgresql://bc_jobs_exec:<password>@<postgres host>:5432/<database>` (the role
   that reaches the `jobs` schema only; `JOBS_CONCURRENCY` and `JOBS_POOL_MAX` as needed). Deploy
   it; it waits on an empty queue. Then set `JOBS_BACKEND__run_action=postgres` on `backend` +
   `jobs-worker` and deploy. When Temporal shows no running `run_action` workflow, scale the
   Temporal-mode executor to `replicas: 0`, and keep it in the definition for rollback.

Watch the queue: `SELECT queue_name, status, count(*) FROM jobs.procrastinate_jobs GROUP BY 1, 2`
(no growing `failed`), the `jobs-worker` and executor logs, and one real run of each kind (a
response expiring, an account deletion, an action on a test submission). Rollback for one kind:
`JOBS_BACKEND__<job>=temporal` on `backend` + `jobs-worker` and redeploy. For `delete_response`,
then run `jobs-sweep --backend temporal`. For `run_action`, scale the Temporal-mode executor back
up first. Leave the Postgres workers running until their queues are empty.

### C — stop writing Mongo

Start when every group, including `auth` and `google`, has passed B and its soak.

1. **Make Mongo a full copy; this is the soft point of no return.** For backend, auth and google:
   read the outbox (`status --json`), run `reconcile --direction postgres->mongo` (it also deletes
   the Mongo copies of records deleted in Postgres), then `verify` until clean; delete by hand only
   the records it reports as `tombstoned`. After C, Mongo falls behind.
2. **Edit the definition.** On `backend` + `jobs-worker`, `auth` and `integrations-googleform`:
   remove every `DB_READ_SOURCE__*` and `DB_WRITE_MODE__*` (a leftover override wins over the
   default), then set `DB_READ_SOURCE=postgres` and `DB_WRITE_MODE=postgres`, and set
   `DB_SHADOW_READ_SAMPLE=0` (a shadow read would now compare against a Mongo that nothing writes).
   On `task-runner`: `DB_WRITE_MODE=postgres`, and remove its `__responses` and `__google`.
3. **Deploy all backend groups together.** Because of the cutover-order rule, `backend` and
   `jobs-worker` take every group in one deploy. `auth` and `integrations-googleform` can go in the
   same deploy.

Watch: one `persistence flags` line per replica, `write_stores = postgres` on every live instance,
5xx and p95 against the baseline, and the jobs. Soak for 14 days.
Rollback during the soak: put `postgres_primary_dual` back for every group, keep shadow reads off,
and redeploy. Then, per service, run `reconcile --direction postgres->mongo`. Records deleted
during C are still in Mongo (`verify` → `missing_in_postgres`, `tombstoned`); the reconcile deletes
them there from the Postgres tombstones, so they never come back.
Stored definition: save it with C's values, and drop the per-group overrides there too.

### Backups and a restore test before D

After D, Postgres is the only copy.

- Confirm that base backups and WAL archiving (point-in-time recovery) cover the application
  database, are kept off the database host, and have a known retention. On a shared cluster, check
  that this database can be restored on its own.
- Restore it to a scratch instance at a chosen point in time. Check that every schema (`app`,
  `auth`, `google`, `jobs`, `admin`, `settings`, `tasks`) is at its expected Alembic revision and
  that row counts per table match the live database at that time (counts only). Record how long
  the restore took.
- Check the connection budget: for every service, replicas × (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`),
  plus the job pools (`JOBS_POOL_MAX`), the admin service and the task runner, must stay below the
  cluster's `max_connections`, with headroom for anything else on it. `DB_STATEMENT_TIMEOUT_MS`
  must be set.

### D — Mongo off

Before D: C has soaked for 14 days; the backups above are verified; a final `mongodump` is taken
(Mongo has not changed since C); and the images are a release whose notes say the services start
without Mongo when no group uses it. Older images still open Mongo at boot, so they keep
`MONGO_URI`.

1. Remove `MONGO_URI`, `MONGO_DB` and any other `MONGO_*` from `backend`, `jobs-worker`, `auth` and
   `integrations-googleform`. If the settings store holds `MONGO_URI`, clear it in the portal
   (Settings → `MONGO_URI`) as well, or the services keep reading it from the store. On
   `task-runner`, remove its `MONGO_URI`, `MONGO_DB` and `GOOGLE_MONGO_DB`. Deploy, and wait until
   every service is healthy and reporting.
2. Set `mongodb` (and `mongo-seed`, if present) to `deploy.replicas: 0` and deploy. Keep the volume,
   and keep it in the definition.

Watch: the services serve normally; Health shows every instance reporting, and
`settings.service_state` shows `write_stores = postgres` for each; `responses.check_undecryptable` (`stores: postgres`) finds 0; 5xx, p95 and the jobs at
baseline. Soak for 7 days.
Rollback: set `mongodb` back to `replicas: 1`, restore the `MONGO_*` variables (and the store
value) and redeploy. Mongo then holds the data as it was at C: to read or mirror from it again,
follow C's rollback.
Stored definition: save it with `replicas: 0` and without `MONGO_*`. A stale copy that still sets
`MONGO_URI` brings Mongo back into the services on the next deploy.

### Decommission (Postgres-only release stable for 30 days)

1. Take a final encrypted `mongodump`, store it off the host, and restore-test it (counts only).
   Delete the Typeform and Google credential databases before archiving, or keep that archive only
   briefly.
2. Remove `mongodb`, `mongo-seed` and every `MONGO_*` from the stored stack definition, and from the
   settings store if it holds any. Keep the volume until its retention ends. Deleting the volume
   is the hard point of no return.
3. The keyset freeze ends here. `keyset.drop_old` with `mongo_retired` is accepted once every live
   backend and Google instance reports `write_stores = postgres`. Don't drop a key that the retained
   Mongo archive still needs until that archive is deleted.
4. Delete the Typeform developer app, if you had one.
5. Drop the deletion tombstones: `DROP TABLE app.deletion_tombstones, auth.deletion_tombstones,
   google.deletion_tombstones` (in a later release's migration), and the Mongo collection goes with
   the Mongo data. They exist only so that reconcile can tell the two stores apart.

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
