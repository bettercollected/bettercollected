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

- **The tenant is the workspace.** Polis's tenant is the workspace id and its product is `SSO_POLIS_PRODUCT` (`bettercollected`). The workspace's SCIM directory ([directory sync](#directory-sync-scim)) attaches to the same tenant.
- **SSO only covers verified domains.** A connection applies to the workspace's email domains verified with a DNS TXT record ([verified-domains.md](verified-domains.md)). A domain that is only claimed, one whose verification was lost (`verificationLostAt`), one verified by another workspace, or one reserved by the operator (including the platform admins' domains) is never used. Sub-domains are separate domains.
- **A domain is a trust grant.** Once a domain is verified and SSO is on, the workspace's IdP decides who every address on that domain is, existing accounts included, **the owner's own**. That is why verification is required, and why **only the workspace owner** can change the SSO configuration (connections, "require SSO", the default role): an Admin able to enable an IdP they control could sign in as the owner or anyone else on the domain.

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

- checks that `SSO_POLIS_URL`, `SSO_REDIRECT_URI` and `SSO_SAML_AUDIENCE` are set;
- generates Polis's secrets into `.env` (once): `BC_POLIS_PASSWORD`, `SSO_POLIS_API_KEY` (Polis's `JACKSON_API_KEYS`), `POLIS_CLIENT_SECRET_VERIFIER`, `POLIS_NEXTAUTH_SECRET` and a 32-character `POLIS_DB_ENCRYPTION_KEY`. Keep them and back them up: losing `POLIS_DB_ENCRYPTION_KEY` loses every connection;
- adds the overlay `docker-compose.sso-deployment.yml`, which starts `polis` and its own `polis-postgres` and puts the backend, the jobs worker and auth on Polis's network.

Polis lives only in that overlay, so a deployment without SSO reads none of it and needs none of its values. The overlay requires them (`${VAR:?}`), so an SSO deployment refuses to start with an empty key. Running compose by hand with SSO:

```bash
docker compose -f docker-compose.deployment.yml -f docker-compose.sso-deployment.yml up -d
```

Polis runs with `IDP_ENABLED=false` (no IdP-initiated sign-in), `OPENID_REDIRECT_EXACT_MATCH=true` (the redirect URI must match exactly), a random `CLIENT_SECRET_VERIFIER` (never Polis's default `dummy`) and `DB_ENCRYPTION_KEY`. The image is pinned by digest to 26.2.0, the version tested; override it with `POLIS_IMAGE` in `.env` only after testing another.

**Network isolation.** Polis fetches nothing an admin typed in (we fetch metadata and discovery documents ourselves, see "SSRF" below), but it does call the IdPs' token, userinfo and JWKS endpoints. So it runs on its own networks, defined in the overlay: `polis-db` (internal, Polis and its Postgres only) and `sso` (Polis, the backend, the jobs worker and auth, with internet egress). It cannot reach Mongo, `app-postgres`, Temporal, Umami or the other services. The backend and auth can reach it, and it can reach their HTTP ports in turn (auth's API needs the internal key). Local development (`docker-compose.sso.yml`) is simpler: Polis joins the local stack's network and keeps its data in `app-postgres`.

The webapp's SSO screens are a build-time flag: build the image with `--build-arg NEXT_PUBLIC_ENABLE_SSO=true`.

### Exposing Polis

Polis listens on `127.0.0.1:5225`. Publish only the paths browsers and IdPs need at `SSO_POLIS_URL`, over TLS, and never the admin API (`/api/v1/*`, authenticated by the API key, used by the backend over the internal network) or the admin UI:

```nginx
server {
    listen 443 ssl;
    server_name sso.example.org;
    location /api/oauth/       { proxy_pass http://127.0.0.1:5225; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto https; }
    location /.well-known/     { proxy_pass http://127.0.0.1:5225; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto https; }
    # only with directory sync (SCIM), see below
    location /api/scim/        { proxy_pass http://127.0.0.1:5225; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto https; }
    location /                 { return 404; }
}
```

`/api/oauth/saml` (the SAML ACS) and `/api/oauth/oidc` (the OIDC redirect) receive the IdPs' answers through the browser; `/api/oauth/authorize` starts a sign-in; `/api/oauth/token` and `/api/oauth/userinfo` are called by the auth service, which uses `http://polis:5225` inside the compose network. Deleting a connection sends Polis the connection's own client secret as a query parameter (the only form Polis's admin DELETE accepts); that request stays on the internal `sso` network, and the admin API must never be exposed.

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

The script generates throwaway secrets in `.sso-dev/` (gitignored), creates the `polis` database, starts `docker-compose.sso.yml` and prints the `SSO_*` lines for `backend/.env` and `auth/.env` (`SSO_POLIS_API_KEY` is `JACKSON_API_KEYS` from `.sso-dev/polis.env`). The mock IdP only issues `@example.com` and `@example.org` addresses, which domain verification refuses to claim, and there is no DNS to publish a record in. So `--seed-workspace` (or `--workspace <id>`) marks `example.com` verified for the workspace **directly in the local Mongo**; this is a local-only shortcut. Then, signed in as the workspace owner (`owner@example.com`, email code), open the workspace's Single sign-on settings, add a SAML connection by pasting the XML from `http://localhost:4000/api/saml/metadata` (a `localhost` metadata URL is refused by design), test it, enable it, and sign out. "Sign in with SSO" with any `@example.com` address then goes through the mock IdP; pick `@example.org` there to see the domain refusal. Both containers listen on `127.0.0.1` only, and mock-saml is pinned to 1.4.2 (by digest). Teardown: `docker compose -f docker-compose.sso.yml -p bettercollected-sso down`, and drop the `polis` database to wipe Polis.

## For workspace admins

Settings → **Single sign-on**. Owner and Admins (`security.manage`) see the page and can **test** a connection, which never signs anyone in. **Only the workspace owner** creates, enables, disables and deletes connections and changes "require single sign-on" and the default role.

1. **Verify your domain** under Settings → Domains first.
2. **Register BetterCollected at your IdP** with the values the page shows: for SAML the **ACS URL** (reply URL) and the **entity ID** (audience), or the SP metadata URL; for OIDC the **redirect URI**. The IdP must send the user's email address (SAML NameID or an email attribute; OIDC `email` claim).
3. **Add a connection** (it needs a verified domain first, so a workspace can't register another organisation's public IdP metadata and squat its entity ID in Polis; refused with 409 `sso_domain_required` otherwise): SAML from the IdP's metadata URL (https and public only) or its metadata XML, or OIDC from the discovery URL plus the client ID and secret. The secret goes to Polis, encrypted there, and is never shown again or stored by BetterCollected. If the IdP's entity ID is already connected to another workspace (for example registered first by someone else), creating it fails with `idp_already_connected` and a message to contact support, who can check who owns it and release it.
4. **Test connection**: you sign in at the IdP once. The result comes back to the page. It passes when the IdP vouched for an address on one of your verified domains. Testing never signs anyone in and never creates accounts or members.
5. **Enable** the connection: only after this connection's current configuration passed a test (re-adding the same IdP updates it in Polis and asks for a new test). One connection is enabled at a time; enabling another disables the first, which allows moving to a new IdP without a gap.
6. Optionally choose the **role for new members** and **require single sign-on**.

People who sign in with SSO for the first time join the workspace with the default role: **Viewer** unless the owner chose Reviewer or Editor (Admin and Privacy officer are never given by an IdP; they are granted by hand). A workspace whose default was stored as `COLLABORATOR` before the new roles keeps it: that is Editor. Existing members keep their role. A **disabled** membership stays disabled: that person gets no session (`sso_membership_disabled`). A **removed** member who signs in with SSO again is added again, like any first SSO sign-in (that is how just-in-time membership works); to keep someone out, remove them at the IdP, or connect a directory: with [directory sync](#directory-sync-scim) the IdP deactivates people, and someone it deactivated can't sign in with SSO again (`sso_deprovisioned`). A workspace with no free seat refuses new members with a clear message and creates no account; the cap is checked before the account exists and again after the membership is written, and a sign-in that raced past the first look gives its seat back (in a tight race both may be refused, never both admitted). SSO members get no personal workspace.

### Requiring single sign-on

"Require single sign-on for *your domains*" refuses every other way of signing in for addresses on the workspace's SSO domains: email codes on the dashboard and on this workspace's own forms, and Google. It needs an enabled connection that passed a test and at least one SSO domain, and while it is on, the enabled connection can't be disabled or deleted.

- **Existing sessions end at their next refresh** (within `AUTH_ACCESS_TOKEN_EXPIRY_IN_MINUTES`, 15 by default): any session for an address on those domains that did not sign in with SSO, member of the workspace or not. Exceptions: the owner's email-code sessions (break-glass) and respondent-scoped sessions (below). When you turn the requirement on you can also sign out the members on those domains at once (the owner's sessions and your own current session are kept).
- **Respondents on other workspaces' forms.** Someone on such a domain may still verify their email with a code to answer *another* workspace's forms. That session is **respondent-scoped** (`scope: "respondent"` and the workspace it was made for): it holds no workspace permission anywhere (`authorize()` grants nothing, and every route beyond answering forms and managing the user's own respondent data depends on `get_full_user`, which answers 403 `respondent_session`: creating workspaces, import OAuth, templates, billing, actions, API keys, platform admin; `/workspaces/mine` may list workspaces but never with dashboard access), carries only the respondent role (no creator, no platform admin), creates no personal workspace, and is exempt from the refresh rule. It acts only on the workspace it was made for (`scope_workspace_id`): on any other workspace's routes it counts as not signed in, and on the SSO workspace's own forms it is refused with `sso_required`. On the SSO workspace's own forms, email codes stay refused for those addresses.

The requirement is only enforced while it can be met: with SSO switched off on the instance, the workspace disabled, the connection disabled or the domain's verification lost, nothing is refused.

**Break-glass:** the **workspace owner** can always sign in with an email code, even when SSO is required, so a broken or misconfigured IdP can't lock everyone out. Google stays refused for the owner too. Keep the owner's mailbox protected; to fix a broken IdP, the owner signs in with a code, turns the requirement off or switches to another connection.

## Security notes

- **State and PKCE.** Every sign-in uses PKCE (S256); the verifier lives only in our Fernet-encrypted state (`AUTH_AES_HEX_KEY`) together with the tenant, the connection and the time, and the state expires after `SSO_STATE_MAX_AGE_SECONDS`. The authorize request names the connection itself (its Polis clientID); the callback checks that userinfo's `requested.tenant`, `requested.product` and `requested.client_id` are the ones the sign-in started with.
- **Order of checks.** The connection, workspace, domain and seat checks run before auth creates an account, so a refused sign-in leaves nothing behind.
- **Login CSRF and replay.** Starting a sign-in (or a test) sets a short-lived HttpOnly, SameSite=Lax cookie `SsoNonce` (path `/api/v1/auth/sso`, 10 minutes) whose SHA-256 travels in the encrypted state. The callback needs that browser's cookie (`sso_session_mismatch` otherwise), and each nonce is accepted once (`sso_used_states`, unique, expiring), so a victim's browser can't be signed in to an attacker's account and a callback can't be replayed. (In the local end-to-end run a replayed callback got past Polis's token exchange and was stopped by this record, so don't rely on Polis for single use.)
- **Redirects.** After sign-in the browser goes only to this instance's origins (`login_redirect.py`: `API_CLIENT_URL` and `allowed_origins`). The dashboard URL is built on that allow-listed origin with the workspace handle URL-quoted as one path segment (so a handle like `//evil.com` can't change the host) and checked against the allow-list again. Errors redirect with a code from a fixed list (`sso_error=`), never free text.
- **Sessions.** An SSO sign-in creates a revocable session like every other provider (`method: "sso"`, listed under Account settings → Sessions). A previous session in the same browser (its cookies) is revoked when the SSO sign-in replaces it.
- **Connection tests.** A failed test is recorded on the connection only for the browser that started it (its nonce) and only while that admin may still manage SSO, so a replayed test state can't mark a connection as failed.
- **Platform admins.** An SSO session never has the platform-admin role: not from `PLATFORM_ADMIN_EMAILS` (the backend tells auth the session is not admin-eligible on sign-in, on every refresh and in the import-OAuth token exchange) and not one stored on the account either (auth leaves it out of the SSO sign-in and the backend strips it on every refresh). On top of that, the platform admins' domains (and `VERIFIED_DOMAINS_RESERVED`) can't be claimed, and a domain that becomes reserved after it was verified is no longer used for SSO.
- **Email case.** SSO compares emails case-insensitively: `bob@acme.com` signs in to an existing `Bob@Acme.com` account instead of creating a second one. Several accounts differing only in case are refused (`sso_account_conflict`). The other sign-in paths still match exactly (a central normalisation is a follow-up).
- **SSRF.** Polis is never handed a URL an admin typed. A SAML metadata URL is fetched by the backend (every redirect hop checked, at most 3, 512 KB cap) and Polis gets the XML. An OIDC discovery document is fetched the same way, and every endpoint it lists (`issuer`, `authorization_endpoint`, `token_endpoint`, `userinfo_endpoint`, `jwks_uri`) must be `https` and resolve only to public addresses; Polis gets those checked endpoints as the connection's metadata (it never fetches the discovery URL), and they are checked again before each test. "Public" means no private, loopback, link-local, CGNAT, multicast, reserved or unspecified ranges, IPv4 or IPv6, and no credentials in the URL. **Residual risk:** names are resolved for the check and again for the request (by the backend, and by Polis when it calls the token, userinfo and JWKS endpoints at sign-in), so a name whose DNS answer changes after the check (rebinding, or a later DNS change at the IdP) is not covered. That is why Polis runs on its own networks (above).
- **Secrets.** The Polis API key is used server-side only. OIDC client secrets pass through the backend to Polis and are never stored or logged by BetterCollected; Polis encrypts its store with `DB_ENCRYPTION_KEY`.
- **Known limitation: leftover entity IDs in Polis.** Deleting a connection deletes it in Polis first (the request fails if Polis is unreachable). Deleting a workspace deletes its Polis tenant on a best-effort basis: if Polis is unreachable at that moment, our records go and the Polis connections stay, and their IdP entity IDs can't be registered by another workspace until an operator deletes them through Polis's admin API (`DELETE /api/v1/sso?tenant=<workspace id>&product=bettercollected`). The deletion is logged as a warning.
- **Not covered:** IdP-initiated sign-in (off in Polis), and single logout (signing out of BetterCollected does not sign out of the IdP). Without a directory, removing someone at the IdP stops new sign-ins, and their existing sessions run until they expire or are revoked; [directory sync](#directory-sync-scim) disables the membership and revokes the sessions. Removing the member from the workspace takes away their access at once.

## API

All under `/api/v1/workspaces/{workspace_id}/sso`, all requiring `security.manage`, and the changes also the workspace owner (`AuthorizationService.require_owner`):

| Method | Path | Result |
|---|---|---|
| GET | `` | `available`, `serviceProvider` (ACS URL, entity ID, SP metadata URL, OIDC redirect URI), `domains`, `connections`, `settings`, `maxConnections` |
| POST | `/connections` | **Owner.** 201. `{type: "saml", name?, metadataXml \| metadataUrl}` or `{type: "oidc", name?, discoveryUrl, clientId, clientSecret}`. 422 `https_required`, `private_address`, `unresolvable_host`, `invalid_url`, `fetch_failed`, `invalid_discovery`, `metadata_required`, `invalid_metadata`, `oidc_fields_required`, `too_many_connections`; 409 `idp_already_connected` (the IdP's entity ID belongs to another workspace) or `connection_exists`; 503 `sso_unavailable` |
| POST | `/connections/{id}/enable` | **Owner.** Enables it, disables the others. 409 `sso_connection_untested` unless this connection passed a test |
| POST | `/connections/{id}/disable` | **Owner.** 409 `sso_required_on` while it is the enabled one and SSO is required |
| DELETE | `/connections/{id}` | **Owner.** 204; also deleted in Polis. 409 as above |
| GET | `/connections/{id}/test` | Owner and Admins. Browser navigation: the IdP, then back to the settings page with `?sso_test=ok` or a code |
| PUT | `/settings` | **Owner.** `{ssoRequired?, defaultRole?, revokeSessions?}`. 409 `sso_connection_required`, `sso_connection_untested`, `sso_domain_required`; 422 `invalid_role`. Answers the settings with `revokedSessions` |

The overview (`GET`) is Owner and Admins and says `canManage` (the caller is the owner).

Sign-in: `GET /api/v1/auth/sso/login?email=` and `GET /api/v1/auth/sso/callback` (Polis's redirect). Login error codes (`?sso_error=`): `sso_disabled`, `sso_not_configured`, `sso_failed`, `sso_expired`, `sso_bad_state`, `sso_tenant_mismatch`, `sso_email_domain_not_allowed`, `sso_workspace_unavailable`, `sso_seat_limit`, `sso_account_conflict`, `sso_session_mismatch`, `sso_membership_disabled`. An email code refused by the requirement answers 403 `{code: "sso_required", message}`; a refused Google sign-in returns to the login page with `login_error=sso_required`. `POST /api/v1/auth/otp/validate` takes an optional `workspace_id` (the workspace whose forms the code was asked for), which decides whether such an address gets a respondent-scoped session.

The auth service's routes (`/auth/sso/authorize`, `/auth/sso/callback`, `POST /auth/sso/account`) are internal like all of auth's API.

## Storage

Collection `sso_connections` (`SsoConnectionDocument`) with its Postgres twin `app.sso_connections` in the identity group (revision `0008`, a new table only): workspace, type (`saml`/`oidc`), name, status (`enabled`/`disabled`), the Polis clientID, tenant and product, the IdP's entity ID or discovery URL and OIDC client ID (never the secret), who created and enabled it, and the last test's time, user and outcome. Unique Polis clientID; index on workspace and status. Collection `sso_used_states` with its twin `app.sso_used_states` (revision `0009`, a new table only): the hash of each accepted sign-in nonce, unique, until it expires (Mongo TTL index; the twin deletes expired rows on each claim). The workspace document carries `sso_required` (with who and when) and `sso_default_role`. Sessions carry `method` (`sso`, `otp`, `google`) and, for a respondent-only session, `scope: "respondent"` with `scope_workspace_id`; the tokens carry them as `auth_method`, `session_scope` and `scope_workspace_id`. Deleting a workspace deletes its connections here and in Polis.

## Tests

- auth: `tests/integration/app/test_sso_service.py` (PKCE and state, tenant/product/connection mismatch, case-insensitive matching, the assertion, no platform-admin role, the internal key), `test_postgres_parity.py` (the case-insensitive lookup in both stores).
- backend: `tests/app/controllers/test_sso_login.py` (unverified, lost, reserved and other workspaces' domains, tenant mismatch, seat cap before the account exists, never downgrading, sessions, redirects, connection tests), `test_sso_admin.py` (admin API, owner only, enabling needs a test, SSRF with redirect hops and OIDC endpoints, SSO required, break-glass, Google, revocation), `test_sso_review.py` (crafted workspace handles, the nonce cookie and single-use states, disabled memberships, the seat race, no stored admin role, sessions ending at refresh, respondent-scoped sessions), `tests/app/services/test_sso_url_guard.py`, `tests/app/repositories/test_sso_connection_parity.py`, and a row per endpoint in `test_permission_matrix.py`. Polis and auth are stand-ins (`tests/app/sso_helpers.py`); nothing calls a real IdP or resolves real names.

## Directory sync (SCIM)

Single sign-on adds people when they first sign in and never notices when they leave. Directory sync closes that gap: the identity provider **provisions** members (before their first sign-in), **deprovisions** them when they leave or are unassigned, and sets their **role from their groups**. Polis runs the SCIM 2.0 server (its Directory Sync); every change it receives arrives at the backend as a signed webhook event, which the backend applies to the workspace. The directory belongs to the same Polis tenant as the workspace's SSO connections (the workspace id).

```
IdP (Okta, Entra ID, ...) ─ SCIM 2.0, bearer token ─▶ Polis /api/scim/v2.0/<directory>
Polis ─ POST, BoxyHQ-Signature ─▶ backend /api/v1/scim/webhook/<our directory id>   (internal `sso` network)
backend: verify ─▶ dedupe ─▶ account (auth, verified domains only) ─▶ membership, role, sessions
nightly / "Resync now" / CLI: backend ─ GET /api/v1/dsync/users|groups ─▶ Polis, then the same rules
```

### For operators

Directory sync needs single sign-on on the instance (`SSO_ENABLED` and the rest, above) and one more setting:

| Service | Setting | Default | Meaning |
|---|---|---|---|
| backend | `SCIM_WEBHOOK_URL` | | Where Polis delivers events: the backend's `/api/v1/scim/webhook` **as Polis reaches it**. `docker-compose.sso-deployment.yml` sets `http://backend:8000/api/v1/scim/webhook` (the internal `sso` network). Each directory's own id is appended. Unset: directory sync is off |
| backend | `SCIM_SIGNATURE_TOLERANCE_SECONDS` | `300` | How old (or early) a signed event may be |
| backend | `SCIM_EVENT_RETENTION_SECONDS` | `86400` | How long accepted events are remembered against replays |
| backend | `SCIM_MAX_WEBHOOK_BYTES` | `1000000` | Largest webhook body (Polis sends at most 1 MB) |
| backend, jobs worker | `SCIM_RECONCILE_CRON` | `17 3 * * *` | The nightly resync (procrastinate cron) |
| backend | `SCIM_RECONCILE_PAGE_SIZE` | `50` | Page size asked of Polis. Polis caps pages at its own `db.pageLimit` (50 by default) whatever is asked; a resync pages on until an empty page, so any cap works |
| backend | `SCIM_RECONCILE_MAX_DEPROVISION_RATIO`, `SCIM_RECONCILE_MIN_DEPROVISION` | `0.2`, `5` | The resync safety stop (below) |
| backend | `SCIM_ROTATION_GRACE_HOURS` | `24` | After a token rotation, resyncs deactivate nobody for this long |

**Expose the SCIM endpoint** next to the sign-in paths, so identity providers can reach it (Polis checks the bearer token; the admin API stays internal):

```nginx
    location /api/scim/        { proxy_pass http://127.0.0.1:5225; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto https; }
```

The SCIM base URL shown to admins is `SSO_POLIS_URL/api/scim/v2.0/<directory id>` (Polis builds it from its `EXTERNAL_URL`).

**The webhook.** Polis posts over the internal `sso` network, so nothing about it has to be public. It is still safe to expose (behind `api.example.org` it is `/api/v1/scim/webhook/<id>`): it is authenticated by the signature alone, and the URL Polis gets always comes from `SCIM_WEBHOOK_URL`, never from a request. If you run Polis outside compose, point `SCIM_WEBHOOK_URL` at an address Polis can reach.

**The nightly resync** runs on the procrastinate jobs worker (`python -m backend.jobs.worker`, the `jobs-worker` compose service), wherever it runs; it needs the same `SSO_*` settings and `SCIM_WEBHOOK_URL` as the backend (the SSO overlay sets both). Without it, use the "Resync now" button, or the CLI from `backend/`:

```bash
uv run python -m backend.scim resync --workspace <workspace id>
uv run python -m backend.scim resync --all
uv run python -m backend.scim resync --workspace <workspace id> --force   # past the safety stop
```

**The resync safety stop.** A resync deactivates everyone Polis no longer lists, so a broken or partial listing could empty a workspace overnight. It therefore refuses, before changing anything, when it would deactivate more than 20 % of the provisioned members and at least 5 of them, or when Polis lists nobody while members are provisioned. The refusal is recorded on the directory (`mass_deprovision_refused`, shown on the settings page; the log has ids and counts only). The owner can force it from the page (after a confirmation) or with `--force`. Listing errors (Polis down, a reply that is not a list) fail the resync instead of passing for an empty directory. One directory's failure never stops the nightly run for the others.

**Duplicate memberships.** A workspace has one membership per user: a unique index on (`workspace_id`, `user_id`) in `workspace_users`, so SSO, SCIM and an invitation racing to add the same person can't create two (the loser reads the existing one). Databases from before may hold duplicates. Check before deploying:

```bash
uv run python -m backend.membership_duplicates   # read-only; exit 1 and a list of ids when there are duplicates
```

Resolve each pair by hand (keep the membership with the right role, delete the other; nothing is deleted automatically), then deploy. If duplicates remain, Postgres revision `0011` stops **before changing anything** with a message naming this command, and the backend logs an ERROR at startup instead of creating the Mongo index (it still starts; new inserts are deduplicated in code). Once resolved, the next migration and the next restart create the indexes.

**Local development.** After `scripts/sso-dev-setup.sh`, the backend runs on the host and Polis in a container, so Polis needs the host's address for webhooks. On Linux add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `polis` service (or use the gateway address of the `bettercollected_default` network, e.g. `docker network inspect bettercollected_default -f '{{(index .IPAM.Config 0).Gateway}}'`) and set `SCIM_WEBHOOK_URL=http://host.docker.internal:8000/api/v1/scim/webhook` in `backend/.env`. The backend must listen on `0.0.0.0` for the container to reach it.

### For workspace admins

Settings → **Single sign-on** → **Directory sync (SCIM)**. Owner and Admins see its status; **only the owner** creates, rotates and deletes the directory, maps groups and resyncs (a directory decides who joins and with which role, Admin included). A directory needs a verified domain, like SSO.

1. **Create the directory**: choose your identity provider (Okta, Microsoft Entra ID, OneLogin, JumpCloud or generic SCIM 2.0). The page shows the **SCIM base URL** and the **bearer token once**: copy both now. The token is never shown again or stored by BetterCollected; if it is lost, rotate it.
2. **At the identity provider** (the generic steps):
   - **Okta:** open the SAML app you use for SSO (or a new "SCIM 2.0 Test App (Header Auth)"), Provisioning → Integration: SCIM connector base URL = the base URL, unique identifier field = `userName`, authentication = HTTP Header with the bearer token. Enable "Create users", "Update user attributes" and "Deactivate users". Assign people and, under "Push Groups", the groups you want to map.
   - **Microsoft Entra ID:** Enterprise applications → your app → Provisioning → Automatic: Tenant URL = the base URL (it ends with `?aadOptscim062020`, keep it), Secret token = the bearer token, "Test connection", then Start provisioning. Assign users and groups to the app; Entra provisions every 40 minutes or so.
   - **Others:** the base URL, bearer authentication with the token, users identified by email (`userName` or the primary email).
3. **Map groups to roles** once the groups appear: each group maps to one workspace role or to none.

**What happens:**

| Directory event | Effect in the workspace |
|---|---|
| `user.created`, `user.updated` (active) | Only for an address on one of the workspace's verified domains: the account is found (case-insensitive) or created (email verified, never the platform-admin role), and the membership created or enabled with the role from its groups, else the default role (the SSO "role for new members"). Marked `provisioned_by: "scim"` |
| `user.updated` (`active: false`), `user.deleted` | The membership is **disabled** (reason `directory`), never deleted (their forms stay with the workspace), and **all** of the account's sessions are revoked (`scim_deprovisioned`), on every workspace, because sessions are per account: the simplest safe choice. Their next refresh fails, within the access-token lifetime (15 minutes by default); their memberships elsewhere are untouched, so they sign in again there. Applies to members invited by hand too, when their address is on one of the workspace's verified domains. A re-activated user is enabled again, if a seat is free, but only from the directory's own deactivation: a membership the plan disabled stays disabled |
| `group.created`, `group.updated` | The group is recorded or renamed (its mapping follows its id) |
| `group.user_added`, `group.user_removed`, `group.deleted` | Group membership is updated and the member's role recomputed |
| Address not on a verified domain | Ignored and listed as a failure ("not on one of this workspace's verified domains") |
| No free seat (`API_ALLOWED_COLLABORATORS`) | Nothing is created (no account, no membership) and it is listed as a failure; the next change or a resync retries. A membership disabled **only by the directory** holds no seat (for invitations and SSO too), so re-enabling it needs a free seat; one disabled by a plan downgrade keeps its seat (an upgrade re-enables it without a check, so the cap must hold it) |
| The auth service is unreachable | Nothing is decided for that user: the webhook answers 503 (Polis retries), a resync skips them and records `auth_unavailable` |
| The workspace owner | Never changed (not disabled, no role change), listed as "left alone" |
| A member invited by hand | Their role is never changed by the directory ("left alone"); a deactivation does disable them (on a verified domain), and a re-activation lifts it |
| A member who joined by SSO sign-in (just in time) | Taken over: from then on the directory manages them |

**Roles.** The highest role among a member's mapped groups wins (Admin, Editor, Reviewer, Viewer, then Privacy officer); members in no mapped group get the default role (Viewer unless the owner chose Reviewer or Editor); changing the default role or a mapping re-applies roles at once. Admin may be mapped; the owner never comes from a directory. Roles are read from the role list at runtime, so new workspace roles become mappable automatically. A member the directory manages shows **"Managed by your directory"** on the members page with the role picker disabled: their role follows their groups at the identity provider, and a change by hand is refused (`PATCH /workspaces/{id}/members/{user_id}` answers 409 `managed_by_directory`) until the directory is deleted. An Editor is stored as `COLLABORATOR`, like the role picker stores it. Mapping groups to member groups (for form-level access) comes with member groups.

**SCIM is authoritative.** While the workspace has a directory, someone it deactivated or deleted cannot sign in with SSO (`sso_deprovisioned`), even if the identity provider still lets them through and even if their membership was removed by hand.

**Rotate token.** Polis cannot change a directory's token, so rotating replaces the directory: a new **base URL and token** (shown once), and the old directory is deleted, so its token stops working. If Polis can't delete it right then, the reply and the page say the old token may still be accepted, with a **Retry** button; every resync retries too. Enter both at the identity provider; it sends its users and groups again. Users are matched by email; groups by Polis id where it is unchanged, else by name when exactly one previous group had that name (its mapping carries over). Several previous groups sharing a name carry nothing over: the new group starts unmapped and is flagged "Check the role" (a name is not proof enough to hand out a role, Admin least of all). **Grace:** for `SCIM_ROTATION_GRACE_HOURS` (24) after a rotation, resyncs deactivate nobody and remove no group, while the identity provider re-pushes; after that the usual rules (and the safety stop) apply. Users the directory had deactivated stay refused for SSO across the rotation.

**Delete.** Syncing stops: members stay with their role, and the directory's records are removed. The directory's own deactivations are lifted: someone it deactivated is enabled again when no other reason holds them and a seat is free; without a free seat they stay disabled (reason `seat_limit`), and the reply (`{reEnabled, leftDisabled}`) and the page say how many. A member also disabled by the plan stays disabled. Remove the SCIM app at the identity provider too.

**Status.** The section shows the last change received, the last resync, counts (active, deactivated, failed, left alone) and the people that need attention, with the reason.

### Security

- The webhook has no session or key: it is authenticated by Polis's `BoxyHQ-Signature: t=<ms>,s=<hex>` (the only header read; Polis 26.2.0 always sends it, and the identical `Ory-Polis-Signature` is ignored), an HMAC-SHA256 of `"<t>.<raw body>"` with the directory's own webhook secret (generated by us, stored encrypted with `AUTH_AES_HEX_KEY`, never returned or logged), compared in constant time. Missing or wrong signatures, timestamps more than 5 minutes off, and unknown directories all get the same 401; nothing but the directory lookup runs before the check.
- Every event must name this directory's Polis id, tenant (the workspace) and product (403 `tenant_mismatch` otherwise).
- Polis gives events no id and resends the same signed request when it retries, so each event is accepted once by a hash of (directory, type, data, signed time, its position in a batch) in `scim_events`; a duplicate answers 200 at once. A failed event releases its record and answers 503, so Polis's retry (3 times) is applied.
- Logs carry ids, event types and outcome codes, never emails or names.
- The SCIM bearer token is shown once and never stored here; Polis checks it.

### API

Under `/api/v1/workspaces/{workspace_id}/scim`; viewing needs `security.manage`, every change the workspace owner.

| Method | Path | Result |
|---|---|---|
| GET | `` | `available`, `hasVerifiedDomain`, `directory` (no secrets), `types`, `counts`, `issues`, `groups`, `defaultRole`, `mappableRoles`, `canManage` |
| POST | `/directory` | **Owner.** 201 `{directory, scimEndpoint, bearerToken}` (the token only here). 409 `sso_domain_required`, `scim_directory_exists`; 422 `invalid_directory_type`; 404 `scim_disabled`; 503 `scim_unavailable` |
| POST | `/directory/rotate` | **Owner.** `{directory, scimEndpoint, bearerToken, previousDirectoryDeleted}` |
| POST | `/directory/cleanup` | **Owner.** Retries deleting the previous Polis directory; 503 `scim_unavailable` while it can't |
| DELETE | `/directory` | **Owner.** `{reEnabled, leftDisabled}`; members stay |
| PUT | `/groups/{group_id}` | **Owner.** `{role}` (a workspace role or null). 422 `invalid_role` |
| POST | `/resync` | **Owner.** Body `{force?}`. `{directory, summary}`; 409 `mass_deprovision_refused` with `summary {wouldDeprovision, provisioned, listed}` (nothing changed); 503 `scim_unavailable`, `auth_unavailable` |

`POST /api/v1/scim/webhook/{directory_id}`: Polis only (signature). 200 `{applied, duplicates}`; 401, 403, 400, 503 as above; 413 above `SCIM_MAX_WEBHOOK_BYTES`, counted while the body is read (chunked bodies included). Auth's internal `POST /auth/sso/directory-account` finds or creates the account.

### Storage

Identity group, each a Mongo collection with its Postgres twin (revision `0010`, new tables only): `scim_directories` (workspace (unique), Polis directory id, tenant, product, type, name, SCIM base URL, the encrypted webhook secret, who created and rotated it, the last event and resync), `scim_users` (each directory user: Polis id, email, active/deleted, the account, the outcome and its reason), `scim_groups` (Polis id, name, mapped role), `scim_group_members` (our group and user ids, one row per pair) and `scim_events` (accepted events by hash, expiring: Mongo TTL index, the twin deletes expired rows on each claim). Workspace memberships carry `provisioned_by` (`sso`, `scim` or none) and `disabled_reasons` (`plan`, `directory`, `seat_limit`): each path lifts only its own reason, so an upgrade doesn't re-enable someone the directory deactivated and the directory doesn't re-enable someone a downgrade disabled (a disabled membership from before has none recorded and counts as `plan`; disabling it for another reason records `plan` first, so the directory can never re-enable it). The directory's status fields (last event, resync outcome, pending clean-up) are written field by field, never by saving the whole record, so they can't undo a concurrent rotation. Revision `0011` makes (`workspace_id`, `user_id`) unique in `workspace_users` (see "Duplicate memberships"). Deleting a workspace deletes its directory here and in Polis.

### Troubleshooting

- **The identity provider's "test connection" fails with 401:** the bearer token is wrong or was rotated; rotate and enter the new base URL and token.
- **Nothing arrives ("No change received yet"):** Polis can't reach `SCIM_WEBHOOK_URL` (check from the Polis container), or the backend refuses the signature (backend log: `SCIM webhook refused ... mismatch` means the secret differs, e.g. the directory was replaced outside BetterCollected; `expired` means the clocks differ by more than 5 minutes). Polis's own log lists failed deliveries. "Resync now" applies everything Polis holds regardless.
- **Someone is listed as failed with "not on one of this workspace's verified domains":** verify that domain, then resync.
- **"no free seat":** free seats or raise `API_ALLOWED_COLLABORATORS`, then resync.
- **A member's role doesn't change:** they were invited by hand or are the owner (the directory leaves roles alone), or their groups are not pushed to the SCIM app.
- **"it would have deactivated too many members":** the safety stop refused a resync. Check the app's assignments at the identity provider (an unassigned group, a filter); if the departures are real, resync with force.
- **A group says "Check the role":** after a rotation several previous groups had its name, so its role was not carried over; choose it again.
- **"The previous directory could not be deleted":** after a rotation Polis was not reachable; press Retry (or wait for the next resync). Until then the old token may still be accepted by Polis.
- **Someone deactivated still has access for a few minutes:** sessions end at their next refresh (the access-token lifetime); their membership is disabled at once, which stops every workspace permission immediately.

### Tests

Backend: `tests/app/controllers/test_scim_review.py` (Polis's capped pages through the real client with 120 users, the safety stop, plan and directory disable reasons, seats, the auth outage, one membership per user and the duplicate report, rotation clean-up, group matching and grace, the signature header), `tests/app/db/test_migrations.py` (0011 refuses with duplicates), `tests/app/controllers/test_scim.py` (signatures valid, invalid, expired and replayed, tenant mismatch, provisioning, deprovisioning with session revocation, the owner, unverified domains, the seat cap, group mapping and recomputation, members invited by hand, the SSO guard, resync, rotation, deletion), `tests/app/repositories/test_scim_parity.py`, and rows in `test_permission_matrix.py`. Auth: `tests/integration/app/test_sso_service.py` (`directory_account`). Polis is a stand-in (`tests/app/scim_helpers.py`).
