# Custom domains through the custom-domain service

BetterCollected serves a workspace's forms on a hostname the customer owns
(`forms.customer.example`). The DNS verification, the certificate and the
edge are provided by the custom-domain service, either the hosted
[Custom Domain API](https://customdomainapi.com/docs/) (customdomainapi.com,
what bettercollected.com uses) or the same open-source service
[self-hosted](https://github.com/sireto/custom-domain). Both expose the same
v1 API and the same assertion contract: the backend talks to the API through
the `custom-domain-sdk` package, and the webapp verifies the signed assertion
the edge adds to every request. Only onboarding differs; see
[Onboarding on the hosted service](#onboarding-on-the-hosted-service) or
[Onboarding on a self-hosted service](#onboarding-on-a-self-hosted-service-operator-once).

Until the operator sets `CUSTOM_DOMAIN_API_URL` and
`CUSTOM_DOMAIN_API_CREDENTIAL`, nothing changes: the backend keeps using the
legacy certificate server (`HTTPS_CERT_API_*`) and the webapp keeps resolving
the workspace from the request host.

## How a request is served

```
customer browser ──► edge (edge.customdomainapi.com when hosted; your own edge name when self-hosted)
                        │  TLS for the customer hostname (on-demand certificate)
                        │  X-Custom-Domain-Assertion: v1.<key>.<payload>.<mac>
                        ▼
                     webapp (the registered origin)
                        │  verifies the assertion (src/lib/server/custom-domain.ts)
                        │  selects the workspace by the assertion's reference = workspace id
                        ▼
                     backend API (browser calls it directly, as today; CORS allows the hostname)
```

The workspace is never selected from the `Host` header on the custom-domain
path once `CUSTOM_DOMAIN_ASSERTION_MODE=required`: a request without a valid
assertion is refused (the layout renders the "not configured" alert), which
also covers direct calls that bypass the edge. In `optional` mode (migration
only) a request that carries no assertion at all falls back to the host
lookup; an invalid one is still refused.

Two probe paths on the webapp exist for the service (Next.js rewrites to
route handlers under `src/app/api/custom-domain/`):

| Path | Purpose |
| --- | --- |
| `/.well-known/custom-domain-origin-verification` | Proves this deployment is the registered origin: returns `CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN` as plain text. |
| `/.well-known/custom-domain-workspace` | The workspace probe: verifies the assertion and answers `{"reference", "application"}` only when that workspace exists. A domain becomes `ready` only after this passes through the edge. |

## What the backend does

`WorkspaceService` (`backend/app/services/workspace_service.py`) and the SDK
wrapper `CustomDomainService` (`backend/app/services/custom_domain_service.py`):

| Action | Call | Stored on the workspace |
| --- | --- | --- |
| Set a domain (`PATCH /workspaces/{id}` with `custom_domain`) | `create_domain(hostname, reference=workspace id, idempotency_key)` | `custom_domain`, `custom_domain_id`, `custom_domain_status`, `custom_domain_dns_records`, `custom_domain_checks`, `custom_domain_verified` |
| Change the domain | register the new one first, then delete the old id; a refused registration leaves the working domain untouched | same |
| Status page (`GET /workspaces/{id}/verify-domain`) | `get_domain` | refreshed |
| "Check again" (`POST /workspaces/{id}/custom-domain/recheck`) | `request_recheck`; a 429 returns `retry_after` | refreshed |
| Remove (`DELETE /workspaces/{id}/custom-domain`) | `delete_domain` | all cleared |
| Webhooks (`POST /custom-domain/webhooks`) | signature verified with `CUSTOM_DOMAIN_WEBHOOK_SECRETS`; stale and duplicate deliveries ignored | status, checks, verified; CORS origin added on `ready`, removed otherwise |

`custom_domain_verified` is derived: `status == ready`. A custom domain is an
allowed CORS origin only while it is verified (on either path); setting or
changing a domain does not add it. The settings page
shows the two DNS records (TXT for ownership, CNAME to the application's edge
target) exactly as the service returns them, the four checks with their
messages, and the status.

## Configuration

Backend (`backend/.env`):

```
CUSTOM_DOMAIN_API_URL=https://edge.customdomainapi.com # hosted; self-hosted: the service's API, not the edge
CUSTOM_DOMAIN_API_CREDENTIAL=cd_...                    # hosted: API keys tab; self-hosted: custom-domain credential issue
CUSTOM_DOMAIN_APPLICATION_ID=<application id>          # hosted: Origin tab; self-hosted: custom-domain application create
CUSTOM_DOMAIN_ASSERTION_KEYS=app_...:<secret>          # hosted: Origin tab; self-hosted: 1:<secret> (EDGE_ASSERTION_KEYS)
CUSTOM_DOMAIN_WEBHOOK_SECRETS=<current>[,<previous>]   # from `python -m backend.custom_domain subscribe`
```

Webapp (server-side environment):

```
CUSTOM_DOMAIN_ASSERTION_KEYS=app_...:<secret>          # same value as the backend
CUSTOM_DOMAIN_APPLICATION_ID=<application id>
CUSTOM_DOMAIN_ASSERTION_MODE=optional                  # during migration; `required` (default) afterwards
CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN=<token>        # hosted: Origin tab; self-hosted: `custom-domain origin register`
```

`CUSTOM_DOMAIN_API_URL` is the base URL without `/v1`: the SDK adds the
version itself (a trailing `/v1`, as the hosted docs print it, is dropped).

The assertion key ring is `<key id>:<secret>[,<key id>:<secret>]`; every
entry verifies, so a rotation keeps both keys for a while:

- **Hosted:** on the Origin tab, **Rotate the key** issues a new `app_…`
  key that starts signing 24 hours later. Add it next to the current one on
  backend and webapp (`app_old:<secret>,app_new:<secret>`), and remove the
  old one after the switch.
- **Self-hosted:** add the new key on the service first, give both keys to
  backend and webapp (`1:<old>,2:<new>`), then remove the old one after a
  minute. The secret is at least 32 characters.

Only ever put **our own application's key** in the ring. The hosted edge is
shared with other applications, and a deployment-wide key would let anyone
holding it sign an assertion that names our application.

## Onboarding on the hosted service

In the portal at [app.customdomainapi.com](https://app.customdomainapi.com),
in the application "BetterCollected":

1. **Origin tab:** add the webapp host (`forms.bettercollected.com`). Deploy
   the webapp with the token shown there as
   `CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN` (served at
   `/.well-known/custom-domain-origin-verification`), then press
   **Verify and use**.
2. **Origin tab:** press **Get your assertion key**. The key id (`app_…`),
   the secret and the application id are shown once; store them as stack
   secrets (`CUSTOM_DOMAIN_ASSERTION_KEYS=app_…:<secret>`,
   `CUSTOM_DOMAIN_APPLICATION_ID`), on the webapp and the backend.
3. **API keys tab:** create the backend's key (`cd_…`, shown once) for
   `CUSTOM_DOMAIN_API_CREDENTIAL`, and set
   `CUSTOM_DOMAIN_API_URL=https://edge.customdomainapi.com`.
4. Deploy, then subscribe to status events as below (`subscribe`).

Customers point their hostname at `edge.customdomainapi.com` (CNAME) and add
the ownership TXT record; both come back from the API and the settings page
shows them exactly as returned. A dedicated edge with our own name would only
change that CNAME target.

On Free, an application holds up to 25 domains, the API key may make 60
requests a minute, and proxied traffic is limited to 600 requests a minute
(100 a second) across all hostnames; over it, visitors get `429`. Paid plans
have their own edge without the proxied-request limit.

The edge terminates TLS for customers' hostnames, so respondents' answers
pass through it on the way to the webapp. The hosted edge runs in Germany.

## Onboarding on a self-hosted service (operator, once)

On the service host:

```bash
custom-domain application create --slug bettercollected --name "BetterCollected" --cname-target edge.bettercollected.com
custom-domain origin register --application bettercollected --host forms.bettercollected.com --scheme https --port 443
#   → prints the verification token: deploy the webapp with CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN first
custom-domain origin verify --application bettercollected --host forms.bettercollected.com --activate
custom-domain credential issue --application bettercollected --label backend
```

Then in the backend environment set the five variables above, deploy, and
subscribe to status events (hosted and self-hosted alike):

```bash
python -m backend.custom_domain subscribe --url https://<api host>/api/v1/custom-domain/webhooks --secret-file webhook.secret
#   → the secret is written once to webhook.secret (mode 0600, never printed);
#     put it in CUSTOM_DOMAIN_WEBHOOK_SECRETS, redeploy, delete the file
```

## Migrating the domains that exist today

The domains currently served by the legacy server keep working until step 5
below. Their customers must change DNS: the A record to the legacy server's
IP becomes a CNAME to the edge (`edge.customdomainapi.com` on the hosted
service) plus the ownership TXT record. Send that notice with a date before step 2: a grandfathered domain
whose TXT record is still missing 24 hours after import is suspended.

1. Export the reference map (hostname → workspace id) while Mongo is
   authoritative:
   `python -m backend.custom_domain export-reference-map --out bc-domains.json`
2. On the service host (for the hosted service, its operator runs this):
   `custom-domain legacy import --application bettercollected
   --reference-map bc-domains.json --grandfather --dry-run`, resolve every
   skipped name (apex domains cannot be imported), then run it for real.
   Grandfathered domains start in `provisioning` with ownership verified by
   the import; they become `ready` once the CNAME points at the new edge and
   the workspace probe passes, and are suspended if the TXT record is still
   missing after 24 hours.
3. `python -m backend.custom_domain adopt --dry-run`, then without
   `--dry-run`: stores each imported domain's id and status on its
   workspace through the routed repository (both stores). It refuses to
   adopt a domain whose reference or hostname does not match the workspace.
4. Tell the affected customers to publish the two records; their settings
   page now shows them.
5. Only then set `ENABLE_LEGACY_API=false` on the service and
   `CUSTOM_DOMAIN_ASSERTION_MODE=required` on the webapp. Until step 5 the
   legacy path still serves domains whose DNS was not changed.

### The one supported order of switches

The backend switch (`CUSTOM_DOMAIN_API_URL` + credential) and the webapp
switch (assertion keys + application id) are independent; only this order
keeps every domain serving throughout:

| Step | Webapp | Backend | Service |
| --- | --- | --- | --- |
| a | `CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN` | – | hosted: Origin tab, **Verify and use**; self-hosted: `origin register`, then `origin verify` |
| b | `CUSTOM_DOMAIN_ASSERTION_KEYS`, `CUSTOM_DOMAIN_APPLICATION_ID`, `CUSTOM_DOMAIN_ASSERTION_MODE=optional` | – | – |
| c | – | `CUSTOM_DOMAIN_API_URL`, `_API_CREDENTIAL`, `_APPLICATION_ID`, `_ASSERTION_KEYS`, then `_WEBHOOK_SECRETS` after `subscribe` | `legacy import`, then `adopt` on the backend |
| d | – | – | customers change DNS; domains reach `ready` |
| e | `CUSTOM_DOMAIN_ASSERTION_MODE=required` | – | `ENABLE_LEGACY_API=false` |

While the service's legacy `/domains` path is live it adds no assertion to
the requests it proxies. In `optional` mode the webapp refuses an invalid
assertion but serves a request without one from the legacy host lookup, so
domains that have not moved yet keep working. `required` (the default when
the mode is unset) refuses requests without an assertion; set it only after
every domain is served by the new edge.

Between steps c and d a legacy domain that `adopt` has not matched yet shows
"being migrated" on its settings page; the customer needs to do nothing until
the DNS notice arrives. Only a domain the service has deleted (`removed`)
asks the customer to set it again.

`python -m backend.custom_domain sweep --dry-run` lists domains in the
service that no workspace references (a replacement whose old domain could
not be deleted at the time); without `--dry-run` it deletes them.

`python -m backend.custom_domain prune-origins --dry-run` lists allowed
origins of custom domains that are not verified; without `--dry-run` it
removes them. The backend also does this on every startup. Origins that match
no workspace are only listed; `--orphans` removes them too, keeping the
client app's origin (`API_CLIENT_URL`) and every `--keep ORIGIN`.

## Rollback

Unset `CUSTOM_DOMAIN_API_URL` on the backend and the webapp's assertion
variables and redeploy: registration goes back to the legacy server and the
webapp resolves by host again. Domains already moved to the new edge keep
serving from the service; nothing in its database is lost.
