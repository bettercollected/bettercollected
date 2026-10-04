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

People who sign in with SSO for the first time join the workspace with the default role (Collaborator today; the setting accepts every workspace role except Admin, which is never given by an IdP). Existing members keep their role. A **disabled** membership stays disabled: that person gets no session (`sso_membership_disabled`). A **removed** member who signs in with SSO again is added again, like any first SSO sign-in (that is how just-in-time membership works); to keep someone out, remove them at the IdP. SCIM deprovisioning (next phase) will handle this properly. A workspace with no free seat refuses new members with a clear message and creates no account; the cap is checked before the account exists and again after the membership is written, and a sign-in that raced past the first look gives its seat back (in a tight race both may be refused, never both admitted). SSO members get no personal workspace.

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
- **Not covered:** IdP-initiated sign-in (off in Polis), single logout (signing out of BetterCollected does not sign out of the IdP), and SCIM provisioning (below). Removing someone at the IdP stops new sign-ins; their existing sessions run until they expire or are revoked. Removing the member from the workspace takes away their access at once.

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

## SCIM (next phase)

Polis also runs a SCIM 2.0 server (Directory Sync) that sends signed webhooks per tenant. The plan, not built yet: a directory created through Polis's `/api/v1/dsync` for the same tenant (the workspace id), and a backend webhook endpoint that verifies the signature with a timestamp window, dedupes events, and maps them to the workspace: `user.created/updated` (active) → account for verified domains only + membership with the default role; deactivated or deleted → disable the membership and `SessionService.revoke_all_for_user` (never delete the person's data); groups → a per-workspace group-to-role mapping (the owner is never changed). That needs one table for event dedupe and the group mapping, with a Mongo twin.
