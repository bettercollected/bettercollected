# Developers Guide

This document explains how to set up bettercollected for local development.
For a high-level tour of how the services fit together, read
[ARCHITECTURE.md](ARCHITECTURE.md) first. For the contribution workflow, see
[../CONTRIBUTING.md](../CONTRIBUTING.md).

> **Note:** The Python services use [**uv**](https://docs.astral.sh/uv/) for
> dependency management (not Poetry), and `common` is a regular directory in this
> repo (not a git submodule). Older instructions mentioning Poetry or
> `git submodule` are obsolete.

## Directory structure

| Path | What it is |
|---|---|
| `webapp/` | Next.js frontend |
| `backend/` | Core FastAPI API |
| `auth/` | Identity (OAuth / OTP / JWT) + Stripe billing |
| `integrations/google/` | Google Forms integration service |
| `temporal/actions-executor/` | Runner for form actions, fed by the Postgres job queue |
| `temporal/worker/` | The old Temporal workflows, used only with `JOBS_BACKEND=temporal` (Temporal is not part of the stack since 4.1) |
| `common/` | Shared Python package (models, enums, crypto, JWT) |

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| uv | latest | https://docs.astral.sh/uv/getting-started/installation/ |
| Python | 3.11+ | uv can install it for you (`uv python install`); see [`.python-version`](../.python-version) |
| Node.js | 26 LTS (22.12+ works) | see [`.nvmrc`](../.nvmrc) — `nvm use` |
| Yarn | 1.x (Classic) | `npm i -g yarn` (Node 25+ no longer ships Corepack) |
| Docker + Compose | latest | for PostgreSQL, nginx, Mailpit, RustFS, Umami |

## 1. Start infrastructure

This brings up PostgreSQL (the application database), nginx, **Mailpit** (a
local email inbox that captures OTP/invite emails), RustFS (S3-compatible
storage) and Umami:

```bash
docker compose -f docker-compose.local.yml up --build -d
```

The first run also builds the document sandbox image (PDF import), which takes
a while.

- PostgreSQL → `localhost:5432`; one role per service (`bc_app`, `bc_auth`,
  `bc_google`, as in the `.env.example` files, and `bc_jobs_exec` for the
  actions executor), created on the first start
- nginx → serves the client host on `:3001` and custom-domain host on `:3002`
- Mailpit → SMTP on `:1026`, web inbox at **http://localhost:8026**

> The backend's dynamic CORS trusts only the origins in the Postgres
> `allowed_origins` table (since 4.1; the Mongo seed no longer writes them).
> Seed them once the backend's schema is migrated: see step 4.

## 2. Configure environment variables

Copy each service's `.env.example` to `.env` and fill it in:

```bash
for d in backend auth integrations/google webapp temporal/worker temporal/actions-executor; do
  cp "$d/.env.example" "$d/.env"
done
```

Leave `MONGO_URI` empty in the Python services. Since 4.1 MongoDB is no
longer a store: it is read only when a 4.0 stack is upgraded, and a set but
unreachable `MONGO_URI` stops the start. (The local compose file still starts a
MongoDB container; nothing uses it while `MONGO_URI` is empty.)

Set `DB_AUTO_MIGRATE=true` in `backend/.env` and `auth/.env` (and
`integrations/google/.env` if you run it): each service then migrates its
Postgres schema when it starts. Without it a service refuses to start while its
schema is behind the code.

### Shared secrets (must match across services)

`AUTH_JWT_SECRET` and `AUTH_AES_HEX_KEY` **must be identical** in `backend`,
`auth` and the Google Forms integration, or cross-service auth and encrypted data
will break. `MASTER_ENCRYPTION_KEYSET` is read by the backend (and the Google
Forms integration), not by auth; the backend also needs
`RESPONDENT_IDENTITY_KEY` (`openssl rand -hex 32`). `AUTH_INTERNAL_NOTIFY_KEY`
(`openssl rand -hex 24`) must also be the same in `backend`, `auth` and the
Google Forms integration: while it is unset, sign-in fails. Generate them once
and paste the same values everywhere:

```bash
# AUTH_AES_HEX_KEY — a Fernet key (despite the name)
python3 -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# AUTH_JWT_SECRET — any high-entropy string
python3 -c "import secrets; print(secrets.token_hex(32))"

# MASTER_ENCRYPTION_KEYSET — a base64 Tink AEAD keyset (required by the backend)
uv run --project backend python -c "import io,base64,tink; from tink import aead, cleartext_keyset_handle; aead.register(); kh=tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM); buf=io.StringIO(); cleartext_keyset_handle.write(tink.JsonKeysetWriter(buf), kh); print(base64.b64encode(buf.getvalue().encode()).decode())"
```

The backend (and its jobs worker), auth, the Google Forms integration and the
Temporal workers (whose `AES_HEX_KEY` is `AUTH_AES_HEX_KEY`) **refuse to
start** when `AUTH_JWT_SECRET` or `AUTH_AES_HEX_KEY` is empty, when the Fernet
key is malformed, or when either is a value that was ever published in this
repository (old `.env.deployment`, READMEs and compose files). The error names
the variable and how to generate it, never the value. The published values are
known only by their SHA-256 in `common/common/configs/shipped_secrets.py`
(copied to `temporal/*/settings/` and `deploy/generate-secrets.sh`;
`common/tests/test_shipped_secrets.py` keeps them identical). The test values in
`.github/workflows/ci.yml` are accepted so tests and local development keep
working, but they are public too: never deploy with them.

**Self-hosted stacks** get their own values from `deploy.sh`: on a new stack
`python -m backend.admin bootstrap-keys` generates `AUTH_JWT_SECRET`,
`AUTH_AES_HEX_KEY`, `AUTH_INTERNAL_NOTIFY_KEY`, `TEMPORAL_API_KEY`,
`MASTER_ENCRYPTION_KEYSET` and `RESPONDENT_IDENTITY_KEY` straight into the settings
store (docs/admin-service.md; an upgrade has `deploy.sh` generate the identity key
once, into the store and `.env`);
the root `.env` (gitignored, mode 600) keeps `SETTINGS_MASTER_KEY` and the database
passwords. An
upgrade imports the values an older release kept in `.env` or `.env.deployment`
(`deploy/generate-secrets.sh` copies and checks them first) and never overwrites
the store. Keep the master key backed up. Local development sets
`SETTINGS_STORE=off` and keeps using plain environment values. Replacing these keys by hand has costs:
a new `AUTH_JWT_SECRET` signs everyone out; data encrypted with the old
`AUTH_AES_HEX_KEY` (Sheets connections and other form-action secrets,
SCIM webhook secrets, registration services, webhooks) can no longer be read. Rotate them with the
portal's `authkeys.*` tasks instead, which keep both keys readable (a ring, `<current>,<previous>`)
until everything is moved: `docs/auth-key-rotation.md`. Responses can only be read
with the `MASTER_ENCRYPTION_KEYSET` they were stored with, so a stack that
already holds responses must keep its keyset (`deploy.sh` imports it and stops
rather than generate a new one for it). A keyset can be rotated without losing data (a new
key, every stored value re-encrypted, then the old key dropped):
`docs/response-keyset-rotation.md`. The services log a warning at startup while
the keyset holds a key that was published in this repository, as the CI test
keyset is.

Other required backend fields: `UNSPLASH_ACCESS_KEY` (may be empty) and
`AWS_PRE_SIGNED_URL_EXPIRY` (must be an integer, e.g. `3600`).

Cookie config for local http: set `API_HOST=localhost` and leave `API_DOMAIN`
empty in `backend/.env` (a cookie domain can't contain a port).

### Email (Mailpit)

Point auth at the local Mailpit and disable TLS/auth:

```dotenv
MAIL_SMTP_SERVER=localhost
MAIL_SMTP_PORT=1026
MAIL_STARTTLS=false
MAIL_SSL_TLS=false
MAIL_USE_CREDENTIALS=false
MAIL_VALIDATE_CERTS=false
MAIL_SENDER=dev@bettercollected.com    # a plain, valid email (no name<addr>, no .local)
```

## 3. Install dependencies

```bash
# Python services
for d in backend auth integrations/google temporal/worker temporal/actions-executor; do
  (cd "$d" && uv sync)
done

# Frontend
(cd webapp && yarn install)
```

## 4. Run the services

| Service | Command | URL |
|---|---|---|
| backend | `cd backend && uv run python -m uvicorn backend.app:get_application --port 8000 --reload` | http://localhost:8000/api/v1/docs |
| auth | `cd auth && uv run python -m uvicorn auth.app:get_application --port 8001` | http://localhost:8001 |
| google integration | `cd integrations/google && uv run python -m uvicorn googleform.app:get_application --port 8003` | http://localhost:8003 |
| webapp | `cd webapp && yarn dev` | http://localhost:3000 |

Once the backend has started (and migrated its schema), seed the reference
data into Postgres (the allowed origins and the Google Forms provider; each
table only while it is empty):

```bash
cd backend && uv run python -m backend.seed_refdata \
  --origin http://localhost:3000 --origin http://localhost:3001 --origin http://localhost:3002 \
  --origin http://localhost:4000 --origin http://localhost:4001 \
  --google-enabled true --google-url http://localhost:8003/api/v1
```

Each service also has a `run.sh`. For the **minimal loop** (build/use a form),
you only need PostgreSQL + backend + auth + webapp; the google integration is
for imports and the jobs worker for background jobs.

### Background jobs (optional)

Background jobs (account and response deletion, imports, scheduled checks) run
on the Postgres job queue (`JOBS_BACKEND=postgres`, the default). Temporal is
not part of the stack since 4.1. Start the backend's jobs worker:

```bash
cd backend && uv run python -m backend.jobs.worker
```

Form actions run in `temporal/actions-executor` (`uv run python main.py`),
which takes its jobs from the same queue and needs `DATABASE_URL` for its
own jobs role (`bc_jobs_exec`). Set one
shared key for the backend's internal job routes: `TEMPORAL_API_KEY` in `backend/.env` and the
same value as `API_KEY` in `temporal/worker/.env` and
`temporal/actions-executor/.env` (e.g. `openssl rand -hex 24`). Without it
those routes answer 503 and the services log an error at startup.

## Logging in locally

Login uses an email OTP. With Mailpit running, request a code from the login
page and read it from the **Mailpit inbox at http://localhost:8026**.

## Multi-host routing

The webapp serves three logical hosts, matched by domain:

- **Admin/dashboard** → `localhost:3000` (`DASHBOARD_DOMAIN`)
- **Client/forms** → `localhost:3001/{workspace_handle}` (`FORM_DOMAIN`), via nginx
- **Custom domain** → `localhost:3002`

Set `DASHBOARD_DOMAIN=localhost:3000` and `FORM_DOMAIN=localhost:3001` and
`NEXT_PUBLIC_API_ENDPOINT_HOST=http://localhost:8000/api/v1` in `webapp/.env`.

### Who may frame a page

`webapp/src/proxy.ts` sets `Content-Security-Policy: frame-ancestors 'self' <dashboard origin>` on every page
(the dashboard origin is `HTTP_SCHEME` + `DASHBOARD_DOMAIN` of the running server, so the builder's form
preview, which frames the client domain, keeps working, also on a single-domain setup). A published form's page
(`/<workspace>/forms/<form>`, its `/preview`, and `/forms/<form>` on a custom domain) sends no framing header.
The header is set only there: `next.config.js` `headers()` is evaluated when the image is built, without the
running server's domains, so it must not carry anything that names them. `X-Frame-Options` is not sent:
`SAMEORIGIN` would stop the dashboard from framing the client domain, and every current browser honours the
`frame-ancestors` directive. Rules in `src/lib/frame-ancestors.ts`, tests in `src/proxy-frame.test.ts`.

## Version in the dashboard sidebar

The dashboard sidebar shows the version the webapp image was built as, under
"Powered by bettercollected": `v4.0.2` for a release, `dev · b3a8cee` /
`staging · b3a8cee` for the develop and master builds. It is a build fact,
`NEXT_PUBLIC_APP_VERSION`, passed as a Docker build argument and inlined by
`next build` (`.github/workflows/deploy.yml` sets it). Respondent pages never
show it. A local `yarn dev` or an image built without it shows nothing. To
build your own image with it:

```bash
docker build --build-arg "NEXT_PUBLIC_APP_VERSION=$(scripts/app-version.sh)" \
  -f webapp/Dockerfile .
```

`scripts/app-version.sh` prints the release tag when the checkout is exactly on
one, else the short commit (shown as `build · b3a8cee`). `deploy.sh` pulls the
published images, which carry their own version.

## Integrations (Google)

Setting up the Google OAuth app is covered in
[RUNNING_INTEGRATIONS.md](RUNNING_INTEGRATIONS.md).

## Tests, lint & format

```bash
# Python (per service)
uv run pytest
uv run black .
uv run flake8 .

# Frontend
yarn test
yarn lint
yarn format:check
yarn build        # type-checks + builds
```

Install pre-commit hooks where a config exists: `pre-commit install`, and commit
from the terminal so hook failures are visible.

## Common gotchas

- **Python version:** the repo targets 3.11+. uv manages the interpreter; if you
  see resolution errors, run `uv python install 3.11`.
- **`common` is a path dependency:** changing a model/enum in `common/` affects
  backend, auth, and integrations — re-`uv sync` and test all consumers.
- **Shared secrets:** if login or decryption fails across services, your
  `AUTH_*` / `MASTER_ENCRYPTION_KEYSET` values differ between them. A service
  that will not start with "Refusing to start ...: AUTH_JWT_SECRET is not set"
  (or "is a value that was published") needs its own value; see
  [Shared secrets](#shared-secrets-must-match-across-services).
- **CORS:** a new host must exist in the Postgres `allowed_origins` table
  (`python -m backend.seed_refdata --origin ...` seeds an empty one).
- **"Refusing to start: the ... group(s) are served from Postgres only ... never
  imported into Postgres":** an older local Mongo volume still holds data for a
  group that is now served from Postgres only (typically the reference data the
  old Mongo seed wrote), or an import stopped halfway. The backend, the auth
  service and the Google Forms integration all check. Run the import command the
  message prints (from the service's directory, with `uv run`), or, for a
  throwaway local stack, start with `DB_DISCARD_UNIMPORTED_MONGO_DATA=<group>`
  (or `all`; names of other services' groups are ignored, so one environment
  file serves them all) and seed Postgres with `seed_refdata` instead. Never set
  the override on a stack whose data matters. A local stack that never had Mongo
  data: leave `MONGO_URI` empty.
