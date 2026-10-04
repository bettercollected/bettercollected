# Single sign-on (SAML and OIDC)

A workspace can let its members sign in with the organisation's identity provider (IdP): Okta, Microsoft Entra ID, Google Workspace, or any SAML 2.0 or OpenID Connect provider. [Ory Polis](https://github.com/ory/polis) (formerly BoxyHQ SAML Jackson) sits between the IdPs and BetterCollected and turns every connection into one OAuth 2.0 code flow. BetterCollected stays the identity owner: accounts, sessions and workspace memberships are ours; Polis only reports who the IdP vouched for.

This guide is for operators (turning SSO on for an instance) and workspace admins (connecting an IdP). It replaces the spike notes (`docs/sso-spike.md` on the old `spike/sso-polis` branch).

## How it fits together

```
browser ─ "Sign in with SSO", work email ─▶ backend GET /auth/sso/login
  backend: email domain ─▶ verified domain ─▶ workspace ─▶ its enabled connection
  auth:    Polis authorize URL (PKCE, encrypted state: tenant, connection, time)
browser ─▶ Polis ─▶ IdP (SAML or OIDC) ─▶ Polis ─▶ backend GET /auth/sso/callback?code&state
  auth:    code exchange (PKCE verifier), userinfo; the code must belong to the
           same tenant and connection; returns the asserted email (no account yet)
  backend: connection still enabled, workspace available, email on one of this
           workspace's verified domains, seat free (for a new member)
  auth:    find or create the account (email verified, no platform-admin role)
  backend: membership with the default role, session, redirect to the dashboard
```

- **The tenant is the workspace.** Polis's tenant is the workspace id and its product is `SSO_POLIS_PRODUCT` (`bettercollected`). A later SCIM directory attaches to the same tenant.
- **SSO only covers verified domains.** A connection applies to the workspace's email domains verified with a DNS TXT record ([verified-domains.md](verified-domains.md)). A domain that is only claimed, one whose verification was lost (`verificationLostAt`), one verified by another workspace, or one reserved by the operator (including the platform admins' domains) is never used. Sub-domains are separate domains.
- **A domain is a trust grant.** Once a domain is verified and SSO is on, the workspace's IdP decides who every address on that domain is, existing accounts included. That is why verification is required and why a workspace can only connect an IdP it controls.

## For operators

### Turning it on (docker-compose.deployment.yml)

SSO is off by default. With `deploy.sh`, add to the root `.env` (the compose substitution file, not `.env.deployment`):

```bash
SSO_ENABLED=true
# Polis as browsers and IdPs reach it, behind your TLS proxy
SSO_POLIS_URL=https://sso.example.org
# the backend's callback; must be reachable by browsers
SSO_REDIRECT_URI=https://api.example.org/api/v1/auth/sso/callback
# the SAML entity ID (audience) IdPs see; any stable URI you own
SSO_SAML_AUDIENCE=https://sso.example.org
```

Then run `./deploy.sh`. With `SSO_ENABLED=true` it:

- generates `BC_POLIS_PASSWORD`, `SSO_POLIS_API_KEY` (Polis's `JACKSON_API_KEYS`), `POLIS_CLIENT_SECRET_VERIFIER`, `POLIS_NEXTAUTH_SECRET` and a 32-character `POLIS_DB_ENCRYPTION_KEY` into `.env` (once; keep them, and back them up: losing `POLIS_DB_ENCRYPTION_KEY` loses every connection);
- creates Polis's own database `polis` and role `bc_polis` in `app-postgres` (idempotent; the role owns only that database);
- starts the `polis` service (compose profile `sso`) and passes the `SSO_*` settings to the backend and auth.

Polis runs with `IDP_ENABLED=false` (no IdP-initiated sign-in), `OPENID_REDIRECT_EXACT_MATCH=true` (the redirect URI must match exactly), a random `CLIENT_SECRET_VERIFIER` (never Polis's default `dummy`) and `DB_ENCRYPTION_KEY`. The image defaults to `boxyhq/jackson:latest`; version 26.2.0 is the one tested. Pin it with `POLIS_IMAGE=boxyhq/jackson:<version>` in `.env`.

The webapp's SSO screens are a build-time flag: build the image with `--build-arg NEXT_PUBLIC_ENABLE_SSO=true`.

### Exposing Polis

Polis listens on `127.0.0.1:5225`. Publish only the paths browsers and IdPs need at `SSO_POLIS_URL`, over TLS, and never the admin API (`/api/v1/*`, authenticated by the API key, used by the backend over the internal network) or the admin UI:

```nginx
server {
    listen 443 ssl;
    server_name sso.example.org;
    location /api/oauth/       { proxy_pass http://127.0.0.1:5225; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto https; }
    location /.well-known/     { proxy_pass http://127.0.0.1:5225; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto https; }
    location /                 { return 404; }
}
```

`/api/oauth/saml` (the SAML ACS) and `/api/oauth/oidc` (the OIDC redirect) receive the IdPs' answers through the browser; `/api/oauth/authorize` starts a sign-in; `/api/oauth/token` and `/api/oauth/userinfo` are called by the auth service, which uses `http://polis:5225` inside the compose network.

### Settings

| Service | Setting | Default | Meaning |
|---|---|---|---|
| backend, auth | `SSO_ENABLED` | `false` | Feature flag. Off: `/auth/sso/*` refuse with `sso_disabled`, the admin API answers `sso_disabled`, no SSO requirement is enforced |
| backend, auth | `SSO_POLIS_URL` | | Polis as browsers reach it |
| backend, auth | `SSO_POLIS_INTERNAL_URL` | `SSO_POLIS_URL` | Polis as the services reach it (`http://polis:5225` in compose) |
| backend, auth | `SSO_POLIS_PRODUCT` | `bettercollected` | Polis product |
| backend, auth | `SSO_REDIRECT_URI` | | The backend's `/api/v1/auth/sso/callback`, registered on every connection |
| backend | `SSO_POLIS_API_KEY` | | One of Polis's `JACKSON_API_KEYS`. Server-side only |
| backend | `SSO_SAML_AUDIENCE` | | Polis's `SAML_AUDIENCE`, shown to admins as the entity ID |
| backend | `SSO_MAX_CONNECTIONS_PER_WORKSPACE` | `5` | |
| backend | `SSO_HTTP_TIMEOUT_SECONDS` | `15` | Polis admin API calls |
| auth | `SSO_STATE_MAX_AGE_SECONDS` | `600` | How long a started sign-in may take |
| auth | `SSO_ASSERTION_MAX_AGE_SECONDS` | `120` | How long the backend has to finish a checked sign-in |
| auth | `SSO_POLIS_CLIENT_SECRET` | | Optional: Polis's `CLIENT_SECRET_VERIFIER`, sent on the token call. Every sign-in uses PKCE, which Polis checks instead |
| webapp (build) | `NEXT_PUBLIC_ENABLE_SSO` | `false` | Shows "Sign in with SSO" and the settings page |

`API_ALLOWED_COLLABORATORS` (backend) is the seat cap a first SSO sign-in is checked against, the same as an accepted invitation. `PLATFORM_ADMIN_EMAILS` must be set on the backend too (it reserves those domains, see below).

### Local development

```bash
docker compose -f docker-compose.local.yml up -d     # Mongo + app-postgres
scripts/sso-dev-setup.sh --seed-workspace            # Polis :5225, mock SAML IdP :4000, demo workspace
```

The script generates throwaway secrets in `.sso-dev/` (gitignored), creates the `polis` database, starts `docker-compose.sso.yml` and prints the `SSO_*` lines for `backend/.env` and `auth/.env` (`SSO_POLIS_API_KEY` is `JACKSON_API_KEYS` from `.sso-dev/polis.env`). The mock IdP only issues `@example.com` and `@example.org` addresses, which domain verification refuses to claim, and there is no DNS to publish a record in. So `--seed-workspace` (or `--workspace <id>`) marks `example.com` verified for the workspace **directly in the local Mongo**; this is a local-only shortcut. Then, signed in as the workspace owner (`owner@example.com`, email code), open the workspace's Single sign-on settings, add a SAML connection by pasting the XML from `http://localhost:4000/api/saml/metadata` (a `localhost` metadata URL is refused by design), test it, enable it, and sign out. "Sign in with SSO" with any `@example.com` address then goes through the mock IdP; pick `@example.org` there to see the domain refusal. Teardown: `docker compose -f docker-compose.sso.yml -p bettercollected-sso down`, and drop the `polis` database to wipe Polis.

## For workspace admins

Settings → **Single sign-on** (Owner and Admins: the `security.manage` permission).

1. **Verify your domain** under Settings → Domains first.
2. **Register BetterCollected at your IdP** with the values the page shows: for SAML the **ACS URL** (reply URL) and the **entity ID** (audience), or the SP metadata URL; for OIDC the **redirect URI**. The IdP must send the user's email address (SAML NameID or an email attribute; OIDC `email` claim).
3. **Add a connection**: SAML from the IdP's metadata URL (https and public only) or its metadata XML, or OIDC from the discovery URL plus the client ID and secret. The secret goes to Polis, encrypted there, and is never shown again or stored by BetterCollected.
4. **Test connection**: you sign in at the IdP once. The result comes back to the page. It passes when the IdP vouched for an address on one of your verified domains. Testing never signs anyone in and never creates accounts or members.
5. **Enable** the connection. One connection is enabled at a time; enabling another disables the first, which allows moving to a new IdP without a gap.
6. Optionally choose the **role for new members** and **require single sign-on**.

People who sign in with SSO for the first time join the workspace with the default role (Collaborator today; the setting accepts every workspace role except Admin, which is never given by an IdP). Existing members keep their role. A workspace with no free seat refuses new members with a clear message and creates no account. SSO members get no personal workspace.

### Requiring single sign-on

"Require single sign-on for *your domains*" refuses every other way of signing in for addresses on the workspace's SSO domains: email codes (on the dashboard and on every workspace's respondent pages) and Google. It needs an enabled connection that passed a test and at least one SSO domain, and while it is on, the enabled connection can't be disabled or deleted. When you turn it on you can sign out the members on those domains at once (their sessions from before; the owner's sessions and your own current session are kept), so their next sign-in goes through the IdP.

The requirement is only enforced while it can be met: with SSO switched off on the instance, the workspace disabled, the connection disabled or the domain's verification lost, nothing is refused.

**Break-glass:** the **workspace owner** can always sign in with an email code, even when SSO is required, so a broken or misconfigured IdP can't lock everyone out. Google stays refused for the owner too. Keep the owner's mailbox protected; to fix a broken IdP, the owner signs in with a code, turns the requirement off or switches to another connection.

## Security notes

- **State and PKCE.** Every sign-in uses PKCE (S256); the verifier lives only in our Fernet-encrypted state (`AUTH_AES_HEX_KEY`) together with the tenant, the connection and the time, and the state expires after `SSO_STATE_MAX_AGE_SECONDS`. The authorize request names the connection itself (its Polis clientID); the callback checks that userinfo's `requested.tenant`, `requested.product` and `requested.client_id` are the ones the sign-in started with.
- **Order of checks.** The connection, workspace, domain and seat checks run before auth creates an account, so a refused sign-in leaves nothing behind.
- **Redirects.** After sign-in the browser goes only to this instance's origins (`login_redirect.py`: `API_CLIENT_URL` and `allowed_origins`). Errors redirect with a code from a fixed list (`sso_error=`), never free text.
- **Sessions.** An SSO sign-in creates a revocable session like every other provider (`method: "sso"`, listed under Account settings → Sessions).
- **Platform admins.** An SSO session never gets the platform-admin role from `PLATFORM_ADMIN_EMAILS`, whatever its email: the backend tells auth the session is not admin-eligible on sign-in, on every refresh and in the import-OAuth token exchange. On top of that, the platform admins' domains (and `VERIFIED_DOMAINS_RESERVED`) can't be claimed, and a domain that becomes reserved after it was verified is no longer used for SSO.
- **Email case.** SSO compares emails case-insensitively: `bob@acme.com` signs in to an existing `Bob@Acme.com` account instead of creating a second one. Several accounts differing only in case are refused (`sso_account_conflict`). The other sign-in paths still match exactly (a central normalisation is a follow-up).
- **SSRF.** Metadata and discovery URLs must be `https`, without credentials, and resolve only to public addresses (no private, loopback, link-local, CGNAT, multicast or reserved ranges, IPv4 or IPv6) before they are handed to Polis, which fetches them. Polis resolves the name again when it fetches, so DNS rebinding is not covered by this check; keep Polis on a network that can't reach internal admin services.
- **Secrets.** The Polis API key is used server-side only. OIDC client secrets pass through the backend to Polis and are never stored or logged by BetterCollected; Polis encrypts its store with `DB_ENCRYPTION_KEY`.
- **Not covered:** IdP-initiated sign-in (off in Polis), single logout (signing out of BetterCollected does not sign out of the IdP), and SCIM provisioning (below). Removing someone at the IdP stops new sign-ins; their existing sessions run until they expire or are revoked. Removing the member from the workspace takes away their access at once.

## API

All under `/api/v1/workspaces/{workspace_id}/sso`, all requiring `security.manage`:

| Method | Path | Result |
|---|---|---|
| GET | `` | `available`, `serviceProvider` (ACS URL, entity ID, SP metadata URL, OIDC redirect URI), `domains`, `connections`, `settings`, `maxConnections` |
| POST | `/connections` | 201. `{type: "saml", name?, metadataXml \| metadataUrl}` or `{type: "oidc", name?, discoveryUrl, clientId, clientSecret}`. 422 `https_required`, `private_address`, `unresolvable_host`, `invalid_url`, `metadata_required`, `invalid_metadata`, `oidc_fields_required`, `too_many_connections`; 409 `idp_already_connected` (the IdP's entity ID belongs to another workspace) or `connection_exists`; 503 `sso_unavailable` |
| POST | `/connections/{id}/enable` | enables it, disables the others |
| POST | `/connections/{id}/disable` | 409 `sso_required_on` while it is the enabled one and SSO is required |
| DELETE | `/connections/{id}` | 204; also deleted in Polis. 409 as above |
| GET | `/connections/{id}/test` | browser navigation: the IdP, then back to the settings page with `?sso_test=ok` or a code |
| PUT | `/settings` | `{ssoRequired?, defaultRole?, revokeSessions?}`. 409 `sso_connection_required`, `sso_connection_untested`, `sso_domain_required`; 422 `invalid_role`. Answers the settings with `revokedSessions` |

Sign-in: `GET /api/v1/auth/sso/login?email=` and `GET /api/v1/auth/sso/callback` (Polis's redirect). Login error codes (`?sso_error=`): `sso_disabled`, `sso_not_configured`, `sso_failed`, `sso_expired`, `sso_bad_state`, `sso_tenant_mismatch`, `sso_email_domain_not_allowed`, `sso_workspace_unavailable`, `sso_seat_limit`, `sso_account_conflict`. An email code refused by the requirement answers 403 `{code: "sso_required", message}`; a refused Google sign-in returns to the login page with `login_error=sso_required`.

The auth service's routes (`/auth/sso/authorize`, `/auth/sso/callback`, `POST /auth/sso/account`) are internal like all of auth's API.

## Storage

Collection `sso_connections` (`SsoConnectionDocument`) with its Postgres twin `app.sso_connections` in the identity group (revision `0008`, a new table only): workspace, type (`saml`/`oidc`), name, status (`enabled`/`disabled`), the Polis clientID, tenant and product, the IdP's entity ID or discovery URL and OIDC client ID (never the secret), who created and enabled it, and the last test's time, user and outcome. Unique Polis clientID; index on workspace and status. The workspace document carries `sso_required` (with who and when) and `sso_default_role`. Sessions carry `method: "sso"`. Deleting a workspace deletes its connections here and in Polis.

## Tests

- auth: `tests/integration/app/test_sso_service.py` (PKCE and state, tenant/product/connection mismatch, case-insensitive matching, the assertion, no platform-admin role, the internal key), `test_postgres_parity.py` (the case-insensitive lookup in both stores).
- backend: `tests/app/controllers/test_sso_login.py` (unverified, lost, reserved and other workspaces' domains, tenant mismatch, seat cap before the account exists, never downgrading, sessions, redirects, connection tests), `test_sso_admin.py` (admin API, SSRF, SSO required, break-glass, Google, revocation), `tests/app/services/test_sso_url_guard.py`, `tests/app/repositories/test_sso_connection_parity.py`, and a row per endpoint in `test_permission_matrix.py`. Polis and auth are stand-ins (`tests/app/sso_helpers.py`); nothing calls a real IdP or resolves real names.

## SCIM (next phase)

Polis also runs a SCIM 2.0 server (Directory Sync) that sends signed webhooks per tenant. The plan, not built yet: a directory created through Polis's `/api/v1/dsync` for the same tenant (the workspace id), and a backend webhook endpoint that verifies the signature with a timestamp window, dedupes events, and maps them to the workspace: `user.created/updated` (active) → account for verified domains only + membership with the default role; deactivated or deleted → disable the membership and `SessionService.revoke_all_for_user` (never delete the person's data); groups → a per-workspace group-to-role mapping (the owner is never changed). That needs one table for event dedupe and the group mapping, with a Mongo twin.
