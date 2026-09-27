# Custom domains through the custom-domain service

BetterCollected serves a workspace's forms on a hostname the customer owns
(`forms.customer.example`). Since this integration, the DNS verification, the
certificate and the edge are provided by the
[custom-domain service](https://github.com/sireto/custom-domain); the
backend talks to its v1 API through the `custom-domain-sdk` package and the
webapp verifies the signed assertion the edge adds to every request.

Until the operator sets `CUSTOM_DOMAIN_API_URL` and
`CUSTOM_DOMAIN_API_CREDENTIAL`, nothing changes: the backend keeps using the
legacy certificate server (`HTTPS_CERT_API_*`) and the webapp keeps resolving
the workspace from the request host.

## How a request is served

```
customer browser ──► edge (edge.bettercollected.com, Caddy)
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
| Webhooks (`POST /custom-domain/webhooks`) | signature verified with `CUSTOM_DOMAIN_WEBHOOK_SECRETS`; stale and duplicate deliveries ignored | status, checks, verified; CORS origin added on `ready` |

`custom_domain_verified` is derived: `status == ready`. The settings page
shows the two DNS records (TXT for ownership, CNAME to the application's edge
target) exactly as the service returns them, the four checks with their
messages, and the status.

## Configuration

Backend (`backend/.env`):

```
CUSTOM_DOMAIN_API_URL=https://<management api>        # the service's API, not the edge
CUSTOM_DOMAIN_API_CREDENTIAL=cd_...                    # custom-domain credential issue
CUSTOM_DOMAIN_APPLICATION_ID=<uuid>                    # custom-domain application create
CUSTOM_DOMAIN_ASSERTION_KEYS=1:<secret>                # the service's EDGE_ASSERTION_KEYS
CUSTOM_DOMAIN_WEBHOOK_SECRETS=<current>[,<previous>]   # from `python -m backend.custom_domain subscribe`
```

Webapp (server-side environment):

```
CUSTOM_DOMAIN_ASSERTION_KEYS=1:<secret>                # same value as the backend
CUSTOM_DOMAIN_APPLICATION_ID=<uuid>
CUSTOM_DOMAIN_ASSERTION_MODE=optional                  # during migration; `required` (default) afterwards
CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN=<token>        # printed by `custom-domain origin register`
```

The assertion secret is at least 32 characters; rotate by adding the new key
first on the service, then giving both keys to backend and webapp
(`1:<old>,2:<new>`), then removing the old one after a minute.

## Onboarding BetterCollected on the service (operator, once)

On the service host:

```bash
custom-domain application create --slug bettercollected --name "BetterCollected" --cname-target edge.bettercollected.com
custom-domain origin register --application bettercollected --host forms.bettercollected.com --scheme https --port 443
#   → prints the verification token: deploy the webapp with CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN first
custom-domain origin verify --application bettercollected --host forms.bettercollected.com --activate
custom-domain credential issue --application bettercollected --label backend
```

Then in the backend environment set the five variables above, deploy, and
subscribe to status events:

```bash
python -m backend.custom_domain subscribe --url https://<api host>/api/v1/custom-domain/webhooks --secret-file webhook.secret
#   → the secret is written once to webhook.secret (mode 0600, never printed);
#     put it in CUSTOM_DOMAIN_WEBHOOK_SECRETS, redeploy, delete the file
```

## Migrating the domains that exist today

The domains currently served by the legacy server keep working until step 5
below. Their customers must change DNS: the A record to the legacy server's
IP becomes a CNAME to `edge.bettercollected.com` plus the ownership TXT
record. Send that notice with a date before step 2: a grandfathered domain
whose TXT record is still missing 24 hours after import is suspended.

1. Export the reference map (hostname → workspace id) while Mongo is
   authoritative:
   `python -m backend.custom_domain export-reference-map --out bc-domains.json`
2. On the service: `custom-domain legacy import --application bettercollected
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
| a | `CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN` | – | `origin register`, then `origin verify` |
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

## Rollback

Unset `CUSTOM_DOMAIN_API_URL` on the backend and the webapp's assertion
variables and redeploy: registration goes back to the legacy server and the
webapp resolves by host again. Domains already moved to the new edge keep
serving from the service; nothing in its database is lost.
