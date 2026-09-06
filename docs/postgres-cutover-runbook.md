# MongoDB → PostgreSQL cutover runbook

Operator procedure for moving bettercollected's data from MongoDB (and its jobs from Temporal)
to the `app-postgres` PostgreSQL database, one repository group at a time, with rollback at every
step. Background and design decisions: `plans/postgres-consolidation.md` (private). Code
conventions: `backend/AGENTS.md` "Persistence".

Everything below is driven by environment variables read at boot — **a flip is a restart**, never
a code change — and by the migration CLI, which runs out of band as a one-off process.

## The moving parts

| piece | where | what it does |
|---|---|---|
| `DB_READ_SOURCE`, `DB_WRITE_MODE` (+ `__<group>` overrides) | each service's env | per repository group: `mongo` → `dual` (write both, read Mongo) → `postgres_primary_dual` (write both, read Postgres) → `postgres` |
| `JOBS_BACKEND` (+ `__delete_user`, `__delete_response`, `__run_action`) | backend, actions-executor | `temporal` (default) or `postgres` (procrastinate) per job kind |
| `DB_SHADOW_READ_SAMPLE` | each service | fraction of reads also issued to the other store and compared |
| `GET /persistence/status` (admin) | backend | flags in effect, routing counters, outbox backlog, Postgres reachability |
| `python -m backend.migrate …` (also `auth.migrate`, `googleform.migrate`) | one-off container, service role | `preflight` · `backfill` · `verify` · `reconcile` · `status` · `jobs-sweep` |
| outbox `mirror_write_failures` | Mongo collection + Postgres table, per service | mirror writes that failed; drained by `reconcile` |
| `jobs-worker` service, actions-executor with `JOBS_BACKEND=postgres` | compose | consume the `default` and `actions` queues |

Groups (backend): `refdata`, `identity`, `forms`, `responses`, `actions`, `ai`, `analytics`.
Auth and google each have one group (`auth`, `google`).

**Cutover-order rule, enforced at boot:** while a group still *reads* Mongo, the groups its Mongo
repositories join into must keep *writing* Mongo. In practice: never set `DB_WRITE_MODE=postgres`
for `forms` while `responses` reads Mongo, for `identity` while `forms` reads Mongo, or for
`actions` while `identity` reads Mongo. `postgres_primary_dual` is always allowed. A violation
fails the service at startup with the rule spelled out.

## R1 — release with everything still on Mongo

Prerequisites in the deployment (`deploy.sh` does these): the `app-postgres` service with the
five role passwords (`APP_POSTGRES_PASSWORD`, `BC_APP_PASSWORD`, `BC_AUTH_PASSWORD`,
`BC_GOOGLE_PASSWORD`, `BC_JOBS_EXEC_PASSWORD`), `DATABASE_URL` per service, `alembic upgrade head`
per service **as its own role**, and `python -m backend.jobs.schema`.

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
   documents with non-ObjectId ids or duplicate unique keys (e.g. two `workspace_forms` rows for
   one workspace+form); fix the data in Mongo first — backfill skips invalid ids and would fail on
   duplicates.
3. **Backfill:** `python -m backend.migrate backfill --max-minutes 30` as many times as needed;
   each run resumes from its checkpoint (`status` shows per-collection state, rows copied,
   last id, and `stalled: true` if a run died mid-way). Use `--collections a,b` to order work,
   `--dry-run` to rehearse. Backfill never overwrites a row the application dual-wrote.
4. **Verify:** `python -m backend.migrate verify` — exit 0 only when counts, per-row checksums and
   the sampled round-trip all agree. For very large collections use `--sample-every 10`.
5. **Reconcile:** `python -m backend.migrate reconcile` copies whatever verify found (Mongo
   authoritative) and marks both outboxes resolved. Run `verify` again.
6. **Shadow reads:** `DB_SHADOW_READ_SAMPLE=0.05` for a week. `metrics.<group>.shadow_diffs`
   must stay at zero; a diff names the repository and method, never the payload.

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
2. Soak 48–72 h: `mirror_failures` for `g` zero, error rate at baseline, `verify --collections`
   for the group's collections clean (Mongo is now the copy, and it should still match).
3. Roll back: `DB_READ_SOURCE__g=mongo`, `DB_WRITE_MODE__g=dual`. One restart.

Jobs: `JOBS_BACKEND__delete_response=postgres` first (scheduled deletions; run
`python -m backend.migrate jobs-sweep --backend postgres` afterwards so every pending
expiration has a job regardless of which engine scheduled it), then `__delete_user`, then
`__run_action` with the actions-executor started with `JOBS_BACKEND=postgres`. Roll back a job
kind with `JOBS_BACKEND__<job>=temporal` and `jobs-sweep --backend temporal`.

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

# migration CLI, one-off container with DATABASE_URL (service role) + MONGO_URI
docker compose -f docker-compose.deployment.yml run --rm --no-deps backend \
  /api/backend/.venv/bin/python -m backend.migrate status
… preflight | backfill --max-minutes 30 | verify | reconcile | jobs-sweep --backend postgres
```

Every command is idempotent and can be interrupted; a re-run continues where it stopped.
