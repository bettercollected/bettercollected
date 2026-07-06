# AGENTS.md

Guidance for AI coding agents (Claude Code and others) working in the **bettercollected** monorepo.
Read this first. Service-specific `AGENTS.md` files live in [backend/AGENTS.md](backend/AGENTS.md),
[webapp/AGENTS.md](webapp/AGENTS.md), [auth/AGENTS.md](auth/AGENTS.md), and [temporal/AGENTS.md](temporal/AGENTS.md) —
the closest file to the code you're editing wins. Deep architecture lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## What this project is

**bettercollected** is a **privacy-friendly form builder SaaS**. Its differentiator: a form creator declares a
*purpose* for data collection that responders consent to before submitting, and responders can later view their
submission and request its deletion (GDPR-style). It is multi-tenant (workspaces), has a native drag-and-drop form
builder, and can **import forms + responses from Google Forms and Typeform**.

Public site: https://bettercollected.com · License: see [LICENSE](LICENSE).

## The shape of the repo (polyglot microservices monorepo)

| Path | Stack | Port | Role |
|---|---|---|---|
| [webapp/](webapp/) | Next.js 14 + TS, Redux Toolkit / RTK Query | 3000 | All UI: builder, dashboards, responder portal, billing |
| [backend/](backend/) | FastAPI + Beanie (MongoDB) | 8000 | Core API — the hub everything routes through |
| [auth/](auth/) | FastAPI + fastapi-users + Stripe | 8001 | Identity (OAuth / email-OTP / JWT) + Stripe billing |
| [integrations/google/](integrations/google/) | FastAPI + Google APIs | 8003 | Google Forms/Drive/Sheets provider microservice |
| `integrations/typeform/` | FastAPI (Typeform APIs) | 8002 | Typeform provider microservice — **not checked out in this clone** |
| [temporal/worker/](temporal/worker/) | temporalio + Selenium | — | Background jobs: imports, deletions, template previews |
| [temporal/csv-worker/](temporal/csv-worker/) | temporalio | — | CSV export of responses |
| [temporal/actions-executor/](temporal/actions-executor/) | temporalio | — | Runs user-defined form-action code |
| [common/](common/) | Python package (Beanie/JWT/crypto) | — | Shared models/enums/services for all Python services |

**Infra** (via `docker-compose.local.yml` / `docker-compose.deployment.yml`): **MongoDB** (app data),
**PostgreSQL + Temporal server** (workflow engine), **Redis**, **nginx** (routes the admin / client / custom-domain
hosts), **Umami + its own PostgreSQL** (self-hosted product analytics, admin UI on `:3003` — see
`backend/AGENTS.md` "Analytics (Umami)" and `plans/umami-self-hosted-form-analytics.md`).

> Note: `integrations/typeform/` and `common/` are referenced by build scripts but live in separate repos /
> are vendored per service. Only `integrations/google` and a top-level `common/` are present in this checkout.
> Typeform's OAuth *login* also lives inside `auth/`, distinct from the Typeform *import* microservice.

## Two architectural ideas you must understand before editing

1. **Provider plugin/proxy pattern.** [common/common/constants/plugin_routes.py](common/common/constants/plugin_routes.py)
   defines a standard route contract (`/{provider}/oauth/*`, `/{provider}/forms`, `/{provider}/import`,
   `/{provider}/forms/{id}/responses`). The backend's `plugin_proxy` controller forwards these to the matching
   provider microservice (google :8003, typeform :8002). Each provider converts its native format into the shared
   **StandardForm**. Adding a provider = implementing that contract in a new microservice + registering a plugin config.

2. **StandardForm — one model for imported and native forms.**
   [common/common/models/standard_form.py](common/common/models/standard_form.py) is the core domain object: rich
   native field types, themes, layouts, and an embedded **Consent**. Whether a form was built in-app or imported, it
   becomes a StandardForm. Don't invent parallel form representations.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for request-level data flow.

## Layering conventions

- **Python (FastAPI) services** follow `fastapi-mvc`: **Controllers** (class-based via `classy-fastapi`) →
  **Services** (business logic, wired by `dependency-injector`) → **Repositories** → **Beanie Documents** (MongoDB).
  Put business logic in services, DB access in repositories, HTTP shape in controllers. Do not query Mongo from a controller.
- **Frontend** is Redux Toolkit + **RTK Query** for all server state (~16 API slices, all against `/api/v1`), plain
  slices + Jotai for client state. Add server calls as RTK Query endpoints, not ad-hoc `fetch`.

## Directory nesting gotcha

Python services double-nest the package: the FastAPI code for `backend` lives at **`backend/backend/app/…`**
(and `auth/auth/app/…`, `integrations/google/googleform/app/…`). The outer dir holds `pyproject.toml`, `run.sh`,
`Makefile`; the inner dir is the importable package. Paths matter — check before assuming.

## Environment & setup

- **Prereqs:** Python **3.10** (exact — services pin `python3.10`), **Poetry**, **Node 16.18+**, **Yarn 1.x**, Docker.
- **One-shot setup:** `./install.sh` (Poetry install for Python services + `yarn` for webapp; skips missing dirs).
- **Env file:** copy/fill `.env.deployment` (keys: `MONGO_URI`, `AUTH_JWT_SECRET`, `AUTH_AES_HEX_KEY`, Stripe,
  Google/Typeform OAuth, `TEMPORAL_SERVER_URL`, mail, encryption keysets). Each service also reads its own `.env`.

## Run / build / test commands

**Everything at once (local):**
```bash
docker compose -f docker-compose.local.yml up --build -d   # mongo + seed data (run FIRST — all services need Mongo)
./run-locally.sh                                            # runs the 6 services in parallel via each service's run.sh
```

**Per Python service** (from the service's outer dir, e.g. `backend/`):
```bash
./run.sh                       # uvicorn with reload (backend :8000, auth :8001, google :8003)
make install                   # poetry install
make test                      # unit + integration tests (pytest)
make unit-test | make integration-test | make coverage
make format                    # black
poetry run flake8 .            # lint (flake8 + docstrings + import-order)
```

**Temporal workers** (from e.g. `temporal/worker/`): venv-based, not Poetry —
`python3.10 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`, then `./run.sh`.

**Webapp** (from `webapp/`):
```bash
yarn                # install
yarn dev            # dev server on :3000 (dev-4000 for :4000)
yarn build          # production build (+ next-sitemap postbuild)
yarn lint           # next lint
yarn lint:fix       # eslint --fix
yarn format:check   # prettier --check
yarn test           # jest (watch mode) + Testing Library + MSW
yarn storybook      # component explorer on :6006
```

## Code style & quality gates

- **Python:** `black` (line length 88) + `flake8` (docstrings, import-order, TODO). Each Python service has a
  `.pre-commit-config.yaml` — run `pre-commit install` and commit **via the terminal** (IDE commit UIs swallow the
  pre-commit failure output). CI runs Schemathesis API contract tests (`.github/workflows/test-schemathesis.yml`).
- **Frontend:** ESLint + Prettier with import sorting, run through `lint-staged`. TypeScript strict-ish; prefer typed
  RTK Query hooks over untyped fetches.

## Things to be careful about

- **Feature flags everywhere.** `webapp/next.config.js` `publicRuntimeConfig` + `ENABLE_*` env vars gate builder V2,
  Google, Typeform, CSV export, response editing, etc. A feature may be code-complete but flagged off — check the flag
  before assuming behavior.
- **Multi-host routing.** The webapp serves three logical hosts (admin `:3000`, client `:3001/{workspace_handle}`,
  custom domain `:3002`) behind nginx; `allowed_origins` in Mongo controls CORS. Custom-domain and workspace routing
  are load-bearing — see [docs/DEVELOPERS_GUIDE.md](docs/DEVELOPERS_GUIDE.md).
- **Auth is cookie-based** with a mutex-guarded silent refresh-token flow ([webapp/src/store/customFetchBase.ts](webapp/src/store/customFetchBase.ts)).
  Blacklisted refresh tokens are stored in Mongo. Don't move auth to header/localStorage tokens without understanding this.
- **Long/durable work goes to Temporal**, not inline request handlers: imports, response/user deletion (the privacy
  promise), CSV export, preview screenshots, action-code execution. Add such work as a workflow, not a blocking call.
- **Encryption.** OAuth credentials and secrets are encrypted with Tink / AES keysets (`MASTER_ENCRYPTION_KEYSET`,
  `*_AES_KEY`). Never log or persist decrypted tokens.
- **`common` is shared.** A change to a model/enum/service in `common/` affects backend, auth, and integrations at once.
  Verify all consumers, not just the one you're touching.

## When you finish a change

1. Run the relevant service's tests + lint/format (commands above).
2. If you touched an API shape, remember Schemathesis and the webapp RTK Query slice that consumes it — keep them in sync.
3. If you touched `common/`, check every Python service that imports the changed symbol.
4. Don't commit or push unless asked. Branch off `develop` (the main branch) for new work.
