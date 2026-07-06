# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [RELEASING.md](RELEASING.md) for how releases are cut.

> This file was introduced partway through the project's life, so history before
> `2.2.0` is captured by git tags and release notes rather than here.

## [Unreleased]

### Added

- Open-source contributor docs and community health files: `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue/PR templates, `SUPPORT.md`,
  `GOVERNANCE.md`, `ROADMAP.md`, `CODEOWNERS`, and this changelog.
- `AGENTS.md` guidance files and `docs/ARCHITECTURE.md`.
- Continuous integration (`ci.yml`): backend and auth `pytest` suites plus
  webapp build/type-check and a Vitest test job, with self-hosted-runner
  preference and a MongoDB service for the backend tests.
- Dependabot configuration for weekly npm, uv, and GitHub Actions updates.
- Initial frontend test suite (Vitest + Testing Library) with a shared config.
- Mailpit for catching outbound email in local development.
- Backend: flow-native template gallery (Support triage, Lead qualification,
  Job application with screening) auto-seeded on every startup — idempotent,
  gated by `DEFAULT_SEED_FLOW_TEMPLATES`/`DEFAULT_WORKSPACE_ID`. See
  `backend/AGENTS.md` "Seed scripts" for the env vars and how to add more.
- Self-hosted product analytics: Umami now ships as a first-class Docker
  Compose service (its own Postgres, admin UI on `:3003`) instead of a
  BetterCollected-hosted default — no self-hosted deployment now silently
  phones home. Form views are attributed to a canonical
  `/{workspace_name}/forms/{slug}` path from the webapp regardless of
  client-host vs. custom-domain routing. See `backend/AGENTS.md`
  "Analytics (Umami)" and `plans/umami-self-hosted-form-analytics.md`.
- Umami website auto-provisioning: the backend now finds-or-creates its
  Umami website by name on startup, so self-hosters no longer have to log
  into the Umami UI and copy a website id into config by hand.
- `docker-compose.deployment.yml` hardening: real health checks (Mongo,
  Postgres, Temporal, backend, auth, Umami) with `depends_on:
  condition: service_healthy` gating, so services actually wait for their
  dependencies to be ready instead of just "started." `deploy.sh` now starts
  Umami too (previously missing) and auto-generates `UMAMI_APP_SECRET` on
  first run.

### Changed

- Corrected `docs/DEVELOPERS_GUIDE.md` to the current **uv + yarn** workflow.
- Rewrote `README.md` for a public audience.
- Sped up the backend test suite (~137s → ~5s) via session-scoped app/DB init.
- Aligned toolchain versions (Node via `.nvmrc`, Python for CI, `.editorconfig`).
- UI/UX: form titles are now shown across the app (forms list and form-detail
  header) with an "Untitled form" fallback, plus a "Forms" breadcrumb, and the
  form tab bar keeps the active tab in view.
- UI/UX: corrected page titles and empty/error states (Templates, Analytics,
  Integrations, Responders, Deletion Requests) and did a copy pass for typos,
  grammar, and consistent, inclusive second-person wording.
- UI/UX: Account Settings derives the avatar and name consistently and no
  longer prints the email twice; Custom Domain shows an explicit Pro upgrade
  prompt on free plans.
- Batched routine dependency updates across all services (npm + uv + GitHub
  Actions) and moved CI actions to Node-24 majors.

### Fixed

- React 19 form-rendering crash and DOM-prop console errors in the webapp.
- React 19 DOM-prop warnings from data tables (`react-data-table-component` v8).
- Form editor no longer auto-saves on load — only on real user edits.
- Invalid nested `<button>` in the form-published modal.
- Analytics now distinguishes a genuine load error (with a retry) from an
  empty state.
- Backend Umami client (`umami_client.py`): error paths raised a raw
  `TypeError` instead of a clean HTTP error (the app's custom `HTTPException`
  takes `content=`, not `detail=`); a failed retry after a 401 also went
  unchecked instead of surfacing a clean error.
- Form analytics `/stats` endpoint 500'd against current self-hosted Umami's
  response shape (flat ints + a `comparison` object, not nested `{value,
  prev}` per metric) — surfaced once Umami was actually reachable end-to-end.
- Local dev: `nginx-local.conf` 502'd on the client-host/custom-domain ports
  (e.g. a form's share URL) because it proxied to `localhost:3000`, which
  inside the nginx container isn't the host where webapp/backend actually run.
- `docker-compose.deployment.yml`: Temporal's `DB=postgresql` was never a
  valid driver name (`temporalio/auto-setup` only accepts `postgres12`,
  `postgres12_pgx`, `mysql8`, `cassandra`) — Temporal has likely never
  started successfully via this compose file; this only surfaced once a real
  health check was added instead of just checking the container was running.
  Also pinned `postgres:latest` (temporal's Postgres) to `postgres:15-alpine`
  and moved it to a named volume — an unpinned tag had already drifted to
  Postgres 18, which refuses to start against an older major version's data
  directory.
- `install.sh` referenced Poetry and a per-service `Makefile`, neither of
  which exist anymore since the Python services moved to `uv` — the script
  was fully broken. Rewritten to `uv sync` per service.
- Backend boots without an `OPENAI_API_KEY` (OpenAI client is created lazily).
- Forms listing/pagination failure (fastapi-pagination under Starlette 1.x).
- Login "Failed to send OTP" flow (route, API host, and cookie-domain issues).
- Numerous Dependabot security advisories across all services.

### Security

- Removed committed Stripe/Sentry secrets from `auth/.env.example` (placeholders
  now). **Note:** these values still exist in git history and should be rotated
  and scrubbed before/at public release — see `SECURITY.md`.

## [2.2.0] - 2026-02-27

- Baseline for this changelog. See the
  [v2.2.0 release](https://github.com/bettercollected/bettercollected/releases/tag/v2.2.0)
  and earlier tags for prior history.

[Unreleased]: https://github.com/bettercollected/bettercollected/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/bettercollected/bettercollected/releases/tag/v2.2.0
