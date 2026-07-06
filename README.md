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
auth, MongoDB (+ seed data), Temporal + workers, nginx (`:3001`/`:3002`), and
[Umami](https://umami.is) analytics (`:3003`, default login `admin`/`umami` —
change it). On first run it also generates a random `UMAMI_APP_SECRET` into a
gitignored root `.env`. The backend auto-provisions the Umami website on
startup, so analytics needs no manual setup.

Configuration lives in [`.env.deployment`](.env.deployment). **The tracked
defaults (including secrets) are for local evaluation only — generate fresh
secrets before exposing an instance to the internet**, and put TLS or a
reverse proxy in front of it yourself.

## Contributing

Contributions are very welcome! Please read **[CONTRIBUTING.md](CONTRIBUTING.md)**
and our [Code of Conduct](CODE_OF_CONDUCT.md). Good places to start:

- Issues labelled [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
- The per-service `AGENTS.md` files for context on the code you're touching

Found a security issue? Please follow our **[Security Policy](SECURITY.md)** —
do not open a public issue.

## License

Licensed under the [Apache License 2.0](LICENSE).
