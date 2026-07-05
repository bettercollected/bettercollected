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
- **Routes** (`controllers/auth_router.py`):
  - `GET /otp/send`, `GET /otp/validate` — email OTP login.
  - `GET /{provider_name}/basic` + `GET /{provider}/basic/callback` — per-provider OAuth login.
  - `GET /callback` — JWT exchange. `GET /status` — session/user status.
- **Stripe billing** (`controllers/stripe_router.py`, logic in `services/stripe_service.py`):
  `GET /stripe/plans`, `GET /stripe/session/create/checkout`, `GET /stripe/session/create/portal`,
  `POST /stripe/webhooks`.

## Cross-service position

- Issues JWTs that the **backend** wraps into cookie sessions (backend owns the refresh-token blacklist, not auth).
- Login OAuth here is distinct from provider *import* OAuth in `integrations/google` (:8003) / typeform (:8002).
- Emails (OTP, invites) go out via `mail_service.py` (SMTP / fastapi-mail); templates in `app/templates/`.

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
