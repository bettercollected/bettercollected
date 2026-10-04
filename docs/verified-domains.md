# Verified email domains

A workspace proves it owns an email domain (for example `acme.com`) by publishing a DNS TXT record. This is part of Phase 0 of the enterprise work: single sign-on may only map a domain its workspace has verified. Mapping a domain hands every address in it, existing accounts included, to that workspace's identity provider (see "domain mapping is a full trust grant" in `docs/sso-spike.md` on the `spike/sso-polis` branch).

This is not the custom domain a workspace serves its forms on. That feature is described in [custom-domain.md](custom-domain.md).

## Who

Only the workspace Owner and Admins can list, claim, verify or remove domains. This is the `security.manage` permission in [enterprise-access-model.md](enterprise-access-model.md). Collaborators and non-members get 403, and requests without a session get 401. The check is made in one place, `WorkspaceDomainService._authorize`, so it can switch to `authorize(user, "security.manage", workspace_id)` once the permission service lands.

## API

All under `/api/v1/workspaces/{workspace_id}/domains`:

| Method | Path | Result |
|---|---|---|
| GET | `` | the workspace's claims |
| POST | `` `{"domain": "acme.com"}` | 201 with the new claim; 422 `{code, message}` when the domain can't be claimed; 409 `already_claimed` or `domain_verified_elsewhere` |
| POST | `/{domain_id}/verify` | checks the TXT record now and returns the claim. The outcome is in `status` and `lastCheckError` |
| DELETE | `/{domain_id}` | 204. A verified domain is released for other workspaces |

A claim ID from another workspace returns 404.

Each claim has `domain` (ASCII/punycode), `displayDomain` (Unicode), `status`, `txtRecordName`, `txtRecordValue`, `verifiedAt`, `lastCheckedAt`, `lastCheckError`, `failedChecks` and `verificationLostAt`.

`status` is one of:
- `pending`: claimed, never checked.
- `verified`
- `failed`: the last check failed.
- `conflict`: another workspace has verified this domain, so this claim cannot verify.

`lastCheckError` is one of:
- `no_record`: NXDOMAIN, or no TXT records at the name.
- `token_mismatch`: TXT records exist, but none carries this claim's token.
- `dns_timeout`
- `dns_error`: SERVFAIL, or no nameserver answered.
- `verified_by_another_workspace`

## The TXT record

```
_bettercollected-verification.acme.com.  TXT  "bettercollected-domain-verification=<token>"
```

- The record goes on a dedicated name, not the apex. That keeps it away from the apex's SPF and other TXT records, and avoids CNAME-at-apex problems.
- Each claim has its own 128-bit random token, so several workspaces' claims can sit side by side on that name. Only the workspace whose token is there can verify.
- The whole string must match exactly. A record longer than 255 bytes is split into several strings, and these are joined before comparing.
- Lookups use `dnspython` with no cache on our side, `search=False`, and a total time limit of `VERIFIED_DOMAINS_DNS_TIMEOUT_S`. They go to the system resolver, or to `VERIFIED_DOMAINS_NAMESERVERS` if set. The resolver is trusted: use one that does DNSSEC validation where that matters.

## Which domains can be claimed

Code: `backend/app/services/domains/names.py`. Domains are stored in their canonical form: lower case, IDNA 2008 with UTS #46 mapping (`idna`), so `Bücher.de` becomes `xn--bcher-kva.de`, and without a trailing dot. These are refused, each with a stable `code`:

| code | what |
|---|---|
| `invalid_domain` | not a host name: a wildcard, `@`, a scheme, path or port, a bad label, an IP address, a single label, or over 253 characters |
| `unknown_suffix` | the top-level domain is not on the Public Suffix List (`.local`, `.internal`, `.test`, `.lan`, ...) |
| `public_suffix` | a public suffix itself, from the ICANN or private section (`co.uk`, `gov.uk`, `github.io`, `blogspot.com`). `myteam.github.io` can be claimed |
| `free_mail_domain` | a free-mail provider: a fixed list (`gmail.com`, `outlook.com`, `yahoo.com`, `icloud.com`, `proton.me`, `gmx.de`, ...) and its sub-domains, plus any registrable domain named after the big providers under any suffix (`yahoo.co.uk`, `hotmail.fr`) |
| `reserved_domain` | documentation and special-use names (`example.com/.net/.org`, `.onion`), `VERIFIED_DOMAINS_RESERVED`, and the domains of `PLATFORM_ADMIN_EMAILS`. An SSO connection on a platform admin's domain would control the platform-admin grant. Sub-domains of reserved domains are refused too |

The public suffix data comes from the `publicsuffixlist` package, which bundles the list. Updating the package updates the list, so keep it in the regular dependency updates. The free-mail list is a hand-kept list of common providers. A small provider that isn't on it can still be claimed, but only by someone who controls its DNS.

Sub-domains are separate domains. Verifying `acme.com` does not cover `eng.acme.com`, and the reverse is also true. Each needs its own record.

A workspace can hold at most `VERIFIED_DOMAINS_MAX_PER_WORKSPACE` claims (default 20).

## One owner per domain

- Any number of workspaces can hold pending claims for the same domain. The first to verify wins.
- Uniqueness is enforced by the database, not only by a read-then-write. `verified_domain` holds the domain while a claim is verified and is unset otherwise. It has a partial unique index in both stores: Mongo `partialFilterExpression {verified_domain: {$type: "string"}}`, Postgres `WHERE verified_domain IS NOT NULL`. If two verifications race, one fails on the index and is stored as `verified_by_another_workspace`.
- Once a domain is verified, other workspaces' claims for it show `conflict`, and new claims for it are refused (409 `domain_verified_elsewhere`).
- The domain becomes free again only when the owner removes its claim or its workspace is deleted. When the account owner deletes their workspaces, `WorkspaceService.delete_workspaces_of_user_with_forms` releases the domains.

## Re-checks and losing the record

`WorkspaceDomainService.recheck_verified_domains(limit)` re-checks verified domains not checked within `VERIFIED_DOMAINS_RECHECK_INTERVAL_HOURS`, oldest first, and returns counts. It is meant for a periodic job. No job schedule is wired up yet.

- A check that passes resets `failedChecks` and clears `verificationLostAt`.
- A check that finds the record missing or wrong (`no_record`, `token_mismatch`) adds one to `failedChecks`. After `VERIFIED_DOMAINS_LOSS_AFTER_FAILED_CHECKS` such checks in a row (default 3), `verificationLostAt` is set.
- `dns_timeout` and `dns_error` are problems with the resolver, not the domain. They are recorded in `lastCheckError` but do not count towards `failedChecks`.
- A domain whose record is lost **stays verified, and is not transferred**. Its owner keeps it, and `domain_owner` still returns that owner. This avoids flapping, and it means a lapsed domain can't be taken over just by registering it. Releasing a lost domain is done by its owner, or by support. SSO can read `verification_lost_at` from the claim to decide whether to warn or refuse.
- "Verify now" on a verified domain is the same check.

## Helpers for single sign-on

On `container.workspace_domain_service()`:

- `domain_owner(domain_or_email) -> PydanticObjectId | None`: the workspace that verified exactly that domain. Pending, failed and conflicting claims don't count.
- `is_domain_verified_for(workspace_id, email_or_domain) -> bool`

Both accept an email address and normalise the input the same way as a claim does.

## Storage

Collection `workspace_domains` (Beanie `WorkspaceDomainDocument`), with its Postgres twin `app.workspace_domains` in the identity group (revision `0006`, a new table only). Spine columns: `workspace_id`, `domain`, `status`, `verified_domain`, `last_checked_at`. Indexes:
- unique `(workspace_id, domain)`
- `domain`
- partial unique `verified_domain`
- `(status, last_checked_at)` for re-checks

## Settings (`VERIFIED_DOMAINS_*`)

| Setting | Default | |
|---|---|---|
| `DNS_TIMEOUT_S` | 5 | total time for one lookup |
| `NAMESERVERS` | empty | comma-separated resolver IPs; empty uses `/etc/resolv.conf` |
| `LOSS_AFTER_FAILED_CHECKS` | 3 | |
| `RECHECK_INTERVAL_HOURS` | 24 | |
| `MAX_PER_WORKSPACE` | 20 | |
| `RESERVED` | empty | comma-separated domains no workspace may claim |
| `PLATFORM_ADMIN_EMAILS` | empty | read without the prefix too, the same variable auth uses |

## Tests

- `tests/app/services/test_domain_names.py`: normalisation and refusals.
- `tests/app/services/test_domain_dns.py`: the check, with the resolver mocked.
- `tests/app/controllers/test_workspace_domains.py`: API, permissions, uniqueness, re-checks and helpers.
- `tests/app/repositories/test_workspace_domain_parity.py`: both stores.

`tests/app/services/test_domain_dns_live.py` does real lookups and only runs with `BC_LIVE_DNS_TESTS=1`.
