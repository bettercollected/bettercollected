# Limits on sign-in code mails and form submits

The sign-in code mail (`POST /workspaces/{id}/auth/otp/send` and
`POST /auth/creator/otp/send`) and the respondent submit
(`POST /workspaces/{id}/forms/{id}/response`) are rate limited. The counters are
fixed windows in Postgres, shared by every replica; a counter's id is a keyed hash,
so no address and no client address is stored.

| What | Limit | Counted by |
|---|---|---|
| Code mail | 10 an hour | client (IPv6 by its /48) |
| Code mail | 3 an hour | mailbox: case, `+tag`, and for Gmail the dots and `googlemail.com` are ignored; the same budget for the workspace and creator routes |
| Code mail, all clients together | `API_CODE_MAIL_PER_HOUR`, default 20000 (0 = off) | one instance-wide counter, the circuit breaker |
| Submit | 30 a minute | client and form |

A refusal is `429` with `{"code": "rate_limited", "message": ..., "retry_after": s}` and
a `Retry-After` header, the same for an address that has an account and one that has
not. The submit limit is checked before the request body is read.

## Why there is exactly one shared budget

A budget many people share (a workspace, a form, all creators) can be used up by a
few networks to lock everyone else out, so there is none per workspace or per form.
The one exception is the circuit breaker: it is the only brake on the code mail being
used to mail random addresses from many networks, so it sits far above normal use.
**When it trips, every code request answers 429 until the hour ends and an ERROR is
logged** ("Sign-in code mail circuit breaker tripped"): look at the access log for the
source, and check `TRUSTED_PROXIES`. It is a stop-gap and goes when a proof of work is
asked for on these routes.

## Known trade-off

Someone who knows an address can request codes for it and keep it at its 3 an hour, so
that person's own code request is refused for the rest of the hour. A code that was
already mailed stays valid for its own lifetime. This is accepted until a proof of work
is asked for.

## Behind a proxy

Per-client limits need the real client address, which comes from `TRUSTED_PROXIES`
(see `docs/settings-inventory.md`). A proxy on a private or loopback address that sends
`X-Forwarded-For` but is not listed would make every user one client, so such a request
is treated as having no client: the per-client limits are skipped and the mailbox and
instance limits still apply. Set `TRUSTED_PROXIES` to the proxy's address (or the
network between the proxy and the backend) to turn the per-client limits on.
