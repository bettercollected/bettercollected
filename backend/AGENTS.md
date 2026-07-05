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
