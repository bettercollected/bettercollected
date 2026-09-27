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
      repositories/   # data access wrapping Beanie documents
      schemas/        # Beanie Document definitions == MongoDB collections
      models/         # DTOs (dtos/), dataclasses/, enum/, types/, filter_queries/
      core/           # provider plugin system: base/, factory/, loader/, plugins/{google,typeform}.py
      handlers/       # startup wiring: database.py (Beanie init), logging
      middlewares/    # DynamicCORSMiddleware, timing
      schedulers/     # form_schedular.py: re-import + expired-response deletion, called by workers via /temporal
      jobs/           # procrastinate app, tasks, worker and schema entrypoints (JOBS_BACKEND=postgres)
      container.py    # dependency-injector AppContainer (wires repos -> services)
      router.py       # aggregates all routers into root_api_router
      asgi.py         # get_application() app factory
    config/           # settings: api, auth, database, temporal, aws, brevo, redis, sentry, apm, openai, umami
    cli/              # `backend serve` -> gunicorn+uvicorn (prod)
    tests/
```

## Request layering (follow this — don't shortcut it)

`Controller (HTTP shape) → Service (business logic) → Repository (Mongo access) → Beanie Document`

- New endpoint: add a method to the relevant Routable in `controllers/`, decorated appropriately; put logic in a
  `services/` class; do all Mongo access through a `repositories/` class. Wire new services/repos in `container.py`.
- Never query Beanie directly from a controller.

## Adding a route

Routers are registered in [backend/app/router.py](backend/app/router.py) via the `@router(...)` decorator
(classy-fastapi Routables) or `register_plugin_class` (the plugin proxy). Follow an existing controller
(e.g. `workspace_forms.py`) as a template — constructor injection, `self.router` methods, camelCase response models.

## Persistence (MongoDB → PostgreSQL, in progress)

Application data lives in MongoDB (Beanie Documents) **and** is moving to PostgreSQL (`app-postgres`, schema `app`);
plan and decisions in `plans/postgres-consolidation.md`. What that means when you touch data code:

- **Every repository is routed.** The container hands out `RoutingRepository` proxies over a Mongo implementation and
  its Postgres *twin* (`app/repositories/postgres/*.py`, one class per Mongo repository, same public methods —
  `tests/app/repositories/test_postgres_surface.py` enforces it). Repositories are grouped (`refdata`, `identity`,
  `forms`, `responses`, `actions`, `ai`, `analytics`); `DB_READ_SOURCE__<group>` / `DB_WRITE_MODE__<group>`
  (`mongo|dual|postgres_primary_dual|postgres`) choose the store per group, flips are restarts, and
  `backend/db/groups.py` declares the cutover order the flags enforce at boot.
- **Adding or changing a repository method:** implement it on both the Mongo class and the twin, mark writes
  `@write_op` (`tests/app/repositories/test_write_markers.py` checks the AST), and `@write_op(replay=True)` for a write
  that mints state the caller didn't pass in (a new document's id, a token) — the mirror then stores the returned
  document instead of re-running the call. Return the *document* from such writes, not a DTO (`WriteResult` when the
  return value must differ from what was stored). Relation documents get `derived_object_id` so both stores agree.
- **Joins:** SQL joins only within a group; a `$lookup` into another group's collection is *composed* through that
  group's routed repository (see `postgres/forms.py`). Never query Mongo or Postgres from a service or controller.
- **Rows:** `backend/db/models.py` — one table per collection, typed spine columns `GENERATED` from the `doc` JSONB
  (query only spine columns; add one + an Alembic revision under `backend/migrations/` when a query needs a new
  field). Migrations run as the service role (`bc_app`), never as the superuser.
- **Mirror failures** land in the outbox (`mirror_write_failures`, Mongo doc or Postgres row — whichever store is
  primary); shadow-read diffs and counters are exposed on `GET /persistence/status` (admin) and the effective flags
  are logged at boot.
- **Migration CLI:** `python -m backend.migrate {preflight,backfill,verify,reconcile,status,jobs-sweep}` (auth and
  google have `python -m auth.migrate` / `python -m googleform.migrate`), the engine in `common/db/migrate/`. Raw
  pymongo + SQLAlchemy Core, never Beanie, never decrypts. Backfill is resumable (checkpoints in `migration_progress`,
  adaptive batches, `--max-minutes`, advisory lock) and never overwrites a row the application wrote
  (`_bc_source = 'app'`); `verify` compares counts, per-row checksums and a sampled round-trip; `reconcile` fixes
  drift with Mongo authoritative (`--direction postgres->mongo` for the fallback) and drains the outboxes.
- **Tests run three ways in CI** (Mongo · everything mirrored · everything served from Postgres). Parity tests
  (`tests/app/repositories/test_*_parity.py`) run each method on both stores; test fixtures must go through
  `container.<repo>()`, never Beanie directly, or the Postgres-served mode fails.

Beanie Documents are registered in [backend/app/handlers/database.py](backend/app/handlers/database.py) `init_db`'s
`document_models` list — **a new collection must be added there or it won't be initialized** (and needs a row +
twin as above). Core domain models (`User`, `StandardForm`, `StandardFormResponse`, `Consent`) come from the shared
`common` package, not from here.
Background jobs go through `services/temporal_service.py`, which dispatches per job kind (`JOBS_BACKEND__<job>`)
to a Temporal workflow (default) or a procrastinate job on Postgres (`backend/jobs/`; worker:
`python -m backend.jobs.worker`, queue tables in the `jobs` schema via `python -m backend.jobs.schema`).

Response `answers` **and** `hidden_fields` (captured URL parameters, see `StandardForm.hidden_fields` for the
declared names) are encrypted at rest via `crypto_service` in `form_response_repository.save_form_response` and
decrypted in `form_response_service.decrypt_form_response` — any new respondent-data field on
`StandardFormResponse` must go through the same two choke points. Answer piping itself is resolved entirely
client-side (webapp `src/utils/answer-piping.ts`); the backend only stores the pipe nodes inside field titles.

**Internal fields** (`StandardFormField.internal`, "for office use only"): staff fill them in on each submission
afterwards; values live in `StandardFormResponse.internal_answers` (encrypted like `answers`, decrypted in
`decrypt_form_response`) with `internal_answers_meta` recording who changed each one and when
(`PATCH /workspaces/{id}/forms/{form_id}/submissions/{response_id}/internal-answers`, any active workspace member).
Rules live in `services/internal_fields.py`: every form payload served to a non-member goes through
`strip_internal_fields`, every respondent-facing response through `strip_internal_answers`, respondent submissions
never store internal values (they are dropped, not rejected, so a field made internal mid-fill doesn't fail
anyone's submission), on-submit actions get the stripped form, and logic (visibility/jumps) may not depend on an internal field (form save and
AI ops both refuse it). `validations.required` on an internal field is stored but not enforced (there is no
staff-side "complete" state yet). A new endpoint that returns a form or a response to respondents must use the
same two strip helpers.

## Seed scripts

`backend/scripts/` holds idempotent seed scripts that populate collections a fresh (or already-running) environment
needs but that don't belong in a migration. Pattern to follow for new ones: a reusable `async def seed_x(...)`
function that assumes Beanie is already initialized (so it can be called from `lifespan` on every boot), plus a thin
`_main()`/`if __name__ == "__main__":` CLI wrapper that creates its own Mongo client for one-off manual runs. Never
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
  survive restarts.
- To add a template: write a new zero-arg builder function returning `{title, description, category, fields}` (see
  `support_triage()`/`lead_qualification()` for the shape) and add it to `TEMPLATE_BUILDERS`.
- To force a re-seed of a changed template, delete it from `form_templates` first (by title) — the next restart (or
  a manual run) recreates it.
- Manual one-off run (e.g. without restarting the app): `uv run python -m scripts.seed_flow_templates` from `backend/`.
- **Gotcha this script already tripped on:** `PydanticObjectId` fields don't validate an *empty string* the way you'd
  expect from an "unset" env var — double-check with a real value, not just `KEY=` in `.env`, if the gallery stays
  empty.

## Analytics (Umami)

Form-view analytics (`FormAnalyticsRouter` — `/{workspace_name}/forms/{slug}/{stats,pageviews,metrics}`) proxy a
self-hosted [Umami](https://umami.is) instance via `services/umami_client.py`. It used to default to a
BetterCollected-hosted Umami; that's gone — see `plans/umami-self-hosted-form-analytics.md` for the full rationale
and architecture.

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
- Deployment: `docker-compose.deployment.yml`'s `backend` service sets `UMAMI_URL=http://umami:3000` (internal
  docker network) automatically — only `UMAMI_USERNAME`/`UMAMI_PASSWORD`/`UMAMI_WEBSITE_ID` need to come from
  `.env.deployment`.

## PDF form import (in progress)

`POST /workspaces/{id}/form-imports` (multipart `file`) turns an uploaded PDF or
photo of a form into a draft form; `GET …/form-imports/{import_id}` reports
progress. Code: `app/services/pdf_import/` (stages), `app/services/pdf_import_service.py`
(start, limits, dispatch), `app/controllers/pdf_import_router.py`.

- **Isolated sandbox in deployment (#703):** the `document-sandbox` compose service
  (same image, `pdf_import/server.py`) runs as `nobody` with no network, a
  read-only filesystem, no capabilities and no env file; backend and jobs worker
  reach it over `PDF_IMPORT_SANDBOX_SOCKET` with `PDF_IMPORT_REQUIRE_ISOLATED_SANDBOX=true`.
  `server.py` and `runner.py` must never import the backend package. Native modes
  (`render`) never run in a local child. An unreachable or unresponsive sandbox
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
  the API or worker process directly. Native rendering needs stronger isolation
  first (separate user, no network, syscall filter).
- **Licences:** pypdf (BSD), pdfplumber/pdfminer (MIT), pypdfium2 (BSD/Apache),
  Pillow. Do not add PyMuPDF (AGPL) or GPL converters.
- **The draft form is created at upload**, and the original is stored under
  `private/<workspace>/<form>/imports/<import>/`, so deleting the form deletes it.
  Import records are deleted with their forms (`WorkspaceFormService`).
- **Stages checkpoint** on the import record (`stages`); a retried job skips
  finished ones. Runs on procrastinate with `JOBS_BACKEND__import_form=postgres`,
  otherwise as a background task in the API process.
- **AI needs consent per import:** nothing from an uploaded document (page text,
  layout text, page images) goes to an AI provider unless the uploader sent
  `ai_consent=true` with that upload (stored with `ai_consent_at`/`_by`). Without it
  `_structure` passes no provider and only the deterministic structuring runs. The
  workspace AI opt-in (#715) will be required on top of it.
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
  `PDF_IMPORT_OPENAI_MODEL`, default `gpt-6-luna`) for questions that reference those
  ids. Labels are rebuilt from the referenced words; invalid answers are retried once,
  then the page is structured deterministically. Result: `fdm.json`. Tests never call
  a real provider (autouse fixture in `tests/app/pdf_import/conftest.py`).
- **Compile** (`pdf_import/compile.py`) turns `fdm.json` into the draft form with explicit
  redesign rules (pages per section, other+specify and follow-up visibility, verbatim
  statements and a terms page, typed-name signatures, B.S./A.D. as two dates, location
  questions, tables as rows of fields for now) and the brand theme from section-bar
  colours (darkened to WCAG AA for white text). Built from an empty form through
  `apply_form_ops` and saved once, so a retry is idempotent. Every applied rule, drop,
  interim mapping and staff-only part is listed in `report.compile`.
- **Artifacts:** stage outputs (`text.json`, `layout.json`, `pages/<n>.png`, `fdm.json`) are stored next to the original
  in the form's private folder, so they are deleted with the form.
- Limits and the default model: `PDF_IMPORT_*` (`config/pdf_import_settings.py`).
- Tests generate their own documents (`tests/app/pdf_import/documents.py`);
  do not add real-world forms to the repository.

## Cross-service integration points

- **Auth:** `services/auth_service.py` — OAuth state + OTP, JWT via `common.services.jwt_service`; refresh-token
  blacklist in Mongo; cookies via `auth_cookie_service.py`.
- **Jobs:** `services/temporal_service.py` starts the three background jobs — user deletion, scheduled response
  deletion (at the response's expiration), action-code execution — on Temporal (default) or, per job kind via
  `JOBS_BACKEND__<job>=postgres`, as procrastinate jobs (`backend/jobs/tasks.py`; `run_action` is deferred by name and
  executed by `temporal/actions-executor`). See plans/postgres-consolidation.md §7.
- **Provider plugins:** `core/plugins/{google,typeform}.py` behind `plugin_proxy_service.py` — forwards standardized
  requests to the external provider microservices (:8003 / :8002).
- **Third-party services:** `aws_service.py` (S3), `stripe_service.py`, `openai_service.py` (prompts/AI form gen),
  `brevo_service.py` (email/events), `umami_client.py` + `analytics_service.py`.

## Run / test

```bash
./run.sh                 # uvicorn backend.app:get_application --reload :8000  (needs Mongo up first)
uv sync                  # install (uv, never pip/poetry)
DATABASE_URL=postgresql+asyncpg://bettercollected:bettercollected@localhost:5432/bettercollected_test uv run pytest
# the same suite mirrored / served from Postgres (what CI runs):
DB_WRITE_MODE=dual ... uv run pytest
DB_READ_SOURCE=postgres DB_WRITE_MODE=postgres ... uv run pytest
uv run alembic -c alembic.ini upgrade head   # as the service role (bc_app), see backend/.env.example
python -m backend.jobs.worker                # procrastinate worker (JOBS_BACKEND=postgres)
```
Prod entry: `backend serve` CLI → gunicorn with uvicorn workers.

## Gotchas

- **CORS is dynamic** (`DynamicCORSMiddleware`) driven by the `allowed_origins` Mongo collection — a new host must be
  seeded there (see root docs / `seed-data.js`) or requests are blocked.
- Startup/shutdown hooks in `asgi.py` create/close the aiohttp client and Mongo client and init Beanie — respect that
  lifecycle when adding global resources (register them in the container, close them on shutdown).
- Settings come from the aggregated `settings` object in `config/`; add new config there rather than reading `os.environ`
  scattered through services.
