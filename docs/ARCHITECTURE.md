# Architecture

Deep reference for how bettercollected fits together. For day-to-day agent guidance see the root
[AGENTS.md](../AGENTS.md); for setup/run see [DEVELOPERS_GUIDE.md](DEVELOPERS_GUIDE.md).

## System diagram

```
                          ┌─────────────────────────────────────────────┐
   Browser  ── nginx ──►  │  webapp (Next.js 14, :3000)                  │
   (admin :3000,          │  Redux Toolkit + RTK Query, cookie auth      │
    client :3001,         └───────────────┬─────────────────────────────┘
    custom :3002)                         │  /api/v1  (cookies, credentials: include)
                                          ▼
                          ┌─────────────────────────────────────────────┐
                          │  backend (FastAPI, :8000)  — CORE HUB        │
                          │  controllers → services → repositories       │
                          └──┬─────────┬──────────┬──────────┬───────────┘
                             │         │          │          │
                 ┌───────────▼──┐ ┌────▼──────┐ ┌─▼────────┐ │
                 │ auth (:8001) │ │ provider  │ │ Temporal │ │  Third-party:
                 │ OAuth/OTP/JWT│ │ plugins   │ │ server   │ │  S3, Stripe,
                 │ Stripe billing│ │ (proxy)  │ │ (PG-backed)│ OpenAI, Brevo,
                 └──────┬───────┘ └────┬──────┘ └─┬────────┘ │  Umami
                        │              │          │          │
                        │      ┌───────▼───────┐  │   ┌──────▼───────────────┐
                        │      │ integrations/ │  │   │ temporal workers:     │
                        │      │ google (:8003)│  │   │  worker / csv-worker /│
                        │      │ typeform(:8002)│ │   │  actions-executor     │
                        │      └───────┬───────┘  │   └──────┬───────────────┘
                        ▼              ▼          ▼          ▼
                 ┌──────────────────────────────────────────────────────┐
                 │  MongoDB (app data, Beanie ODM)   ·   Redis (cache)    │
                 └──────────────────────────────────────────────────────┘

  Shared Python package `common/` (models, enums, JWT, crypto, HTTP client) is imported by
  backend, auth, and integrations/google.
```

## Core domain model: StandardForm

[common/common/models/standard_form.py](../common/common/models/standard_form.py) is the single canonical form
representation. Everything — forms built natively in the drag-and-drop builder **and** forms imported from Google or
Typeform — is normalized into a `StandardForm`. Key pieces:

- **Fields** (`StandardFormFieldType` / `FormBuilderTagTypes`): a rich set — short/long text, markdown, multiple
  choice, multiselect, checkboxes, email, number, phone, link, date/time (+ ranges), dropdown, rating, linear scale,
  file upload, ranking, matrix, plus layout tags (headers, dividers, labels).
- **Presentation:** `Theme`, `LayoutType` (two-column / single-column background variants), embeds (`EmbedProvider`).
- **Consent** (embedded, from `common/common/models/consent.py`): the privacy core — declared purpose,
  `ConsentResponse`, and `ResponseRetentionType`. Responders consent to the purpose before submitting.

Responses are `StandardFormResponse`. When editing anything form-shaped in the webapp or a provider service, conform
to this model rather than introducing a parallel structure.

## The provider plugin/proxy system

External form providers (Google, Typeform) are integrated as **interchangeable plugins** that all implement one route
contract, defined in [common/common/constants/plugin_routes.py](../common/common/constants/plugin_routes.py):

```
/{provider}/oauth/authorize   /{provider}/oauth/callback   /{provider}/oauth/revoke   /{provider}/oauth/verify
/{provider}/forms             /{provider}/forms/{form_id}
/{provider}/import            /{provider}/import/{form_id}
/{provider}/forms/{form_id}/responses    /{provider}/forms/{form_id}/responses/{response_id}
```

- Each provider is a **standalone FastAPI microservice** (`integrations/google` on :8003, typeform on :8002) that
  implements this contract and exposes a `POST /{provider}/convert/standard_form` transform.
- The **backend** exposes a `plugin_proxy` controller + `plugin_proxy_service.py` that forwards standardized requests
  to the right provider service, based on `FormPluginConfigDocument` rows in Mongo (`forms_plugin_configs`: enabled,
  provider_name, provider_url, auth_callback_url, type). `common/common/base/plugin.py` provides the registration base.
- **Adding a new provider:** (1) build a microservice implementing the contract + StandardForm conversion, (2) add a
  `forms_plugin_configs` document pointing at it, (3) register its plugin in `backend/app/core/plugins/`. No changes to
  form storage or the webapp's form model are needed.

## Authentication flow

- **Login** is handled by the `auth` service (:8001): email **OTP** (`/otp/send`, `/otp/validate`) or **OAuth** via a
  provider (`/{provider}/basic` + `/basic/callback`). It issues **JWTs** and hands them back through the backend.
- The **backend** wraps this in cookie-based sessions (`auth_service.py`, `auth_cookie_service.py`), with a
  refresh-token flow; revoked refresh tokens are stored in Mongo (`BlackListedRefreshTokens`).
- The **webapp** sends cookies (`credentials: 'include'`) and silently refreshes via a mutex-guarded retry in
  [webapp/src/store/customFetchBase.ts](../webapp/src/store/customFetchBase.ts).
- Secrets/OAuth credentials are encrypted with **Tink / AES keysets** (`MASTER_ENCRYPTION_KEYSET`, `*_AES_KEY`) —
  see `common/common/services/crypto_service.py`. Never persist or log decrypted tokens.

## Background jobs (Temporal)

Durable / long-running work does not block request handlers — the backend's `temporal_service.py` starts workflows or
creates **Schedules** on the Temporal server (PostgreSQL-backed). Three worker services consume them:

| Worker | Workflows | Activities | Purpose |
|---|---|---|---|
| `temporal/worker` | `ImportFormWorkflow`, `DeleteResponseWorkflow`, `DeleteUserWorkflow`, `SaveTemplatePreview` | `import_form`, `delete_response`, `delete_user`, `save_preview`, `get_preview_image` | Provider imports, GDPR-style response/user deletion, template preview screenshots (Selenium/Chrome) |
| `temporal/csv-worker` | `ExportCSVWorkflow` | `export_as_csv` | Export form responses to CSV |
| `temporal/actions-executor` | `RunActionCode` | `run_action_code` | Execute user-defined form-action / automation code |

Each job kind can instead run as a **procrastinate** job on Postgres (`JOBS_BACKEND__<job>=postgres`, tables in the
`jobs` schema): the backend's `jobs-worker` consumes `delete_user` / `delete_response`, the actions-executor consumes
`run_action` (`JOBS_BACKEND=postgres` in its entrypoint). Temporal stays the default until the cutover
(plan: [plans/postgres-consolidation.md](../plans/postgres-consolidation.md) §7).

## Example end-to-end flows

**Importing a Google Form**
1. Webapp calls backend `/{provider}/import/{form_id}` (RTK Query `importApi`).
2. Backend `plugin_proxy` forwards to the google microservice (:8003), or enqueues an `ImportFormWorkflow` on Temporal.
3. The google service (or the `import_form` activity) calls Google Forms + Drive APIs, converts the result via
   `POST /google/convert/standard_form`, and the form is stored as a `StandardForm` (`FormDocument`) under the workspace.
4. A re-import is triggered through the backend's `/temporal/import/{workspace_id}/form/{form_id}` callback.

**Submitting a response (with consent)**
1. Responder loads the public form (webapp `app/forms/[form_id]`), reviews the declared purpose/consent.
2. On submit, webapp posts to backend `workspace_responses`; consent + retention are recorded alongside the
   `StandardFormResponse`.
3. Later, the responder can request deletion → backend enqueues `DeleteResponseWorkflow` on Temporal, which removes the
   response (and propagates to the source provider where applicable).

## Data stores

- **MongoDB** — application data via Beanie Documents, today's authoritative store. Backend collections are
  registered in [backend/app/handlers/database.py](../backend/backend/app/handlers/database.py) `init_db`; core
  models come from `common/`.
- **PostgreSQL (`app-postgres`)** — the application database that is replacing MongoDB and Temporal
  (plan: [plans/postgres-consolidation.md](../plans/postgres-consolidation.md)). One database, one schema per
  service (`app`, `auth`, `google`, `jobs`), one least-privilege role each — the actions-executor's role can reach
  `jobs` only, because it runs user-authored code. Every repository in backend, auth and the google integration has
  a Postgres twin behind a `RoutingRepository`; per-group flags (`DB_READ_SOURCE__<g>`, `DB_WRITE_MODE__<g>`) move
  a group from Mongo to mirrored (`dual`) to served-from-Postgres, with Mongo kept current by a reverse mirror until
  removal. Mirror failures go to an outbox; shadow reads compare the stores on live traffic; the flags in effect
  are logged at boot and served on `GET /persistence/status`.
- **PostgreSQL (Temporal)** — used only by the Temporal server (auto-setup image), not by application code;
  goes away with Temporal.
- **Redis** — caching (notably in `integrations/google`).
- **S3 (AWS/Wasabi)** — media/file uploads (`aws_service.py`); public assets on Wasabi.

## Observability

Sentry + Elastic APM are initialized across services (backend `asgi.py`, and the Python services generally). Product
analytics use **Umami**, self-hosted as its own compose service (`umami_client.py` + `analytics_service.py` query it;
the webapp loads its tracker script directly from `UMAMI_SCRIPT_URL` and calls `umami.track()` to attribute public
form views to a canonical `/{workspace_name}/forms/{slug}` path regardless of client-host vs. custom-domain routing —
see `backend/AGENTS.md` "Analytics (Umami)" and `plans/umami-self-hosted-form-analytics.md`). Transactional email
and events go through **Brevo** / SMTP (`brevo_service.py`, `mail_service.py`).

## Deployment

- Images built per service (`.github/workflows/build-images.yml`), tagged `bettercollected/<service>:nightly`.
- `docker-compose.deployment.yml` runs the full stack (webapp, backend, auth, both integrations, temporal + workers,
  mongo + seed, postgres, nginx, **umami + its own postgres**). `deploy.sh` / `Dockerfile.*.mongo-seed` handle seeding.
- nginx (`nginx-deployment.conf`) fronts the admin/client/custom-domain hosts. Umami's admin UI is exposed directly on
  host port `3003` in this first pass (no nginx/TLS routing yet).
