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
      schedulers/     # APScheduler jobs (form_schedular.py)
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

## Data / MongoDB

Beanie Documents are registered in [backend/app/handlers/database.py](backend/app/handlers/database.py) `init_db`'s
`document_models` list — **a new collection must be added there or it won't be initialized.** Core domain models
(`User`, `StandardForm`, `StandardFormResponse`, `Consent`) come from the shared `common` package, not from here.
APScheduler uses a separate DB (`init_scheduler_db`).

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
  login `admin`/`umami` — change it). Create a website there, copy its id into `UMAMI_WEBSITE_ID`.
- **Config** (`config/UmamiSettings.py`, env prefix `UMAMI_`): `URL`, `USERNAME`, `PASSWORD`, `WEBSITE_ID` — all four
  required. `UmamiClient.authenticate()` checks `settings.umami_settings.is_configured` up front and raises a clean
  503 ("Analytics is not configured on this instance.") instead of attempting a doomed login — check this first if
  the analytics endpoints 503 unexpectedly.
- **Gotcha this file already tripped on:** the app's custom `HTTPException` (`app/exceptions/http.py`) takes a
  `content=` kwarg, not FastAPI's `detail=` — passing `detail=` raises a `TypeError` instead of the intended clean
  error. Already fixed in `umami_client.py`; keep this in mind if you add more raises there.
- Canonical path construction (`form_url = f"/{workspace_name}/forms/{slug}"`) must stay in sync with the webapp's
  `trackCanonicalFormView` helper (`webapp/src/lib/analytics/umami.ts`) — both sides hard-code the same shape so
  custom-domain and client-host traffic land under one path.
- Deployment: `docker-compose.deployment.yml`'s `backend` service sets `UMAMI_URL=http://umami:3000` (internal
  docker network) automatically — only `UMAMI_USERNAME`/`UMAMI_PASSWORD`/`UMAMI_WEBSITE_ID` need to come from
  `.env.deployment`.

## Cross-service integration points

- **Auth:** `services/auth_service.py` — OAuth state + OTP, JWT via `common.services.jwt_service`; refresh-token
  blacklist in Mongo; cookies via `auth_cookie_service.py`.
- **Temporal:** `services/temporal_service.py` connects to the Temporal server, creates **Schedules**, and starts
  workflows (form import, CSV export, response/user deletion, action code). On startup `migrate_schedule_to_temporal()`
  can migrate legacy APScheduler jobs (gated by settings).
- **Provider plugins:** `core/plugins/{google,typeform}.py` behind `plugin_proxy_service.py` — forwards standardized
  requests to the external provider microservices (:8003 / :8002).
- **Third-party services:** `aws_service.py` (S3), `stripe_service.py`, `openai_service.py` (prompts/AI form gen),
  `brevo_service.py` (email/events), `umami_client.py` + `analytics_service.py`.

## Run / test

```bash
./run.sh                 # uvicorn backend.app:get_application --reload :8000  (needs Mongo up first)
make install             # poetry install
make test                # unit + integration
make unit-test | make integration-test | make coverage
make format              # black
poetry run flake8 .      # lint
```
Prod entry: `backend serve` CLI → gunicorn with uvicorn workers.

## Gotchas

- **CORS is dynamic** (`DynamicCORSMiddleware`) driven by the `allowed_origins` Mongo collection — a new host must be
  seeded there (see root docs / `seed-data.js`) or requests are blocked.
- Startup/shutdown hooks in `asgi.py` create/close the aiohttp client and Mongo client and init Beanie — respect that
  lifecycle when adding global resources (register them in the container, close them on shutdown).
- Settings come from the aggregated `settings` object in `config/`; add new config there rather than reading `os.environ`
  scattered through services.
