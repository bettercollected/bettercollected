# auth/AGENTS.md

Scoped guidance for the **identity + billing** service. Read the root [../AGENTS.md](../AGENTS.md) first.

## Role

Central authentication/identity service **and** Stripe billing. Handles OAuth login via form providers, email OTP,
JWT issuance, user status, and subscription checkout/portal/webhooks. Serves on **:8001**. It is *not* the same as the
provider *import* microservices — this service does login/identity; imports live in `integrations/*`.

## Where things live (double-nested: `auth/auth/…`)

```
auth/
  pyproject.toml, run.sh          # outer: tooling (Poetry)
  auth/
    app/
      controllers/   # auth_router.py, users_router.py, stripe_router.py, ready_router.py
      services/      # provider factory + providers, stripe, mail, user, database
      repositories/  # user, provider
      schemas/       # request/response DTOs
      models/        # request/response models
      templates/     # email HTML (OTP, invites)
      container.py   # dependency-injector wiring
      router.py
    config/
    cli/             # `auth` CLI entry
```

## Tech

FastAPI + **fastapi-users[beanie,oauth]** (user management on MongoDB via Beanie), `dependency-injector`,
`classy-fastapi`, **stripe**, `google-auth-oauthlib` + `google-api-python-client`, `pyjwt`, `fastapi-mail`.
Shares the local `common` package. JWT + crypto helpers come from `common.services`.

## Auth providers & flows

- **Provider factory** — `services/auth_provider_factory.py` (`get_auth_provider`) wires **Google** and **Typeform**
  OAuth providers (`google_auth_provider.py`, `typeform_auth_provider.py`, both extending `base_auth_provider.py`).
  Add a new login provider by implementing `base_auth_provider` and registering it in the factory.
- **Account linking** (#758) — accounts are keyed by email, so a provider sign-in may use or create the account for
  an email only when the provider verified it: go through `services/provider_sign_in.py`
  (`account_for_provider_sign_in`), never `save_user` directly. Google needs `verified_email`; Typeform's `/me`
  email is unproven, so Typeform sign-in is always refused (existing and new accounts alike — a new one would squat
  the address). A refusal returns the state without `user` plus `error`/`provider`; the backend redirects to the
  login page with `login_error=unverified_email&login_provider=…`, which the webapp explains. `GET /callback` (the
  backend's import-OAuth token exchange) never creates accounts, and the backend only sends it the signed-in user's
  own email.
- **Single sign-on** (`services/sso_service.py`, `controllers/sso_router.py`, `SSO_*` settings; docs/sso.md): not a
  basic-auth provider (the factory refuses `sso`). The backend picks the tenant (workspace) and the Polis connection;
  `GET /auth/sso/authorize` builds the Polis URL (PKCE, encrypted state with tenant, connection, time and the backend's
  context), `GET /auth/sso/callback` exchanges the code, checks userinfo's `requested` tenant/product/client_id and
  returns the asserted email with a short-lived encrypted assertion, **creating no account** (the backend checks the
  domain and the seat cap first); `POST /auth/sso/account` then finds or creates the account through
  `account_for_provider_sign_in`, matching emails case-insensitively (`find_users_by_email_ci`), `email_verified`
  true, and never the platform-admin role (`roles_for(..., verified=False)`).
- **Routes** (`controllers/auth_router.py`):
  - `GET /otp/send`, `GET /otp/validate` — email OTP login.
  - `GET /{provider_name}/basic` + `GET /{provider}/basic/callback` — per-provider OAuth login.
  - `GET /callback` — JWT exchange. `GET /status` — session/user status.
- **Stripe billing** (`controllers/stripe_router.py`, logic in `services/stripe_service.py`):
  `GET /stripe/plans`, `GET /stripe/session/create/checkout`, `GET /stripe/session/create/portal`,
  `POST /stripe/webhooks`.
- **Platform admins** (`ADMIN` role, not workspace admins — and *every* platform-admin power behind the backend's
  `get_logged_admin`, not only metrics): `PLATFORM_ADMIN_EMAILS` (comma-separated) adds ADMIN to those users' token
  roles via `services/platform_admins.py:roles_for`, **only for sessions whose email was verified at sign-in**: OTP
  login, and Google when userinfo reports `verified_email`. Typeform's `/me` email never gets it; the `/callback` JWT
  exchange (import OAuth re-issuing the signed-in session's token, same email) gets it only when the backend passes
  that session's `email_verified=true`. The session's `email_verified` claim lives in the backend-issued tokens (`common.models.user.User`);
  on refresh the backend passes it to `GET /status?email_verified=`, which grants only when it is true. Never stored,
  so removing an email revokes it at the user's next token (access tokens already issued keep it until they
  expire, `AUTH_ACCESS_TOKEN_EXPIRY_IN_MINUTES` on the backend, 15 minutes by default); an ADMIN stored on the user document still counts. Sessions from before this
  claim existed count as unverified (sign in again). `GET /admin/metrics` (user counts for the backend's platform
  metrics page) requires ADMIN.

## Internal-only API (#766)

Nothing outside the deployment may call this service: the browser only ever talks to the backend, which calls
auth server-to-server. Every route requires the shared key in the `X-Internal-Key` header
(`controllers/internal_key.py` `require_internal_key`, `hmac.compare_digest`; **503** while
`AUTH_INTERNAL_NOTIFY_KEY` is unset, **403** when the header is missing or wrong) **except**:

- `GET /ready` — health checks;
- `POST /stripe/webhooks` — authenticated by its Stripe signature (Stripe calls the backend, which forwards here
  with the key, but the route must keep working on the signature alone).

`/admin/metrics` and `/notifications/*` need the key *and* their own Bearer checks. The auth, users and admin
routers take the guard router-level (`@router(..., dependencies=INTERNAL_ONLY)`); notifications and
`stripe_router.py` have it per route (a `Depends` parameter — classy-fastapi's route decorators can't take
`dependencies=`), the latter to leave the webhook open. A new
route is guarded automatically when it lives on a guarded router; `tests/integration/app/controllers/test_internal_key_guard.py`
walks every route in the OpenAPI schema and fails if one answers without the key (add it to `OPEN` only on
purpose). Tests: `app_runner` sends the key by default; `without_internal_key(app_runner)` drops it.

The setting keeps its historical name `AUTH_INTERNAL_NOTIFY_KEY` (it first guarded only notification mails) and
must have the **same value on the backend (and its jobs worker), auth and integrations/google**. All three log an
ERROR at startup when it is unset but still start (a refusal to boot would turn a config miss into an outage);
until it is set, sign-in, session refresh, invitations and member lists fail with 503. Callers: backend
`services/internal_auth.py` `auth_service_headers()` (enforced by `backend/tests/app/services/test_auth_call_sites.py`),
google `services/migration_service.py`. Never put the key on a shared HTTP client (it also calls third parties).

## Cross-service position

- Issues JWTs that the **backend** wraps into cookie sessions (backend owns the sessions and their revocation, not
  auth; a refresh asks `/auth/status`, and a 404 there ends the session).
- Login OAuth here is distinct from provider *import* OAuth in `integrations/google` (:8003) / typeform (:8002).
- Emails (OTP, invites) go out via `mail_service.py` (SMTP / fastapi-mail); templates in `app/templates/`.
  **Workspace titles never reach a header (#761):** the From display name is always `ORGANIZATION_NAME`
  (`MailService` takes no sender-name argument), subjects are fixed wording, and a workspace title, form title or
  inviter name appears only in the body, through `one_line` (single line, capped) and the autoescaped `render`.
  A caller-supplied workspace image (`/auth/otp/send`) is shown only when it starts with one of
  `MAIL_IMAGE_URL_PREFIXES` (this instance's public storage, default the hosted bucket's `public/`); otherwise the
  mail shows an initial. Self-hosters on other storage set it to `<AWS_PUBLIC_URL or AWS_ENDPOINT_URL>/<bucket>/public/`.
  An inviter's avatar may also come from `MAIL_AVATAR_URL_PREFIXES` (default `https://lh3.googleusercontent.com/`,
  where Google sign-in's `picture` is served); images load on open, so any other host would learn the recipient's IP.
  The code mail's body names the workspace as "<workspace> via <ORGANIZATION_NAME>". `/auth/otp/send` never refuses
  over-long values (a refusal makes the backend answer the respondent 502): titles are capped, bad images dropped. The mails are English only; there is no locale support yet.
- **Notifications** (`controllers/notifications_router.py`, `services/notification_service.py`):
  `POST /notifications/submission-update` mails a respondent (fixed subject "Update on your submission") that staff responded to their submission. Not a
  relay: **only the backend may call it** — the internal key, like every route (see "Internal-only API"),
  because a user's
  token alone would let anyone mail any address from our domain. Also a Bearer JWT (the backend forwards the
  poster's; it keys the burst guard), the sender name is always `ORGANIZATION_NAME` (the workspace title
  appears only in the body), structured fields only (`recipient`,
  `form_title`, `workspace_title`, `link`; extra keys → 422), a fixed autoescaped template, single-line titles,
  and the link must be `/<handle>/submissions/<id>` on `CLIENT_URL` (also read from `API_CLIENT_URL`) or
  `CLIENT_ADMIN_URL` — custom domains are refused on purpose. A per-sender, per-process burst guard answers 429.

## Run / test

```bash
./run.sh            # uvicorn auth.app:get_application :8001  (needs Mongo up)
make install        # poetry install
make test           # pytest (if targets present)
make format         # black
poetry run flake8 . # lint
```

## Gotchas

- **Stripe secrets & webhook signature:** `STRIPE_SECRET`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRODUCT_ID`,
  `STRIPE_*_URL` come from env — verify webhook signatures in `stripe_service.py`; never trust unsigned webhook bodies.
- **OAuth redirect URIs** must match what's registered with Google/Typeform (`*_REDIRECT_URI`, `GOOGLE_BASIC_AUTH_REDIRECT`);
  a mismatch fails silently at the provider. See [../docs/RUNNING_INTEGRATIONS.md](../docs/RUNNING_INTEGRATIONS.md).
- **JWT/crypto secrets** (`AUTH_JWT_SECRET`, `AUTH_AES_HEX_KEY`) are shared contract with the backend — changing them
  breaks existing sessions across services.
- Local OAuth over http needs `OAUTHLIB_INSECURE_TRANSPORT=1` / `OAUTHLIB_RELAX_TOKEN_SCOPE=1` (already in `.env.deployment`).
