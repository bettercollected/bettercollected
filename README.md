<p align="center">
<img width="300" alt="bettercollected" src="https://s3.eu-central-1.wasabisys.com/bettercollected/public/bettercollected_logo.png">
</p>

<p align="center">
<b>Open-source, privacy-first form and data collection platform</b>
</p>

<p align="center">
<a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/License-Apache_2.0-blue.svg"></a>
<a href="CONTRIBUTING.md"><img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg"></a>
<a href="https://bettercollected.com"><img alt="Website" src="https://img.shields.io/badge/website-bettercollected.com-6E56CF"></a>
</p>

---

## What is bettercollected?

**bettercollected** is an open-source ([Apache 2.0](LICENSE)), privacy-first
platform for building forms and collecting data. Privacy is built into the
form flow: the creator declares the **purpose** of the data they collect, respondents
**consent** before they submit, and they can later **view their submission and
request its deletion**.

Run it on your own infrastructure (the whole stack, analytics included) or use
the hosted version at [bettercollected.com](https://bettercollected.com). Forms
are also available as code: a **REST API**, an **MCP server** for AI clients, and
**Python and TypeScript SDKs** work on the same forms as the builder.

## Features

**Build and collect**

- Drag-and-drop form builder with a rich set of field types, show/hide rules,
  page jumps and multiple endings
- Import forms and their responses from **Google Forms**. Access to Google
  Forms is read-only: forms and responses are imported, nothing is written back
  to Google Forms. The operator can set the
  import to `readonly` (imported data stays, no new imports) or `off`
  ([docs/RUNNING_INTEGRATIONS.md](docs/RUNNING_INTEGRATIONS.md))

**Privacy and data rights**

- Forms declare the purpose of the data they collect and ask respondents for
  consent, with an optional retention period after which answers are deleted
- Respondents can view what they submitted and request its deletion; staff
  close a request as deleted, or as declined with a stated reason

**Responses**

- Each response opens on its own full page that looks like the form
- Search responses by respondent email
- CSV export
- Form analytics with self-hosted **[Umami](https://umami.is)**: no third-party
  analytics service sees respondent data

**Teams**

- Workspaces with members and roles (Owner, Admin, Editor, Reviewer, Viewer,
  Privacy officer)
- Custom domains for a workspace's forms, once the operator connects the
  custom-domain service ([docs/custom-domain.md](docs/custom-domain.md))
- Single sign-on (SAML and OpenID Connect) and SCIM directory sync, for
  instances that enable it ([docs/sso.md](docs/sso.md))

**For developers**

- **REST API** for forms as code: create, edit, validate and publish forms, read
  responses ([docs/api/README.md](docs/api/README.md), with an OpenAPI document)
- **MCP server** at `/api/v1/mcp` on the backend, so AI clients can work with
  forms through the same operations as the API
  ([docs/api/README.md](docs/api/README.md), [docs/spec/README.md](docs/spec/README.md))
- **SDKs:** [Python](sdk/python) (with the `bettercollected` command line tool)
  and [TypeScript](sdk/typescript)
- **Workspace API keys** with scopes, created by a workspace admin. A key never
  does more than its creator may do at that moment, and every call is recorded
  in the workspace's API audit log
- **Form spec v1:** a form as a JSON document, changed by edit operations with
  a JSON Schema ([docs/spec/README.md](docs/spec/README.md))

**AI form assistant (available to enable)**

- Off by default. It needs an AI provider configured on the instance (OpenAI,
  Google Gemini, or an OpenAI-compatible endpoint such as a self-hosted model),
  and a workspace admin has to turn it on for the workspace. Until then the
  server refuses every AI request for that workspace and sends no form content,
  prompts or responses to any provider.

## Try it

**Cloud:** the hosted version is at **[bettercollected.com](https://bettercollected.com)**.

**Self-host / develop locally:** see the setup below.

## Architecture

bettercollected is a monorepo of a few services:

| Service | Stack | Role |
|---|---|---|
| [`webapp/`](webapp) | Next.js + TypeScript | Frontend (builder, dashboards, respondent pages) |
| [`backend/`](backend) | FastAPI + PostgreSQL | Core API, public REST API and MCP server; the same image runs the jobs worker (background jobs on the Postgres job queue), the internal admin portal and the document sandbox |
| [`auth/`](auth) | FastAPI + PostgreSQL + Stripe | Identity (OAuth / OTP / JWT) + billing |
| [`integrations/google/`](integrations/google) | FastAPI + Google APIs | Google Forms import |
| [`temporal/actions-executor/`](temporal/actions-executor) | Python | Optional runner for form actions, fed by the Postgres job queue (the directory keeps its old name) |
| [`common/`](common) | Shared Python package | Models, enums, crypto, JWT |
| [`sdk/`](sdk) | Python + TypeScript | Clients for the public API, and the CLI |

Infra: PostgreSQL (one database, one schema and role per service), nginx,
S3-compatible object storage for uploads, and Umami (self-hosted analytics, with
its own PostgreSQL). Since 4.1 MongoDB is no longer a store: it starts only
under the `legacy-mongo` compose profile, to import a 4.0 stack's data once on
upgrade. Temporal is not part of the stack since 4.1. A deep dive lives in
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Quick start (local development)

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Node 20+ (see
[`.nvmrc`](.nvmrc)), Yarn 1.x, and Docker.

```bash
# 1. Start infra: PostgreSQL, nginx, Mailpit (email inbox), S3-compatible
#    storage (RustFS) and Umami
docker compose -f docker-compose.local.yml up --build -d

# 2. Copy the env files, then fill them in (see below)
cp backend/.env.example backend/.env
cp auth/.env.example auth/.env
cp webapp/.env.example webapp/.env

# 3. Install & run, each in its own terminal
(cd backend && uv sync && uv run python -m uvicorn backend.app:get_application --port 8000 --reload)
(cd auth && uv sync && uv run python -m uvicorn auth.app:get_application --port 8001)
(cd webapp && yarn install && yarn dev)   # http://localhost:3000

# 4. Once the backend has started: seed the allowed origins and the
#    Google Forms provider into Postgres (each table only while it is empty)
(cd backend && uv run python -m backend.seed_refdata \
  --origin http://localhost:3000 --origin http://localhost:3001 --origin http://localhost:3002 \
  --origin http://localhost:4000 --origin http://localhost:4001 \
  --google-enabled true --google-url http://localhost:8003/api/v1)
```

In the env files:

- `AUTH_JWT_SECRET`, `AUTH_AES_HEX_KEY` and `MASTER_ENCRYPTION_KEYSET` must be
  the same in `backend` and `auth` (the guide below shows how to generate them).
  The services refuse to start when `AUTH_JWT_SECRET` or `AUTH_AES_HEX_KEY` is
  empty or a value that was ever published in this repository. `backend` also
  needs `RESPONDENT_IDENTITY_KEY` (`openssl rand -hex 32`).
- Leave `MONGO_URI` empty: a fresh install has no MongoDB data, and a set but
  unreachable `MONGO_URI` stops the start. (The local compose file still starts
  a MongoDB container; nothing uses it then.)
- Set `DB_AUTO_MIGRATE=true` in `backend/.env` and `auth/.env` so each service
  migrates its Postgres schema when it starts. Without it a service refuses to
  start while its schema is behind.
- The `.env.example` files set `DEBUG=true` (HTML tracebacks); the code default
  is off.

Sign-in uses an emailed code: read it in the Mailpit inbox at
http://localhost:8026. Background jobs (account and response deletion) run in
the jobs worker: `cd backend && uv run python -m backend.jobs.worker`.

The full walkthrough (generating the shared secrets, env vars, the Google Forms
integration and common gotchas) is in
**[docs/DEVELOPERS_GUIDE.md](docs/DEVELOPERS_GUIDE.md)**. Integration setup (the
Google app) is in [docs/RUNNING_INTEGRATIONS.md](docs/RUNNING_INTEGRATIONS.md).

## Self-hosting

The entire stack — including analytics — runs on your own machine, so no
third-party service ever sees responder data:

```bash
./deploy.sh                # everything except form-provider integrations
./deploy.sh googleform     # ... with Google Forms import
./deploy.sh down           # stop the stack
```

`deploy.sh` brings up the full stack from
[`docker-compose.deployment.yml`](docker-compose.deployment.yml) with health
checks and correct startup ordering: webapp (`:3000`), backend (`:8000`),
auth, nginx (`:3001`/`:3002`), the
internal admin service, the jobs worker (background jobs run on the Postgres
queue; there is no Temporal in the stack since 4.1) and the document sandbox, and
[Umami](https://umami.is) analytics (its tracker on `:3003` through nginx; its
dashboard on `127.0.0.1:3004` only, with the built-in `admin`/`umami` login
replaced by a generated password on the first run). The databases are
reachable on the compose network only.

**What you provide:** one value, `PLATFORM_ADMIN_EMAILS` (who may sign in to
the internal admin portal), in the gitignored root `.env`; optionally
`ADMIN_ALLOWED_IPS` if you reach the portal from another address than the host.
On a host with a public address, also set the web app's addresses before the
first run, in `.env.deployment`: `DASHBOARD_DOMAIN`, `FORM_DOMAIN` (host names,
e.g. `forms.example.org`) and `HTTP_SCHEME` (default `https://`). A new stack's
allowed origins (CORS) are seeded from them into Postgres; without them the
stack is taken for a local trial and gets the localhost origins.
**What `deploy.sh` generates, once, and never overwrites:** the database
passwords, `UMAMI_APP_SECRET` and `SETTINGS_MASTER_KEY` into the root `.env`
(keep that file, and back up `SETTINGS_MASTER_KEY` separately: without it the
settings store cannot be read), and the stack's own keys (`AUTH_JWT_SECRET`,
`AUTH_AES_HEX_KEY`, `AUTH_INTERNAL_NOTIFY_KEY`, `TEMPORAL_API_KEY`,
`MASTER_ENCRYPTION_KEYSET`, and the respondent identity key
`RESPONDENT_IDENTITY_KEY`) straight into the settings store, where nothing prints
them. A stack upgrading from 4.0 gets the identity key on its first 4.1 deploy, in
the store and in `.env` (back it up with the other keys, see
`docs/respondent-identity.md`). On a new stack it ends by showing a one-time setup token on the
console. Everything else is a setting in the store. Details, the host commands
and the upgrade path: [docs/admin-service.md](docs/admin-service.md).
**Upgrading from 4.0:** since 4.1 the stack runs on Postgres only and has no
MongoDB. Run `./deploy.sh` of the new release as before: it stops the services,
imports and verifies the data still in Mongo (MongoDB starts for that only, under
the `legacy-mongo` compose profile), stops on any difference with the counts, and
then stops MongoDB and keeps its volume. Expect the stack to be down while it runs.
Details: "Upgrading to 4.1" in
[docs/postgres-cutover-runbook.md](docs/postgres-cutover-runbook.md).
`./deploy.sh typeform` and `./deploy.sh both` are refused: Typeform was removed.

`.env.deployment` (the services' env file) is your own file and is not tracked:
`deploy.sh` creates it from the template
[`.env.deployment.example`](.env.deployment.example) (mode 600) when it is missing
and never overwrites it. The template ships no secrets; the file is only needed
for values you want to set from a file. The services refuse to start when
`AUTH_JWT_SECRET` or `AUTH_AES_HEX_KEY` is empty or a value that was ever
published in this repository. Put TLS or a reverse proxy in front of the stack
yourself, and set `TRUSTED_PROXIES` in the root `.env` (or the setting in the
portal) to the address(es) or CIDR(s) it connects to the backend from
(comma-separated). The backend takes the client address from `X-Forwarded-For`
only for requests from those proxies; without it every client looks like the
proxy (and shares its rate limits).
Route the proxy to the backend's port `8000` only, and let it add
`X-Forwarded-For`. Never publish or proxy port `8001`: it is the backend's
internal listener, where the task runner and the workers reach their key-only
routes (see "Internal routes" in [docs/admin-service.md](docs/admin-service.md)).
Do not put a reverse proxy in front of the admin portal's port (`8100`): behind a
proxy on the host every client would look like the Docker gateway, which the
portal's address check admits. Reach the portal with an SSH tunnel (see
[docs/admin-service.md](docs/admin-service.md), "Network").

**Upgrading an existing instance:** read
[Upgrading to 4.0](docs/admin-service.md#upgrading-to-40) first (backups, what
changes, the steps in order, behaviour changes, rollback, and a checklist for after
the deploy), and see the [changelog](CHANGELOG.md). In short: back up the root `.env`,
`.env.deployment` and the database, keep a copy of `.env.deployment` across the
`git pull` (it is no longer tracked, so the pull deletes or refuses it; see the guide), set `PLATFORM_ADMIN_EMAILS` (and `TRUSTED_PROXIES`
behind a proxy) in the root `.env`, then re-run `./deploy.sh`. It imports the keys and
settings your files hold into the settings store (never overwriting), compares them,
and tells you when to remove the old values with `./deploy.sh settings-prune`. Back up
`SETTINGS_MASTER_KEY`: it cannot be recovered. If you deploy without `deploy.sh`, set
`RESPONDENT_IDENTITY_KEY` (`openssl rand -hex 32`, kept forever) on the backend, which
refuses to start without it, and, if you run an actions executor, the same random value
as `TEMPORAL_API_KEY` in the backend and as `API_KEY` on the executor; until then form
actions fail with 503. A stack from before 4.1 that still runs Temporal has it retired
by `deploy.sh` (see `docs/admin-service.md`, "Temporal is retired").

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

Besides one service per built image, a deploy updates the services that run the backend image
under their own stack service name: `admin`, `document-sandbox`, `jobs-worker` and `task-runner`
(as in `docker-compose.deployment.yml`). Every stack the workflow deploys must run them.

## Contributing

Contributions are very welcome! Please read **[CONTRIBUTING.md](CONTRIBUTING.md)**
and our [Code of Conduct](CODE_OF_CONDUCT.md). Good places to start:

- Issues labelled [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
- The per-service `AGENTS.md` files for context on the code you're touching

Found a security issue? Please follow our **[Security Policy](SECURITY.md)** —
do not open a public issue.

## License

Licensed under the [Apache License 2.0](LICENSE).
