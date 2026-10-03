# Enterprise SSO spike: Ory Polis (2026-10-03)

**Question.** Can BetterCollected offer "Sign in with your company IdP" by putting
[Ory Polis](https://github.com/ory/polis) (formerly BoxyHQ SAML Jackson) in front of
customer IdPs, while our own auth service stays the identity owner (users, tokens,
workspace membership)?

**Answer: yes.** The full loop works end to end against a local mock SAML IdP, in a
real browser, on branch `spike/sso-polis`. Polis turned SAML into a plain OAuth 2.0
code flow, so our side is one more login provider plus a just-in-time membership step.
The work that's left is not the protocol. It's the trust model around it: verified
domains, token lifetime and revocation, SSO-required enforcement, SCIM processing and
admin UI.

This is a spike. The code is flagged off (`SSO_ENABLED`, `NEXT_PUBLIC_ENABLE_SSO`).
It is real code, but the shortcuts listed under "Shortcuts taken" would have to go
before production.

---

## 1. What was proven

Versions: `boxyhq/jackson:latest` = Polis **26.2.0**, `boxyhq/mock-saml:latest` = **1.4.2**.

Checks done in Chrome (DevTools MCP) against the local stack (webapp :3000, backend
:8000, auth :8001, Polis :5225, mock IdP :4000):

| Check | Result |
|---|---|
| Login page → "Sign in with SSO" → `jane.sso@example.com` → mock IdP → back | Landed on `/example-corp-sso/dashboard/forms`, sidebar shows the workspace and role **Collaborator** |
| `GET /api/v1/auth/status` | 200, `email: jane.sso@example.com`, roles `FORM_RESPONDER, FORM_CREATOR` |
| Workspace membership (Mongo `workspace_users`) | new row `{user_id: <jane>, roles: ["COLLABORATOR"]}` next to the owner's `ADMIN` row; `/workspaces/mine` lists `example-corp-sso` |
| Token claims (decoded from the `Set-Cookie` on `/auth/sso/callback`) | `{"sub":"jane.sso@example.com", "email_verified": true, ...}` |
| Refusal A: `jane@unmapped-corp.com` (domain not mapped) | Back on `/login?sso_error=sso_not_configured` with the message *"Single sign-on isn't set up for this email domain..."*. Never left our domain. `/auth/status` → 401, no cookies |
| Refusal B: the tenant's IdP asserts `mallory@example.org` (outside the tenant's domains) | Polis completed SAML, then auth refused it: `/login?sso_error=sso_email_domain_not_allowed`, *"Your identity provider signed you in with an email address this workspace's single sign-on doesn't cover."* `/auth/status` → 401, and **no user document was created** |
| After rebasing onto #763 (verified-email linking) | Loop re-run with `raj.sso@example.com`: same result |

Tests (mocked Polis HTTP / mocked auth):
- `auth/tests/integration/app/test_sso_auth_provider.py`: 20 tests covering the authorize URL
  and PKCE, unmapped and invalid emails, flag off by default, a successful exchange
  (verifier, redirect_uri and secret sent; email lower-cased; `email_verified`), an email
  outside the tenant's domains (including a domain mapped to *another* tenant, and
  sub-domains), a code issued for another tenant, Polis 401/403/unreachable, tampered or
  foreign state, expired state, the platform-admin grant, and settings parsing.
- `backend/tests/app/controllers/test_sso_login.py`: 10 tests covering the redirect to
  Polis, the error redirect, a successful callback (redirect target, cookie claims,
  COLLABORATOR row, idempotent on a second login), an existing ADMIN not downgraded,
  refusal giving no cookies, an unknown workspace, an IdP `?error=` and missing
  params, and free-text error codes not being reflected.
- Full suites on the rebased branch: auth **70 passed** (Mongo and Postgres-served);
  backend **728 passed, 6 skipped** in each of the three modes (Mongo, dual,
  Postgres-served); webapp `tsc --noEmit` clean. ESLint could not run in the worktree
  (it can't resolve `@eslint/js` through the symlinked `node_modules`), so it is not
  verified.

## 2. The flow

```
browser            webapp :3000      backend :8000              auth :8001                    Polis :5225          IdP (mock :4000)
  | "Sign in with SSO", work email
  |--------------------------------> GET /auth/sso/login?email=&creator=
  |                                   |-- GET /auth/sso/basic?login_hint=&client_referer_url= -->|
  |                                   |      domain -> tenant (SSO_DOMAIN_TENANTS); unmapped -> 404 sso_not_configured
  |                                   |      state = Fernet({referer, creator, tenant, product, issued_at, pkce_verifier})
  |                                   |<-- {auth_url: POLIS/api/oauth/authorize?client_id=tenant=<ws>&product=bettercollected
  |                                   |               &redirect_uri=BACKEND/auth/sso/callback&state&code_challenge(S256)&login_hint}
  |<-- 307 to Polis --------------------|
  |---------------------------------------------------------------------------------> authorize: find connection(tenant, product),
  |                                                                                     check redirect_uri (exact match)
  |<-------------------------------------------------------------------------------- SAML AuthnRequest (redirect binding)
  |-------------------------------------------------------------------------------------------------------> login
  |<------------------------------------------------------------------------------------------------------- SAMLResponse (POST form)
  |---------------------------------------------------------------------------------> /api/oauth/saml: verify signature/audience,
  |<-------------------------------------------------------------------------------- 302 BACKEND/auth/sso/callback?code&state
  |--------------------------------> GET /auth/sso/callback?code&state
  |                                   |-- GET /auth/sso/basic/callback?code&state -------------->|
  |                                   |      decrypt state (<=10 min old)  --- POST /api/oauth/token (code, code_verifier, redirect_uri) -->
  |                                   |                                    --- GET  /api/oauth/userinfo (Bearer)                     -->
  |                                   |      requested.tenant/product == state's? else 403 sso_tenant_mismatch
  |                                   |      email domain in tenant's domains? else 403 sso_email_domain_not_allowed
  |                                   |      account_for_provider_sign_in(email, verified=True)  (find or create, #763)
  |                                   |<-- {user (email_verified=true), sso_workspace_id, client_referer_url}
  |                                   |   add_sso_member(workspace, user): COLLABORATOR unless already a member
  |                                   |   personal workspace + NEW_USER tag (same as Google sign-in)
  |<-- 307 /<workspace_name>/dashboard/forms + Authorization/RefreshToken cookies (our JWTs)
```

On any refusal, the backend redirects to the referer (or `API_CLIENT_URL/login`) with
`?sso_error=<code>` and sets no cookies. Only codes from a fixed allow-list are
passed through; anything else becomes `sso_failed`.

## 3. How to run it

Prerequisites: `docker-compose.local.yml` up (Mongo and `app-postgres` on network
`bettercollected_default`), with `backend/.env` and `auth/.env` filled in.

```bash
# Polis + mock IdP, throwaway keys/secrets in .sso-dev/ (gitignored), `polis` database,
# demo workspace "example-corp-sso" (id 65e5501d0000000000000001), SAML connection.
# Idempotent; prints the auth settings.
scripts/sso-dev-setup.sh --seed-workspace            # or: --workspace <id> [--domain acme.io]

# auth: add the printed settings to auth/.env (or export them), e.g.
#   SSO_ENABLED=true
#   SSO_POLIS_URL=http://localhost:5225
#   SSO_REDIRECT_URI=http://localhost:8000/api/v1/auth/sso/callback
#   SSO_POLIS_CLIENT_SECRET=<CLIENT_SECRET_VERIFIER from .sso-dev/polis.env>
#   SSO_DOMAIN_TENANTS=example.com:65e5501d0000000000000001
(cd auth && ./run.sh)                                 # :8001
(cd backend && ./run.sh)                              # :8000, no new settings
(cd webapp && NEXT_PUBLIC_ENABLE_SSO=true yarn dev)   # :3000, "Sign in with SSO" under the email form
```

Then open `http://localhost:3000/login`, choose "Sign in with SSO", enter any
`@example.com` address, and sign in at the mock IdP with the same user (any password).
To see refusal B, pick `@example.org` in the mock IdP.

Teardown: `docker compose -f docker-compose.sso.yml -p bettercollected-sso down`. To
wipe Polis's data, also drop the `polis` database.

### Configuration

| Where | Setting | Meaning |
|---|---|---|
| auth | `SSO_ENABLED` (default `false`) | Feature flag. Off → `/auth/sso/*` answers `sso_disabled` |
| auth | `SSO_POLIS_URL` / `SSO_POLIS_INTERNAL_URL` | Polis for the browser / for server-to-server calls (defaults to the former) |
| auth | `SSO_POLIS_PRODUCT` (default `bettercollected`) | Polis product; the tenant is the workspace id |
| auth | `SSO_POLIS_CLIENT_SECRET` | Polis's `CLIENT_SECRET_VERIFIER` (see 5.2) |
| auth | `SSO_REDIRECT_URI` | Backend `/api/v1/auth/sso/callback`; must equal the connection's redirect URL |
| auth | `SSO_DOMAIN_TENANTS` | Spike-only tenant resolution: `domain:workspace_id,...` |
| auth | `SSO_STATE_MAX_AGE_SECONDS` (600) | Maximum duration of a sign-in |
| webapp | `NEXT_PUBLIC_ENABLE_SSO` | Shows the SSO entry (build-time) |
| Polis | `JACKSON_API_KEYS`, `DB_URL`, `DB_ENCRYPTION_KEY`, `NEXTAUTH_*`, `CLIENT_SECRET_VERIFIER` | Generated into `.sso-dev/polis.env` |
| Polis | `DB_ENGINE=sql DB_TYPE=postgres`, `IDP_ENABLED=false`, `OPENID_REDIRECT_EXACT_MATCH=true`, `SAML_AUDIENCE` | Set in `docker-compose.sso.yml` |

The Polis admin API key (`JACKSON_API_KEYS`) is used only by the setup script. Auth
never needs it.

**Storage: Postgres.** Polis stores its data in its own `polis` database in the
existing `app-postgres` container (tables `jackson_index`, `jackson_store`,
`jackson_ttl`). It worked first time, so we didn't need its in-memory or sqlite mode.
In production it should get its own database and role, like `auth`, `app` and
`google` have.

## 4. What Polis gave us for free vs. what we built

**Free (Polis):**
- SAML SP: AuthnRequest, ACS, signature and audience validation, metadata parsing.
  Connections are created through `/api/v1/sso` from raw IdP metadata (tested) or a
  metadata URL. OIDC IdPs use the same API (not tested).
- One OAuth 2.0 code flow (`/api/oauth/authorize|token|userinfo`) for every connection,
  with PKCE S256, `redirect_uri` allow-listing per connection, and a profile that
  includes `requested.tenant/product`.
- Multi-tenancy keyed by `(tenant, product)`, with no per-customer OAuth client
  registration (the client_id `tenant=<t>&product=<p>` convention). Also
  `idp_hint`/IdP selection when a tenant has several connections (not tested).
- Directory Sync / SCIM 2.0 server with signed webhooks (section 6).
- An admin UI on :5225 (NextAuth login) with connection management and SSO traces for
  debugging failed logins (not explored).

**Built (this branch, about 600 lines of production code plus tests):**
- `auth/auth/app/services/sso_auth_provider.py`: the provider (PKCE, encrypted state
  with tenant and age, token/userinfo exchange, tenant match, domain check, verified
  sign-in through #763's `account_for_provider_sign_in`), plus
  `auth/auth/config/sso_settings.py`. Registered in `AuthProviderFactory` as `sso`;
  `/{provider}/basic` takes an optional `login_hint`.
- Backend `GET /auth/sso/login` and `GET /auth/sso/callback`
  (`controllers/auth_router.py`), `AuthService.get_sso_login_url/sso_callback`, and
  `WorkspaceUserService.add_sso_member`. JIT membership reuses
  `add_user_to_workspace_with_role`, the same call an accepted invitation makes.
- Webapp `sso-sign-in.tsx` (button → work-email form → full navigation; fixed error
  messages per code).
- Dev infra: `docker-compose.sso.yml`, `scripts/sso-dev-setup.sh`, and `.sso-dev/` in
  `.gitignore`.

## 5. Security notes

### 5.1 Trust decisions made in the code
- **The domain decides trust.** The IdP's asserted email counts as verified only if
  its domain belongs to the tenant whose connection authenticated it. Everything else
  is refused before any account is touched. So an SSO login can never reach an
  account outside the tenant's domains. That includes a domain mapped to *another*
  tenant, and sub-domains (both covered by tests).
- **The code must belong to the tenant we started with.** The tenant is kept in our
  encrypted state and compared with Polis's `requested.tenant/product` from userinfo.
- **Since #763, all provider sign-ins go through `account_for_provider_sign_in`.** SSO
  passes `email_verified=True` only after the domain check, and the session carries the
  `email_verified` claim.
- **Consequence: mapping a domain to a tenant hands that tenant's IdP full control of
  every address in the domain.** That includes existing accounts (their workspaces,
  forms, responses) and the `PLATFORM_ADMIN_EMAILS` grant, which applies to verified
  sessions (tested). With the spike's static mapping, the operator vouches for the
  domain. In production, **domain verification (DNS TXT) is a hard prerequisite**.
  Platform-admin domains such as ours should never be claimable by a customer, or the
  ADMIN grant should require OTP/Google even when SSO is on.
- **Error codes:** the redirect carries only allow-listed codes, never free text.

### 5.2 Polis behaviour worth knowing (read from the 26.2.0 source, `npm/src/controller/oauth.ts`)
- **Token endpoint with PKCE:** when the authorize request carried a `code_challenge`,
  `/api/oauth/token` checks only the `code_verifier` and ignores `client_secret` (a
  public-client flow). Our verifier lives only in our encrypted state, so this is
  fine. We send the secret anyway.
- **Without PKCE**, the encoded `tenant=&product=` client_id is checked against one
  global `CLIENT_SECRET_VERIFIER`, which **defaults to `dummy`**. That secret is shared
  by every tenant. Always set it to a random value (the setup script does), and always
  use PKCE.
- **Anyone can start an authorize flow for any tenant** (the client_id is not secret).
  What protects us is the per-connection `redirect_uri` allow-list. We set
  `OPENID_REDIRECT_EXACT_MATCH=true`; Polis's default only compares scheme, host and
  port.
- `scope=openid` would need Polis JWT signing keys. We use plain OAuth and userinfo,
  which is enough because the code exchange is server-to-server.

### 5.3 Shortcuts taken (must not ship as-is)
1. **Static `SSO_DOMAIN_TENANTS`** instead of verified domains owned by a workspace.
2. **Collaborator cap:** JIT uses the invitation path, so `API_ALLOWED_COLLABORATORS`
   applies. Over the cap, the sign-in is refused (`sso_failed`, no cookies), but the
   auth user document has already been created. Order and messaging need a decision
   (seat-based billing?).
3. **Side effects:** an SSO user who signs in as a creator also gets a personal
   workspace and the NEW_USER tag, like the Google flow does. An enterprise probably
   wants SSO users to have only the org workspace.
4. **Email case:** `get_user_by_email` matches exactly. SSO lower-cases emails, so an
   existing mixed-case account (`Bob@Example.com`) would get a second account. This
   already affects the other providers and should be fixed centrally (normalised email
   index).
5. **Redirect target** comes from the `Referer` (existing pattern for Google). The
   success redirect only keeps the referer's origin, but neither origin is validated
   against `CLIENT_ADMIN_URL`. Production should allow-list it.
6. JIT happens in the backend after auth has already created the user. If the
   workspace is gone or disabled, the user exists but gets no session
   (`sso_workspace_unavailable`). Harmless, but not atomic.
7. Only tested in Polis's default single-instance setup with `IDP_ENABLED=false`.

## 6. SCIM / Directory Sync

**It works locally** in this Polis version, with no license key. What was exercised
(scratch script, nothing committed):
- `POST /api/v1/dsync` (admin API key) with `type: generic-scim-v2`, the tenant and
  product, `webhook_url` and `webhook_secret`. The response gives a SCIM base URL
  `/api/scim/v2.0/<directory id>` and a bearer secret.
- SCIM `POST /Users`, `POST /Groups` (with a member), `PATCH /Users/<id> active=false`
  all returned the expected resources. A wrong bearer gave 401.
  `GET /api/v1/dsync/users?tenant=&product=` listed the user as inactive.
- Webhooks arrived as `user.created`, `group.created` and `user.updated`
  (`active:false`), each with `tenant`, `product`, `directory_id` and a normalised
  `data` (`email`, `first_name`, `last_name`, `active`, `raw`), plus a header
  `BoxyHQ-Signature: t=<ms>,s=<hmac>`.
- Not verified: whether a member given at group creation, or added by `PATCH`, emits
  `group.user_added` (only `group.created` was seen); deletes; ordering and retries
  (Polis retried 3 times when the endpoint was unreachable); batching
  (`DSYNC_WEBHOOK_BATCH_*`); real Okta/Entra quirks; and how the signature is computed
  (to verify, read `npm/src/directory-sync` and implement it against that, not
  against the docs).
- Local gotcha: in this Docker setup, `host.docker.internal` does not resolve inside
  the container. The webhook had to target the network gateway (`10.0.1.1`).

**Sketch of the mapping to our model.** Not implemented. It would be a new
backend endpoint, for example `POST /api/v1/sso/directory-events`. It verifies the HMAC
(with a timestamp window), dedupes by event id, and processes events by tenant, where
the tenant is the workspace id:

| SCIM event | Our effect |
|---|---|
| `user.created` / `user.updated` with `active:true` | Upsert the account by email **only for the tenant's verified domains** (same rule as sign-in), then ensure a workspace membership with the default role (COLLABORATOR). Optionally pre-provision, so a user exists before their first login |
| `user.updated` with `active:false`, or `user.deleted` | Disable the membership (`workspace_users.disabled`), **revoke sessions** (needs Phase 0), and keep the account and its forms (the workspace owns forms). Never delete the person's data from a directory event alone; GDPR deletion stays an explicit flow |
| `group.*` / `group.user_added/removed` | A per-workspace mapping `{IdP group → role}`, e.g. `bettercollected-admins → ADMIN`, else COLLABORATOR. Recompute the member's role from their groups. The owner is never changed by SCIM |
| Directory deleted | Stop syncing and leave members as they are; an admin decides |

Persistence: one new Postgres table for event dedupe and audit, plus the group→role
mapping on the workspace. Both need Mongo twins while the store migration is in
progress.

## 7. Gaps and risks

- **Session revocation (the big one).** Our access tokens are self-contained JWTs.
  Production access tokens live **30 days**. Locally, `AUTH_ACCESS_TOKEN_EXPIRY_IN_MINUTES=43200`,
  and the SSO cookie came back with `Max-Age=2592000`. Refresh tokens are
  only blacklisted on logout. Neither offboarding in the IdP nor a SCIM deactivation
  can end a session today. Even with SCIM wired up, a fired employee keeps access for
  up to 30 days. Needed: short access tokens (5–15 min); a refresh that re-checks
  "account active, membership active, SSO still allowed or required" (`/auth/refresh`
  already calls auth's `/status`, which is the natural hook); and a per-user
  `token_version` / `sessions_revoked_at` checked at refresh, or on every request for
  high-value actions.
- **#758 / #763 account linking.** Merged during the spike (#763). SSO now goes through
  `account_for_provider_sign_in`. The remaining question is policy: once a domain is
  "SSO required", should OTP and Google sign-ins for that domain be refused, or sent
  to SSO? Otherwise a departed employee with mailbox access, or a Google account on
  the same address, bypasses the IdP.
- **Domain verification.** Needs a model: `workspace_domains {domain, workspace_id,
  verified_at, method, token, sso_required}`, unique by verified domain. Also DNS TXT
  verification with periodic re-checks, and a policy for public-mail domains (never
  claimable).
- **IdP-initiated login.** Disabled (`IDP_ENABLED=false`) and untested. If it's turned
  on, Polis sends a code with no state of ours, which our callback refuses
  (`sso_bad_state`). Supporting it needs a dedicated entry point that resolves the
  tenant from Polis's `requested` and mitigates login CSRF. Recommendation: SP-initiated
  only at first, which most customers accept.
- **Logout / SLO.** Our logout clears only our cookies. Polis's OAuth bridge does not
  propagate SAML Single Logout to us (not investigated further), and the IdP session
  survives our logout. Most B2B SaaS don't do SLO; document it. The real control is
  the revocation above plus SCIM.
- **Multi-replica.** Our side is stateless: the state is Fernet-encrypted with the
  shared `AUTH_AES_HEX_KEY`. Polis keeps sessions, codes and tokens in Postgres, so
  several replicas can share it, provided `DB_ENCRYPTION_KEY`, `NEXTAUTH_SECRET` and
  the API keys are identical. Not tested with more than one replica. Polis is one more
  service to deploy, monitor and upgrade. It can also be embedded as an npm library
  (`@boxyhq/saml-jackson`) in a Node service, which isn't an option for our Python
  stack. Keep it as a container on an internal network and expose only
  `/api/oauth/*` and `/api/scim/*` (plus the ACS) publicly. The admin API and UI
  should not be public.
- **SSO-required enforcement** isn't built at all. It has to cover sign-in **and**
  refresh, plus a break-glass path for the workspace owner when the IdP is broken.
- **Licensing.** Image 26.2.0 ran SSO and SCIM without `BOXYHQ_LICENSE_KEY`. Which
  Ory Polis features are enterprise-only (for example the admin portal's
  "setup links" for self-serve customer configuration) **was not checked**. Check this
  before planning Phase 4 around them.
- **The mock IdP is lenient.** It only issues `@example.com` / `@example.org`, signs
  with our throwaway key, and gives no groups or roles. Real IdPs (Entra, Okta, Google
  Workspace) and their attribute mappings were not tested. That includes where
  `email` comes from (Polis maps an attribute and may fall back to NameID; not
  verified).

## 8. Effort estimate

Engineer-days for one developer who knows this codebase, including tests and the
Mongo/Postgres twins. These are rough; the ranges reflect the unknowns above.

| Phase | Scope | Estimate |
|---|---|---|
| **0. Tokens/revocation + domain model** | Short access tokens + refresh-time checks (account, membership, SSO policy); `token_version`/revocation on the user; `workspace_domains` model + DNS TXT verification + re-checks; public-mail blocklist; Polis in deployment compose (own database and role, secrets, internal network) | **8–12** |
| **1. OIDC SSO** | Harden this spike: tenant from verified domains, connection CRUD via Polis admin API (operator-run at first), JIT policy (no personal workspace, seat limits), redirect allow-list, error UX, tests against a real OIDC IdP (e.g. Google Workspace or Entra dev tenant) | **5–8** |
| **2. SAML + SSO-required domains** | SAML connections (mostly free from Polis), tested against Okta/Entra; SSO-required: refuse OTP/Google for the domain at sign-in and refresh, route to SSO, owner break-glass; decide on IdP-initiated | **5–8** |
| **3. SCIM** | Signed webhook endpoint, dedupe/audit table, user/group events → membership/role, deactivation → revocation, group→role mapping, tests with Okta's SCIM validator | **8–12** |
| **4. Admin UI + audit** | Workspace settings: domains (verify), SSO connection (metadata URL/XML or OIDC client), SSO-required toggle, directory + group mapping, test-connection; audit log of SSO and SCIM events visible to workspace admins | **10–15** |

**Total: about 36–55 engineer-days.** Phase 0 blocks the others. Phase 1 can begin
alongside the domain model. A minimal sellable "SSO for Teams" is Phases 0–2, about
18–28 days. In it, connections are set up by us on request, without self-serve UI.
