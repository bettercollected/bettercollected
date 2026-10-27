# backend/AGENTS.md

Scoped guidance for the **core API** service. Read the root [../AGENTS.md](../AGENTS.md) first.

## Role

The FastAPI hub that the webapp and other services talk to. Owns workspaces, forms, responses, responders,
consent, templates, media, billing glue, analytics, and the **provider plugin proxy**. Serves on **:8000** under
prefix `/api/v1`.

## Where things live (note the double nesting: `backend/backend/…`)

```
backend/
  pyproject.toml, run.sh, Makefile      # outer: tooling
  backend/
    app/
      controllers/    # class-based routes (classy-fastapi Routables) — one file per domain
      services/       # business logic (~40 services) — the fat layer, DI-injected
      repositories/   # data access (Postgres): the repositories in postgres/*.py
      schemas/        # stored document definitions (Record classes) == the collections 4.0 had in MongoDB
      models/         # DTOs (dtos/), dataclasses/, enum/, types/, filter_queries/
      handlers/       # startup wiring: logging
      middlewares/    # DynamicCORSMiddleware, timing
      schedulers/     # form_schedular.py: expired-response deletion, called by workers via /temporal
      jobs/           # procrastinate app, tasks, worker and schema entrypoints (JOBS_BACKEND=postgres)
      container.py    # dependency-injector AppContainer (wires repos -> services)
      router.py       # aggregates all routers into root_api_router
      asgi.py         # get_application() app factory
    config/           # settings: api, auth, database, temporal, aws, redis, apm, openai, umami
    cli/              # `backend serve` -> gunicorn+uvicorn (prod)
    tests/
```

## Request layering (follow this — don't shortcut it)

`Controller (HTTP shape) → Service (business logic) → Repository (Postgres access) → Record`

- New endpoint: add a method to the relevant Routable in `controllers/`, decorated appropriately; put logic in a
  `services/` class; do all data access through a `repositories/` class. Wire new services/repos in `container.py`.
- Never query the database directly from a controller.

## Authorization (workspace permissions)

Every workspace-scoped access decision goes through `services/authorization_service.py`
(docs/enterprise-access-model.md). Services name the permission an action needs —
`authorize(user, Permission.X, workspace_id, form_id=None)` raises 403 (then 404 when `form_id` is
not a form of that workspace), `has_permission(...)` returns a bool for "staff view or public view"
branches. Never compare `owner_id` or roles in a service, and never decide access from a
membership read directly: access goes through `AuthorizationService`.

- **Catalogue:** `models/enum/permission.py` (`workspace.manage`, `members.manage`, `form.edit`,
  `response.read`, ...). **Roles** (`models/enum/workspace_roles.py`, mapped in
  `ROLE_PERMISSIONS`, the doc's §2 table): every owner holds all, the billing owner (`owner_id`)
  and each member with role `OWNER` alike (`is_owner_membership`; an active membership either
  way); `ADMIN` all but `workspace.billing`; `EDITOR` forms and responses; `REVIEWER` read and
  annotate; `VIEWER` read; `PRIVACY_OFFICER` `form.read`, `privacy.manage`, `analytics.read`,
  `audit.read` and never `response.read/annotate/export`. Each role grants only its own set.
  `COLLABORATOR` is the stored spelling of `EDITOR` (never rewritten; write `stored_role(...)`, report
  `canonical_role(...)`); `roles: []` (legacy) is an Editor; an unknown role grants nothing.
  A disabled membership grants nothing; in a disabled workspace (billing owner downgraded) only
  owners keep `form.read`, `response.read/export/delete`, `privacy.manage` and `analytics.read`
  (a downgrade never disables an owner's membership).
- **Members:** `PATCH /workspaces/{id}/members/{user_id}` changes a role (`members.manage`; never
  one's own, never above the caller's own permissions, so only owners give `OWNER`; only owners
  change or remove an owner; never the billing owner's; a workspace always keeps an active owner);
  invitations carry a role; `POST .../members/{user_id}/make-billing-owner` (`workspace.billing`,
  any owner; `.../transfer-ownership` is its old name) moves `owner_id` to another active owner,
  refused for a default workspace or a paid one (billing hangs off the billing owner's account) —
  `services/workspace_members_service.py`, rules in docs/enterprise-access-model.md "Owners". A Privacy officer also deletes a response
  with a *pending* deletion request (`privacy.manage`) and never holds the answer permissions,
  whatever other role they have. MCP/API-key calls also require the key's creator to hold the
  scope's permission at call time (`services/api_access.py` `SCOPE_PERMISSIONS`, shared
  by MCP and the public API).
- **Webapp:** `GET /workspaces/{id}/permissions` returns the caller's effective permissions; the UI
  gates controls with `useWorkspacePermissions().can(...)` (owners: `workspace.billing`).
- **Respondent paths** (a submitter's own submission, receipts, "my submissions", their deletion
  requests) authorise by the submitter's identity, not through permissions. Platform admin
  (`get_logged_admin`) is separate.
- **Tests:** a new workspace endpoint gets a row in `tests/app/controllers/test_permission_matrix.py`.

## Adding a route

Routers are registered in [backend/app/router.py](backend/app/router.py) via the `@router(...)` decorator
(classy-fastapi Routables) or `register_plugin_class` (the plugin proxy). Follow an existing controller
(e.g. `workspace_forms.py`) as a template — constructor injection, `self.router` methods, camelCase response models.

## Persistence (PostgreSQL only since 4.1)

Application data lives in PostgreSQL (`app-postgres`, schema `app`); the MongoDB of 4.0 is read only by the import
(`python -m backend.migrate`), with pymongo. There is no Beanie, no routing between stores, no mirror and no shadow
read. Runbook of the move: `docs/postgres-cutover-runbook.md`. What that means when you touch data code:

- **Every group is served from Postgres only (4.1)** (`POSTGRES_ONLY_GROUPS` in `backend/db/groups.py`: `refdata`,
  `analytics`, `ai`, `actions`, `identity`, `forms` and `responses`): there is no Mongo repository and no routing. The
  documents are `common.records.Record` classes, the repositories the `app/repositories/postgres/*.py` classes on
  `RecordRepository` (the container hands them out directly), and a `DB_*__<group>` flag other than `postgres`
  refuses the start (`load_backend_flags`; the store settings of the cutover are read for that refusal alone, the
  service-wide `DB_READ_SOURCE` / `DB_WRITE_MODE` mean nothing to the backend). No query joins across groups: the workspace repository reads a
  workspace's copy of an action through the actions repository, the template repository reads the title of the
  workspace a template was imported from through the workspace repository (`with_origin_titles` in
  `postgres/forms.py`), and the responses repository reads a form's title and importer through the forms
  repositories (`form_titles` / `form_importers` in `app/repositories/response_scope.py`). A fresh store gets its
  reference data from `python -m backend.seed_refdata`. What remains of the 4.0 dual run is the import tooling
  (`common/db/migrate/`: backfill, verify, reconcile, `resolve-outbox`, tombstones, the verified marker), with its tests
  (`tests/app/migrate/routed.py` keeps a test-only migrating group, `responses`, so verify and reconcile stay covered;
  the 4.0 Beanie classes it plants in a real Mongo are frozen in `tests/app/db/beanie_originals.py`, Beanie being a
  test-only dependency).
  Startup (API, job worker, `backend.scim`) and `seed_refdata` refuse while one of their collections has Mongo documents,
  an empty table and no finished backfill (`backend/db/mongo_import_guard.py`, a wrapper of the shared core `common/db/migrate/import_guard.py`, which auth and the
  Google integration use too; fix: `python -m backend.migrate --group
  <g> backfill`; override `DB_DISCARD_UNIMPORTED_MONGO_DATA`); a set but unreachable `MONGO_URI` refuses too, so
  Mongo-less tests run with `MONGO_URI=""`. `verify`/`reconcile` skip these groups by default and exit 2 when one is
  named (`Target.postgres_only_groups`).
- **Adding or changing a repository method:** implement it on the Postgres repository. A read-then-write that depends
  on what it read (merge into a stored answer set, close a deletion request, replace a group's members) runs in one
  transaction on the stored row, locked with `SELECT ... FOR UPDATE` (`_locked_doc`, the forms repository's
  `_locked_draft`) or, where no row exists yet, under a transaction-scoped advisory lock on the natural key
  (`_advisory_lock`): never write back a copy read earlier. Relation documents get `derived_id` so a repeated write
  addresses the same row. Timestamps come from `common.clock.utcnow()`; `record.touch()` where Mongo's `save()` moved
  `updated_at`. Responses stay encrypted at rest: the repository stores and returns the ciphertext (`answers`,
  `hidden_fields`, `internal_answers`, feedback) and never decrypts, logs or queries it, except `patch_form_response`,
  which merges into the decrypted answers inside its transaction and encrypts them again.
- **Joins:** SQL joins only within a group; a `$lookup` into another group's collection is *composed* through that
  group's repository (see `postgres/forms.py`, `response_scope.py`). Never query Mongo or Postgres from a service or controller.
- **No Beanie, no Mongo client in the application.** `common/tests/test_no_beanie_in_runtime.py` fails when a
  runtime module imports Beanie (or Motor, mongomock) or a service lists it among its runtime dependencies. The only
  Mongo access is the import's own pymongo client (`common/db/migrate/`, `backend/db/mongo_import_guard.py`).
- **Rows:** `backend/db/models.py` — one table per collection, typed spine columns `GENERATED` from the `doc` JSONB
  (query only spine columns; add one + an Alembic revision under `backend/migrations/` when a query needs a new
  field). Migrations run as the service role (`bc_app`), never as the superuser.
- **Mongo is not used:** the backend, its job worker, auth and the Google service never connect to it
  (`/persistence/status` reports `"mongo": {"used": false, "status": "not used"}`). The one exception is the startup check
  for unimported 4.0 data, which opens a client of its own while `MONGO_URI` is set. A test that drives Mongo itself (the
  import tooling) goes on `MONGO_DRIVEN` in `tests/conftest.py` (CI's Postgres shards run without Mongo; docs/ci.md);
  such a session also sets the frozen 4.0 Beanie classes up on the test Mongo (`mongo_database()`).
- **Schema check at startup** (`common/db/schema_guard.py`, wired in `backend/db/startup.py`; auth and google pass
  their own `MigrationTarget` in their `asgi.py`): the service refuses to start unless Postgres is configured and
  reachable and its schema is at the code's Alembic head (and, for the backend, procrastinate's `jobs` tables exist when
  a job kind is on Postgres). `deploy.sh` migrates explicitly; `DB_AUTO_MIGRATE=true` (default
  off) makes each service run `alembic upgrade head` in-process at startup instead, serialised across replicas by a
  per-schema Postgres advisory lock (a waiting replica gives up after `DB_AUTO_MIGRATE_LOCK_WAIT_SECONDS`, default
  300; the migration's own DDL waits at most 60s for a table lock). A new revision has to ship with the code that
  needs it. A database migrated *past* the image (a rollback) only logs a warning and starts, so **migrations must
  be expand-only**: never drop or rename what the previous release still uses in the same release that stops using
  it. They also run in one transaction, so no `CREATE INDEX CONCURRENTLY` / `autocommit_block` — ship that as a
  manual step. Tests: `common/tests/test_schema_guard.py`,
  `tests/app/db/test_auto_migrate.py` (real throw-away database initialised by `postgres/init`).
- **`backend/admin/`** is a separate, internal admin service's package: its own schema `admin` and Alembic chain
  (`backend/admin/alembic.ini`, revisions `0001_…`, run as the migration role `bc_admin_mig`, runtime role `bc_admin`
  via `ADMIN_DATABASE_URL`; roles created by `postgres/ensure-admin-roles.sh`), keys derived from
  `SETTINGS_MASTER_KEY`, and an append-only, HMAC-chained `audit_log` (`services/audit.py`; verify with
  `python -m backend.admin audit-verify`). It must never import `backend.app.router/container/controllers` or
  `common.services.crypto_service` (tests enforce it). New admin tables need explicit grants in their revision: there
  are deliberately no default privileges. Sessions, email-code sign-in, CSRF and gate levels 2-4 live in
  `services/sessions.py`, `services/signin.py`, `gate/checkers.py`, `gate/csrf.py` and `controllers/portal.py` (pages are
  Jinja2 templates with no inline script or style; details in `docs/admin-service.md`). The viewing pages (dashboard, health, configuration, metrics, audit log, sessions) are in `controllers/pages.py`, `services/pages.py` and `repositories/views.py`; they are GET-only at the second-factor level and never select secret values. The settings and task pages (which change state, behind a fresh code) and the setup wizard are described in `docs/admin-service.md`. Platform counts come from two definer functions, `admin.platform_counts_app()` and `admin.platform_counts_auth()` (created by `postgres/ensure-admin-roles.sh`, each owned by a NOLOGIN role of its own schema, `bc_count_app` / `bc_count_auth`, with column-level SELECT on that schema only; never a superuser, they call only `pg_catalog` functions, no definer function may read tables of more than one owning role; the admin roles cannot read `app`/`auth`; `repositories/views.py` combines the answers as data). The Health page reads the other schemas' Alembic revisions and mirror-outbox counts the same way (`admin.schema_revision_<schema>()`, `admin.outbox_counts_<schema>()`, owners `bc_count_app` / `bc_count_auth` / `bc_count_google`), against heads parsed from the revision files in the image (`schema_heads.py`; `backend/Dockerfile` copies the auth and Google ones). Admin writes are serialised by row locks (`admin.take_lock`, migration 0013), never advisory locks; the runner's audit rows go through `tasks.audit_append` / `settings.task_write_keyset` (migration 0015), the runner role has no access to `admin.audit_log`; settings history rows are never updated (re-wraps append to `settings.history_wraps`). Pages show a permanent reminder to back up `SETTINGS_MASTER_KEY`. Tests: `tests/admin/`.
- **The outbox of 4.0** (`mirror_write_failures`, a Postgres table per schema and the Mongo collection a 4.0 stack
  wrote) is read by `resolve-outbox` and drained by `reconcile` during the import; nothing writes it in 4.1. The
  effective flags (the jobs backends) are logged at boot and served on `GET /persistence/status` (admin).
- **Operator commands** that touch application data (`jobs-sweep`, `backend.custom_domain`,
  `backend.membership_duplicates`) go through the container's repositories, booted with `backend/cli_store.py`
  (`open_container`, Postgres only), never a raw Mongo collection. The admin tasks and the break-glass scripts cover
  Postgres alone (`plan_task_stores`, `admin/tasks/impl/responses_common.py`): `stores: mongo` and `both` refuse
  `store_retired` before anything connects, no write mode is read, and `keyset.drop_old` needs the signed
  `mongo_retired` param (`store_retired` without it) and a finished 4.0 import (`import_incomplete`:
  `MONGO_URI` set on the runner, or an unfinished backfill in `migration_progress`).
- **Migration CLI:** `python -m backend.migrate {preflight,backfill,verify,reconcile,status,resolve-outbox,jobs-sweep}` (auth and
  google have `python -m auth.migrate` / `python -m googleform.migrate`), the engine in `common/db/migrate/`. Raw
  pymongo + SQLAlchemy Core, never Beanie, never decrypts. Backfill is resumable (checkpoints in `migration_progress`,
  adaptive batches, `--max-minutes`, advisory lock) and never overwrites a row the application wrote
  (`_bc_source = 'app'`); `verify` compares counts, per-row checksums and a sampled round-trip; `reconcile` fixes
  drift with Mongo authoritative (`--direction postgres->mongo` is refused unless the 4.0 stack's write modes, as the
  operator's environment states them, say Postgres was primary) and drains the outboxes (full runs only); a deleted
  record (a tombstone) is deleted on the side that still has it, never copied back. `--group <g>` limits preflight/backfill/verify/reconcile/status to a
  repository group (`backend/db/groups.py` `COLLECTION_GROUPS`; a test keeps it in step with the container's
  `COLLECTION_GROUPS` map). A clean full `verify` writes the "migration verified" marker into `<schema>.store_migration`
  (`common/db/marker.py`, read with `migration_verified(conn, service)`); `status --json` is the operators'
  machine-readable view.
- **Tests:** the Postgres repositories' results are pinned in JSON fixtures written from the 4.0 parity runs
  (`tests/fixtures/forms_repositories.json`, `responses_repositories.json`; `tests/app/repositories/pinned.py`),
  never regenerated to make a change pass. Test fixtures go through `container.<repo>()`; Beanie appears only in the
  frozen originals of the import tests (`tests/app/db/beanie_originals.py`). CI runs one Postgres mode (docs/ci.md).
- **The `doc` codec is pinned** (`common/db/codec_golden.py`): golden fixtures in each service's
  `tests/fixtures/codec_golden/` hold the exact `doc` JSON and `_bc_checksum` of synthetic instances of every
  mirrored document class (plus raw BSON documents in `common`). A new class shows up as unpinned cases, a new
  field as changed cases of its class; regenerate on purpose with `scripts/regenerate-codec-golden.sh` and review
  the diff. Any other change to an existing case means stored rows would encode differently: that needs a
  migration plan, not a fixture update.

A new collection is a `Record` class (`common.records`) with a row in `backend/db/models.py` and an Alembic revision;
there is no Beanie registration. Core domain models (`User`, `StandardForm`, `StandardFormResponse`, `Consent`) come from the shared
`common` package, not from here.
Background jobs go through `services/temporal_service.py`, which dispatches per job kind (`JOBS_BACKEND__<job>`)
to a procrastinate job on Postgres (default; `backend/jobs/`; worker:
`python -m backend.jobs.worker`, queue tables in the `jobs` schema via `python -m backend.jobs.schema`) or, with
`JOBS_BACKEND__<job>=temporal`, a Temporal workflow.

Response `answers` **and** `hidden_fields` (captured URL parameters, see `StandardForm.hidden_fields` for the
declared names) are encrypted at rest via `crypto_service` in `PostgresFormResponseRepository.save_form_response` and
decrypted in `form_response_service.decrypt_form_response` — any new respondent-data field on
`StandardFormResponse` must go through the same two choke points. Answer piping itself is resolved entirely
client-side (webapp `src/utils/answer-piping.ts`); the backend only stores the pipe nodes inside field titles.

**Responses belong to a workspace (#768):** a provider form (Google Forms, Typeform) linked to several
workspaces has the same `form_id` in each, and a provider response can be stored once per workspace
(same `response_id`; unique per `(response_id, workspace_id)` in Postgres, revision 0015). Every response
and deletion request stores the `workspace_id` it was collected in or imported into. Workspace reads never
filter on `form_id` alone: list/count methods of the responses repositories take a `ResponseScope`
(`repositories/response_scope.py`, `response_scope(...)` or `FormResponseService.scope`). A single
response is looked up as the workspace's own copy (`FormResponseService.workspace_response`,
`find_response_in_workspace`; 404 otherwise, for staff, respondents, receipts and MCP alike), and every
write to it goes to that copy **by its `_id`** (internal answers, feedback, edits, deletion), never by
`response_id`. Responses stored before #768 have no `workspace_id`: they count for a workspace only when
the form is linked to it alone, until `scripts/backfill_response_workspaces.py` (dry run by default) has
stamped them; ambiguous ones stay hidden. Unlinking a form from one of several workspaces deletes that
workspace's responses, and is refused (409) while the form has unattributed ones; account deletion only
removes the deleted workspaces' links and responses of a form that stays elsewhere.

**Internal fields** (`StandardFormField.internal`, "for office use only"): staff fill them in on each submission
afterwards; values live in `StandardFormResponse.internal_answers` (encrypted like `answers`, decrypted in
`decrypt_form_response`) with `internal_answers_meta` recording who changed each one and when
(`PATCH /workspaces/{id}/forms/{form_id}/submissions/{response_id}/internal-answers`, `response.annotate`).
Rules live in `services/internal_fields.py`: every form payload served to a non-member goes through
`strip_internal_fields`, every respondent-facing response through `strip_internal_answers`, respondent submissions
never store internal values (they are dropped, not rejected, so a field made internal mid-fill doesn't fail
anyone's submission), on-submit actions get the stripped form, and logic (visibility/jumps) may not depend on an internal field (form save and
AI ops both refuse it). `validations.required` on an internal field is stored but not enforced (there is no
staff-side "complete" state yet). A new endpoint that returns a form or a response to respondents must use the
same two strip helpers.

**Respondent feedback** ("Respond to submissions"): a form built here opts in with
`WorkspaceFormSettings.respondent_feedback_enabled` and lists its `feedback_statuses` (≤ 10, 1–40 chars,
unique ignoring case; `normalize_feedback_statuses`; switching either is `form.edit`). Members with
`response.annotate` post `POST /workspaces/{id}/forms/{form_id}/submissions/{response_id}/feedback`
(`{status?, message?}`, at least one; a status outside the form's list → 422). Entries are appended to
`StandardFormResponse.respondent_feedback` (`add_respondent_feedback`, `replay=True`), message encrypted like
`answers` and decrypted in `decrypt_form_response`. `StandardFormResponseCamelModel.respondent_feedback` is
`exclude=True`: the stored list (staff identity, ciphertext) is never serialised. Members get
`SingleSubmissionResponse.feedback` (who posted each); respondents get `response.feedback` through
`present_to_respondent` (`services/respondent_feedback.py`): the workspace title as author, never staff — on
their submission page, the by-uuid receipt and, as `currentStatus` only, "my submissions". A new update emails
a notice (never the update) through auth's `POST /notifications/submission-update` with the poster's token,
only when the form requires a verified identity and the submitter is identified; a mail failure is logged and
never fails the update. The link is always `API_CLIENT_URL/<workspace_name>/submissions/<response_id>` (auth
accepts only its configured hosts, so never a custom domain).

**Repeating groups:** a `group` field with `properties.repeat` (`RepeatSettings`: min/max items ≤ 50,
item label/title, `export_layout`) in `common/models/standard_form.py`; the model rejects nested groups and
unsupported child types (`REPEAT_CHILD_FIELD_TYPES`) — legacy imported groups without `repeat` are untouched.
The answer is `answers[<group id>] = {type: "group", items: [{<child id>: <answer>}, ...]}`, encrypted with
the rest of `answers`. `services/repeating_groups.py` checks submissions and edits against the published
form (item limits, required questions per item, item-scoped visibility evaluated like the webapp's
`utils/repeating-groups.ts` — keep the two in step). AI ops: `add_group`, `add_field.groupId`,
`move_field.toGroupId`, group conditions via `groupMode` COUNT/ANY/ALL. Internal fields are not allowed
inside a repeating group (model, builder save and AI ops refuse it).

**Date questions:** `properties.label` is a short label shown with the picker ("Start date"), apart
from the title. `properties.date_rules` (`DateRule`, at most 5) constrain the answer: before / after /
on or before / on or after a fixed date, today, or another date question (`field_id`). The model refuses
rules on non-date questions and on the question itself; `date_rule_problems` (common) checks the rest on
every form save and in AI ops (the question exists, is a respondent-facing date of the same scope —
page level, or the same repeating group, per item — and rules form no circle); `prune_date_rules` drops
rules a structural AI edit left dangling. `services/date_rules.py` enforces them on submit and response
edits (422), skipping rules whose other question is unanswered or hidden by logic, like the webapp's
`utils/date-rules.ts` — keep the two in step. Dates are compared as `YYYY-MM-DD` strings; "today" is
accepted within one day either side of UTC (the server can't know the respondent's zone), and on an edit
"today" is the submission day.

**Answer validation** (`services/answer_validation.py`): every submission and respondent edit is checked
against the form the respondent filled, the same way the respondent page does (`validateSlide`,
`utils/answer-rules.ts`, `utils/conditional-logic.ts` — keep them in step; shared cases in
`docs/spec/answer-validation.cases.json`, run by pytest and vitest). Required counts on the pages the
respondent goes through (replayed from page 1 with the submitted answers and the same jump resolution),
leaving out questions hidden by logic, internal questions and content blocks; repeating-group items are
checked per item. Answer rules (min/max length, pattern, min/max value, min/max choices) apply to
counted questions with an answer. Types apply to every answer (the value in the slot of the question's
type, existing option ids), and ids that are not questions of the draft or the published version are
refused (on an edit, unknown ids are dropped as before and only changed answers are reported). Patterns
are matched with RE2 (`google-re2`, linear time); longer text than 10,000 characters is left to the
browser. Creator patterns are untrusted, so their cost is bounded: RE2 gets 1 MB per pattern
(`PATTERN_MAX_MEM`: heavy ones fail fast), programs over 5,000 instructions are not used, one
response compiles at most 50 uncached patterns and spends at most 0.25 s on patterns, the cache is
bounded by entries and total program size, and `check_answers` runs in a worker thread. A pattern
over 200 characters (the cap the builder and the form spec share,
`common.form_spec.models.PATTERN_MAX_LENGTH`), one RE2 cannot compile (lookarounds,
backreferences) or one past the budget is not enforced; only field ids are logged. Integers too
big for a float count as Infinity, as in JavaScript. Problems answer 422 `{"code": "invalid_answers", "errors": [{"fieldId", "rule", "item"?}]}`,
never with values. `RESPONSE_VALIDATION_ENFORCE=false` switches to log only (form id, count, rule codes).
v1 and imported forms (fields not on pages) are not validated.

**Calculated fields** (`services/calculated_fields.py`, webapp twin `utils/calculated-fields.ts`): a
`calculated` field on a page stores an expressions-v1 AST at `properties.expression`
([../docs/spec/expressions-v1.md](../docs/spec/expressions-v1.md)), a display `format` and
`hidden_from_respondents`. Variables share logic's namespace: page question ids (as logic reads them),
`<group id>.<question id>` lists, declared hidden-field names, other calculated ids. Every save (builder,
spec, AI ops after each op) refuses a malformed AST, unknown or internal variables and circles (422
`invalid_calculation` with `fieldId` and the JSON pointer `path`). Submit and respondent edit recompute
every calculated field with the Python evaluator, in dependency order, and store the server's value
(`number`, `boolean` or `text` slot); client values are dropped, and answer validation replays logic and
jumps with the server values. "today" is the server's UTC date on submit, the submission day on an edit.

**Verified email domains** ([../docs/verified-domains.md](../docs/verified-domains.md)): a workspace's
Owner/Admins claim an email domain (`/workspaces/{id}/domains`) and prove it with a TXT record
`_bettercollected-verification.<domain>` = `bettercollected-domain-verification=<token>`. Code:
`services/workspace_domain_service.py` (one access check, `_authorize`, to become `security.manage`),
`services/domains/names.py` (IDNA + Public Suffix List via `publicsuffixlist`; refuses public suffixes,
free-mail and reserved domains, incl. `PLATFORM_ADMIN_EMAILS` domains) and `services/domains/dns_txt.py`
(dnspython, no cache). A domain is verified by at most one workspace: the partial unique index on
`verified_domain` in both stores decides races. A verified domain whose record disappears keeps its owner
(`verification_lost_at` after N failed re-checks, never transferred). SSO only trusts
`sso_domain_claim` / `sso_domains` (verified, not lost, not reserved now). Tests never resolve real names
(`tests/app/domain_helpers.py`).

**Single sign-on** ([../docs/sso.md](../docs/sso.md)), flagged off (`SSO_ENABLED`): SAML/OIDC through Ory Polis,
tenant = workspace id. Code in `services/sso/`: `polis_client.py` (Polis admin API, `SSO_POLIS_API_KEY`, never logs
bodies), `url_guard.py` (SSRF: https, public addresses only; `fetch_public` fetches metadata/discovery documents
ourselves, every redirect hop checked; Polis never gets an admin-typed URL), `connection_service.py` (admin API
`/workspaces/{id}/sso/*`: view and test need `security.manage`, every change is **owners only**
(`AuthorizationService.require_owner`, any owner); enabling needs a passed test; one enabled connection at a time;
SSO-required + offered session revocation), `login_service.py` (`/auth/sso/login|callback`: every check before auth
creates the account: connection enabled, workspace available, the IdP's email on *this* workspace's SSO domain, seat
cap via `WorkspaceUserService.has_free_seat`; JIT membership with the default role, never downgrading; fixed
`sso_error` codes; a `SsoNonce` cookie + single-use `sso_used_states` against login CSRF and replay; the dashboard
redirect quotes the workspace handle; "Test connection" records the outcome and signs nobody in, asks a SAML IdP for a fresh
sign-in (auth's `test`/`protocol` flags; nothing for OIDC, Polis's param forwarding stays off) and, when it fails, keeps only the received address's *domain*
(`last_test_domain`) and the IdP's claim *names* (`last_test_claims`), never addresses or values, never logged), `policy.py`
(SSO-required refuses email codes and Google for those domains, ends non-SSO sessions at refresh; the workspace's owners
keep email codes as break-glass; on other workspaces' forms an email code only gives a **respondent-scoped session**
(`session_scope="respondent"`), which `authorize()` grants nothing; default SSO role Viewer; an owner may pick Reviewer or Editor, never Owner, Admin or Privacy officer). Connections: `sso_connections` + Postgres twin (revision 0008); used states: `sso_used_states` (0009). Sessions record `method="sso"`; an SSO
session is never platform-admin-eligible (`session_service.platform_admin_proof`, used for `/auth/status` and
`/auth/callback`). Tests use `tests/app/sso_helpers.py` (fake Polis and auth).

**SCIM directory sync** ([../docs/sso.md](../docs/sso.md), "Directory sync"), needs SSO plus `SCIM_WEBHOOK_URL`: a
workspace's directory in Polis's dsync, same tenant. Code in `services/scim/`: `polis_dsync.py` (dsync admin API),
`signature.py` (`BoxyHQ-Signature` HMAC over the raw body, 5-minute window, constant time), `webhook_service.py`
(`POST /scim/webhook/{our directory id}`, public, signature only: unknown directory / bad signature 401, tenant
mismatch 403, dedupe in `scim_events`, a failed event releases its claim and answers 503 so Polis retries),
`sync_service.py` (the rules: verified SSO domains only, seat cap before the account exists, auth's internal
`POST /auth/sso/directory-account`, memberships `provisioned_by="scim"`, deactivation **disables** and
`revoke_all_for_user(SCIM_DEPROVISIONED)`, never the billing owner (`owner_protected`; a co-owner is deactivated like anyone, their role never changed) or a member invited by hand, JIT `"sso"` memberships are
taken over; group→role, highest wins via `roles.py`, which reads `WorkspaceRoles` at runtime (stored with `stored_role`); `update_member_role` refuses a `"scim"` membership while the directory exists (409 `managed_by_directory`); `is_deprovisioned` is
the guard `login_service` uses to refuse `sso_deprovisioned`; `reconcile`), `directory_service.py` (admin API
`/workspaces/{id}/scim/*`: view `security.manage`, every change owners only; create needs a verified domain; the
bearer token is returned once, the webhook secret stored encrypted with `container.crypto`; rotate replaces the
Polis directory and matches users by email, groups by name). Resync: the button, `python -m backend.scim resync`,
and the nightly procrastinate periodic task `scim_reconcile`. Storage: `scim_directories`, `scim_users`,
`scim_groups`, `scim_group_members`, `scim_events` (Postgres only, revision 0010). Polis caps dsync pages (50): `_pages` steps by what came back until an empty page, a non-list reply is `PolisError`; a resync refuses mass deprovisioning (`ReconcileRefused`, owner `force`) and removes nobody for `SCIM_ROTATION_GRACE_HOURS` after a rotation; `AuthUnavailable` decides nothing (webhook 503, resync skips). Memberships: `disabled_reasons` (`plan`, `directory`; `disable_for`/`enable_for`, each path lifts only its own), disabled ones hold no seat (`active_member_count`), one per workspace and user (unique index: Postgres 0011, which refuses while duplicates exist; `python -m backend.membership_duplicates`; inserts go through `add_if_absent`). Tests: `tests/app/scim_helpers.py`, `test_scim.py`, `test_scim_review.py`.

## Seed scripts

`backend/scripts/` holds idempotent seed scripts that populate collections a fresh (or already-running) environment
needs but that don't belong in a migration. Pattern to follow for new ones: a reusable `async def seed_x(...)`
function that takes its repositories as arguments (so it can be called from `lifespan` on every boot), plus a thin
`_main()`/`if __name__ == "__main__":` CLI wrapper that connects the stores itself for one-off manual runs. Reads
and writes go through the container's repositories. Never
overwrite existing data — check-then-create, so re-running (including "run" via a normal app restart) is always safe.

**`seed_flow_templates.py`** — seeds the flow-native template gallery (branching used as the hook: support triage,
lead qualification, job-application screening). It's wired into [asgi.py](backend/app/asgi.py)'s `lifespan`
right after `init_db`, so **it runs automatically on every backend startup** — an already-deployed environment picks
up new/changed templates the next time it restarts, no manual step required.

- Gated by `DEFAULT_SEED_FLOW_TEMPLATES` (`DefaultResourcesWorkspaceSettings`, default `true`). Set `false` to
  disable if you manage the gallery by hand.
- Requires `DEFAULT_WORKSPACE_ID` to be a valid ObjectId hex string — templates are matched to the gallery by
  `workspace_id`, and the templates API (`GET /templates`) only serves public templates from that one workspace id.
  **If it's unset, seeding is skipped with a log warning** (not an error) — this is also why an empty/misconfigured
  `DEFAULT_WORKSPACE_ID` silently produces an empty gallery even with templates in the DB: check this first.
- Idempotent by title + `builder_version="v2"` — never overwrites an existing template, so hand-edits in the DB
  survive restarts. One exception: at startup it gives an existing template's yes/no fields the Yes/No choices
  earlier versions left out (forms made from them showed the question with nothing to answer), and
  `repair_leaflet_design` moves templates still wearing the old seeded theme to the Leaflet preset and style
  (`template_theme()`, read from `constants/themes.py`, never copied) and fills an empty welcome description
  and empty page section titles (`section_title`).
  That repair recognises the script's own templates by title, `builder_version="v2"`, public, not imported,
  and exactly the builder's questions (type + title); a theme changed by hand is kept, nothing is created,
  and forms made from a template keep their stored theme. The existence
  check, that repair and new templates all go through the template repository.
- Every choice-type field needs its choices stored: the responder renders yes/no, dropdown and multiple-choice
  options from `properties.choices` (yes/no falls back to Yes/No, the others show nothing). Use `_yes_no()` and
  `_choices(...)`.
- To add a template: write a new zero-arg builder function returning `{title, description, category, fields}` (see
  `support_triage()`/`lead_qualification()` for the shape) and add it to `TEMPLATE_BUILDERS`. A payload may also
  carry `language` (stored as the template's `settings.language`, which forms made from it keep), `welcome_page`
  and `thankyou_page`.
- **Dutch-first templates** (`scripts/dutch_first_templates.py`): rental home application, school enrolment,
  request to an organisation, new colleague, event registration. Each is written once with its Dutch (B1 plain
  language) and English text side by side and seeded as two templates (`settings.language` `nl` / `en`) with the
  same questions: one question per page, a "why we ask this" line on every question, few required answers,
  nothing pre-selected, no ID numbers or documents, follow-up pages skipped unless a yes/no question is answered
  yes (page jumps on yes/no only: choice conditions are not used there). `tests/scripts/test_dutch_first_templates.py`
  checks the twins match, the wording rules, the jump paths, that every template ships a retention period (days,
  carried as `settings.response_expiration_type` / `response_expiration`, so a form made from it enforces it) and
  that a form made from one publishes. The prose of both languages is copied to
  `webapp/src/utils/plain-language/dutch-first-templates.fixture.json`, which the webapp's B1 check tests run over
  (rewrite it with `REGENERATE_TEMPLATE_PROSE=1` after a wording change). Change wording in that file, then delete
  the seeded template by title to re-seed it. A Dutch-first template seeded before it carried a period gets it from
  the seed (`repair_retention`) when BOTH retention keys are empty; a period set by hand stays. A template's period is
  checked like a form's when a template is created or updated (422), an update keeps the settings its body leaves
  out (an explicit null clears), and a form saved as a template carries its period. Importing a template into another
  workspace still resets its settings (`import_template_to_workspace`), as before.
- To force a re-seed of a changed template, delete it from `form_templates` first (by title) — the next restart (or
  a manual run) recreates it.
- Manual one-off run (e.g. without restarting the app): `uv run python -m scripts.seed_flow_templates` from `backend/`.
- **Gotcha this script already tripped on:** `PydanticObjectId` fields don't validate an *empty string* the way you'd
  expect from an "unset" env var — double-check with a real value, not just `KEY=` in `.env`, if the gallery stays
  empty.

## Analytics (Umami)

Form-view analytics (`FormAnalyticsRouter` — `/{workspace_name}/forms/{slug}/{stats,pageviews,metrics}`) proxy a
self-hosted [Umami](https://umami.is) instance via `services/umami_client.py`. It used to default to a
BetterCollected-hosted Umami; that's gone, so no self-hosted deployment phones home.

- **Debug mode:** `DEBUG` defaults to false (no HTML tracebacks on 500s). `backend/.env.example` sets `DEBUG="true"` for local development; deployments keep it off.
- **Local dev:** `docker compose -f docker-compose.local.yml up` starts Umami at `http://localhost:3003` (default
  login `admin`/`umami` — change it). No need to create a website by hand — see auto-provisioning below.
- **Config** (`config/UmamiSettings.py`, env prefix `UMAMI_`): `URL`, `USERNAME`, `PASSWORD` are required (`has_credentials`);
  `WEBSITE_ID` is optional. `UmamiClient.authenticate()` checks `settings.umami_settings.is_configured` (credentials
  *and* a website id) up front and raises a clean 503 ("Analytics is not configured on this instance.") instead of
  attempting a doomed login — check this first if the analytics endpoints 503 unexpectedly.
- **Website auto-provisioning:** if `WEBSITE_ID` is unset but credentials are present, `asgi.py`'s `lifespan` calls
  `umami_client.provision_umami_website()` on every startup — it finds a website named `WEBSITE_NAME` (default
  `"BetterCollected"`) or creates one, then sets `settings.umami_settings.WEBSITE_ID` in memory for the rest of the
  process. Idempotent (matches by exact name, never creates a duplicate); never blocks startup (logs and continues
  if Umami isn't reachable yet). Set `WEBSITE_ID` explicitly to skip this and pin a specific website.
- **Gotcha this file already tripped on:** the app's custom `HTTPException` (`app/exceptions/http.py`) takes a
  `content=` kwarg, not FastAPI's `detail=` — passing `detail=` raises a `TypeError` instead of the intended clean
  error. Already fixed in `umami_client.py`; keep this in mind if you add more raises there.
- Canonical path construction (`form_url = f"/{workspace_name}/forms/{slug}"`) must stay in sync with the webapp's
  `trackCanonicalFormView` helper (`webapp/src/lib/analytics/umami.ts`) — both sides hard-code the same shape so
  custom-domain and client-host traffic land under one path.
- Deployment: `deploy.sh` seeds the `UMAMI_URL` setting with `http://umami:3000` (internal docker network; it is
  not pinned in compose any more) and replaces Umami's built-in `admin`/`umami` login with a generated password
  stored as the `UMAMI_PASSWORD` setting (`deploy/umami-rotate.js`). `UMAMI_WEBSITE_ID` stays optional.
- **No personal data in events.** Event properties must never carry a user's email or other personal data.
  The web app used to send the signed-in user's email as an event property (`email`); events stored
  before that change still hold it. `scripts/umami/email-data-count.sql` (read-only) and
  `email-data-purge.sql` (a dry run unless `-v apply=1`) count and delete those event-data rows in the
  Umami database. They print counts only, and the usage is in each file's header.

## Public API (forms as code)

`/api/v1/public/v1` is a FastAPI app of its own (`app/public_api/`), mounted in
`asgi.py` next to `/mcp`: its own OpenAPI document
(`docs/api/public-v1.openapi.json`, regenerate with
`uv run python -m backend.app.public_api.openapi`; a test checks it), one
error shape, Bearer API keys only (never cookies). It mirrors MCP and calls
the same code: scopes and the creator re-check in `services/api_access.py`,
responses through `services/api_responses.py`, ops through
`persist_ops_to_form`, create/replace through `services/form_spec/writes.py`
(which uses `WorkspaceFormService.create_form` / `update_form`). PUT needs
`If-Match` and writes with `update_form_if_unchanged`. `Idempotency-Key`
records live in `api_idempotency_keys` (`services/idempotency.py`). Rate limit
per key on the shared limiter (`API_PUBLIC_API_*`). Docs: `docs/api/README.md`.

## AI consent (#715)

No user content (form content, prompts, the AI profile, memory, responses, uploaded
documents) goes to an AI provider until the workspace has opted in. Code:
`services/ai/consent.py`, enforced through `OpenAIService.provider_for_workspace`.

- **Workspace setting:** `ai_enabled` on the workspace document (default off; a
  missing value counts as off, so existing workspaces start with AI off), with
  `ai_provider` (the one provider consent was granted for), `ai_enabled_by`/`_at`
  and `ai_disabled_by`/`_at`. `GET/PUT /workspaces/{id}/ai-settings`; only admins
  change it, and only for a provider configured on the instance.
- **One choke point:** every AI path gets its provider from
  `provider_for_workspace(workspace_id, requested)`, which raises 403
  `{"code": "ai_not_enabled", "message": ...}` while AI is off and always returns
  the consented provider (a client-chosen `provider` is ignored unless it is that
  one). Call it **after** the membership check and **before** loading the AI
  profile, memory or responses. Never call `_get_provider` from a feature: it is
  the raw lookup (tests replace it with a fake).
- **Memory extraction** after a chat turn also needs the user's own "Learn my
  preferences" (`UserAIPreferenceMemoryDocument.learn_preferences`, default off,
  `PUT /workspaces/{id}/ai-memory/settings`); `extract_from_turn` re-checks both.
- **PDF import** needs the per-upload `ai_consent` on top (see below).
- **Response insights (#716)** also need the form's own "Allow AI insights on
  responses" (`WorkspaceFormSettings.ai_insights_*`: enabled, the provider id and
  name the respondent notice shows, who and when;
  `PUT …/forms/{id}/ai/insights/settings`, `ai.manage`, needs the workspace
  opt-in to turn on); running and reading them is `response.read`. While on, the respondent
  form's trust strip names the provider. Only forms collected here
  (`settings.provider == "self"`) qualify: an imported form's respondents
  answered on Google Forms / Typeform and never saw the notice, so the setting
  and generate both refuse it, and only `provider == "self"` responses are ever
  analysed. **Only responses whose page showed the notice (#752):** while the
  setting is on, the published form fetch (`GET …/forms/{id}?published=true`)
  carries `aiNoticeToken` (`services/ai/notice_token.py`: HMAC-SHA256 under a key
  derived from `AUTH_JWT_SECRET`, binding workspace, form id, provider id and
  name, `ai_insights_enabled_at` and when it was issued; valid 24 hours). The form
  page sends it back as the multipart field `ai_notice_token` on submit;
  `stamp_response` clears whatever the body claims and sets
  `ai_notice_shown_at`/`ai_notice_provider_name` only for a valid token matching
  the current setting. A respondent's edit never adds the stamp (it merges
  answers, so earlier answers would become analysable): it keeps the stored one
  and clears what the body claims. The respondent form shows the notice in the
  privacy strip itself, not only in the collapsed panel, wherever a token is
  sent. Generate reads
  `list_recent_with_ai_notice` (stamped for the setting's provider name, shown
  at or after `ai_insights_enabled_at`, so turning it off and on again excludes
  earlier ones); `created_at` plays no part. Responses from before #752 carry no
  stamp and are never analysed. A workspace provider other than the one the notice named
  (id and resolved name, so a changed `COMPAT_BASE_URL` host counts) is
  refused (403 `ai_insights_not_enabled`) until the form setting is renewed. The
  projection redacts email/phone answers and leaves out internal fields and their
  answers (internal in the draft or any published version,
  `all_internal_field_ids(..., every_version=True)`); free-text answers are sent
  as written, and the UI says so.
- **MCP API keys with `responses:read`** hand full, unredacted answers to an
  external AI client: creating one requires `acknowledgeUnredactedResponses`,
  stored as `responses_read_acknowledged_by`/`_at` on the key.
- **Tests** never call a real provider: `tests/app/ai_helpers.py` has a counting
  `FakeProvider`, `use_fake_provider` (replaces only the raw lookup, so the opt-in
  check still runs) and `enable_ai(workspace)`. A new AI path needs a test that it
  answers 403 `ai_not_enabled` with zero provider calls while AI is off.

## AI limits

What one AI request may cost, all in `config/ai_settings.py` (env prefix `AI_`).

- **Calls** (`services/ai_form_provider.call_provider`): each provider request
  has `AI_REQUEST_TIMEOUT_SECONDS` (60) and the whole call, client retries
  (`AI_CLIENT_MAX_RETRIES`, 1) included, `AI_CALL_TIMEOUT_SECONDS` (120); a
  timeout is 504 `ai_timeout`, any other provider failure 502 `ai_unavailable`.
  Output tokens per call type: `AI_MAX_OUTPUT_TOKENS_GENERATE` (16000), `_CHAT`
  (8000), `_REVIEW` (8000), `_INSIGHTS` (4000), `_MEMORY` (1000); document
  import pages keep `PAGE_MAX_TOKENS`/`PAGE_TIMEOUT_S`.
- **Form generation** (outline first, below): the outline call and its
  retry stop at `AI_GENERATION_TIMEOUT_SECONDS` (240); a build's gap-filling
  calls (up to 5 pages, each with its retry) share one deadline,
  `AI_GAP_FILL_DEADLINE_SECONDS` (120), after which the build goes on with
  what was filled and says so in its notes.
- **Structured replies** (`services/ai/structured.py`): every reply is
  validated with Pydantic (`FormOutline`, and a model per chat/review/
  insights/memory reply); an unusable one gets one retry with the problems
  (locations and messages, never values), then 502 `ai_unusable_reply`.
  The outline and gap-filling calls pass a strict JSON schema
  (`json_schema`, strict-mode rules as in the import schema), which OpenAI
  uses as structured output; other calls ask for JSON mode (OpenAI
  `json_object`, Gemini `application/json`, the compatible endpoint unless
  `AI_COMPAT_JSON_MODE=false`; Gemini and the compatible endpoint get JSON
  mode for a schema too). A provider's `chat()` takes `max_output_tokens`,
  `json_mode` and `json_schema`; use `chat_json(...)` or
  `chat_structured(...)` for a reply that must be JSON.
- **Rate limits and budget** (`services/ai/usage.AIUsageGuard`, on the shared
  `FixedWindowRateLimiter`): `provider_for_workspace(..., user_id=...)` admits
  one AI request after the opt-in check: `AI_RATE_LIMIT_PER_USER` (10) and
  `AI_RATE_LIMIT_PER_WORKSPACE` (30) per `AI_RATE_LIMIT_WINDOW_SECONDS` (60),
  then the workspace's daily (UTC) counters: requests always counted, capped
  by `AI_DAILY_REQUEST_BUDGET`, and tokens where the provider reports usage
  (`record_tokens`, bound to the workspace by `bind_usage`), capped by
  `AI_DAILY_TOKEN_BUDGET`; both caps 0 = none. Over a limit: 429
  `{"code": "ai_rate_limited" | "ai_daily_limit", "message"}` with
  `Retry-After`. A document upload with `ai_consent` is admitted at upload
  (`admit_import`, only while AI is on) and its job resolves the provider with
  `admit=False`; applying a review fix calls no provider and has its own
  `AI_RATE_LIMIT_FIX_PER_USER` (60). 0 turns a limit off.
- **Proposals** (`services/ai/proposals.py`): the editor's chat turns use
  `mode: "propose"`: the ops are dry-run, nothing but the chat turn is
  stored, and `POST …/ai/proposals/{id}/accept` (optional `opIndexes`)
  applies them atomically, only to the version of the form the proposal
  was made from (`base_updated_at`; ops address pages and fields by
  position too), through `persist_ops_to_form` with the conditional write
  on that base: 409 `proposal_stale` when the form changed since, 422
  `proposal_selection_changes_meaning` when a chosen op without the ones
  left out would change something other than its step showed, 422
  `proposal_dependency` for a chosen op whose ref comes from one left out;
  `…/reject` only marks it. The editor saves pending edits before it asks.
  A proposal lives on its chat turn (`messages[].proposal`, both stores;
  statuses are written with `update_proposal`, never by saving the whole
  session), can be accepted for `AI_PROPOSAL_TTL_SECONDS` (3600), and a
  one-time claim in the rate-limit counters (`FixedWindowRateLimiter.claim`),
  taken by accept and reject alike, lets exactly one of them decide; an
  unexpected error after the claim opens the next attempt (`attempt` on the
  record) so a retry can decide, and a form deleted meanwhile is a 404. Accepting uses the review-fix allowance. `apply`
  stays the API default (MCP, older clients).
- **Untrusted content** (`services/ai/untrusted.py`): form contents, the AI
  profile, preference memory, respondents' answers and the chat exchange go
  into prompts only through `fence(tag, text)` (which defuses the tags inside
  the text), and every system prompt carries `UNTRUSTED_CONTENT_RULES`.
  Model output is never executed: ops are validated by the ops engine, image
  and policy links are checked (`image_urls.py`, `policy_url.py`).
- **Logging:** AI paths log error types, counts and ids only, never a prompt,
  a reply, a tool query or an exception message.
- **Outline-first generation** (`services/ai/outline.py`,
  `outline_compile.py`, `outline_service.py`): every AI-built form is
  planned as an outline (title, language, pages with section titles,
  question intents with `whyWeAsk` on identity questions, show/hide and
  jump intents, `omitted` questions) and then compiled into one atomic
  ops batch with refs on a blank Leaflet form, saved once.
  `POST …/forms/ai/outline` (`{prompt, documentText?}`, the document is
  fenced) returns the outline only; `POST …/forms/ai/build`
  (`{outline, fillGaps?}`) builds an outline the person may have edited and
  returns `{formId, title, quality, notes}`; `POST …/forms/ai` runs both in
  one request and still returns the saved form. A model outline gets one
  corrective retry for shape and for `outline_problems` (choices, reasons,
  rules on later answers, backward jumps); an edited one is authoritative:
  rules that no longer fit are dropped with a note, and the model is only
  asked (one structured call per page, at most 5) to fill missing choices
  and reasons, never to change what the person wrote (`fillGaps: false`
  sends nothing; identity questions on later pages left without a reason
  are named in the notes). A build without a
  provider call still needs the opt-in and uses the fix allowance. MCP:
  `create_form_outline`, `build_form_from_outline` (`forms:write`). The
  compliance review is not run on build (it is a model call of its own).
- **Quality evals:** `services/ai/quality.check_form_quality` scores a
  generated or edited form (why-we-ask, questions per page, section titles,
  EN/NL language, duplicates, required fields, choices, image hosts, logic
  references, the Leaflet default) with findings that carry codes and ids,
  never form text. The synthetic golden replies in `tests/fixtures/ai_evals/`
  run through the real pipeline (`services/ai/eval_pipeline.py`) in CI; when a
  prompt change moves a finding on purpose, update the fixture. To measure a
  prompt change against a provider, run `AI_EVAL_ALLOW_LIVE=1 uv run python -m
  scripts.ai_eval --live --out <dir outside the repo>` (both the flag and the
  variable are needed; it sends only the synthetic prompts in `prompts.json`,
  costs tokens, honours the AI limits unless `--ignore-limits`, and writes
  `report.json` and `report.md`). `--prompts` only accepts a file inside
  `tests/fixtures/ai_evals/`. Without `--live` it replays the fixtures and
  never reads `backend/.env`. Never in CI. Never run --live on a production
  host.

## PDF form import (in progress)

`POST /workspaces/{id}/form-imports` (multipart `file`) turns an uploaded PDF or
photo of a form into a draft form; `GET …/form-imports/{import_id}` reports
progress. Code: `app/services/pdf_import/` (stages), `app/services/pdf_import_service.py`
(start, limits, dispatch), `app/controllers/pdf_import_router.py`.

- **Isolated sandbox in deployment (#703):** the `document-sandbox` compose service
  (same image, `pdf_import/server.py`) runs as `nobody` with no network, a
  read-only filesystem, no capabilities, no env file and a seccomp allowlist
  (`deploy/seccomp/document-sandbox.json`, see its README: EPERM for anything
  unlisted, `socket` only `AF_UNIX`, no ptrace/mount/namespaces/keyctl/bpf). A new
  mode or library that needs another syscall shows up as "could not read"; find
  it with strace as the README says, then run `test_sandbox_container.py` (needs
  the image `bettercollected/backend:sandbox-test`, skipped otherwise). Backend and jobs worker
  reach it over `PDF_IMPORT_SANDBOX_SOCKET` with `PDF_IMPORT_REQUIRE_ISOLATED_SANDBOX=true`.
  `server.py` and `runner.py` must never import the backend package. Native modes
  (`render`, `logo`: the organisation logo upload, and `image`: a fetched
  picture, see "Images on forms" below; both decoded and re-encoded without
  metadata by `pdf_import/logo_image.py`, see `services/form_logo.py`; the API
  never decodes an image itself and answers 503 without the sandbox)
  never run in a local child. An unreachable or unresponsive sandbox
  raises `SandboxUnavailable` (not the document's fault): the import stays queued
  while retries remain, and is failed with a "try again later" message on the
  last one (`ImportPipeline.give_up`), so it never holds the workspace's import
  slot. Keep the container's `mem_limit` above `DOC_SANDBOX_PARALLEL` x
  `PDF_IMPORT_SANDBOX_MEMORY_MB` + 512m.
- **Sandbox output is untrusted:** the child parsed an attacker-supplied file, so
  every stage validates what comes back (types, ranges, ids, sizes) before using
  it or putting any of it into a storage key.
- **Untrusted documents are only opened in the sandbox** (`pdf_import/sandbox.py`):
  `_child.py` runs in Python isolated mode with a scrubbed environment (no
  secrets), a temporary working directory, its own memory/CPU/core limits, a
  wall-clock timeout, and at most `PDF_IMPORT_MAX_PARALLEL_SANDBOXES` at once.
  `analysis.py` and `fonts.py` must stay importable without the `backend`
  package (relative imports only). Never run pypdf/pdfplumber/pypdfium2 work in
  the API or worker process directly. Native rendering only runs in the isolated
  container (separate user, no network, seccomp filter; see above).
- **Licences:** pypdf (BSD), pdfplumber/pdfminer (MIT), pypdfium2 (BSD/Apache),
  Pillow. Do not add PyMuPDF (AGPL) or GPL converters.
- **Workspace limits are enforced by the insert** (`form_import_repo.create_within_limits`):
  one running import and imports per day are counted and the record inserted
  under a per-workspace lock, a lease document in `form_import_locks` (unique
  `_id`) on Mongo and `pg_advisory_xact_lock` in the same transaction on Postgres,
  so parallel uploads cannot both pass. The write is `replay=True` and raises
  `ImportLimitReached` on refusal, so the mirror never re-runs the check. The
  service's earlier count is only a cheap look; a start refused at the insert
  deletes the draft it created. A start that waits longer than `LOCK_WAIT_S`
  for the lock is refused as `import_in_progress` in both stores (Postgres sets
  `lock_timeout` for the transaction instead of failing with the session's).
  `test_repository_parity.py` pauses every start between its counts and its
  insert, so the parallel test fails every time the lock is missing.
- **The draft form is created at upload**, and the original is stored under
  `private/<workspace>/<form>/imports/<import>/`, so deleting the form deletes it.
  Import records are deleted with their forms (`WorkspaceFormService`).
- **A failed import removes its empty draft** (`ImportPipeline.discard_draft`, on
  refusal, unexpected failure and `give_up`): only while the draft is `untouched`
  (no fields, never published: the same test as the compile guard), through
  `WorkspaceFormService.delete_draft_form`, which keeps the import record. The
  record stays with `form_id = None` and a note in `report.notes`; review and page
  images then answer 404, and the webapp's failed screen says the draft was
  removed. A draft the user already edited or published is kept.
- **Every failure has an `error_code`** (API `errorCode`) next to the English
  `error`: the refusal code (`encrypted`, `unreadable`, `too_many_pages`,
  `too_large`, `too_complex`, `timeout`, `empty`, ...), `no_questions` (compile
  found nothing to ask: failing beats an empty draft), `unavailable`
  (`give_up`), `failed` (unexpected), `interrupted` (expired, see below), and
  `waiting_for_reader` while queued for a retry. The webapp translates by code (`builder` namespace,
  `PDF_IMPORT.ERROR.<code>`, EN + NL, `components/pdf-import/import-failure.tsx`);
  a new code needs both locales. Logs carry the import id and code, never the
  file name or document text.
- **An import whose job died is expired as `interrupted`** (#703): the job writes
  `heartbeat_at` every `PDF_IMPORT_HEARTBEAT_S` (30s) while it runs, during long
  stages and retry waits too (`ImportPipeline.keep_alive`, around the in-process
  retries and the procrastinate job), and every pipeline save sets it. An active
  import whose last progress (`heartbeat_at`, else `started_at`/`created_at`) is
  older than `PDF_IMPORT_STALE_AFTER_S` (600s: total run time is unbounded, the
  longest silence of a live import is one model call retried, 2 x 120s) is
  failed by `form_import_repo.expire_stale` under the same workspace lock as the
  limit check, then its untouched draft is removed like any failure's. It runs on
  every start, when the progress screen reads a stale import, and in the
  procrastinate worker's `expire_stale_imports` sweep (`PDF_IMPORT_STALE_SWEEP_CRON`).
  A job that finds its import expired at its next heartbeat is cancelled, so it
  never writes over the failure. `touch` sets only `heartbeat_at` (Mongo `$set`,
  Postgres row lock), never the rest of the record.
- **Stages checkpoint** on the import record (`stages`); a retried job skips
  finished ones. Runs on procrastinate (the default, `JOBS_BACKEND__import_form=postgres`),
  with `=temporal` as a background task in the API process.
- **AI needs two consents per import:** nothing from an uploaded document (page
  text, layout text, page images) goes to an AI provider unless the workspace has
  AI enabled (see "AI consent" below) **and** the uploader sent `ai_consent=true`
  with that upload (stored with `ai_consent_at`/`_by`). With either missing
  `_structure` passes no provider, only the deterministic structuring runs, and
  `report.notes` names what is missing.
- **Answers on filled-in forms never become questions:** words inside answer
  boxes, on answer lines and in table answer cells (`structuring.value_words`)
  are left out of the model prompt, of labels/options and of the heuristic. A box
  or line holding text counts as filled when it is in another font or size than
  the label beside it (`layout._filled_in`); same style means printed text.
- **Document text stays in private import artifacts** (`text.json`, `layout.json`,
  next to the original, deleted with the form). Never copy values found in an
  uploaded document into the form, import records or logs, and send the model only
  what a stage needs to recognise questions.
- **Output of the sandbox is capped in the parent** (`PDF_IMPORT_MAX_RESULT_BYTES`):
  the API/worker has no memory limit of its own. Word counts are capped too; an
  over-limit document is refused as `too_complex`, never silently truncated.
- **Legacy fonts:** `pdf_import/legacy_decode.py` decodes Preeti-layout Devanagari
  fonts (Preeti, Aakriti) with our own tables (the known converters are GPL).
  Decoded words are trusted per page (plausibility) and per line (one malformed
  word taints its line); untrusted lines are left for the image-reading stage,
  and a page with too many of them switches route to `vision`. Add a font family
  by adding a decoder and tests of common words; never trust an unknown legacy
  font's text.
- **Layout primitives** (`pdf_import/layout.py`) are deterministic geometry over the
  drawing and the recovered words: section bars, answer slots (box, underline,
  leader dots), character/date cell runs, checkboxes (squares, `( )`, glyphs), data
  tables (a header row plus empty rows; grids of label/answer boxes are layout,
  not tables), photo/thumbprint boxes, signatures, staff-only regions, paragraphs
  and images. They reference words by index into the page's word list.
- **Rendering and structuring:** `render` (pdfium / Pillow, native, isolated sandbox
  container only, never a local child: for development run the `document-sandbox`
  compose service; one page per call) stores page PNGs;
  `structure` (`pdf_import/structuring.py`) asks the instance's default AI provider
  (`analyze_page`: page image + words and layout items by id, JSON schema; OpenAI uses
  `PDF_IMPORT_OPENAI_MODEL`, default `gpt-6-luna`, with **strict** structured output)
  for questions that reference those ids. `structuring.schema()` must stay valid for
  OpenAI strict mode — every object lists all its properties in `required` (optional
  ones are nullable, a nullable object is an `anyOf` with null), `additionalProperties:
  false` everywhere, no length/pattern/format/range keywords; `test_structuring.py`
  checks it. `validate()` drops nulls first, so null = absent. Labels are rebuilt from
  the referenced words; invalid answers are retried once, then the page is structured
  deterministically. Staff-only elements carry their labelled answer places
  (`fields`, from `structuring.staff_fields`: slots inside the staff region, labels only
  from words inside it, slots a question claimed left alone). Result: `fdm.json`. Tests
  never call a real provider (autouse fixture in `tests/app/pdf_import/conftest.py`).
- **Compile** (`pdf_import/compile.py`) turns `fdm.json` into the draft form with explicit
  redesign rules (pages per section, other+specify and follow-up visibility, verbatim
  statements and a terms page, typed-name signatures, B.S./A.D. as two dates, location
  questions) and the brand theme from section-bar colours (darkened to WCAG AA for white
  text). Built from an empty form through `apply_form_ops` (pages, then `add_group` at
  the planned positions, then logic) and saved once, so a retry is idempotent;
  `with_stable_ids` renumbers every uuid in order of appearance, group children and
  the logic pointing at them included. Every applied rule and drop is listed in
  `report.compile`.
  - **Staff-only parts → internal fields** (D5/D10): each labelled slot becomes an
    internal field (only `INTERNAL_CAPABLE_TYPES`; photo/thumbprint boxes are listed as
    dropped) on pages of their own at the end, with no heading statement (a visible
    field would keep the page alive for respondents). No "Please specify" or other
    logic is ever built on them, and `internal_logic_violations` runs on the result.
    A part with nothing labelled is only listed (`staff_only_listed`).
  - **Repeating groups** (D7): an open-row table becomes a group (one question per
    column, max = the paper's empty rows capped at 50, min 1 only if required, item
    label from the table's label or its first column); a table with labelled rows stays
    a grid of fields. Joint-applicant blocks (`applicant_index` 1..n asking the same
    questions, compared by kind + label without numbers) become one "Applicants" group
    with max = n; questions that cannot repeat (uploads, tables, location sketches) stay
    per applicant with "Applicant N:" prefixes, and blocks that differ keep the
    prefixes. Logic stays item-scoped: a rule whose source is a group child is only
    kept when its target is in the same group.
- **Artifacts:** stage outputs (`text.json`, `layout.json`, `pages/<n>.png`, `fdm.json`) are stored next to the original
  in the form's private folder, so they are deleted with the form.
- Limits and the default model: `PDF_IMPORT_*` (`config/pdf_import_settings.py`).
- Tests generate their own documents (`tests/app/pdf_import/documents.py`);
  do not add real-world forms to the repository.

## Images on forms (first-party only)

Respondents' browsers never contact a third-party image host. Every image a
form holds (theme and page-theme backgrounds, welcome/ending images, page
layout and question images, the cover) and every saved theme's background is
one of ours; `services/image_urls.py` is the single allow-list:

- **Our storage** (`AWS_PUBLIC_URL` or the endpoint, our bucket, `public/`,
  `media_library/`, `images/`) and the builder's two built-in placeholders.
- **Unsplash through our server:** a form stores an Unsplash photo by its
  canonical address, `https://images.unsplash.com/<photo>` (as the picker and
  the AI image search give it), which names no host of ours, so it stays right
  on every instance and domain. The webapp loads it through its own API at
  render time (`<NEXT_PUBLIC_API_ENDPOINT_HOST>/images/unsplash/<photo>`,
  `src/utils/first-party-image.ts`, every render path including the link
  preview's cover). The backend never writes an API host into a form: an
  address of the route on any host (`<anything>/images/unsplash/<photo>`) is
  stored as the canonical Unsplash one (`unsplash_route.to_canonical_url`).
  The backend itself shows form images to nobody (no e-mail or export carries
  them); API and MCP output return the canonical address.
  The route, `GET /images/unsplash/{photo}` (`services/image_service.py`,
  `services/unsplash_route.py`), takes a photo path and only
  `w h q fit fm crop auto` (rounded to a fixed set of sizes, AVIF asked as
  WebP, `crop` only `entropy`), fetches from the fixed host with no redirects,
  has the sandbox's `image` mode re-encode it, stores it once under
  `public/image-cache/unsplash/<hash>` and redirects there. Rate-limited per
  client address (`API_IMAGE_PROXY_*`; IPv6 by /64,
  `utils/client_ip.rate_limit_key`), tighter for requests that fetch, plus one
  cap on fetches by everyone together (`API_IMAGE_PROXY_GLOBAL_FETCHES_PER_WINDOW`).
- **Pasted addresses are copied in:** `POST /workspaces/{id}/images/import`
  (`form.edit`, `API_IMAGE_IMPORTS_*` per person) fetches through
  `services/image_fetch.py` (https only, default port, no credentials; DNS
  resolved by us and every answer must be public, the connection pinned to
  that address; at most 3 redirects, each re-checked; timeouts; 10 MB read
  while streaming; JPEG/PNG/WebP only), re-encodes in the sandbox and stores
  under `public/media/<workspace>/`. Refusals are 422 `{code, message}` with a
  plain-language message the editor shows; logs carry the code, never the
  address.
- **Saves are checked** (`services/form_images.py`): the whole-form PATCH, form
  creation and the saved-themes PATCH keep first-party addresses (canonical
  Unsplash ones included), store route addresses as canonical Unsplash ones,
  keep an address the stored draft (or stored themes) already holds, and
  refuse anything else with 422 `image_not_allowed`; a template copy and a
  duplicate drop it instead. Tests: `test_image_urls.py`, `test_image_fetch.py`,
  `test_images.py`, `test_form_images.py` (no network: fetch, DNS and the
  sandbox are faked).

## Registration of submissions (case systems)

Behind `OPEN_FORMULIEREN_REGISTRATION=on|off` (default off; `config/registration_settings.py`, read at call time
through `services/registration/mode.py`). A workspace's admins register **services** (https address, encrypted
write-only secret) and per form choose the **variables** sent as a Generic JSON body; each submission writes a
**delivery** row (ids, status, counters, our error code: never answers) and queues the procrastinate job
`register_submission(delivery_id)`. Docs: `docs/open-formulieren-registration.md`. Rules to keep:

- Code in `services/registration/` (`client.py` the one outgoing call, `body.py` the body, `service.py` the logic),
  tables `registration_services`, `form_registrations`, `registration_deliveries` (revision 0023), router
  `controllers/registration_router.py`. It is Postgres-only and runs on the backend jobs worker, never the actions
  executor.
- The request path (`WorkspaceFormService.submit_response`) only inserts the row and defers the job by id; it never
  calls out and never fails the submission. Answers are decrypted only inside `RegistrationService._attempt`.
- Outbound calls go through `services/safe_http.py` rules (shared with `image_fetch.py`): https, port 443, every
  resolved address public, the connection pinned to the checked address, no redirects, size and time caps. Never add an
  http/private-address allowance or a second HTTP path; tests swap `client.resolve`, `client.network_backend` and
  `client.ssl_context` (`tests/app/registration/tls_server.py`).
- The secret is write-only (`services/registration/secrets.py`: Fernet, bound to workspace and service); no response,
  log, job argument or delivery record may carry it, an answer, a body, an address or the destination's text.
- Switch off: endpoints answer 410 `registration_off` (except `/registration/status`), nothing is queued, the jobs and
  sweeps do nothing; saved settings and rows stay. A new registration endpoint calls `refuse_when_off()` first and
  gets a row in `tests/app/registration/test_permissions.py`.

## Cross-service integration points

- **Auth:** `services/auth_service.py` — OAuth state + OTP, JWT via `common.services.jwt_service`; sessions in
  `services/session_service.py` (below); cookies via `auth_cookie_service.py`. The auth service's API is internal-only (#766): every
  call to `settings.auth_settings.BASE_URL`/`CALLBACK_URI` passes `headers=auth_service_headers(...)`
  (`services/internal_auth.py`, the shared `AUTH_INTERNAL_NOTIFY_KEY`); `tests/app/services/test_auth_call_sites.py`
  fails on a call without it. Never add the key to a shared client — it also calls third parties.
- **Sessions** (`services/session_service.py`, `sessions` collection, identity group): every sign-in
  (`SessionService.start`: OTP, Google basic sign-in) creates a session whose id is the tokens' `sid`.
  Tokens carry `typ` (`access`/`refresh`); an access token is accepted without a database read only with `typ=access`
  and a `sid`, so `AUTH_ACCESS_TOKEN_EXPIRY_IN_MINUTES` (default 15; never the old 43200) bounds how long a revoked
  session keeps working. The refresh path (`get_logged_user` when the access token expired, and `POST /auth/refresh`)
  needs the session live and unexpired and auth's `/auth/status` to know the user (404 revokes the session); a failed
  refresh is `SessionEnded` (401, the handler clears both cookies). Only `POST /auth/refresh` rotates the refresh
  token (new `jti`, same `sid`): server-side rendering forwards cookies and drops `Set-Cookie`, so the implicit refresh
  must not. The jti a rotation replaced gets an access token only (never a refresh token) for
  `AUTH_REFRESH_REUSE_GRACE_SECONDS` (60); any other old jti is a replay and revokes the session. Every
  refresh that does not rotate re-checks the session after asking auth (`touch` must match a live row). Re-issuing tokens inside a session (plan
  change, import OAuth) only sets a new access token for the same `sid`. Revocation: `GET /auth/logout`,
  `GET/DELETE /auth/sessions[/{sid}]`, `SessionService.revoke_all_for_user` (requesting account deletion; the
  hook for deprovisioning); the deletion itself deletes the rows. Expired rows go through a Mongo TTL index on
  `expires_at` and `delete_expired` on the list/revoke-all paths (there is no periodic job). The user-deletion job
  names its user by an encrypted `UserDeletion` (user id + email), never by a stored token; `DELETE /auth/user`
  (Temporal) needs the API key and that request in `X-User-Deletion`. Tokens without `sid` (before sessions) are refused: those users sign in once more. The
  `blacklisted_refresh_tokens` table is unused and kept until a later release drops it. After sign-in the redirect
  goes only to this instance's origins (`services/login_redirect.py`: `API_CLIENT_URL` + `allowed_origins`).
- **Jobs:** `services/temporal_service.py` starts the three background jobs — user deletion, scheduled response
  deletion (at the response's expiration), action-code execution — as procrastinate jobs on Postgres (default;
  `backend/jobs/tasks.py`; per job kind `JOBS_BACKEND__<job>=temporal` selects the Temporal workflow; `run_action` is deferred by name and
  executed by `temporal/actions-executor`). See `docs/postgres-cutover-runbook.md`.
  The workers call back into the internal job routes (`/temporal/*`, action update, template preview,
  `DELETE /auth/user`) with the `api-key` header, checked by `get_api_key` (`user_service.py`) against
  `TEMPORAL_API_KEY` (`services/internal_job_key.py`): **503** while it is unset, empty or the old
  `random_api_key`, **403** when wrong, constant-time compare. A new worker-only route takes
  `Depends(get_api_key)`; tests in `tests/app/controllers/test_internal_job_key.py`.
- **Provider plugins:** `plugin_proxy_service.py` forwards standardized requests to the external provider
  microservices (:8003 / :8002).
- **Third-party services:** `aws_service.py` (S3), `stripe_service.py`, `openai_service.py` (prompts/AI form gen),
  `umami_client.py` + `analytics_service.py`. `event_service.py` posts platform events (sign-up, upgrade,
  account deletion, ...) to the optional `EVENT_WEBHOOK_URL` with the event type and user id only: never an
  email address or other personal data.

## Run / test

```bash
./run.sh                 # uvicorn backend.app:get_application --reload :8000  (needs Postgres up first)
uv sync                  # install (uv, never pip/poetry)
DATABASE_URL=postgresql+asyncpg://bettercollected:bettercollected@localhost:5432/bettercollected_test uv run pytest
# without Mongo, as the CI shards run it (a fresh install has MONGO_URI empty):
MONGO_URI="" uv run pytest -m "not mongo"
uv run pytest -m mongo                   # the import tests: need a Mongo server (MONGO_URI)
uv run pytest -n 4 --dist loadgroup      # in parallel (CI): each xdist worker gets <db>_gwN in Mongo and Postgres
uv run alembic -c alembic.ini upgrade head   # as the service role (bc_app), see backend/.env.example
DB_AUTO_MIGRATE=true ./run.sh                # or: migrate app + jobs schemas at startup (advisory-locked)
python -m backend.jobs.worker                # procrastinate worker (JOBS_BACKEND=postgres, the default)
```
Prod entry: `backend serve` CLI → gunicorn with uvicorn workers.

## Gotchas

- **CORS is dynamic** (`DynamicCORSMiddleware`) driven by the `allowed_origins` table (Postgres) — a new host must be
  stored there (`python -m backend.seed_refdata --origin ...` on an empty table) or requests are blocked.
  A workspace's custom domain is added only while it is verified (`services/custom_domain_origins.py`, the one
  place that adds or removes those origins) and stale ones are pruned at startup.
- **Respondent identity** (anonymous responses): never compare or store `hash_string(email)`; use
  `utils/respondent_identity.py` (`identity_of`, `matches`: `v2:` HMAC under `RESPONDENT_IDENTITY_KEY`, no MD5
  fallback). The API refuses to start without the key; `identity_rekey.py` converts stored values. Details:
  `docs/respondent-identity.md`.
- Startup/shutdown hooks in `asgi.py` create/close the aiohttp client and the Postgres engine — respect that
  lifecycle when adding global resources (register them in the container, close them on shutdown).
- Settings come from the aggregated `settings` object in `config/`; add new config there rather than reading `os.environ`
  scattered through services.
- **Client addresses and rate limits:** read a client's address with `utils/client_ip.request_client_ip(request)`,
  never a raw header, and never log it. The logic is the pure `common/utils/client_ip.resolve_client_ip(peer,
  forwarded_for, cf_connecting_ip, trusted_proxies, cloudflare_ips)` (reusable by other services; the backend module
  re-exports it). The default trusts no proxy: the TCP peer is the client. Only when the peer is inside
  `TRUSTED_PROXIES` (alias `API_TRUSTED_PROXIES`; comma-separated IPs/CIDRs, IPv4 and IPv6) is X-Forwarded-For walked
  from the right, skipping trusted proxies, taking the first untrusted hop (never the left-most entry); when that hop
  is a Cloudflare edge (`API_TRUST_CLOUDFLARE`, default on; ranges built in as `CLOUDFLARE_IPS`, dated, overridable with
  `API_CLOUDFLARE_IPS`) the client is `CF-Connecting-IP`. Garbage never raises; it falls back to the last readable
  hop. Private ranges are NOT trusted implicitly (a container on the overlay could forge the headers). Counters
  key IPv6 by /64 (`rate_limit_key`). `services/rate_limiter.FixedWindowRateLimiter` counts requests per scope, client and window in
  `rate_limit_counters` (analytics group, twin revision 0013), shared by every replica; counter ids are keyed hashes,
  so no address is stored. The public `flow-events` endpoint uses it (#767), per /64 for IPv6, and deletes events after
  `API_FLOW_EVENTS_RETENTION_DAYS` (395): a Mongo TTL index on `created_at`, and for Postgres a sweep on the write path
  (`FlowEventService._sweep_expired`, at most every 6 h per process, using the existing `created_at` index).
