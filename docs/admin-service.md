# Internal admin service

A small separate service, started from the backend image with
`python -m backend.admin.serve`. It is not part of the public API: it has its
own application, no CORS, and shares no router or container with the backend.

## Network

- Published on the host's loopback only (`127.0.0.1:${ADMIN_PORT:-8100}`) and
  never referenced by nginx. Reach it from elsewhere with an SSH tunnel:
  `ssh -L 8100:127.0.0.1:8100 <host>`, then open `http://localhost:8100`.
- It runs alone on the `admin-edge` network (`ADMIN_EDGE_SUBNET`, default
  `172.30.77.0/29`). Docker's port publishing makes host traffic arrive from
  that network's gateway (`ADMIN_EDGE_GATEWAY`), which is allowed in addition
  to `ADMIN_ALLOWED_IPS`.

## Gate

Every request must pass, in order: the `Host` allowlist, then the client
address allowlist. A request that fails either gets a bare 404 and a rate
limited warning log line. Routes are registered with a required level;
anything unregistered is a 404. `/healthz` answers `ok` to loopback peers only.
Responses carry a strict CSP and related security headers. Bodies are capped
at 64 KB and only form or JSON content types are accepted.

## Sign-in and sessions

Sign-in is by an 8-digit code mailed to an address listed in
`PLATFORM_ADMIN_EMAILS` (read once at start). The sign-in form
answers every address the same way, so it does not reveal who is an
admin. A code lasts 10 minutes, works once and allows five attempts; asking
for a new one cancels the old one. Wrong codes lock the address (15 minutes,
then 1 hour, then 4 hours) and many wrong codes across the service pause
sign-in for 10 minutes; admins are mailed once when either happens. The
sign-in mail uses the platform's `MAIL_*` settings.

A session cookie (`__Host-bcadmin`, `Secure`, `HttpOnly`, `SameSite=Strict`) holds
a random token; only its hash is stored. Sessions end after 30 minutes idle or
8 hours in total (`ADMIN_SESSION_IDLE_MINUTES`, `ADMIN_SESSION_ABSOLUTE_HOURS`
can only shorten these), are bound to the client address and browser, and at
most three stay live per admin. A signed-in session whose second factor is still
pending can reach only `/mfa` and `/logout`. Removing an address from
`PLATFORM_ADMIN_EMAILS` ends its sessions at the next start or request.
Every state-changing request needs a CSRF token and a same-origin
`Origin` (`ADMIN_PUBLIC_ORIGINS`). Operator commands:
`python -m backend.admin unlock <email>`, `resume-sign-in`, `revoke-sessions [email]`.

The `admin` compose service does not yet receive `ADMIN_DATABASE_URL`,
`SETTINGS_MASTER_KEY`, `PLATFORM_ADMIN_EMAILS` or `MAIL_*`, nor a route to the
database; that wiring and its acceptance checks come with the deployment stage.

## Variables (no secrets)

| Variable | Default | Meaning |
|---|---|---|
| `ADMIN_PORT` | `8100` | host port (loopback) |
| `ADMIN_ALLOWED_IPS` | `127.0.0.1/32` | allowed client CIDRs; invalid entries stop startup |
| `ADMIN_ALLOWED_HOSTS` | `localhost:<port>,127.0.0.1:<port>` | allowed `Host` values |
| `ADMIN_TRUSTED_PROXIES` | empty | proxies whose `X-Forwarded-For` is believed |
| `ADMIN_EDGE_SUBNET` / `ADMIN_EDGE_GATEWAY` | `172.30.77.0/29` / `172.30.77.1` | the admin network |
| `PLATFORM_ADMIN_EMAILS` | empty | addresses allowed to sign in |
| `ADMIN_PUBLIC_ORIGINS` | `http://localhost:<port>,http://127.0.0.1:<port>` | origins state-changing requests may come from (scheme, host, port) |
| `ADMIN_SESSION_IDLE_MINUTES` / `ADMIN_SESSION_ABSOLUTE_HOURS` | `30` / `8` | session lifetimes (shorter only) |
