# Limits on sign-in code mails and form submits

The sign-in code mail (`POST /workspaces/{id}/auth/otp/send` and
`POST /auth/creator/otp/send`) and the respondent submit
(`POST /workspaces/{id}/forms/{id}/response`) are rate limited. The counters are
fixed windows in Postgres, shared by every replica; a counter's id is a keyed hash,
so no address and no client address is stored.

| What | Setting (live, 0 = off) | Counted by |
|---|---|---|
| Code mail | `API_CODE_MAIL_PER_CLIENT_PER_HOUR`, default 60 an hour | client (IPv6 by its /64, one subscriber or device) |
| Code mail | `API_CODE_MAIL_PER_ADDRESS_PER_HOUR`, default 3 an hour | mailbox: case, `+tag`, and for Gmail the dots and `googlemail.com` are ignored; the same budget for the workspace and creator routes |
| Code mail, all clients together | `API_CODE_MAIL_PER_HOUR`, default 20000 an hour | one instance-wide counter, the circuit breaker |
| Submit | `API_SUBMIT_PER_CLIENT_FORM_PER_MINUTE`, default 30 a minute | client and form |

All four are read on every request (no restart): change them in the settings store or
the environment, and the next request uses the new value.

## When the limiter itself fails

A limiter that fails (a database error, a lock timeout or a pool timeout on the counters)
is handled by what the route needs, and the error class is logged as a warning:

- **Sign-in code routes fail closed.** The request answers `503` with `Retry-After: 60`
  and no mail is sent ("Rate limiter failed, code request refused"). These routes need
  the database to send a code anyway, and the circuit breaker runs in the same check:
  under a flood, a timeout on its one counter is exactly when it is needed, so an error
  must not skip it. Sign-in works again on the first request after the database recovers.
- **The response submit fails open.** The submit goes on ("Rate limiter failed, request
  let through"): losing a respondent's answer to a counter error is worse than one
  unlimited request.

A real refusal is still a `429` on both.

A refusal is `429` with `{"code": "rate_limited", "message": ..., "retry_after": s}` and
a `Retry-After` header, the same for an address that has an account and one that has
not. The submit limit is checked before the request body is read.

## With the spam check on

With `CAPTCHA_ENABLED` on, both code routes also ask for a proof of work (purpose `mail`,
`docs/captcha.md`) and check it **before** these limits count: a request without a valid
proof is refused with 422 and uses up no budget, so the limits below can no longer be used
up by someone who only knows an address. The limits stay as they are.

## Why there is exactly one shared budget

A budget many people share (a workspace, a form, all creators) can be used up by a
few networks to lock everyone else out, so there is none per workspace or per form.
The one exception is the circuit breaker: it is the only brake on the code mail being
used to mail random addresses from many networks, so it sits far above normal use.
**When it trips, every code request answers 429 until the hour ends and an ERROR is
logged** ("Sign-in code mail circuit breaker tripped"): look at the access log for the
source, and check `TRUSTED_PROXIES`. It is a stop-gap and goes when a proof of work is
asked for on these routes.

**Runbook: an attack is being mailed through the code mail.** Look at the access log for
the source and block it at the proxy. If sign-in is down for everyone in the meantime
because the breaker tripped, set `API_CODE_MAIL_PER_HOUR=0` to restore sign-in while the
source stays blocked (it turns only the breaker off; the per-client and per-mailbox limits
still hold), and put it back to its value afterwards.

## Organisations behind one address

A school, an office or a municipality that reaches the internet through one address is one
client: all its people share the 60 code mails an hour. If that is too tight (a whole
class signing in at 09:00), raise `API_CODE_MAIL_PER_CLIENT_PER_HOUR`; no release is
needed. The per-mailbox limit is not affected: each person still has 3 code mails an hour.

## Known trade-off

Someone who knows an address can request codes for it and keep it at its 3 an hour, so
that person's own code request is refused for the rest of the hour. The same limit locks
out a person who asks for a code a fourth time within the hour (a resend that is not
needed): wait for the hour to end, or ask the operator to raise
`API_CODE_MAIL_PER_ADDRESS_PER_HOUR`. A code that was
already mailed stays valid for its own lifetime. This is accepted until a proof of work
is asked for.

## Behind a proxy

Per-client limits (code mail and submit) need the real client address, which comes from
`TRUSTED_PROXIES` (see `docs/settings-inventory.md`). Unset, or missing the reverse proxy
the API sees, they are off. A proxy on a private or loopback address that sends
`X-Forwarded-For` but is not listed would make every user one client, so such a request
is treated as having no client: the per-client limits are skipped and the mailbox and
instance limits still apply. Set `TRUSTED_PROXIES` to the proxy's address (or the
network between the proxy and the backend) to turn the per-client limits on.
