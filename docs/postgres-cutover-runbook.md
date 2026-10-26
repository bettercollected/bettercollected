# MongoDB → PostgreSQL cutover runbook

Operator procedure for moving bettercollected's data from MongoDB (and its jobs from Temporal)
to the `app-postgres` PostgreSQL database, one repository group at a time, with rollback at every
step. Code conventions: `backend/AGENTS.md` "Persistence".

**What this page describes.** The dual-run machinery (`DB_READ_SOURCE`, `DB_WRITE_MODE`, shadow reads,
the mirror and its outbox, `/persistence/status` counters) is 4.0.x behaviour: 4.1 removed it, and its
services refuse any value of those flags other than `postgres`. The text about them stays because the
cutover is run on 4.0.x images, and because the file and line references in it are to `v4.0.13`. What
4.1 keeps of it is the import tooling (`python -m backend.migrate`, `auth.migrate`,
`googleform.migrate`) and the startup check for data that was never imported. A short, ordered
version of the whole upgrade is in [upgrade-4.1.md](upgrade-4.1.md).

Everything below is driven by environment variables read at boot — **a flip is a restart**, never
a code change — and by the migration CLI, which runs out of band as a one-off process.

**Two routes.** The phases below (1 to 3) and the Swarm stages are the *staged* route: group by
group on 4.0.x, with soaks, ending on Postgres with Mongo off before 4.1. A stack that already
mirrors everything on 4.0.x (`DB_WRITE_MODE=dual`, verified clean) can instead take the *straight*
route, where two flag rolls and the 4.1 deploy are the cutover, with no write outage and nothing
soaking: "Cutover at the 4.1 deploy", with its rollback, "Rolling back to 4.0.x after the 4.1
deploy", in the Swarm section. The read and
primary switches (A, B), C, D and every soak are superseded on the straight route; Phase 1 and
Stage 0 (mirror, backfill, verify) are its prerequisite.

## The moving parts

| piece | where | what it does |
|---|---|---|
| `DB_READ_SOURCE`, `DB_WRITE_MODE` (+ `__<group>` overrides) | each service's env | per repository group: `mongo` → `dual` (write both, read Mongo) → `postgres_primary_dual` (write both, read Postgres) → `postgres` |
| `JOBS_BACKEND` (+ `__delete_user`, `__delete_response`, `__run_action`, `__purge_provider_credentials`, `__revoke_google_grant`) | backend, actions-executor | `postgres` (procrastinate; the default from 4.1, `temporal` on 4.0.x) or `temporal` per job kind; `purge_provider_credentials` exists on `postgres` only (set it there, or account deletions that need a purge fail after the erasure and are retried: with `__delete_user=postgres` the integrity monitor reports them as overdue; on Temporal they show only in the Temporal UI and the backend's error log) |
| `DB_SHADOW_READ_SAMPLE` | each service | fraction of reads also issued to the other store and compared |
| `GET /persistence/status` (admin) | backend | flags in effect, routing counters, outbox backlog, Postgres reachability |
| `python -m backend.migrate …` (also `auth.migrate`, `googleform.migrate`) | one-off container, service role | `preflight` · `backfill` · `verify` · `reconcile` · `status [--json]` · `jobs-sweep`; `--group <g>` or `--collections a,b` limit a run |
| outbox `mirror_write_failures` | Mongo collection + Postgres table, per service | mirror writes that failed; drained by a full `reconcile` |
| `store_migration` | Postgres table, per service schema | the "migration verified" marker and per-group verify records, written only by a clean `verify` (see "Verified marker") |
| `jobs-worker` service, actions-executor on the Postgres queue (the default from 4.1; it then needs `DATABASE_URL`, the `bc_jobs_exec` role's URL, and exits at start naming it when empty, unless `JOBS_BACKEND=temporal`) | compose | consume the `default` and `actions` queues |
| `DB_AUTO_MIGRATE` (default `false`) | backend (+ jobs-worker), auth, google | `true`: each service runs `alembic upgrade head` for its own schema at startup (backend: plus procrastinate's `jobs` tables), under a per-schema Postgres advisory lock |

Groups (backend): `refdata`, `identity`, `forms`, `responses`, `actions`, `ai`, `analytics`.
Auth and google each have one group (`auth`, `google`). Which collections belong to which backend
group is declared in `backend/backend/db/groups.py` (`COLLECTION_GROUPS`); it matches the `group`
of the repository that serves each collection, so `--group g` on the migration CLI covers exactly
what `DB_READ_SOURCE__g` / `DB_WRITE_MODE__g` move. `--group` accepts several groups (repeated or
comma-separated); an unknown group stops the CLI with exit code 2 and the list of valid groups.
`--group` and `--collections` cannot be combined.

**Reference data on a new stack (4.1).** The `refdata` group (allowed origins, the Google Forms
provider, coupon codes, price suggestions, feedback) is served from Postgres only. A new stack gets
its allowed origins and the Google Forms provider from `python -m backend.seed_refdata`, which
`deploy.sh` runs once, after the migrations and the keys and before any service starts, with the
web app's public origins (`HTTP_SCHEME` + `DASHBOARD_DOMAIN` / `FORM_DOMAIN`). The `mongo-seed`
job no longer writes reference data to Mongo. An upgraded stack is never seeded: its reference data
is imported from Mongo (`--group refdata backfill`). On a stack without `deploy.sh` (Swarm), run
the command once on an empty store, in a one-off backend container, with your origins:
`python -m backend.seed_refdata --origin https://<dashboard host> --origin https://<forms host>`
(each table is seeded only while it is empty).

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

1. Deploy with all flags at their defaults (`mongo` / `temporal` on 4.0.x; from 4.1 `JOBS_BACKEND` defaults to `postgres`, see "Jobs" below). Behaviour is unchanged; the only
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
   copied back from the other. The whole step, copies included, is capped at twice the mirror
   timeout, so a hung store can't hold a request longer; a copy cut off by the cap is still
   re-checked. When a copy was made but its re-check failed (or it was cut off), the outbox entry
   reads `CopyUnverified: …`. `reconcile` leaves such entries open; only a clean full `verify`
   (one that writes the marker) resolves them.
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
   authoritative) and, when run over every collection, marks the Mongo-side outbox resolved (the
   Postgres-side one only by `--direction postgres->mongo` or a clean full `verify`). Run `verify`
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
   expired copy as absent: verify never reports one and reconcile never copies one.
   A row the application wrote to Postgres after Mongo's copy is kept and counted as
   `newer_in_postgres`; with `reconcile --mongo-wins`, Mongo's copy replaces it in the groups
   whose `DB_WRITE_MODE`/`DB_WRITE_MODE__g` is explicitly `mongo` or `dual` (never by default).
   While the Postgres-side outbox has unresolved entries, no row the application wrote is replaced
   at all, with or without `--mongo-wins`.
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
3. Roll back: `DB_READ_SOURCE__g=mongo`, `DB_WRITE_MODE__g=dual`. One restart. First, while `g`
   is still on `postgres_primary_dual`, run `reconcile --group g --direction postgres->mongo` if
   the Postgres-side outbox (`status`) has open entries: after the flip it is refused, and a
   Postgres write whose Mongo mirror failed would be the only copy. A `--group` run does not
   resolve the entries, and until they are resolved `reconcile` replaces no application-written
   row of this service in any group. Resolve them with a full `reconcile --direction
   postgres->mongo` (when every group is on `postgres_primary_dual`) or, after the flip, with a
   clean full `verify` (it resolves the entries recorded before it started).
   **Stuck case:** after such a rollback, a write that went to Mongo first but whose Postgres mirror
   failed leaves an older application row in Postgres. Every `mongo->postgres` run keeps that row
   while the Postgres-side outbox is open, so `verify` never gets clean and the entries never
   resolve. You can tell because `newer_in_postgres` keeps growing and `verify` keeps reporting
   mismatches in that group. The way out is `resolve-outbox`, run with the services' flags after
   the `--group` copy above:
   1. Run `reconcile` (`mongo->postgres`) once: it copies the records Mongo has and Postgres
      lacks, and deletes copies of deleted records, so they do not hold the entries back.
   2. `python -m backend.migrate --group g resolve-outbox` (a dry run; auth and google the same
      way, without `--group`). For each open Postgres-side entry of `g` it compares, in both
      stores, the rows the entry names (the ObjectIds among its recorded arguments) and every row
      of the group. By default an entry is resolvable only on proof that Mongo holds what
      Postgres holds: the same checksum, a row copied from Mongo, no live copy on either side,
      or a Postgres row deleted since (a newer tombstone) with no Mongo copy. Timestamps never
      prove anything. It prints counts only: `resolvable`, and `kept` by reason
      (`missing_in_mongo`, `missing_in_postgres`, `older_in_mongo`, `superseded`,
      `delete_pending`, `expired_one_side`, `group_differs` when a row the entry does not name
      is not proven, `unknown_repository`). It exits 1 while any entry is kept.
   3. Rerun it with `--apply`: it resolves the resolvable entries and keeps the rest (it never
      resolves an entry recorded after it read them). To see which rows keep an entry, add
      `--ids-file <new local path>`: the file gets the entry and row ids with each reason (mode
      0600, never overwritten). Do not mail or paste it. Never resolve a kept entry by hand.
   4. `superseded` means Mongo's copy differs and has a later `updated_at` (not older than the
      entry). That is the stuck case itself, but it is no proof: a Mongo save built from a copy
      that never got the Postgres write stamps a later time too. Check those rows in both stores
      (`--ids-file`). Add `--accept-superseded` **only after confirming the newer Mongo version
      should win: the Postgres changes of these entries will be discarded by reconcile.** If a
      Postgres change must survive, copy it into Mongo by hand first, then rerun.
   5. Run `reconcile` (`mongo->postgres`), then `verify`. With the entries resolved, Mongo's
      copies replace the older rows, and `verify` comes back clean.

   From 4.1, the open entries of the groups served from Postgres only (refdata, analytics, ai,
   actions, identity) are counted apart as `postgres_only_leftover`: they record mirror writes
   to a Mongo those groups no longer read or write, so there is nothing to prove, and they do not
   change the exit code. They still make `reconcile` keep every application row, so clear them
   once with `resolve-outbox --apply --clear-postgres-only-leftovers` (only these entries; a dry
   run first shows the count).

Jobs: `JOBS_BACKEND__delete_response=postgres` first (scheduled deletions; run
`python -m backend.migrate jobs-sweep --backend postgres` afterwards so every pending
expiration has a job regardless of which engine scheduled it; on 4.0.x it reads the responses through
the routed repository, so from `DB_READ_SOURCE__responses`, and opens Mongo only while the `responses`
group still uses it; the 4.1 sweep reads Postgres only and says so, `"read_from": "postgres"`), then
`__delete_user`, then
`__run_action` with the actions-executor started with `JOBS_BACKEND=postgres`. Roll back a job
kind with `JOBS_BACKEND__<job>=temporal` and `jobs-sweep --backend temporal`.

**From 4.1 `JOBS_BACKEND` defaults to `postgres`**, and compose never sets it, so a stack that has
not set it (or `JOBS_BACKEND__<job>`) switches every job kind to the queue at the first 4.1
service, with no flip of its own. So before the 4.1 deploy: `jobs-worker` runs (its replicas are
not zero); the actions executor either has `DATABASE_URL` (the `bc_jobs_exec` URL) or
`JOBS_BACKEND=temporal`, set *before* its image is updated (CI updates it with the tag, and without
either it exits at start naming `DATABASE_URL`: its `run_action` jobs would have no consumer);
and at the upgrade, `python -m backend.migrate jobs-sweep --backend postgres` (a one-off in a
backend task) puts every scheduled response deletion on the queue. Keep the Temporal server and
worker until the schedules and workflows already in Temporal (`delete_response`, `delete_user`,
`run_action`) have run: the old schedules fire into the worker, which calls the backend's
`/temporal/*` routes. A response whose deletion cannot be queued is logged (id and error class) and
left to the next `jobs-sweep`; it no longer fails the submission. Roll a kind back with
`JOBS_BACKEND__<job>=temporal` and `jobs-sweep --backend temporal`, as above.

**On a compose stack, 4.1's `./deploy.sh` does all of this after the new release is up**
(`retire_temporal`), when the stack still runs Temporal: the sweep, then a bounded wait until
Temporal runs no workflow (`BC_TEMPORAL_DRAIN_SECONDS`, default 300; its schedules are not counted,
the sweep copied them onto the queue; they keep firing until the containers go), then the removal of the Temporal worker, Temporal and Temporal's database
containers, **keeping the volume** `<project>_temporal-postgres-data`. A failure, or workflows still
running after the wait, stops the deploy with the stack on 4.1 and the old containers untouched; run
`./deploy.sh` again later, or `BC_TEMPORAL_DRAIN=skip ./deploy.sh` to remove Temporal without waiting
(what is still running in it is lost). The 4.1 compose file has no Temporal, Temporal database or
worker service, and `./deploy.sh` refuses a `JOBS_BACKEND` or `JOBS_BACKEND__<job>` of `temporal` in
`.env.deployment`, before it starts or changes any container or data. The text of this section about keeping Temporal
running is for 4.0.x and for an orchestrated stack, which does these steps by hand.

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

`reconcile --direction postgres->mongo` runs only while every group it covers is on
`DB_WRITE_MODE=postgres_primary_dual`, so run it with the services' flags; the CLI refuses
otherwise (`--dry-run` excepted). Under `dual` Mongo deletes first and records no tombstone for a
document that isn't there, so a delete racing reconcile's Mongo insert could bring the record back.

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
expired Postgres tombstones as it records deletes (a bounded batch every 200 deletes, after
the delete committed and in a transaction of its own), and
`reconcile` prunes them at the end of each run. Drop the tables and the collection with the Mongo
decommission (below).

A *full* reconcile (no `--group` or `--collections`) then marks the unresolved entries of the
outbox it repairs resolved (`mongo->postgres` the Mongo-side one, `postgres->mongo` the
Postgres-side one); a partial reconcile leaves the outboxes alone (their entries name a repository and method,
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

## Accounts whose emails differ only in case

auth revision `0005` makes `auth.users` unique by `lower(email)` in place of the exact `email`
constraint: every sign-in path matches emails ignoring case, so `Jane@Example.com` and
`jane@example.com` are one account. Older versions matched the code sign-in exactly, so a store
can hold two accounts for one address. Then the migration refuses before changing anything,
naming only the counts (and the read-only query below), and auth does not start until they are
resolved; on the import from 4.0, `python -m auth.migrate preflight` counts them as duplicate keys
and `backfill` stops the `users` collection on the first one. Nothing is merged automatically:
each account has its own workspaces, forms, memberships, sessions and billing, and no rule can
pick one without taking from the other. List them by id (Postgres, or the same grouping in Mongo
before the import):

```sql
SELECT lower(email), count(*), array_agg(id ORDER BY id) AS ids
FROM auth.users WHERE email IS NOT NULL
GROUP BY lower(email) HAVING count(*) > 1;
```

```js
// mongosh, auth's 4.0 database
db.users.aggregate([{$match:{email:{$type:"string"}}},
  {$group:{_id:{$toLower:"$email"}, ids:{$push:"$_id"}}}, {$match:{"ids.1":{$exists:true}}}])
```

Run the query **before upgrading**, while the previous version still serves: the new auth does not
start on a schema behind its code. If the migration already refused, go back to the previous
image (the refusal changed nothing) and resolve them there. For each group, find out with the
person which account they use (in the backend: the workspaces each id owns or belongs to, its last
sign-in, a Stripe customer id). Move what they need to the account that stays (invite it to the
other account's workspaces, transfer ownership), then delete the other account through the
product's account deletion, so its sessions, memberships and billing go with it. Never delete a
row only in `auth.users`. Then upgrade again (or run `preflight` and `backfill` again).

4.0.11 and later also have an admin task for this, `auth.resolve_case_duplicate_accounts`
(docs/admin-service.md): run it on the previous version, before the upgrade or the import. It
drops by fixed rules only the accounts that have no forms (or, when none in a group has forms,
all but the one created last), and lists the groups where two or more accounts have forms for the
handling above. Review its dry run first.

## Google credentials without a user id (once, after upgrading)

The Google Forms integration encrypts a stored Google credential with a key derived from the
user's id. Legacy rows connected by older versions have no `user_id`; before this fix every token
refresh stored their access and refresh tokens unencrypted. The integration no longer writes a
credential it cannot encrypt, and reconnecting Google Forms gives such a row the signed-in user's
id. Delete the rows that are left: no `user_id`, or tokens stored in plain text. Their owners
connect Google Forms again on their next import; nothing else is lost (imported forms and
responses live in the backend). The step is safe to run again and prints counts only. Run it after
the import from 4.0 (`python -m googleform.migrate`), which copies whatever Mongo held.

A store still on 4.0, with the google group writing Mongo, runs the Mongo step below first, then
the Postgres one, so that neither store copies a row back to the other (a Mongo → Postgres
`backfill` of the google group copies whatever Mongo holds). From 4.1 the service no longer reads
Mongo, so the Mongo step does not apply there.

**Use the admin portal task `google.purge_unencrypted_credentials`** (Tasks page; from 4.0.10).
It applies exactly the filters below. On 4.0.x it runs Mongo first and then Postgres, and its dry
run (required first) shows the count per store. **From 4.1 it covers Postgres alone** and never
connects to Mongo: `stores: postgres` is the default (`auto` means the same), `mongo` and `both`
are refused (`store_retired`), and no `DB_WRITE_MODE*` is read. The apply needs the usual
confirmation code, deletes, and records the counts in the audit log. Counts only, never ids,
emails or tokens, and running it again deletes nothing.

Order: on 4.0.x, purge both stores before upgrading. On 4.1, finish the import from 4.0
(`python -m googleform.migrate backfill`, then `verify`) first and purge after it: the import
copies whatever Mongo holds, readable tokens included. On 4.1 the apply refuses
(`import_incomplete`) until the import is over: while the runner still has a Mongo connection
(`TASK_RUNNER_MONGO_URI`: remove it first, as step 7 of the cutover does), or while
`google.migration_progress` records the credentials' backfill as not `done` or with documents
skipped. It reads that record through the runner's data role, which the roles script grants
(`postgres/ensure-admin-roles.sh` of 4.1: re-run it, "Roles and grants"); without the grant the
apply refuses `import_state_unreadable`. A store with no record at all (the stack never had Mongo,
or its import never started) cannot be told apart: **confirm that the 4.0 import ran, or that the
stack never had Mongo, before the apply.** The task does not touch Mongo's own copy; no manual
step is needed while the import is not run again (purge Mongo's copy first, with the 4.0.x task, if
a rehearsal will run it again).

It needs:

- the function `google.purge_unencrypted_credentials` in Postgres, created by
  `postgres/ensure-admin-roles.sh` (run it once after upgrading to 4.0.10 or later; `deploy.sh`
  does). Until then the task refuses with `purge_function_missing`. The runner's
  `bc_tasks_data_google` role still has no DELETE: it may only execute that function;
- on 4.0.x only, the runner's Google Mongo connection while Mongo still holds credentials
  (`TASK_RUNNER_MONGO_URI`, `TASK_RUNNER_GOOGLE_MONGO_DB`), with a user that may delete from
  `Oauth2CredentialDocument` (`readWrite` on it, as for the keyset tasks).

The manual steps below remain as a fallback.

```bash
# Mongo (while the google group still writes it), against the service's MONGO_DB:
mongosh "<MONGO_URI>" --quiet --eval '
  const q = {$or: [{user_id: {$in: [null, ""]}},
                   {"credentials.token": {$exists: true}},
                   {"credentials.refresh_token": {$exists: true}}]};
  const c = db.getSiblingDB("<MONGO_DB>").getCollection("Oauth2CredentialDocument");
  print("to delete:", c.countDocuments(q));
  print("deleted:", c.deleteMany(q).deletedCount);'
```

```sql
-- Postgres, as the google service's role:
SELECT count(*) AS to_delete FROM google.oauth_credentials
WHERE coalesce(user_id, '') = ''
   OR (jsonb_typeof(doc->'credentials') = 'object' AND NOT doc->'credentials' ? '$binary');
DELETE FROM google.oauth_credentials
WHERE coalesce(user_id, '') = ''
   OR (jsonb_typeof(doc->'credentials') = 'object' AND NOT doc->'credentials' ? '$binary');
```

## Phase 3 — remove Mongo and Temporal

Only after two weeks fully on Postgres with everything at `postgres`/`postgres`:
`mongodump` archived and restore-tested; then the removal PRs (code, dependencies, compose,
env, docs). Keep the Mongo volume and dump for 30 days. Regression after removal: redeploy the
R2 images (they still know both stores) and `reconcile --direction postgres->mongo` to catch
Mongo up from the dump plus the outbox.

## Upgrading to 4.1 — the Postgres-only groups

From 4.1 the `refdata`, `analytics`, `ai`, `actions`, `identity`, `forms` and `responses` groups of the
backend, and the `auth` and `google` groups of the auth service and the Google Forms integration, are
served from Postgres only (`POSTGRES_ONLY_GROUPS` in
`backend/backend/db/groups.py` is the list in force): their Mongo collections are read by
nothing but the import, and a `DB_READ_SOURCE__<g>`/`DB_WRITE_MODE__<g>` other than `postgres` for
one of them refuses the start. A stack whose data for these groups is still only in Mongo must
import it, or it would run with no allowed origins, coupon codes, price suggestions, feedback, flow
events, AI memories and profiles, actions, workspaces, members, sessions, forms or templates.

**The start refuses until the import is done.** The backend API, its job worker and
`python -m backend.scim` check at startup, after the schema check
(`backend/backend/db/mongo_import_guard.py`), every collection of those groups
(`COLLECTION_GROUPS`); the auth service and the Google Forms integration do the same for their own
collections (`auth/auth/db/import_guard.py`, `integrations/google/googleform/db/import_guard.py`; the
shared core is `common/common/db/migrate/import_guard.py`). A start is refused when a collection has
documents in Mongo and its import is not finished, which means either of:
- a backfill of it is recorded in any state but `done` (interrupted, paused, running or failed),
  **whatever rows its Postgres table already holds**: a half-imported table does not pass for an
  imported one, and the log says `import unfinished: backfill <state>`;
- no backfill of it is recorded and its Postgres table has no row (rows with no recorded backfill are
  the application's own writes, not an import).

The log names each group and collection with its Mongo count, and the command to run
(`python -m backend.migrate --group <g> backfill`, `python -m auth.migrate --group auth backfill`,
`python -m googleform.migrate --group google backfill`). The check is a
`SELECT EXISTS` per table and one read of the backfill checkpoints; Mongo is asked (one `find_one`
per collection, plus an estimated count for the message, with bounded waits) only about the
collections that are empty in Postgres or whose backfill is not `done`. After a finished import an
empty table counts as the application's
doing (rows deleted or expired since), so the check never blocks a stack that imported. Without
`MONGO_URI` (a new 4.1 install) Mongo is never contacted. With `MONGO_URI` set, a Mongo that cannot
be read refuses the start too: the check cannot tell whether data would be lost. Remove
`MONGO_URI` only when Mongo holds nothing to keep (stage D below, or step 7 of "Cutover at the 4.1
deploy"). `python -m
backend.seed_refdata` runs the same check for `refdata` before it seeds the empty tables, since
seeded rows would hide unimported ones from the check.

**With `deploy.sh` (compose stacks).** `./deploy.sh` of 4.1 does the import itself, once, before
any service of the new release starts. A stack counts as one to import when it has the Mongo volume
of its compose project (`<project>_mongo-data`) or a `MONGO_URI` in `.env.deployment` (an external
Mongo), and the root `.env` has no `BC_LEGACY_MONGO_IMPORTED`. Then it:

1. stops the services that write Mongo (`backend`, `jobs-worker`, `auth`,
   `integrations-googleform`, `task-runner`): nothing may change Mongo between the copy and the
   check. The stack is down until the import is done;
2. starts `mongodb` under the `legacy-mongo` compose profile (with the volume only; the only way
   MongoDB starts in 4.1). A 4.0 stack's `MONGO_URI` (the one in its settings store or
   `.env.deployment`) is what the one-off containers read;
3. migrates the Google integration's schema when the stack does not run it (its Mongo data is
   imported all the same), then runs, in a one-off container of the new image, for **auth, google,
   then the backend**: `preflight`, `backfill` and `verify` (`python -m auth.migrate`,
   `python -m googleform.migrate`, `python -m backend.migrate`). The backend's `verify` skips the
   Postgres-only groups, whose `backfill` the startup check above verifies;
4. **stops on any failure** before a service starts: a preflight problem (invalid ids, duplicate
   unique keys), a backfill `error` or a verify difference prints the collections concerned with
   their counts (Mongo, Postgres, missing, mismatched, ...; never a value or a sample id). Nothing
   is deleted. The full output (counts and ids) is in `legacy-mongo-import.<time>.log` (mode 600).
   Fix the cause (Phase 1 above describes each check) and run `./deploy.sh` again: the backfill
   resumes and the checks run again. Or go back to 4.0: check out the 4.0 release and run its
   `./deploy.sh` (4.0 still reads Mongo, which was left as it was);
5. on success prints each service's counts per collection, clears `MONGO_URI` in the settings store
   (`deploy.sh settings-clear`: the store keeps its versions, so `settings-restore MONGO_URI
   --version N` brings it back for a rollback; once 4.1 has served traffic, what it wrote is in
   Postgres only and a 4.0 reading Mongo would not see it), blanks a `MONGO_URI` line in `.env.deployment`
   (backup `.env.deployment.pre-4.1.<time>`), records `BC_LEGACY_MONGO_IMPORTED=<time>` in the
   root `.env`, and stops and removes the `mongodb` container. **The `mongo-data` volume is kept**:
   keep it, and an encrypted `mongodump` of it, until 4.1 has run well for a while (the
   decommission step below); deleting it is the point of no return and never part of a deploy.

Before that import, and after the new services are up, the same `./deploy.sh` also does the 4.1
steps that are not about Mongo (each is one function in the script):
- **The respondent identity key** (`ensure_identity_key`, before the import or any service start). It
  uses a `RESPONDENT_IDENTITY_KEY` set in the root `.env` as it is (one only in
  `.env.deployment` is copied into `.env`, since compose does not pass that file's value to the
  backend). A key set only in the shell is used for that run and saved nowhere: put it in `.env`.
  With none anywhere, and a database that never had a key, it generates one into the
  settings store and into the root `.env`, printing that it did and never the value. It stops before
  any 4.1 service starts, writing no key (the stack stays on 4.0; the image pull, migrations,
  `ensure-admin-roles` and the key import have already run), when the database already has a key check and no key is
  configured, when `.env` and the store both hold a key and nothing says they are the same one
  (`BC_IDENTITY_KEY_SOURCE=env` says the `.env` one is intended), or when `SETTINGS_STORE=off` and the
  key is only in the store. Keep the key forever, with the other secrets: `.env` has a copy when
  `deploy.sh` generated the key; when it exists only in the store (a new stack's `bootstrap-keys`, or an
  unwritable `.env`), back up the settings store together with the master key.
- **The identity pass** (`identity_pass`), once the backend is up: `python -m backend.identity_rekey`
  in a one-off container, printing the key's fingerprint (write it down) and the remaining count; it
  retries while another process holds the lock, fails the deploy for a missing or wrong key (exit 3
  or 4) and only warns when values remain.
- **Temporal's retirement** (`retire_temporal`), described under "Jobs" above.

The check the operator does by hand after that is the same as on any route: submit an
anonymous response with your own account and confirm you can open it ([upgrade-4.1.md](upgrade-4.1.md),
section 4).

The next deploys find `BC_LEGACY_MONGO_IMPORTED` and never start MongoDB again. A stack that already
serves everything from Postgres (stages C and D below done on 4.0) sets
`BC_LEGACY_MONGO_IMPORTED=done` in the root `.env` by hand before the upgrade, so the import does
not compare Mongo with a Postgres that has moved on. A new 4.1 stack never starts MongoDB and stores
no `MONGO_URI`. `TASK_RUNNER_MONGO_URI` in the root `.env` is not touched: remove it once Mongo is
stopped (deploy.sh reminds you); on 4.1 the task runner never uses it, but `keyset.drop_old` and
the Google credentials purge refuse (`import_incomplete`) while it is set. The backend and the jobs worker default to
`DB_READ_SOURCE=postgres` and `DB_WRITE_MODE=postgres` in the compose file, the task runner to
`DB_WRITE_MODE=postgres`.

**What to run by hand** (an orchestrated stack, or ahead of the upgrade). Best before the upgrade,
with the 4.0 images (the CLI is the same):

```bash
python -m backend.migrate --group refdata,analytics,ai,actions,identity,forms,responses preflight
python -m backend.migrate --group refdata,analytics,ai,actions,identity,forms,responses backfill   # resumable; re-run until done
python -m backend.migrate status                                          # backfill=done per collection
# auth and the Google Forms integration, the same way
python -m auth.migrate preflight && python -m auth.migrate backfill && python -m auth.migrate status
python -m googleform.migrate preflight && python -m googleform.migrate backfill && python -m googleform.migrate status
```

After an upgrade that refused to start, run the same `backfill` in a one-off container of the 4.1
backend image (the CLI does not start the app, so the check does not stop it; see "One-off
commands" and "Quick reference"), then start the services again. A collection whose backfill
stopped with `error` (or documents whose `_id` is not an ObjectId, which `preflight` counts) keeps
the start refused until it is fixed and re-run.

`verify` and `reconcile` of the 4.1 backend no longer cover its groups (all of them are served from
Postgres only): without `--group` they skip them and say so on stderr; `--group refdata` (or
`--collections` naming one of their collections) exits with code 2 and names the group. The final
`verify` of the cutover is the one run on 4.0.x images, before the roll. Auth and the Google Forms
integration still verify and reconcile their own import. `reconcile --direction
postgres->mongo` checks each group's effective write mode (the backend's own flags), not the global
`DB_WRITE_MODE`.

**Override.** To start anyway and leave a group's Mongo data behind, set
`DB_DISCARD_UNIMPORTED_MONGO_DATA` to the groups to give up (`refdata,ai`; `auth`; `google`) or
`all`. It applies to the backend and jobs-worker (the backend's groups), the auth service (`auth`) and
the Google Forms integration (`google`). It can sit in one environment file the services share: each
service ignores the groups of the other services (an info line in the log), so only `all`, or a
name of its own, discards anything. A name that no service knows refuses the start; `all` stands
alone. Every start with it set logs a warning, and one per collection it lets through, with its
count. It is never set by default: use it only when that data is known to be worthless (a test
stack), and remove it after the start. The data stays in Mongo, so a later `backfill` can still bring
it in.

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

Two routes. **Straight to 4.1** ("Cutover at the 4.1 deploy", then "Rolling back to 4.0.x after the
4.1 deploy"): after a final clean `verify` and a fresh backup, two rolling flag updates
(`postgres_primary_dual`, then `postgres`, each followed by a check) and the 4.1 deploy are the
cutover; no write outage and no soaks. **Staged** (Stage 0 to Decommission, further down): for
operators who want to move group by group on 4.0.x first, with the soaks listed there. The two share
the ground rules, the one-off commands and what to watch.

The staged stages: **Stage 0** is Phase 1 plus a week of shadow reads. For each group, **A** (read
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
- **The task runner's `DB_WRITE_MODE` and `DB_WRITE_MODE__responses` follow the backend's
  values** and change in the same deploy, while the stack runs 4.0.x images. From 4.1 the runner
  reads no write mode: its tasks cover Postgres alone (`stores: postgres`, the default; `mongo`
  and `both` are refused with `store_retired`; docs/admin-service.md, "Task runner").
- **Migrations:** `DB_AUTO_MIGRATE=true` on `backend`, `jobs-worker`, `auth` and
  `integrations-googleform`, from Stage 0 on ("Who runs the migrations"). A release whose notes
  name a migration with non-transactional DDL is migrated by hand first (one-off commands below).
- **Let Swarm roll back a service that refuses to start.** A bad flag combination, a broken
  cutover-order rule or a schema behind the code stops the process at boot. With
  `update_config: {parallelism: 1, order: start-first, failure_action: rollback, monitor: 60s}`, the
  old tasks keep serving and Swarm puts the previous spec back. The stored definition still holds
  the rejected values: correct it before the next deploy.
- **Old and new flags run side by side while a service rolls.** Every transition below is safe in
  that window, for one of two reasons: every task keeps writing both stores (A, B, and roll 1 of the
  straight route), or every task already reads the store they all write (C, and roll 2). Don't run `backfill`, `verify` or
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
  From 4.1 `keyset.drop_old` also needs the signed `mongo_retired` statement and refuses
  (`import_incomplete`) while the runner has a Mongo connection or `migration_progress` records an
  unfinished backfill; see "Decommission".

### One-off commands

Run the migration CLI inside a running task of the service. That task has the service's role,
flags, settings and networks, and runs the same image tag. That tag matters: the verified marker
records the code version, and the CLI checks the schema head it knows.

```bash
docker service ps <stack>_backend --filter desired-state=running   # which node runs a task
# on that node:
C=$(docker ps -q -f name=<stack>_backend. | head -n1)
docker exec "$C" /api/backend/.venv/bin/python -m backend.migrate status
docker exec "$C" /api/backend/.venv/bin/python -m backend.migrate --group identity verify
docker exec "$C" /api/backend/.venv/bin/alembic -c /api/backend/alembic.ini current
# auth and the Google integration, the same way:
#   <stack>_auth                    /api/auth/.venv/bin/python -m auth.migrate …
#   <stack>_integrations-googleform /api/integrations/google/.venv/bin/python -m googleform.migrate …
```

When the stack runs the settings store (`SETTINGS_STORE=required`), the CLI needs the master key
as well. If it is a Swarm secret, export it inside the container before the command, and never
print it: `export SETTINGS_MASTER_KEY="$(cat /run/secrets/<the secret's name>)"`. Paste only the
counts a command prints.

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

### Cutover at the 4.1 deploy (straight from 4.0.x on `dual`)

For a stack that already writes both stores on 4.0.x (`DB_WRITE_MODE=dual`, Stage 0 done) the
cutover is three rolling updates in a row, with no write outage and no soaks:

1. the flags move from `dual` to `postgres_primary_dual` (Postgres becomes the store the services
   read and write first; Mongo stays a mirror);
2. then to `postgres` (Mongo stops being written);
3. then the 4.1 tag swaps the code (both releases read and write Postgres only).

Each is an ordinary rolling update of the stored definition, and nothing is scaled down on purpose
(one exception, the task runner, in step 5). The waits are the commands' own run times, a check after
each roll and, when a check finds something, a decision. Mongo is kept, volume and all, as the copy
as of the end of step 4.

**Why this order.** While a service rolls, old and new tasks run side by side. A task must never
save a document it read from a copy that another task has since replaced. Going straight from `dual`
to `postgres` would break that: an old task reads Mongo, which the new tasks no longer write, and
saves over newer Postgres data. The route goes through `postgres_primary_dual` so that every task,
old or new, keeps writing both stores:

| roll | old tasks | new tasks | a stale read is possible |
|---|---|---|---|
| step 3, `dual` → `postgres_primary_dual` | read Mongo; write Mongo, then copy to Postgres | read Postgres; write Postgres, then copy to Mongo | only for a record whose copy has not landed yet (the copy follows the write within the same request) or failed (the failure is recorded in the outbox, naming the record) |
| step 4, `postgres_primary_dual` → `postgres` | read Postgres; write Postgres, then copy to Mongo | read Postgres; write Postgres only | no: every task reads the one store they all write |
| step 5, 4.0.x → 4.1 | read and write Postgres only | read and write Postgres only | no |

What the code does in each, checked against `v4.0.13` (the modules it cites for the mirror and the
convergence check, `common/db/routing.py`, `convergence.py` and `mongo.py`, were removed in 4.1; they
and their line numbers are on `release/4.0`, and the text keeps its meaning for the 4.0.x tasks it is
about):

- **The flag combinations.** Reading Postgres is valid with `postgres_primary_dual` and with
  `postgres`; reading Mongo is valid with `dual` and `postgres_primary_dual`
  (`common/db/flags.py:51-58`). The cutover-order rule does not stand in the way: it only looks at a
  group that still reads Mongo (`flags.py:230-240`, skipped for a group read from Postgres at
  `:231-232`), and every group moves together. All of backend, `jobs-worker`, auth and the Google
  integration load the same flags (`backend/backend/app/container.py:211`, `auth/auth/app/container.py:37`,
  `integrations/google/googleform/app/containers/__init__.py:37`); `jobs-worker` is the backend's
  container. The task runner never loads them: on 4.0.x it reads its own `DB_WRITE_MODE*` only, to
  decide which stores a task covers (`postgres_primary_dual`: Postgres then Mongo; `postgres`:
  Postgres only); from 4.1 its tasks cover Postgres alone and read no write mode.
- **Writes and their copy.** A routed write goes to the primary store, then to the other one,
  bounded by `DB_MIRROR_TIMEOUT_MS` (2 s), and the copy can never fail the request
  (the 4.0 routing layer). Afterwards the copy of every row the
  write touched is compared with the primary's and rewritten where they differ, so two writes that
  reach the copy in the other order do not leave it with the older version (the 4.0 convergence check).
  A copy that failed is recorded in the *primary's* store (`common/db/runtime.py:148-187`): in a
  Mongo collection while Mongo is primary, in the service's `mirror_write_failures` table while
  Postgres is. In `status --json` these are `mirror_failures.mongo` (a Postgres copy under a Mongo
  primary failed) and `mirror_failures.postgres` (a Mongo copy under a Postgres primary failed).
- **What is not covered.** Two tasks writing the *same* record in the same few milliseconds, one
  from each side of the roll, end with the last write on both stores, as two replicas would
  anyway: one of the two writes is gone and nothing records it. The window is the length of one
  request, on one record, during the roll.
- **Startup.** Postgres being unreachable is fatal once any group reads or writes Postgres first
  (`flags.py:151-163`, `common/db/runtime.py:89-96`), which is the case from step 3 on. The schema
  check is the same as under `dual` (`common/db/schema_guard.py:435-445`). Nothing at startup looks
  at the verified marker (`migration_verified` is read only by `status`, `common/db/migrate/engine.py:1773`).
  Mongo stays connected while any group uses it and is not connected at all once every group is on
  `postgres` (the 4.0 flags and Mongo startup).
- **What to look at.** Each replica logs `persistence flags` once at start
  (`backend/backend/db/startup.py:42`, `auth/auth/app/asgi.py:64`,
  `integrations/google/googleform/app/asgi.py:58`) with `read_source` and `write_mode` per group.
  Health's `write_stores` reads `mongo,postgres` for both `dual` and `postgres_primary_dual` and
  `postgres` after step 4 (`common/settings/write_stores.py:12-17`), so Health tells step 4 apart
  but not step 3. Logs: `mirror write failed` is a failed copy; `mirror copy
  repaired` is a copy rewritten after two writes arrived out of order, a few of
  which are expected while old and new tasks overlap.

**Before you start**

- **Do not start until 4.0.14 is released** and the rollback section below has been re-checked
  against its code (the two things it adds, the job handlers and `release_pending`, are described
  there from their intent; the 4.0.14 changelog entry is the authority and wins over this text where
  they differ). Cutting over without a 4.0.14 to roll back to means the 4.0.13 caveats of the
  rollback apply.
- The stack runs 4.0.14 or later 4.0.x with Stage 0's values on `backend`, `jobs-worker`, `auth`,
  `integrations-googleform` and `task-runner` (`DB_WRITE_MODE=dual`, `DB_AUTO_MIGRATE=true`). 4.0.14
  is the rollback target below: it is the first 4.0.x that runs what 4.1 leaves queued and reads what
  4.1 writes. A stack on an earlier 4.0.x moves to 4.0.14 first, as an ordinary image update with
  the same flags, and is checked in Health, before anything below. (Before 4.0.13 a clean `verify`
  could not write the `backend` marker.)
- **Save the rollback definition:** a copy of the stored stack definition as it is deployed now (image
  tags, flags, `MONGO_*`, the task runner's `ADMIN_TASKS_BACKEND_URL`), outside the stack manager's
  history. "Rolling back to 4.0.x" below starts from it.
- The keyset freeze is in force (Ground rules): no `keyset.reencrypt`, no `keyset.drop_old`, until the
  rollback window below has closed. Start no other admin task that writes (the `responses.*` tasks
  that change data) from step 3 until step 6 is done.
- **Generate the respondent identity key now** and keep it with the stack's other secrets, never in
  a ticket, a chat or a database backup: `openssl rand -hex 32` (docs/respondent-identity.md, "The
  key"). It is used by the backend only, and the 4.1 backend refuses to start without it. Step 5 puts
  it into the stored definition before the tag; a different value later makes every stored anonymous
  identity unmatchable, so it is permanent.
- **Hold the Google settings.** From the first 4.1 service (step 5) until the rollback window has
  closed, change none of `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_AUTH_URI`,
  `GOOGLE_TOKEN_URI` and `GOOGLE_SHEET_REDIRECT_URL` in the admin portal (no set, restore or clear),
  and set none of the 4.1-only keys there either (`GOOGLE_FORMS_IMPORT`, `GOOGLE_SHEETS_OAUTH`).
  The reason is in the rollback's step 1 ("Settings"); if one was changed anyway, the remedy is
  there too. Settle any change to them before step 5 instead.
- **Gate:** the 4.1 section of `CHANGELOG.md` has its "Upgrade notes" and they match the stack
  changes in step 5 below. Also compare the compose file of the 4.1 tag with the one of the tag you
  run (`git diff <4.0 tag> <4.1 tag> -- docker-compose.deployment.yml`). A difference is a step this
  section is missing: do not start before it is settled.

**Steps**

1. **Final `verify` on 4.0.x**, per service, with the services running (one-off commands below).
   It must exit 0 on all three. Output is counts only; paste that, nothing else.

   ```bash
   docker exec "$C" /api/backend/.venv/bin/python -m backend.migrate verify
   docker exec "$C" /api/backend/.venv/bin/python -m backend.migrate status --json
   # auth: /api/auth/.venv/bin/python -m auth.migrate …
   # Google: /api/integrations/google/.venv/bin/python -m googleform.migrate …
   ```

   In each service's `status --json`: `marker` is not `null`; the backfill checkpoint of every
   collection is `done` (4.1's start check relies on it); `outbox` is 0 for both stores and
   `mirror_failures.<store>.unresolved` is 0. Anything else: Phase 1 step 5 (`reconcile`, then
   `verify` again) and do not go on until it is clean. Two more gates, so that nothing is found only
   after the tag:
   - the `workspace_forms` checkpoint in the backend's `status --json` is `done` with `skipped` 0
     (4.1's response tools refuse with `forms_import_incomplete` otherwise;
     `backend/backend/db/forms_import.py`);
   - `python -m auth.migrate preflight` reports no values that differ only in letter case (it logs
     the counts as a warning). auth revision 0005 refuses to migrate while any exist, and 4.1's
     `auth` would then not start: resolve them first ("Accounts whose emails differ only in case").
2. **Backups, before the first flag roll.** A fresh Postgres backup of the application database
   (every schema) from your backup tool, confirmed finished and listed; and
   `mongodump --archive --gzip` of every Mongo database (backend, auth, the Google integration),
   encrypted and kept off the host. The services keep writing while they run, so each is a restore
   point as of when it started; what was written after it is in the live stores (Mongo is a current
   copy until step 4 has finished). The restore test of "Backups and a restore test before D"
   applies here too: do it once before the cutover if it has never been done.
3. **Roll 1: Postgres primary, Mongo still mirrored** (`dual` → `postgres_primary_dual`). Step 1
   ran before the backups, with the writes continuing: repeat its `status --json` check
   (`outbox` 0 for both stores, `mirror_failures.<store>.unresolved` 0 on every service) right now,
   so that whatever is open after the roll is from the roll. Then edit the stored definition (image
   tags unchanged, no replica count changed) and deploy:

   | service | change |
   |---|---|
   | `backend`, `jobs-worker`, `auth`, `integrations-googleform` | `DB_READ_SOURCE=postgres`, `DB_WRITE_MODE=postgres_primary_dual`; remove every `DB_READ_SOURCE__*`, `DB_WRITE_MODE__*` and `DB_SHADOW_READ_SAMPLE`; `DB_AUTO_MIGRATE=true` stays |
   | `task-runner` | `DB_WRITE_MODE=postgres_primary_dual`; remove `DB_WRITE_MODE__RESPONSES` and `DB_WRITE_MODE__GOOGLE` |

   `backend` and `jobs-worker` go in the same deploy with identical flags (Ground rules). Let Swarm
   roll back a service that refuses to start (Ground rules): a replica that cannot start puts the
   `dual` spec back, and the stored definition then still holds the rejected values until you
   correct it. Wait until every replica of every service runs the new spec and logged
   `persistence flags` with `read_source: postgres` and `write_mode: postgres_primary_dual` for every
   group. Watch `mirror write failed` in the logs of the four services while it rolls.

   **What the roll cannot protect, said plainly.** The route is a choice not to stop the writers, and
   it has windows nothing detects:
   - An old task reads a record from Mongo in the moment before a new task's write to it has been
     copied to Mongo (the copy follows within the same request, bounded by `DB_MIRROR_TIMEOUT_MS`,
     2 s), and saves it. The old task's write wins on both stores. No outbox entry, no log line and
     no `verify` shows it.
   - A copy that failed (`mirror write failed`) leaves the other store stale until something
     rewrites it. If a task of the other generation reads that stale copy and saves it, that save
     wins on both stores, a later `verify` is clean, and a clean full `verify` marks every
     Postgres-side outbox entry recorded before it started (and the unverified Mongo-side ones) as resolved
     (`common/db/migrate/engine.py:1361-1377`). The lost write then leaves no trace except the
     entry, which is why the entries are listed *before* `verify` (below).
   - Two writes to one record at once, one from each generation, run their post-copy convergence in
     opposite directions (an old task treats Mongo as primary, a new one Postgres): each copies its
     primary over the other store and re-reads, up to three rounds.
     It ends with one value on both stores (the other write is lost, silently) or with `Diverged`,
     which is recorded in the primary's outbox: the
     Mongo side for an old task, the Postgres side for a new one, so "both above 0" below catches it.
   - A write that touched more than 500 rows (a bulk delete or update, `MAX_CONVERGED_IDS`;
     the log says `mirror convergence skipped`) is not
     converged and records no entry. Only the `verify` after the roll covers those rows.

   **Check, before anything else changes** (no service rolling, no one-off CLI running):
   1. **List first, then `verify`.** Per service, collect the `mirror write failed` lines of the
      roll's time (group, repository, method; they carry no ids) and the open outbox rows on both
      sides, the exception type only (the stored message can carry key values, such as the value
      of a duplicate key, `common/db/runtime.py:140-142`):

      ```sql
      -- Postgres side, as the service's role or a superuser; <schema> is app, auth or google
      SELECT table_name, op, row_id, split_part(error, ':', 1) AS error_type, created_at
      FROM <schema>.mirror_write_failures WHERE resolved_at IS NULL ORDER BY created_at;
      ```

      ```js
      // Mongo side, in the service's Mongo database; toArray() prints every document
      db.mirror_write_failures.aggregate([
        {$match: {resolved_at: null}},
        {$project: {_id: 0, table_name: 1, op: 1, row_id: 1, created_at: 1,
                    error_type: {$arrayElemAt: [{$split: ["$error", ":"]}, 0]}}},
        {$sort: {created_at: 1}}]).toArray()
      ```

      Cross-check the number of rows on each side against `status --json` (`outbox`). The `row_id` is
      best-effort and is **not only ids**: up to 20 values per row, any string argument of 64
      characters or fewer is kept as it was passed (a title, a key, a token), only an address is
      replaced by a hash (`email:…`), and a call that named none is `-` (`runtime.py:114-145`). A
      `-` or hashed row names only its repository (the class name in `table_name`, not a collection)
      and method, and cannot be looked up. Treat the list as sensitive: keep it only outside the
      stores, in an access-controlled place, and never paste it into a ticket, a chat or a log.
   2. **Look at each listed record** before `verify` resolves anything, without reading its
      contents: compare its `updated_at` in the two stores, and run `reconcile --dry-run` (both
      directions) and read `verify`'s counts and sampled ids for the collection. A record whose
      copies differ shows as `mismatched` or `missing_in_*` and holds a write the other store lacks.
      A record whose `updated_at` is later than the entry's `created_at` was saved again after the
      failed copy, possibly from the stale copy; what was written in between is not recoverable from
      the stores, and the step 2 backups predate it. A record whose `updated_at` did not move may
      still have been saved again, since not every write bumps it (for the form imports only the
      Mongo store does, `backend/backend/app/schemas/form_import.py:98`): the check can raise a
      doubt, not remove one. Decide each with the people who own the data. A `-` row, or a hashed one,
      cannot be looked up: treat the whole repository method as suspect and review that repository's
      recent changes with its owners.
   3. **Then, per service:** `verify` over every collection (no `--group`) exits 0, and `status
      --json` shows `outbox` 0 for both stores and `mirror_failures.mongo.unresolved` and
      `mirror_failures.postgres.unresolved` 0. Counts only. This shows that the two stores agree now,
      not that nothing was lost; the accepted residual risk is the list above.

   If it is not clean, do not go on, and do not run a `reconcile` blindly: its two directions decide
   differently which store wins. Every task is on `postgres_primary_dual` now, so Postgres is what
   users are served. Read `status --json` first, run each `reconcile` as a dry run (`--dry-run`),
   over every collection (no `--group`; only a full run drains an outbox), then for real, then
   `verify` again:
   - only `mirror_failures.postgres.unresolved` above 0 (a new task could not copy a write to Mongo;
     Postgres holds it), or `verify` differs with both outboxes at 0 (two tasks wrote one record at
     once): `reconcile --direction postgres->mongo`. It copies Postgres's version over Mongo's, which
     the CLI allows only while every group it covers is on `postgres_primary_dual`
     (`common/db/migrate/cli.py:315-350`).
   - only `mirror_failures.mongo.unresolved` above 0 (an old task could not copy a write to
     Postgres; Mongo holds a write Postgres lacks): plain `reconcile` (`mongo->postgres`) first, but
     **only if `verify`'s differences are limited to the ids of that Mongo-side outbox**: per
     collection, its `mismatched` and `missing_in_*` counts do not exceed the distinct ids listed for
     that collection's repository, and the sampled ids it prints (at most 5 per kind,
     `engine.py:716-740`) are among them. The outbox names a repository class, not a collection, and
     a `-` or hashed row maps to no collection at all: so **any `-` or hashed row, or any collection
     with differences but no listed ids, means stop and decide per record**, not plain `reconcile`.
     The reason: plain `reconcile` compares
     `updated_at` (copies Mongo's version where it is at least as new as Postgres's and keeps a row
     the application wrote to Postgres after it, counted as `newer_in_postgres`,
     `engine.py:1097-1121`), and not every Postgres write moves `updated_at` (for the form imports
     the Mongo store alone bumps it, `backend/backend/app/schemas/form_import.py:98`), so a newer
     Postgres row with an equal `updated_at` could be overwritten by an older Mongo copy. Do not run
     `postgres->mongo` first: it would write Postgres's older copy over the only copy of that write.
   - both above 0: stop and decide per record. While the Postgres-side outbox has an open entry,
     `mongo->postgres` replaces no row the application wrote (`engine.py:839-857`), and
     `postgres->mongo` replaces Mongo's copy whatever it holds (`engine.py:1140-1195`). The ids are
     in the listed rows (best-effort, as above), and the question per record is which of the two
     writes should stand.
   A clean full `verify` resolves every Postgres-side entry recorded before it started, and the
   unverified (`CopyUnverified:`) Mongo-side entries recorded before it started; a full `reconcile`
   of the matching direction resolves the other Mongo-side entries
   (`engine.py:1332-1346`, `:1361-1377`). Go on only with `verify` at exit 0 and both outboxes at 0,
   after the listed records have been looked at.
4. **Roll 2: Postgres only** (`postgres_primary_dual` → `postgres`), as a second rolling update:

   | service | change |
   |---|---|
   | `backend`, `jobs-worker`, `auth`, `integrations-googleform` | `DB_READ_SOURCE=postgres`, `DB_WRITE_MODE=postgres`; `DB_AUTO_MIGRATE=true` stays |
   | `task-runner` | `DB_WRITE_MODE=postgres` |

   There was no override or shadow flag left after step 3, so nothing else changes. Old tasks read
   Postgres just as the new ones do, so no task reads a stale copy; old tasks keep copying their
   writes to Mongo until Swarm replaces them and new ones do not. From the end of this roll Mongo is
   a copy as of that moment and falls behind: do not run `verify` or `reconcile` against it any
   more (it would report the difference, which is the point of the step). Keep `MONGO_*` where it is
   for now: the old tasks of this roll still write Mongo, 4.1's start check may still look at it,
   and the rollback needs it unchanged. On 4.0.x `postgres` for every group is the combination the
   CI suites of the backend, auth and the Google integration run, and those services start without
   Mongo being read. **Every replica must log `persistence flags` with `postgres` everywhere before
   you go on**, `settings.service_state.write_stores` must read `postgres` for every live instance
   (instances replaced by the roll age out after two minutes, "Watching a stage"), and
   `GET /api/v1/persistence/status` must show Mongo as not used: a `failure_action: rollback` in the
   next step would otherwise put a `postgres_primary_dual` spec back. Do not push the release tag
   before this step is done and checked.
5. **Deploy 4.1**, in this order. Every service keeps running and the update is rolling: from here
   both releases read and write only Postgres, so old and new tasks side by side are safe.
   1. **Roles and grants, before the tag.** Run `postgres/ensure-admin-roles.sh` of the 4.1 tag as the
      database superuser inside the `app-postgres` container, the way the stack ran it for earlier
      releases (`deploy.sh` does `docker compose exec -T app-postgres bash -s < postgres/ensure-admin-roles.sh`;
      on Swarm, `docker exec -i <app-postgres container> bash -s < postgres/ensure-admin-roles.sh`:
      `-i`, not `-t`). The script refuses to run unless the container's environment holds
      `BC_ADMIN_PASSWORD`, `BC_ADMIN_MIG_PASSWORD`, `BC_TASKS_PASSWORD`,
      `BC_TASKS_DATA_APP_PASSWORD` and `BC_TASKS_DATA_GOOGLE_PASSWORD` (letters, digits and
      `. _ ~ -` only): the Swarm `app-postgres` service must carry all five, as it does when the
      stack has run the script before (since 4.0.10). Check that they are set; never print their
      values. The script is idempotent. 4.1 adds `admin.credential_purges_overdue()`, a column
      `SELECT` on `jobs.procrastinate_*` for `bc_count_app`, and a `SELECT` on
      `app.migration_progress` for the task runner's data role; without them Health's integrity
      monitor and the response tools' `forms_import_incomplete` check fail. It also grants
      `bc_tasks_data_google` a column `SELECT` on `google.migration_progress` (once the Google
      schema has it): without it `google.purge_unencrypted_credentials` and `keyset.drop_old`
      refuse `import_state_unreadable`. Run it again once the 4.1 services have migrated, as
      `deploy.sh` does.
   2. **Scale the task runner down, and give the backend its key.** Set `task-runner` to
      `replicas: 0` and add `RESPONDENT_IDENTITY_KEY` (the value generated under "Before you start")
      to the `backend` service, and set the actions executor's `DATABASE_URL` (the `bc_jobs_exec` URL) or
      `JOBS_BACKEND=temporal` on it (see "Jobs" in sub-step 3), in the stored definition, and deploy.
      **Both must be deployed
      before the tag is pushed in sub-step 4:** the tag updates the images with the environment of the
      last deploy, a 4.1 backend without the key refuses to start (Swarm then puts the old spec
      back), and an executor without either setting exits at start. 4.0.x ignores the variable, so
      this deploy changes nothing else. Only `backend`
      reads it: not `jobs-worker`, `auth`, `integrations-googleform` or the task runner. Put it in the
      environment, not the settings store: the portal and `settings-set` handle tiers T1 to T3, and
      this key is T4. The task runner is the only service scaled down, and only until sub-step 5: a 4.1 backend answers
      the admin-task routes on its internal listener only, while the runner points at port 8000 until
      then. Start no admin task meanwhile. The Temporal worker and the actions executor stay up: until
      sub-step 6 the 4.1 backend takes their key-only routes on port 8000 from private addresses (the
      `direct` default), as the 4.0.x backend does. 4.0.x workers therefore call a 4.1 backend between
      the tag and sub-step 5: the route modules they call (`temporal_router.py`, `template_router.py`
      and `workspace_forms.py` under `backend/backend/app/controllers/`) are unchanged between
      `v4.0.13` and `develop` apart from one added signed-in-user route, so the call shapes are
      the same; what runs behind them is not
      compared here, and the first run of each kind (an action, a deletion) after the tag is the
      check.
   3. **Edit the stored definition for 4.1** (do not deploy it yet). It carries the 4.1 image
      tags (a definition still on the 4.0.x tags, deployed after the images were updated, would put
      every image back), the task runner's replicas restored, `integrations-typeform` at
      `replicas: 0` if the stack still has it (its own Mongo database; 4.1 removes the service; keep
      it in the saved rollback definition), and the 4.1 changes the upgrade notes (the gate above)
      must agree with:
      - **The internal listener** (docs/admin-service.md, "Internal routes"; never publish port
        8001): the task runner's `ADMIN_TASKS_BACKEND_URL` and the `SERVER_URL` of the Temporal
        worker and the actions executor (both call the API's key-only routes) point at
        `http://backend:8001/api/v1`. The backend's `API_INTERNAL_ROUTES=internal_port` follows in
        sub-step 6, not with this deploy. A Swarm stack must set it in the end: with the default
        `direct`, Swarm's ingress mesh lets outside callers reach the worker routes on port 8000,
        and only their key stops them. The admin-task routes exist on port 8001 only.
      - **Jobs** ("Jobs" in the phases above): `JOBS_BACKEND` is not set on `backend` and
        `jobs-worker`, so 4.1 runs every kind on the queue. Set the actions executor's
        `DATABASE_URL` (the `bc_jobs_exec` URL) or `JOBS_BACKEND=temporal` on it, before the
        tag updates its image (without either it exits at start): sub-step 2 deploys it, and the
        definition of this sub-step keeps it; `jobs-worker` keeps its replicas.
      - **The task runner's environment:** remove `MONGO_URI` (step 7 does it for good; until then
        `keyset.drop_old` and the Google credentials purge refuse `import_incomplete`). Its
        `MONGO_DB`, `GOOGLE_MONGO_DB` and `DB_WRITE_MODE*` are no longer read.
      - **The key:** `RESPONDENT_IDENTITY_KEY` on `backend`, as deployed in sub-step 2 (keep it in this
        definition: a stored definition without it, deployed later, stops the backend).
      - Whatever else the upgrade notes ([upgrade-4.1.md](upgrade-4.1.md)) name.
   4. **Push the release tag.** CI updates the images of every service in a rolling update: `backend`,
      `jobs-worker`, `task-runner`, `admin` and `document-sandbox` run the backend image. The 4.1
      `backend`, `jobs-worker`, `auth`, `integrations-googleform` and `admin` start now, still with
      step 4's environment. Wait until every service runs a 4.1 image and is healthy.
   5. **Deploy the stored definition of sub-step 3**, which brings the task runner back and points
      the runner and the workers at port 8001.
   6. **Then close port 8000 to the workers' routes:** add `API_INTERNAL_ROUTES=internal_port` to the
      `backend` definition and deploy again, once the workers and the runner call port 8001.

   `DB_AUTO_MIGRATE=true` migrates `auth` and `google` to revision 0005 on the first 4.1 start (each
   service logs `schema … migrated`; `auth` 0005 refuses, with counts, while two accounts differ only
   in the case of their email). A service that refuses to start rolls back by itself under the
   `update_config` of Ground rules.
   Then, as a one-off in a backend task, `python -m backend.migrate jobs-sweep --backend postgres`
   (every scheduled response deletion onto the queue); keep the Temporal server and worker until the
   schedules and workflows already in Temporal have run ("Jobs"). (This stack has no `deploy.sh`; a
   compose stack's `./deploy.sh` does the sweep and the Temporal removal itself.)

   **Respondent identity, once sub-step 4 has finished and no 4.0.x backend replica is left**
   (docs/respondent-identity.md, "The one-time conversion"). The 4.1 backend converts the stored
   anonymous identities itself, in the background after it has started, and again about five minutes
   later; a 4.0.x replica that was still running during the roll can have stored one more old value
   in between.
   - **Compare the fingerprint.** Every backend start and every pass logs `key fingerprint=<8 hex
     digits>`. Write it down at the first start; every replica must log the same one (a replica with
     another key does not start).
   - **Run the pass once by hand**, as a one-off in a backend task (the backend's environment, so
     with the key): `python -m backend.identity_rekey --expect-fingerprint <the digits>`. It must
     exit 0 with `remaining` 0 for both tables. Exit codes: 1 values remain or the run failed, 2
     another process holds the lock (run it again), 3 the key is missing or unusable, 4 the key is
     not the one that converted the stored identities. For a very large `form_responses` table, run
     it (`--dry-run` first) before sub-step 4 instead, so the API's own pass has nothing to do.
   - The anonymous-response check is part of step 6.
6. **Smoke test and Health.** Run the production smoke test (docs/smoke-test.md): its "standing
   responses export and decrypt" check is the canary for keys and codec. Portal → Health: every
   instance reporting, the `admin`, `app`, `auth` and `google` schemas current, no unresolved outbox
   row. `responses.check_undecryptable` (`stores: postgres`) finds 0. A sign-in, a submission and
   its read-back by hand. **Then submit an anonymous response with your own account and check that
   you can open it** (and, after asking for the deletion of a test response, that the request is in
   your list): that proves the key in use is the one the stored identities were converted with. While
   the backend does not trust its key those paths answer 503 and the log names the cause.
7. **Mongo off, volume kept.** In the stored definition set `mongodb` (and `mongo-seed`, if present)
   to `deploy.replicas: 0` and remove `MONGO_URI`, `MONGO_DB` and any other `MONGO_*` from
   `backend`, `jobs-worker`, `auth`, `integrations-googleform` and `task-runner` (`GOOGLE_MONGO_DB`
   as well). If the settings store holds `MONGO_URI`, clear it in the portal (Settings →
   `MONGO_URI`; the store keeps its versions). Deploy and wait until every service is healthy and
   reporting. Keep the volume and the encrypted dump: retention is in "Decommission".

Step 3 is where Postgres becomes primary, step 4 where Mongo stops being written, and step 5
swaps the code. To back out of step 3 or 4 before the tag, use the rollback of B in "Per group: A,
then B" (copy Postgres into Mongo with `reconcile --direction postgres->mongo` while still on
`postgres_primary_dual`, then set `dual`) and "Making Mongo a current copy again" below (after step
4, Mongo is behind and must be copied first). The rollback of 4.1 below undoes step 5 (the image
tags and the 4.1-only settings) and keeps step 4's flags.

### Rolling back to 4.0.x after the 4.1 deploy

Writes since the deploy exist only in Postgres, so a rollback keeps Postgres as the store and never
reads Mongo as it is. **The rollback target is 4.0.14 or later**, and production is on it before the
cutover ("Before you start" above): it is the first 4.0.x with handlers for the job kinds 4.1 can
leave queued and with `release_pending` in its SSO connection statuses, so it needs no manual
clearing for either. On 4.0.13 or earlier those two need the caveats marked below. What the code
allows, checked against `v4.0.13` and `develop` (the `file:line` references are to `v4.0.13`; for
the two things 4.0.14 adds, its changelog entry is the authority and wins over this text if the
details differ):

- **Schema.** 4.0.13 starts on a database migrated by 4.1. Its schema check refuses only a schema
  *behind* the code; one *ahead* (a revision the image does not know) logs a warning and starts
  (`common/db/schema_guard.py:215-222, 442-445`), and `DB_AUTO_MIGRATE` then applies nothing
  (`:350-351`). Against 4.0.13's heads (`app` 0021, `admin` 0018, `auth` 0004, `google` 0004), 4.1
  adds `auth` 0005 (unique `lower(email)` index in place of the exact constraint) and `google` 0005
  (the `purge_user_credentials` function). Both leave 4.0.13's tables and columns as they were.
  Never run `alembic downgrade` for a rollback: `auth` 0005's downgrade would fail on accounts that
  differ only in case, and nothing in 4.0.13 needs it. Effect of 0005 that remains: on 4.0.x a
  sign-in whose email differs only in case from an existing account's now fails instead of creating
  a second account. If 4.1 ships further migrations, this paragraph has to be redone before the tag.
- **Stored documents.** 4.1 writes the same `doc` bytes 4.0.13 reads
  (`common/records/codec.py:1-26`, pinned by the codec golden tests), and the stored document models
  are the same in both releases. Three things 4.1 can leave behind that 4.0.x may not know, all
  checked in step 1 below: SSO connections in the new `release_pending` status (4.0.13's status enum
  has no such value, so reading the row fails; 4.0.14 and later read it); queued jobs of kinds a
  4.0.13 worker has no task for (procrastinate marks them failed, with no retry; 4.0.14 and later
  have a handler for each); and settings rows written on 4.1 that 4.0.x refuses (a startup refusal
  for a secret; this one is the same in every 4.0.x). **Google Forms import after a rollback works
  as it always did on 4.0.x:** `GOOGLE_FORMS_IMPORT` is a 4.1 setting that 4.0.x does not have
  (nothing in `v4.0.13` reads it), so whatever it was set to, it is ignored, and imports and calls
  with a stored credential work again. Google Sheets actions reconnected on 4.1 under
  `GOOGLE_SHEETS_OAUTH=backend` (the `drive.file` scope, through the sign-in client) may hold
  credentials 4.0.13's Google service cannot use: reconnect them after the rollback if a sheet stops
  filling.
- **Mongo** was last written during step 4 of the cutover (the last roll in which a 4.0.x task copied
  writes to it). 4.0.x starts without it
  (the 4.0 Mongo startup; the CI suites of the backend, auth and the Google integration run this
  way), so the rollback does not need it at all.

- **Anonymous identities.** 4.1 stores the identity of an anonymous response as a keyed hash
  (`v2:` + HMAC-SHA256 under `RESPONDENT_IDENTITY_KEY`); 4.0.x compares the unsalted MD5 it stored
  before. While 4.0.x runs, respondents cannot find, view or ask to delete their own anonymous
  submissions (staff see every response as usual). Nothing is lost, and nothing is converted
  back: the next 4.1 start converts whatever 4.0.x stored meanwhile. Keep `RESPONDENT_IDENTITY_KEY`
  in the definition (4.0.x ignores it) and never change it: a different key makes every stored
  identity unmatchable (docs/respondent-identity.md).

**Rollback (images back; Postgres stays the only store).** No Mongo, no `reconcile`; nothing is
lost.

1. **Check what 4.1 wrote that 4.0.13 cannot use**, on the 4.1 stack, counts and key names only
   (read-only SQL as the admin service's role or a superuser):

   ```sql
   -- SSO connections 4.0.13 cannot read
   SELECT count(*) AS sso_release_pending FROM app.sso_connections WHERE status = 'release_pending';
   -- queued jobs of kinds a 4.0.13 worker does not know
   SELECT task_name, status, count(*) FROM jobs.procrastinate_jobs
   WHERE task_name IN ('purge_provider_credentials', 'revoke_google_grant',
                       'sso_release_retry', 'recheck_verified_domains')
     AND status IN ('todo', 'doing') GROUP BY 1, 2;
   -- settings 4.1 may have written in a form 4.0.13 refuses
   SELECT key, version, readers, updated_at FROM settings.entries
   WHERE key IN ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_AUTH_URI', 'GOOGLE_TOKEN_URI',
                 'GOOGLE_SHEET_REDIRECT_URL', 'GOOGLE_FORMS_IMPORT', 'GOOGLE_SHEETS_OAUTH',
                 'API_INTERNAL_PORT', 'API_INTERNAL_ROUTES', 'DB_DISCARD_UNIMPORTED_MONGO_DATA');
   ```

   - **SSO.** On 4.0.14 or later nothing needs clearing. 4.0.14 reads a `release_pending` connection
     and treats it like a disabled one: no sign-in through it, never the enforced connection, and the
     admin enable, disable, test and delete calls on it answer 404. The release logic itself is not
     in 4.0.x, so those rows stay as they are until 4.1 runs again, and the connection keeps the
     entity ID it holds. The count above is a confirmation, not a gate. On 4.0.13 or earlier,
     `sso_release_pending` above 0 blocks the rollback, since it cannot read those rows: run
     `python -m backend.sso release-pending` in a backend container (it deletes those connections in
     Polis, then their rows); recheck. Rows that stay (Polis unreachable, or SSO not configured: the
     command then reports `skipped`) need a manual decision by the operator before the rollback,
     because deleting them locally gives up the entity ID they hold.
   - **Jobs.** `purge_provider_credentials` and `revoke_google_grant` are real obligations (erasing a
     deleted account's stored provider credentials, revoking an old Google grant). On 4.0.14 or later
     the backend's `jobs-worker` has a handler for each of the four kinds, so nothing needs clearing:
     the two obligations rows 4.1 left really run (retried hourly, up to 48 attempts, as on 4.1), and
     `sso_release_retry` and `recheck_verified_domains` rows complete as no-ops (a rolled-back stack
     never schedules them again; verified domains are re-checked when 4.1 returns). Temporal has no
     workflow for any of these, and the scheduled one-shot rows of `delete_response` exist only in
     the Postgres queue, so **the rollback must keep `JOBS_BACKEND=postgres` and run the
     `jobs-worker` on the 4.0.14 image** (step 2). The query above is a confirmation. On 4.0.13 or
     earlier a worker fails every queued row of these kinds (`TaskNotFound`, no retry): let 4.1's
     `jobs-worker` finish the two obligations first when time allows (the query shows 0 for them);
     otherwise note how many were failed, and repeat them on 4.1 after the next roll-forward.
   - **Settings.** The cutover's rule is to leave these alone from the first 4.1 service until this
     window closes ("Hold the Google settings" in "Before you start"); this is what happens, and what
     to do, when it was not followed. 4.0.x refuses a settings row whose key it does not know (`UNKNOWN_KEY`) or whose
     readers are not a subset of its own (`SPEC_MISMATCH`: `common/settings/snapshot.py:170-186`).
     4.1 added `BACKEND` to the readers of `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
     `GOOGLE_AUTH_URI`, `GOOGLE_TOKEN_URI` and `GOOGLE_SHEET_REDIRECT_URL`, and the readers of a row
     are stamped from the running release's spec when the row is written
     (`backend/admin/services/settings_store.py:544`). So a set, restore or clear of one of those in
     the portal on 4.1 makes a row that 4.0.13 refuses, and that includes a restore: it stamps the
     4.1 readers again. A service on `SETTINGS_STORE=required` refuses to start when a refused row is
     a critical key (every secret, and every key of tier T3 or T4) with no value in its environment
     (`common/settings/loader/runtime.py:220-230`). All five keys are critical: `GOOGLE_CLIENT_SECRET`
     is a secret, and `GOOGLE_CLIENT_ID`, `GOOGLE_AUTH_URI`, `GOOGLE_TOKEN_URI` and
     `GOOGLE_SHEET_REDIRECT_URL` are tier T3 (`common/settings/inventory.py:118, 439-442, 465`). So a
     refused row of any of them stops `auth` and `integrations-googleform` at start
     (`GOOGLE_SHEET_REDIRECT_URL`: the Google integration only, the one that reads it in 4.0.13). Keys
     only 4.1 knows (`GOOGLE_FORMS_IMPORT`, `GOOGLE_SHEETS_OAUTH`, `API_INTERNAL_*`,
     `DB_DISCARD_UNIMPORTED_MONGO_DATA`) are refused and ignored, which is harmless. If any of the
     five widened keys has a version written since the cutover (`updated_at`, or the key's history in
     the portal), put it right **before the services of the rollback start**, either by setting the
     value in the rollback definition's environment (an environment value wins over the store
     and exempts the key from the startup check; for the secret the operator must have its value
     to hand, the portal never shows it), or by rolling back `admin` first and setting the
     key again in its portal (4.0.13's `admin` stamps the readers 4.0.13 accepts).
2. **Edit the rollback definition** (the copy saved before the cutover): image tags back to the
   4.0.14-or-later tag it holds (an older one brings back the 4.0.13 caveats of step 1) for every
   service the 4.1 deploy changed (the list is in `.github/workflows/deploy.yml`,
   including `webapp`); flags **as in step 4 of the cutover** (`postgres` everywhere, not the saved
   `dual`); the task runner's `ADMIN_TASKS_BACKEND_URL` and the `SERVER_URL` of the Temporal worker
   and the actions executor back to port 8000 (4.0.13's backend has no internal listener);
   `GOOGLE_FORMS_IMPORT` and `API_INTERNAL_ROUTES` removed; any settings fix of step 1;
   `JOBS_BACKEND=postgres` kept on `backend` and `jobs-worker` (no `JOBS_BACKEND__<job>` naming
   `temporal`), and `jobs-worker` kept at its replicas on the 4.0.14 image;
   `mongodb` stays at 0 replicas and `MONGO_*` stay out. `integrations-typeform`, which 4.1 removed,
   stays at 0 replicas: it reads its own Mongo database, so bring it back only together with
   Mongo (below); imported Typeform forms stay readable without it.

   **A compose stack** has no stored definition: check out the 4.0.14 (or later 4.0.x) tag and run its
   `./deploy.sh`, keeping the upgrade's settings where they differ (read from the 4.0.14 compose file,
   not from a rollback run of a real stack):
   - the 4.0.x compose file sets no `DB_READ_SOURCE` or `DB_WRITE_MODE` itself. Its backend, job
     worker, auth and Google Forms service read `.env.deployment`, so `DB_READ_SOURCE=postgres` and
     `DB_WRITE_MODE=postgres` go there; its task runner takes `DB_WRITE_MODE` from the root `.env` and
     refuses with `write_mode_unknown` without it, so set `DB_WRITE_MODE=postgres` there too;
   - 4.0.x defaults `JOBS_BACKEND` to `temporal`: set `JOBS_BACKEND=postgres` in `.env.deployment`, and
     keep the `jobs-worker`, as above;
   - 4.0.x's `./deploy.sh` starts MongoDB, Temporal, the Temporal worker and Temporal's database
     again (they are in its service list). Temporal comes back on the volume 4.1 kept
     (`temporal-postgres-data`); with the flags above no service reads or writes data in Mongo, but
     `mongod` and `mongo-seed` (which drops its seed account and creates missing collections) still
     open its volume. What Temporal's old schedules do when its worker returns, with the queue
     already holding the same work, has not been tried;
   - the root `.env` keeps `RESPONDENT_IDENTITY_KEY` and `BC_LEGACY_MONGO_IMPORTED` (4.0.x ignores
     both), and the `MONGO_URI` that 4.1 blanked stays blank (`.env.deployment.pre-4.1.<time>` holds the
     old value; do not restore it while the flags say `postgres`).
3. **Deploy it.** Both releases write Postgres only, so a rolling update is safe. Services log
   `schema 'auth' is ahead` and `schema 'google' is ahead` (expected, `schema_guard.py:215-222`).
4. **Check:** `persistence flags` shows `postgres` on every replica; Health shows every instance
   reporting and the outboxes empty; the smoke test passes; `responses.check_undecryptable`
   (`stores: postgres`) finds 0; a sign-in, a submission and its read-back by hand; a Google Forms
   import works as on any 4.0.x (the 4.1 `GOOGLE_FORMS_IMPORT` setting is ignored); no job of the
   four kinds above is `failed`. **Keep the `jobs-worker` until no row is `todo` or `doing` for the
   two obligation kinds** (read-only, task names and status counts only):

   ```sql
   SELECT task_name, status, count(*) FROM jobs.procrastinate_jobs
   WHERE task_name IN ('purge_provider_credentials', 'revoke_google_grant')
     AND status IN ('todo', 'doing') GROUP BY 1, 2;
   ```

   An empty result means both obligations are done; a row that keeps being retried is an erasure
   or a revocation that has not happened yet.
5. **Never start a service with `DB_READ_SOURCE=mongo` or any `dual`/`mongo` write mode against the
   old Mongo volume** until the next section is done: it would serve the data as of the cutover and
   mirror it over the newer Postgres rows. The keyset freeze continues.

Rolling forward again is an image update: the flags already suit 4.1.

**Making Mongo a current copy again** (only to go back to the staged path on `dual`, or to keep a
Mongo copy while you decide). It is available while the Postgres tombstones cover the time since the
cutover: they are kept 120 days (`common/db/tombstones.py:62`) and dropped by a later release's
migration ("Decommission", step 5). `reconcile --direction postgres->mongo` deletes a Mongo copy
only when a tombstone says the record was deleted; a Mongo-only row without one stays
(`missing_in_postgres`) and would come back under `dual`
(`common/db/migrate/engine.py:981-1024`). Past the retention, stay on the rollback above.

1. **Start Mongo, unread.** `mongodb` back to `replicas: 1` on the same volume, wait until healthy.
   Restore `MONGO_URI`, `MONGO_DB` (and `GOOGLE_MONGO_DB`) on `backend`, `jobs-worker`, `auth`,
   `integrations-googleform` and `task-runner` from the rollback definition, and the portal's
   `MONGO_URI` if you cleared it. The flags stay `postgres`, so nothing connects. Deploy.
2. **Postgres primary, Mongo mirrored.** `DB_READ_SOURCE=postgres` and
   `DB_WRITE_MODE=postgres_primary_dual` on `backend`, `jobs-worker`, `auth` and
   `integrations-googleform`; `DB_WRITE_MODE=postgres_primary_dual` on `task-runner`. Deploy. Every
   write now goes to Postgres first and is copied to Mongo; every read is Postgres, so the stale
   Mongo copy is never served, and a rolling update is safe: old and new tasks both read Postgres.
   (4.0.x accepts this combination: `common/db/flags.py:51-58`.)
3. **Copy Postgres into Mongo**, in each service's container, with the service's own flags (the CLI
   refuses unless every group it covers is on `postgres_primary_dual`, `cli.py:327-350`; there is no
   `--mongo-wins` in this direction, `cli.py:380-382`). Dry run first, then the real run over every
   collection (no `--group`; only a full run drains the Postgres-side outbox):

   ```bash
   … python -m backend.migrate reconcile --direction postgres->mongo --dry-run
   … python -m backend.migrate reconcile --direction postgres->mongo
   # auth.migrate and googleform.migrate the same way
   ```

   Read the counts per collection: `skipped` above 0 (the application changed the record meanwhile):
   run it again. `tombstoned` above 0 (copies of a deleted record on both sides): delete them by id
   after checking ("Reconcile and deleted rows"), then run it again. Outbox entries at 0 afterwards.
4. **`verify`** per service exits 0 and `status --json` shows the marker, 0 open outbox entries and
   0 unresolved `mirror_failures.postgres` (the copies to Mongo that failed under a Postgres primary). A replayed record may show as mismatched (see "Reconcile
   and deleted rows"): reconcile again, verify again.
5. **Stay or go back to `dual`.** On `postgres_primary_dual` Postgres is primary and Mongo a current
   copy: the usual rollback window, and a fine place to stay. To return to Mongo as primary, run the
   step 3 reconcile once more first (the CLI refuses after the flip) and confirm the Postgres-side
   outbox is 0, then set `DB_READ_SOURCE=mongo`, `DB_WRITE_MODE=dual` (no overrides) on the same
   services and deploy, as in Phase 2 step 3. Then `verify` again and watch
   `mirror_failures.mongo` (the copies to Postgres that fail under a Mongo primary) and the outbox.

Whatever you ran last is the new stored definition. To roll forward again after the plain rollback,
move the image tags to 4.1. After "Making Mongo a current copy again", nothing is stopped: from
`postgres_primary_dual` repeat step 4 of the cutover (a rolling update to `postgres`), then the
tags as in step 5, and take Mongo off as in step 7; from `dual`, repeat the cutover from step 1.

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

The `google` steps run on 4.0.x. From 4.1 on, `integrations-googleform` has no Mongo store: it
serves from Postgres only and refuses to start while `DB_READ_SOURCE`, `DB_WRITE_MODE` or their
`__google` overrides name anything but `postgres` (unset is fine). `googleform.migrate` still
reads the 4.0 Mongo data for the import. The same holds for `auth` and the `auth` service
(`DB_READ_SOURCE`, `DB_WRITE_MODE` and their `__auth` overrides; `auth.migrate` for the import).

**A, the read switch.** Add the read override and redeploy the service(s). Writes stay on `dual`,
so Mongo stays primary. Shadow reads stay on and now compare Postgres answers with Mongo's. Soak
at least 48 h, or 72 h for `identity`, `auth`, `forms` and `responses`. Before `auth`'s A, run a
full `auth.migrate reconcile` and a clean `auth.migrate verify`: before 4.0.2 some auth writes
skipped the mirror. Rollback: remove the override and redeploy.

**B, the primary switch.** Add the write override (and the `task-runner`'s for `responses` and
`google`), then redeploy. Postgres is now authoritative for the group, and the reverse mirror keeps
Mongo current: failures now land under `mirror_failures.postgres`. Soak at least 72 h. In `verify`, a
record replayed into Mongo can show as mismatched ("Reconcile and deleted rows"). Rollback: run
`reconcile --group <g> --direction postgres->mongo` (it deletes the Mongo copies of records deleted
in Postgres, see "Reconcile and deleted rows"). Then set `DB_WRITE_MODE__<g>=dual`, keep the read on Postgres,
and redeploy. Undo A afterwards if needed. Never move a group from `mongo` straight to `postgres`,
and never set `postgres` for a group at this stage.

A and B use only `dual` and `postgres_primary_dual`, so the cutover-order check at boot never
fires here; it matters at C. Stored definition: save it after every A and every B, so a routine
image deploy never reverts a group.

### Jobs flips (alongside A and B, done before D)

On 4.0.x the default is `temporal`, and these flips move one kind at a time. From 4.1 the default
is `postgres` ("Jobs" in the phases above): a stack that has not finished them switches the rest
at the 4.1 deploy.

`jobs-worker` must run (at least one replica, the backend's flags). `DB_AUTO_MIGRATE` on the
backend creates procrastinate's `jobs` tables, or run `python -m backend.jobs.schema` once as a
one-off. Temporal and its worker stay in the stack: this cutover removes neither. (Staged route, on
4.0.x. A compose stack's 4.1 `./deploy.sh` removes them after the roll, once what they hold has run;
see "Jobs" above.)

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

While the Mongo volume and the tombstones exist, Mongo can still be made a current copy again
("Rolling back to 4.0.x after the 4.1 deploy", "Making Mongo a current copy again"). Deleting the
volume, or the later migration that drops the tombstone tables (step 5), ends that; the plain
rollback of that section, which needs neither, stays.

1. Take a final encrypted `mongodump`, store it off the host, and restore-test it (counts only).
   Delete the Typeform and Google credential databases before archiving, or keep that archive only
   briefly.
2. Remove `mongodb`, `mongo-seed` and every `MONGO_*` from the stored stack definition, and from the
   settings store if it holds any. Keep the volume until its retention ends. Deleting the volume
   is the hard point of no return.
3. The keyset freeze ends here. On 4.1 `keyset.drop_old` scans Postgres alone and needs the signed
   `mongo_retired` statement (`store_retired` without it); it is accepted once every live backend
   and Google instance reports `write_stores = postgres`, the runner has no `MONGO_URI` (unset
   `TASK_RUNNER_MONGO_URI` first) and `migration_progress` of each schema records no unfinished
   backfill (`import_incomplete` otherwise; the roles script's grant on
   `google.migration_progress` must be in place, else `import_state_unreadable`). Confirm that the
   4.0 import ran, or that the stack never had Mongo: a missing record cannot say. Don't drop a key that the retained
   Mongo archive still needs until that archive is deleted.
4. Delete the Typeform developer app, if you had one.
5. Drop the deletion tombstones: `DROP TABLE app.deletion_tombstones, auth.deletion_tombstones,
   google.deletion_tombstones` (in a later release's migration), and the Mongo collection goes with
   the Mongo data. They exist only so that reconcile can tell the two stores apart.

## Quick reference

```bash
# what is in effect, reachability (admin cookie); 4.0.x also: flags, counters, outbox.
# 4.1: the jobs backends in use and whether Postgres answers
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
… --group refdata backfill | --group identity verify | --group identity,forms reconcile
# 4.1: verify/reconcile skip every Postgres-only group (--group naming one exits 2)
… --group forms resolve-outbox [--apply] [--accept-superseded] [--ids-file <new path>]   # Phase 2 "stuck case"
```

`status --json` prints one JSON document (`format: 1`): per collection its group, the counts in
Mongo and Postgres and the backfill checkpoint; per group the last clean verify; the outbox depth
per store; mirror failures per store (total, unresolved, unresolved per repository method); the
last clean verify of any kind; and the marker (`null` until one is written). Counts and names
only, never document contents. Plain `status` prints the same as a short summary.

Every command is idempotent and can be interrupted; a re-run continues where it stopped.
