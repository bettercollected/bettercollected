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

## Variables (no secrets)

| Variable | Default | Meaning |
|---|---|---|
| `ADMIN_PORT` | `8100` | host port (loopback) |
| `ADMIN_ALLOWED_IPS` | `127.0.0.1/32` | allowed client CIDRs; invalid entries stop startup |
| `ADMIN_ALLOWED_HOSTS` | `localhost:<port>,127.0.0.1:<port>` | allowed `Host` values |
| `ADMIN_TRUSTED_PROXIES` | empty | proxies whose `X-Forwarded-For` is believed |
| `ADMIN_EDGE_SUBNET` / `ADMIN_EDGE_GATEWAY` | `172.30.77.0/29` / `172.30.77.1` | the admin network |
