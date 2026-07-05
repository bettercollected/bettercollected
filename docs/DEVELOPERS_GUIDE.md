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
| `temporal/worker/`, `temporal/actions-executor/` | Temporal background workers |
| `common/` | Shared Python package (models, enums, crypto, JWT) |

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| uv | latest | https://docs.astral.sh/uv/getting-started/installation/ |
| Python | 3.11+ | uv can install it for you (`uv python install`); see [`.python-version`](../.python-version) |
| Node.js | 20+ | see [`.nvmrc`](../.nvmrc) — `nvm use` |
| Yarn | 1.x (Classic) | `corepack enable` or `npm i -g yarn` |
| Docker + Compose | latest | for MongoDB, nginx, Mailpit |

## 1. Start infrastructure

This brings up MongoDB (with seed data), nginx, and **Mailpit** (a local email
inbox that captures OTP/invite emails):

```bash
docker compose -f docker-compose.local.yml up --build -d
```

- MongoDB → `localhost:27017` (root/root)
- nginx → serves the client host on `:3001` and custom-domain host on `:3002`
- Mailpit → SMTP on `:1026`, web inbox at **http://localhost:8026**

> The seed step inserts the `allowed_origins` documents that the backend's
> dynamic CORS relies on — the app won't accept requests from an un-seeded host.

## 2. Configure environment variables

Copy each service's `.env.example` to `.env` and fill it in:

```bash
for d in backend auth integrations/google webapp temporal/worker temporal/actions-executor; do
  cp "$d/.env.example" "$d/.env"
done
```

Set `MONGO_URI=mongodb://root:root@localhost:27017` in the Python services.

### Shared secrets (must match across services)

`AUTH_JWT_SECRET`, `AUTH_AES_HEX_KEY`, and `MASTER_ENCRYPTION_KEYSET` **must be
identical** in `backend`, `auth`, and the integrations, or cross-service auth and
encrypted data will break. Generate them once and paste the same values
everywhere:

```bash
# AUTH_AES_HEX_KEY — a Fernet key (despite the name)
python3 -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# AUTH_JWT_SECRET — any high-entropy string
python3 -c "import secrets; print(secrets.token_hex(32))"

# MASTER_ENCRYPTION_KEYSET — a base64 Tink AEAD keyset (required by the backend)
uv run --project backend python -c "import io,base64,tink; from tink import aead, cleartext_keyset_handle; aead.register(); kh=tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM); buf=io.StringIO(); cleartext_keyset_handle.write(tink.JsonKeysetWriter(buf), kh); print(base64.b64encode(buf.getvalue().encode()).decode())"
```

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

Each service also has a `run.sh`. For the **minimal loop** (build/use a form),
you only need MongoDB + backend + auth + webapp; the google integration is for
imports and Temporal is for async jobs.

### Temporal (optional)

Import, deletion, CSV export, and preview features run as Temporal workflows.
Start a Temporal dev server and the workers:

```bash
temporal server start-dev            # serves on :7233
(cd temporal/worker && uv sync && uv run python main.py)
```

Set `TEMPORAL_SERVER_URL` in the relevant `.env` files.

## Logging in locally

Login uses an email OTP. With Mailpit running, request a code from the login
page and read it from the **Mailpit inbox at http://localhost:8026**. (The code
is also stored in Mongo under `bettercollected_auth.users.otp_code`.)

## Multi-host routing

The webapp serves three logical hosts, matched by domain:

- **Admin/dashboard** → `localhost:3000` (`DASHBOARD_DOMAIN`)
- **Client/forms** → `localhost:3001/{workspace_handle}` (`FORM_DOMAIN`), via nginx
- **Custom domain** → `localhost:3002`

Set `DASHBOARD_DOMAIN=localhost:3000` and `FORM_DOMAIN=localhost:3001` and
`NEXT_PUBLIC_API_ENDPOINT_HOST=http://localhost:8000/api/v1` in `webapp/.env`.

## Integrations (Google / Typeform)

Setting up the Google and Typeform OAuth apps is covered in
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
  `AUTH_*` / `MASTER_ENCRYPTION_KEYSET` values differ between them.
- **CORS:** a new host must exist in the Mongo `allowed_origins` collection.
