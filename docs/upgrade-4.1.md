# Upgrading from 4.0.x to 4.1

For whoever runs a bettercollected stack on 4.0.x and moves it to 4.1: a self-hoster on the compose
stack (`deploy.sh`) or an operator of an orchestrated (Docker Swarm) stack. This page is the short
version, in the order you do things. The long version, with every check and its reasoning, is the
[cutover runbook](postgres-cutover-runbook.md); this page links to its sections instead of repeating
them. Where the two disagree, the runbook and the release's changelog entry win.

**What changes.** From 4.1 every service keeps its data in PostgreSQL only. MongoDB is no longer a
store: it is read once, to import what a 4.0 stack still holds there, and then switched off. Background
jobs run on the Postgres job queue by default. Anonymous responses are tied to their respondent with a
keyed hash, which needs a new secret. Typeform and the Brevo marketing tracker are gone.

**Two kinds of stack.**

| Your 4.0.x stack | Route |
|---|---|
| Compose stack from `deploy.sh`, data in MongoDB (the 4.0 default) | `./deploy.sh` of 4.1 imports the data itself: [3A](#3a-compose-stack-deploysh) |
| Orchestrated stack that already writes both stores (`DB_WRITE_MODE=dual`, mirror verified) | The runbook's cutover at the 4.1 deploy: [3B](#3b-orchestrated-stack-already-on-dual) |

A stack that already serves everything from Postgres with Mongo off (the staged route, stages C and D
of the runbook) skips the import; it still needs the new key (section 2) and the identity pass
(step 3.4).

## 1. Before you start

1. **Be on 4.0.14 or later.** It is the rollback target: the first 4.0.x that finishes the jobs 4.1
   leaves queued and reads the single sign-on rows 4.1 writes. A stack on an earlier 4.0.x moves to
   4.0.14 first, as an ordinary image update with the same settings, and is checked before anything
   else. See the runbook, ["Cutover at the 4.1 deploy"](postgres-cutover-runbook.md#cutover-at-the-41-deploy-straight-from-40x-on-dual),
   "Before you start".
2. **Full verification on 4.0.x** (orchestrated stack: every service, with the services running):
   `python -m backend.migrate verify`, `python -m auth.migrate verify` and
   `python -m googleform.migrate verify` exit 0, and `status --json` shows a marker, every backfill
   `done` and no open outbox entry. How to run them: ["One-off commands"](postgres-cutover-runbook.md#one-off-commands).
   On a compose stack that never mirrored, `./deploy.sh` runs this for you (3A).
3. **Backups, fresh, before anything changes.** A Postgres backup of the application database (every
   schema), confirmed finished, and a `mongodump --archive --gzip` of every Mongo database (backend,
   auth, the Google integration), **encrypted and kept off the host**. Keep both until 4.1 has run
   well; the retention rules are in ["Decommission"](postgres-cutover-runbook.md#decommission-postgres-only-release-stable-for-30-days).
4. **The Mongo to Postgres import is complete.** Per service, `python -m <service>.migrate status`
   (`backend.migrate`, `auth.migrate`, `googleform.migrate`) shows the backfill `done` for every
   collection. Why this matters:
   - **Every service that holds data refuses to start while the import is unfinished:** the backend
     API, its job worker and `python -m backend.scim` for the backend's groups, the auth service for
     its accounts and the Google Forms integration for its credentials and forms. A collection that
     has documents in Mongo stops the start when a backfill of it is recorded in any state but
     `done` (interrupted, paused, running, failed), **whatever rows Postgres already holds**, or when
     none is recorded and its Postgres table is empty. The log names the group, the collection, its
     count and the command to run (`python -m backend.migrate --group <g> backfill`,
     `python -m auth.migrate --group auth backfill`,
     `python -m googleform.migrate --group google backfill`). If `MONGO_URI` is set but Mongo cannot
     be read, the start is refused as well. Details:
     ["Upgrading to 4.1"](postgres-cutover-runbook.md#upgrading-to-41--the-postgres-only-groups).
   - `DB_DISCARD_UNIMPORTED_MONGO_DATA` starts a service anyway and leaves its Mongo data behind. It
     takes `all` or the groups to give up (the backend's groups, `auth`, `google`), and it can sit in
     one environment file the services share: each service ignores the other services' groups, so
     only `all` or a name of its own discards anything. It is for a test stack whose data is
     worthless. Never set it on a stack you care about, and remove it after the start.
   - Two more gates from the runbook: the `workspace_forms` backfill is `done` with `skipped` 0
     (otherwise the response tools refuse with `forms_import_incomplete`), and
     `python -m auth.migrate preflight` reports no accounts whose emails differ only in letter case
     (auth migration 0005 refuses to run while any exist; resolve them first:
     ["Accounts whose emails differ only in case"](postgres-cutover-runbook.md#accounts-whose-emails-differ-only-in-case)).
5. **Generate the respondent identity key now** (section 2) and put it where the backend will read it
   before the first 4.1 backend starts. The 4.1 backend refuses to start without it.
6. **Compare the compose file of your tag with the 4.1 tag** (`git diff <4.0 tag> <4.1 tag> --
   docker-compose.deployment.yml`), and read the "Upgrade notes" of the 4.1 section of
   [CHANGELOG.md](../CHANGELOG.md). A difference the notes do not explain is a step missing here.

## 2. New and changed settings

### New

| Setting | Where | What to do |
|---|---|---|
| `RESPONDENT_IDENTITY_KEY` | backend only (not the job worker, auth, the Google integration or the task runner) | **Required.** Generate it **once**, before you roll the backend to 4.1: `openssl rand -hex 32`. Compose: the root `.env`. Orchestrated: the backend's environment in the stack definition. Set it in the environment: it is a tier T4 secret, and the portal and `settings-set` handle tiers T1 to T3 only. A new compose stack gets one from `bootstrap-keys`; an upgrading stack does not, so set it yourself before the first 4.1 start. 4.0.x ignores it, so it is safe to add before the upgrade, and on an orchestrated stack it has to be deployed before the 4.1 tag is pushed. |

The key rules, in short (full text: [respondent-identity.md](respondent-identity.md)):

- **Keep it forever, with the other secrets.** The stored identities of anonymous responses are
  converted with it and cannot be converted back. A different key later makes every stored identity
  unmatchable: respondents could no longer find or delete their own anonymous submission.
- **Never in a database backup, a ticket, a chat or the repository.** Keep it with the stack's other
  secrets, outside the database, and restore it from there: a database restore does not bring it back.
- The backend checks the key at every start against a check value it stores in Postgres (not the
  key). A replica with a different key does not start. **At the first 4.1 start, write down the 8
  hexadecimal digits after `key fingerprint=` in the log.** You will compare them later.
- It must be at least 32 random bytes as hex or base64; a short, repeating or patterned value is
  refused at start.

### Changed defaults

| Setting | 4.0.x | 4.1 |
|---|---|---|
| `JOBS_BACKEND` (and `JOBS_BACKEND__<job>`) | `temporal` | **`postgres`**: account deletion, scheduled response deletion, action runs, form imports and the credential and grant erasure jobs run on the Postgres queue. The compose file never sets it, so a stack that did not set it switches at the first 4.1 service. The `jobs-worker` service must be running (at least one replica). `JOBS_BACKEND=temporal` (or per job) keeps a kind on Temporal. |
| actions executor `DATABASE_URL` (Swarm; the compose stack has no executor) | not needed | **Required while `JOBS_BACKEND` is `postgres`**: the URL of the `bc_jobs_exec` role. Without it (and without `JOBS_BACKEND=temporal`) the executor exits at start naming the setting. Set it **before** the 4.1 image reaches the executor. |
| `API_INTERNAL_PORT` | not present | The backend also listens on 8001 (never publish it). The admin-task routes answer there only. |
| `API_INTERNAL_ROUTES` | not present | `direct` by default: the Temporal worker's and the executor's key-only routes also answer on port 8000, from private addresses. **Set `internal_port` once the workers call port 8001**; on Swarm or any stack whose port 8000 is reachable from outside, this is required, not optional. See [admin-service.md](admin-service.md#internal-routes). |
| `SERVER_URL` (Temporal worker, executor), `ADMIN_TASKS_BACKEND_URL` (task runner) | the backend on port 8000 | `http://backend:8001/api/v1`. The compose stack does this itself. |
| `GOOGLE_FORMS_IMPORT` | not present | `on` (default: unchanged behaviour), `readonly` (imported forms and responses stay, no new import, re-sync or call to Google) or `off`. Set the same value on the backend and the Google Forms service. See [RUNNING_INTEGRATIONS.md](RUNNING_INTEGRATIONS.md). |
| `GOOGLE_SHEETS_OAUTH` | not present | `google_service` (default, unchanged) or `backend`. Leave it alone unless you have followed [RUNNING_INTEGRATIONS.md](RUNNING_INTEGRATIONS.md). |

### Retired settings

Remove them from the stack definition, `.env` and `.env.deployment`, and from the settings store.

| Setting | What happens if it is still set on 4.1 |
|---|---|
| `DB_READ_SOURCE`, `DB_WRITE_MODE` | Unset, empty or `postgres` is fine. Any other value (`mongo`, `dual`, `postgres_primary_dual`) **stops the start** and names the setting. Backend: only the per-group forms (`DB_READ_SOURCE__<group>`, `DB_WRITE_MODE__<group>`, for `refdata`, `analytics`, `ai`, `actions`, `identity`, `forms`, `responses`) are checked; the service-wide value means nothing to it and is ignored. Auth and the Google Forms integration check the service-wide value **and** their own `__auth` / `__google` override. The task runner reads no write mode any more. (`common/common/db/flags.py`, `refuse_stale_store_flags`.) |
| `DB_SHADOW_READ_SAMPLE`, `DB_MIRROR_TIMEOUT_MS` | Read by nothing; ignored. |
| `MONGO_URI`, `MONGO_DB`, `GOOGLE_MONGO_DB` | Read only by the import commands and by the startup checks of the backend, auth and the Google Forms integration (a `MONGO_URI` that is set and unreadable refuses the start). Remove them once Mongo is off (4.). On the task runner, `TASK_RUNNER_MONGO_URI` set makes `keyset.drop_old` and the Google credentials purge refuse (`import_incomplete`); unset it. |
| `BREVO_TRACKER_KEY`, `BREVO_TRACKER_API_URL`, `BREVO_CONTACTS_API_KEY` | Ignored, as are stored rows for them. |
| `TYPEFORM_*` | Ignored. The `integrations-typeform` service is gone: scale it to 0 and remove it from the definition (keep it in your saved 4.0.x definition, for a rollback). Forms already imported from Typeform stay readable. `./deploy.sh typeform` and `./deploy.sh both` are refused; use `./deploy.sh` or `./deploy.sh googleform`. |

### Other changes that may need an action

- **Mail images (self-hosting).** A workspace logo in the sign-in code mail shows only when its address
  starts with one of `MAIL_IMAGE_URL_PREFIXES` (auth; admin portal, mail section). The default is the
  hosted storage's `public/` prefix: a stack on other storage sets it to its own public storage prefix.
- **Mail sender.** Sign-in, invitation and submission-update mails come from the instance's name
  (`ORGANIZATION_NAME`) with fixed subjects; tell your users if they filter by workspace name.
- **Single sign-on.** Before enabling it on a hosted stack, filter Polis's internet egress as
  described in [sso.md](sso.md) ("Polis egress"). SSO stays off unless `SSO_ENABLED` is set.

## 3. Steps

### 3A. Compose stack (`deploy.sh`)

The stack is **down while the import runs**: plan a window sized to your data.

1. Sections 1 and 2 done. In particular: backups taken, and `RESPONDENT_IDENTITY_KEY` in the root `.env`.
2. Check out the 4.1 tag and run `./deploy.sh`. It stops the services that write Mongo, starts MongoDB
   (only for this, under the `legacy-mongo` compose profile), runs `preflight`, `backfill` and
   `verify` for auth, the Google integration and the backend, and **stops before any service of 4.1
   starts if a check fails**, printing counts only (the full output, ids included, is in
   `legacy-mongo-import.<time>.log`, mode 600). Fix the cause and run `./deploy.sh` again; the
   backfill resumes. On success it clears `MONGO_URI`, records `BC_LEGACY_MONGO_IMPORTED` in the root
   `.env`, stops and removes the `mongodb` container and **keeps the `mongo-data` volume**. Details:
   ["Upgrading to 4.1"](postgres-cutover-runbook.md#upgrading-to-41--the-postgres-only-groups).
3. `deploy.sh` runs `postgres/ensure-admin-roles.sh` itself. Nothing to do by hand.
4. Continue with 3C.

A stack that already serves everything from Postgres sets `BC_LEGACY_MONGO_IMPORTED=done` in the root
`.env` before the upgrade, so the import does not compare Mongo with a Postgres that has moved on.

### 3B. Orchestrated stack already on `dual`

Follow the runbook's [cutover at the 4.1 deploy](postgres-cutover-runbook.md#cutover-at-the-41-deploy-straight-from-40x-on-dual)
steps 1 to 7; do not improvise the order. In outline:

1. Final `verify` and its gates (section 1), then the backups.
2. Roll 1 (`postgres_primary_dual`), check, roll 2 (`postgres`), check: both on the 4.0.14 images.
3. **Before the tag** (the runbook's step 5, sub-step 2), deploy the stored definition with the new
   items that 4.1 needs at its first start: `RESPONDENT_IDENTITY_KEY` on `backend`, and the
   executor's `DATABASE_URL` or `JOBS_BACKEND=temporal`. 4.0.x ignores the key, so this deploy changes
   nothing yet. This has to come first: the tag updates the images with the environment of the last
   deploy, and a 4.1 backend without the key refuses to start (Swarm then rolls it back by itself).
4. Roles and grants (`postgres/ensure-admin-roles.sh` of the 4.1 tag, as the database superuser
   inside the Postgres container), the task runner to 0 replicas, the 4.1 definition (image tags,
   internal listener URLs, no `MONGO_URI` on the runner, `integrations-typeform` at 0), push the tag,
   deploy the definition, and finally `API_INTERNAL_ROUTES=internal_port`.
5. Continue with 3C.

### 3C. After the roll, both routes

1. **Check every service came up** on 4.1 and logged `schema … migrated` (or that your pre-deploy
   migrations ran): `app`, `admin`, `auth` and `google` at head. On `auth`, revision 0005 refuses with
   counts while case-duplicate accounts exist (section 1).
2. **Run `ensure-admin-roles` again** once the 4.1 services have migrated (compose: `deploy.sh` does
   this; orchestrated: the same command as before the tag). Without it, Health's integrity monitor and
   the response tools' `forms_import_incomplete` check fail, and so do the Google credential tasks.
   See the runbook, step 5, sub-step 1.
3. **Compare the key fingerprint.** The backend logs `key fingerprint=` at every start and every
   identity pass. It must equal the one you wrote down at the first 4.1 start, on every replica. A
   replica with another key does not start.
4. **Run the identity pass once more when no 4.0 backend replica is left.** The API converts the
   stored anonymous identities in the background after it starts, and again about five minutes
   later; a 4.0 replica still running during the roll can store one more old value in between. By
   hand, in a one-off container (or `exec` in a backend task) with the backend's environment:

   ```bash
   python -m backend.identity_rekey --expect-fingerprint <the 8 digits you wrote down>
   ```

   Done when it exits 0 and reports `remaining` 0 for both tables. The other exit codes: 1 values
   remain or the run failed, 2 another process holds the lock (try again), 3 the key is missing or
   unusable, 4 the key is not the one that converted the stored identities. For a very large
   `form_responses` table, run it with `--dry-run` and then for real *before* the roll instead.
5. **Queue sweep.** In a backend task or one-off container:

   ```bash
   python -m backend.migrate jobs-sweep --backend postgres
   ```

   It puts every scheduled response deletion on the Postgres queue (idempotent). `deploy.sh` does not
   run it.
6. **Temporal: drain, then remove.** Keep the Temporal server and its worker running until every
   workflow and schedule already in Temporal has run (response deletion, account deletion, action
   runs): the old schedules fire into the worker, which calls the backend. When the Temporal UI (or
   CLI) shows no running workflow and no remaining schedule of those kinds, stop the worker and then
   the Temporal server; keep their volume for a while. On the 4.1 backend only three things start
   Temporal work (account deletion, scheduled response deletion, action runs), and each is on the
   queue by default, so nothing new arrives once they have run. <!-- verify: the UI/CLI check is described, not scripted, and the compose file of 4.1 still ships the Temporal services (removing them from the file is a separate change) --> Until then do not remove them: the runbook, ["Jobs"](postgres-cutover-runbook.md#phase-2--serve-from-postgres-one-group-at-a-time),
   explains why.

## 4. After the upgrade

1. **Smoke checks, by hand** (the automated suite is described in [smoke-test.md](smoke-test.md)):
   sign in with an emailed code; create, publish and answer a form; read the response back; open a
   response you submitted earlier and confirm it decrypts. **Submit an anonymous response with your own
   account and confirm you can open it and, after asking for its deletion on a test response, see the
   request in your list.** That proves the key in use is the one the stored identities were converted
   with. While the backend does not trust its key, those paths answer 503 and the cause is in the log
   (with the short fingerprints).
2. **Health page** of the admin portal: every instance reporting, the `admin`, `app`, `auth` and
   `google` schemas current, no unresolved outbox row (rows a 4.0.x dual run left are cleared with
   `resolve-outbox --apply --clear-postgres-only-leftovers`, see the runbook), the job queue showing no failed job. On
   an orchestrated stack, also run the `responses.check_undecryptable` task (it must find 0).
3. **Mongo off, volume kept.** Scale `mongodb` (and `mongo-seed`, if present) to 0 and remove every
   `MONGO_*` variable from `backend`, `jobs-worker`, `auth`, `integrations-googleform` and
   `task-runner` (and `MONGO_URI` from the settings store). On compose, `deploy.sh` already did
   this and kept the volume. **Keep the volume and the encrypted dump** until 4.1 has run well;
   deleting the volume is the point of no return and is never part of an upgrade
   (["Decommission"](postgres-cutover-runbook.md#decommission-postgres-only-release-stable-for-30-days)).
4. Until then, change none of the Google client settings in the admin portal (see the rollback notes
   below): the rollback window is open.

## 5. Rolling back

Writes since the upgrade exist **only in Postgres**, so a rollback keeps Postgres as the store and
never reads the old Mongo as it is. Rolling back means putting the 4.0.14 images back, nothing more.
Never start a service with `DB_READ_SOURCE=mongo` or a `dual` write mode against the old Mongo volume:
it would serve the data as of the upgrade and copy it over newer Postgres rows. Never run
`alembic downgrade`.

The full procedure, with the checks to run first, is in
["Rolling back to 4.0.x after the 4.1 deploy"](postgres-cutover-runbook.md#rolling-back-to-40x-after-the-41-deploy).
In outline:

1. **Image tags back to 4.0.14 (or later 4.0.x)** for every service the upgrade changed, from the
   4.0.14 definition you saved before you started. Keep the settings of the upgrade where they
   differ from the saved definition:
   - `DB_READ_SOURCE=postgres` and `DB_WRITE_MODE=postgres` (not the old `dual`); on a compose stack
     put them in `.env.deployment` <!-- verify: 4.0.x compose reads .env.deployment for the services (env_file in the 4.0 compose file) and does not set these flags itself; the rollback of a compose stack is not described in the runbook, which is written for stored stack definitions -->;
   - **`JOBS_BACKEND=postgres` kept, and the `jobs-worker` kept on the 4.0.14 image.** 4.0.14 has
     a handler for each job kind 4.1 can leave queued. Temporal has no workflow for them. Keep the
     worker until no row is `todo` or `doing` for `purge_provider_credentials` and
     `revoke_google_grant` (query in the runbook);
   - the task runner's `ADMIN_TASKS_BACKEND_URL` and the workers' `SERVER_URL` back on port 8000;
     `GOOGLE_FORMS_IMPORT` and `API_INTERNAL_ROUTES` removed;
   - `mongodb` stays at 0 replicas and `MONGO_*` stay out. `integrations-typeform` stays at 0.
2. **What 4.1-only data does on 4.0.14:**
   - Queued erasure jobs (`purge_provider_credentials`, `revoke_google_grant`) **run for real**. The
     two periodic 4.1 jobs (`sso_release_retry`, `recheck_verified_domains`) complete without doing
     anything and are not scheduled again.
   - Single sign-on connections in `release_pending` status are **read as disabled**: no sign-in
     through them, never the enforced connection, and the admin calls on them answer 404. They stay
     as they are until 4.1 runs again.
   - **Google Forms import works as it always did on 4.0.x.** `GOOGLE_FORMS_IMPORT` does not exist
     there and is ignored, whatever it was. A Google Sheets action reconnected under
     `GOOGLE_SHEETS_OAUTH=backend` may hold credentials the 4.0 Google service cannot use:
     reconnect it if a sheet stops filling.
   - **Anonymous submissions:** 4.0 compares the old MD5 identity, so while 4.0 runs respondents
     cannot find or delete their own anonymous submissions. Nothing is lost; the next 4.1 start
     converts whatever 4.0 stored in the meantime. Keep the key.
   - **Accounts:** after auth revision 0005, a sign-in whose email differs only in case from an
     existing account fails on 4.0.x instead of creating a second account.
   - **Google client settings changed in the admin portal on 4.1** (a set, restore or clear of
     `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_AUTH_URI`, `GOOGLE_TOKEN_URI`,
     `GOOGLE_SHEET_REDIRECT_URL`) make a settings row 4.0.x refuses, and a refused row of those keys
     can stop `auth` and the Google service at start. The runbook's rollback, step 1 "Settings", has
     the query and the fix. Prefer not to change them during the window.
   - The schemas are ahead of the 4.0.14 code: the services log `schema '<name>' is ahead` and start,
     which is expected.
3. **Check:** `persistence flags` shows `postgres` on every replica, Health shows every instance
   reporting, the smoke checks pass, and no job of the four kinds above is `failed`.

**If you also need Mongo back as a current copy** (to return to the staged `dual` path, or to keep a
copy while you decide), that is the second half of the same runbook section, "Making Mongo a current
copy again": start `mongodb` on its volume, set `postgres_primary_dual`, then copy Postgres into Mongo
with `reconcile --direction postgres->mongo` in each service (dry run first), and `verify`. It works
only while the deletion tombstones cover the time since the upgrade (kept 120 days). Past that, stay
on the plain rollback. Rolling forward again afterwards is an image update.

## Where to read more

- [postgres-cutover-runbook.md](postgres-cutover-runbook.md): every step, check and rollback above, in full.
- [respondent-identity.md](respondent-identity.md): the keyed identity hash, the key rules, the one-time conversion.
- [admin-service.md](admin-service.md): the internal listener and the portal's Health page.
- [RUNNING_INTEGRATIONS.md](RUNNING_INTEGRATIONS.md): the Google Forms and Google Sheets switches.
- [smoke-test.md](smoke-test.md) and [../CHANGELOG.md](../CHANGELOG.md): what to check, and what changed.
