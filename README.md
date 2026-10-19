<p align="center">
<img width="300" src="https://s3.eu-central-1.wasabisys.com/bettercollected/public/bettercollected_logo.png">
</p>

<p align="center">
<b>Privacy-Friendly Form Builder For Conscious Companies</b>
</p>

<p align="center">
<a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/License-Apache_2.0-blue.svg"></a>
<a href="CONTRIBUTING.md"><img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg"></a>
<a href="https://bettercollected.com"><img alt="Website" src="https://img.shields.io/badge/website-bettercollected.com-6E56CF"></a>
</p>

---

## What is bettercollected? [🔗](https://bettercollected.com)

**bettercollected** is an open-source, privacy-friendly form builder. It lets
you show responders that you care about their data: creators declare the
**purpose** of the data they collect, responders **consent** before submitting,
and they can later **view their submission and request its deletion** (a
GDPR-style flow baked into the product).

It provides a **workspace** to host all your forms in one place — forms built
with the native drag-and-drop builder, or **imported from Google Forms and
Typeform**.

More at [bettercollected.com](https://bettercollected.com).

## Features

- 🧩 Drag-and-drop form builder with a rich set of field types
- 🔐 Consent + purpose declaration, response viewing, and deletion requests
- 🔗 Import forms and responses from **Google Forms** and **Typeform**
- 🏢 Multi-tenant **workspaces** with members and custom domains
- 📊 Form analytics powered by **self-hosted [Umami](https://umami.is)** — no
  responder data leaves your infrastructure — plus CSV export
- 🤖 AI-assisted form generation

## Try it

**Cloud:** the hosted version is at **[bettercollected.com](https://bettercollected.com)**.

**Self-host / develop locally:** see the setup below.

## Architecture

bettercollected is a polyglot microservices monorepo:

| Service | Stack | Role |
|---|---|---|
| [`webapp/`](webapp) | Next.js + TypeScript | Frontend (builder, dashboards, responder portal) |
| [`backend/`](backend) | FastAPI + MongoDB (Beanie) | Core API |
| [`auth/`](auth) | FastAPI + Stripe | Identity (OAuth / OTP / JWT) + billing |
| [`integrations/`](integrations) | FastAPI + Google/Typeform APIs | Form-provider integrations |
| [`temporal/`](temporal) | Temporal workers | Background jobs (imports, deletion, CSV, previews) |
| [`common/`](common) | Shared Python package | Models, enums, crypto, JWT |

Infra: MongoDB, Redis, PostgreSQL + Temporal, nginx, and Umami (self-hosted
analytics, with its own PostgreSQL). A deep dive lives in
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Quick start (local development)

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Node 20+ (see
[`.nvmrc`](.nvmrc)), Yarn 1.x, and Docker.

```bash
# 1. Start infra (MongoDB + seed data, nginx, Mailpit email inbox)
docker compose -f docker-compose.local.yml up --build -d

# 2. Copy and fill env files (see the developers guide for required secrets)
cp backend/.env.example backend/.env
cp auth/.env.example auth/.env
cp webapp/.env.example webapp/.env
# the .env.example files set DEBUG=true (HTML tracebacks); the code default is off

# 3. Install & run
(cd backend && uv sync && uv run python -m uvicorn backend.app:get_application --port 8000 --reload)
(cd auth && uv sync && uv run python -m uvicorn auth.app:get_application --port 8001)
(cd webapp && yarn install && yarn dev)   # http://localhost:3000
```

The full walkthrough — env vars, shared secrets, provider OAuth, Temporal, and
common gotchas — is in **[docs/DEVELOPERS_GUIDE.md](docs/DEVELOPERS_GUIDE.md)**.
Integration setup (Google/Typeform apps) is in
[docs/RUNNING_INTEGRATIONS.md](docs/RUNNING_INTEGRATIONS.md).

## Self-hosting

The entire stack — including analytics — runs on your own machine, so no
third-party service ever sees responder data:

```bash
./deploy.sh                # everything except form-provider integrations
./deploy.sh googleform     # ... with Google Forms import
./deploy.sh typeform       # ... with Typeform import
./deploy.sh both           # ... with both
./deploy.sh down           # stop the stack
```

`deploy.sh` brings up the full stack from
[`docker-compose.deployment.yml`](docker-compose.deployment.yml) with health
checks and correct startup ordering: webapp (`:3000`), backend (`:8000`),
auth, MongoDB (+ seed data), Temporal + workers, nginx (`:3001`/`:3002`), the
internal admin service, the jobs worker and the document sandbox, and
[Umami](https://umami.is) analytics (its tracker on `:3003` through nginx; its
dashboard on `127.0.0.1:3004` only, with the built-in `admin`/`umami` login
replaced by a generated password on the first run). Temporal and the
databases are reachable on the compose network only.

**What you provide:** one value, `PLATFORM_ADMIN_EMAILS` (who may sign in to
the internal admin portal), in the gitignored root `.env`; optionally
`ADMIN_ALLOWED_IPS` if you reach the portal from another address than the host.
**What `deploy.sh` generates, once, and never overwrites:** the database
passwords, `UMAMI_APP_SECRET` and `SETTINGS_MASTER_KEY` into the root `.env`
(keep that file, and back up `SETTINGS_MASTER_KEY` separately: without it the
settings store cannot be read), and the stack's own keys (`AUTH_JWT_SECRET`,
`AUTH_AES_HEX_KEY`, `AUTH_INTERNAL_NOTIFY_KEY`, `TEMPORAL_API_KEY`,
`MASTER_ENCRYPTION_KEYSET`) straight into the settings store, where nothing
prints them. On a new stack it ends by showing a one-time setup token on the
console. Everything else is a setting in the store. Details, the host commands
and the upgrade path: [docs/admin-service.md](docs/admin-service.md).

[`.env.deployment`](.env.deployment) ships no secrets and is only needed for
values you want to set from a file. The services refuse to start when
`AUTH_JWT_SECRET` or `AUTH_AES_HEX_KEY` is empty or a value that was ever
published in this repository. Put TLS or a reverse proxy in front of the stack
yourself, and set `TRUSTED_PROXIES` in the root `.env` (or the setting in the
portal) to the address(es) or CIDR(s) it connects to the backend from
(comma-separated). The backend takes the client address from `X-Forwarded-For`
only for requests from those proxies; without it every client looks like the
proxy (and shares its rate limits).
Do not put a reverse proxy in front of the admin portal's port (`8100`): behind a
proxy on the host every client would look like the Docker gateway, which the
portal's address check admits. Reach the portal with an SSH tunnel (see
[docs/admin-service.md](docs/admin-service.md), "Network").

**Upgrading an existing instance:** read
[Upgrading to 4.0](docs/admin-service.md#upgrading-to-40) first (backups, what
changes, the steps in order, behaviour changes, rollback, and a checklist for after
the deploy), and see the [changelog](CHANGELOG.md). In short: back up the root `.env`,
`.env.deployment` and the database, set `PLATFORM_ADMIN_EMAILS` (and `TRUSTED_PROXIES`
behind a proxy) in the root `.env`, then re-run `./deploy.sh`. It imports the keys and
settings your files hold into the settings store (never overwriting), compares them,
and tells you when to remove the old values with `./deploy.sh settings-prune`. Back up
`SETTINGS_MASTER_KEY`: it cannot be recovered. If you deploy without `deploy.sh`, set
the same random value as `TEMPORAL_API_KEY` in the backend and as `API_KEY` on the
Temporal worker and the actions-executor; until then imports, scheduled deletions and
form actions fail with 503 and the services log an error at startup.

### CI deployments

GitHub Actions deploys updated service images through
[Docker Stack](https://github.com/mesudip/docker-stack) and Docker Manager. Set
these repository variables before enabling the workflow:

| Environment | Ref | Manager variable | Stack variable |
| --- | --- | --- | --- |
| Development | `develop` | `DEVELOP_MANAGER` | `DEVELOP_STACK` |
| Staging | `master` | `STAGING_MANAGER` | `STAGING_STACK` |
| Production | a Git tag | `PROD_MANAGER` | `PROD_STACK` |

Each manager variable must contain that environment's Docker Manager URL. The
workflow authenticates with GitHub OIDC, so the matching Docker Manager must
trust this repository as an OIDC client.

## Contributing

Contributions are very welcome! Please read **[CONTRIBUTING.md](CONTRIBUTING.md)**
and our [Code of Conduct](CODE_OF_CONDUCT.md). Good places to start:

- Issues labelled [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
- The per-service `AGENTS.md` files for context on the code you're touching

Found a security issue? Please follow our **[Security Policy](SECURITY.md)** —
do not open a public issue.

## License

Licensed under the [Apache License 2.0](LICENSE).
