# Rust workspace

The Rust side of the bettercollected backend. `bc-api` is an edge service that sits in front of the Python
backend: it answers the route groups that are switched on, and forwards every other request to the Python
backend untouched. It reads the same PostgreSQL schema and verifies the same session cookies. It owns no schema
and runs no migrations: the Python backend's Alembic chain does.

It is not part of any compose file, image or deployment yet.

## Layout

| Crate | What it holds |
|---|---|
| `bc-config` | Environment reading by the Python names; refuses unset and published secrets; the seam for a settings-store reader (`source::SettingsSource`, not implemented) |
| `bc-db` | The Postgres pool and the startup check that schema `app` is at the Alembic head this build was written against |
| `bc-auth` | Verification of the session cookie (JWT key ring, claim rules). No session refresh |
| `bc-authz` | Roles to permissions and the effective-permissions decision, pure functions |
| `bc-crypto` | Opening and sealing of the response ciphertext (`v1:` prefix, Tink AES-GCM), with golden tests against values the Python backend wrote |
| `bc-http` | Error shapes, CORS from the `allowed_origins` table, the client address behind trusted proxies, request privacy (what a log line may say, which responses are never cached) |
| `bc-api` | The axum binary: `/health`, the route groups, the pass-through |
| `contract/` | The harness that runs the Python backend and `bc-api` side by side (Python) |

`bc-api/src/groups/` holds one module per route group, `bc-api/src/store/` one module per table family, so
that work on different groups touches different files. The only shared line is the entry in
`groups::ALL`.

## Build, test, run

The toolchain is pinned in `rust-toolchain.toml` (rustup installs it on first use).

```
cd rust
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
cargo build -p bc-api            # target/debug/bc-api
```

Every crate shares the lints in the workspace `Cargo.toml` (`unsafe_code` is forbidden). `deny.toml` allows only
permissive licences (MIT, Apache-2.0, BSD-2/3, ISC, Zlib, Unicode-3.0, BSL-1.0, CDLA-Permissive-2.0, Unlicense);
CI runs `cargo deny check`.

Run it next to a Python backend that already migrated a database:

```
export DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
export AUTH_JWT_SECRET=...                  # the same secret (ring) the Python backend uses
export BC_PYTHON_UPSTREAM=http://127.0.0.1:8000
export BC_RUST_ROUTES=permissions           # leave empty to forward everything
cargo run -p bc-api
```

### Settings

| Variable | Meaning | Default |
|---|---|---|
| `DATABASE_URL` | Postgres; a SQLAlchemy driver suffix (`+asyncpg`) is accepted | required |
| `AUTH_JWT_SECRET` | Session signing secret, or a ring `<current>,<previous>` (each side 32 or more characters) | required; a published value is refused |
| `AUTH_AES_HEX_KEY` | Fernet key ring; checked when set, not needed yet | unset |
| `BC_PYTHON_UPSTREAM` | `http://host[:port]` of the Python backend (plain HTTP, no path) | required |
| `BC_RUST_ROUTES` | Route groups served by Rust, comma separated | empty: everything goes to Python |
| `BC_API_BIND` | Listen address | `127.0.0.1:8080` |
| `BC_API_DB_POOL_MAX` | Pool size | `10` |
| `BC_PYTHON_UPSTREAM_CONNECT_TIMEOUT_SECS` | Time to open a connection to Python | `5` |
| `BC_PYTHON_UPSTREAM_TIMEOUT_SECS` | Time for Python's response headers, and the longest silence between two chunks of a body in either direction | `120` |
| `BC_SERVED_BY_HEADER` | Add `X-BC-Served-By: rust\|python` to responses (for the contract harness) | off |
| `TRUSTED_PROXIES` / `API_TRUSTED_PROXIES`, `API_TRUST_CLOUDFLARE`, `API_CLOUDFLARE_IPS` | Which proxies in front are believed about the client address; same meaning as in the Python backend | trust nobody |
| `SSO_ENABLED`, `TOTP_ENABLED`, and the feature switches the permissions answer reports (`CAPTCHA_ENABLED`, ...) | Same names and parsing as the Python settings | off |

Settings are read from the environment only. The settings store of the Python services is not read yet, so a
stack whose secrets live only in that store cannot run this service.

## The per-group switch

A route group is a set of routes that moves from Python to Rust together. `BC_RUST_ROUTES` names the groups
Rust serves; nothing else is served by Rust, and a name that does not exist stops the start. Today there is one
group, `permissions` (`GET /api/v1/workspaces/{workspace_id}/permissions`).

Putting a group back on Python is one setting: remove its name and restart. Inside a served group, a request
the Rust side cannot or should not decide (another method of the path, a session that needs refreshing, a
workspace that requires single sign-on, an odd path) is forwarded to Python as it came in, so the answer is
Python's.

`GET /health` is the edge's own liveness answer; it does not ask Python.

## The pass-through

Everything that is not served is forwarded to `BC_PYTHON_UPSTREAM`:

- method, path and query, all headers except the hop-by-hop ones, the original `Host`, and the body, streamed in
  both directions without buffering;
- the response comes back as it is: status, headers (repeated `Set-Cookie` stay repeated) and a streamed body;
  redirects are not followed;
- the TCP peer is appended to `X-Forwarded-For`. The Python backend decides whom to believe from its own
  `TRUSTED_PROXIES`, which must therefore include the address of this service;
- a client that disconnects cancels the request to Python;
- Python unreachable is `502`, no answer in time is `504`, with a body that says nothing of the cause;
- a failure logs the method and the path with receipt numbers redacted, never a query string, header, cookie,
  body or client address.

`Upgrade`/WebSocket requests are not proxied (the backend serves none).

## Contract harness

`contract/` checks that the Rust side answers like the Python backend: same status code, same headers except a
short list of transport ones (`contract/compare.py`), same JSON after parse (key order and whitespace may
differ). It creates a fresh database, migrates and seeds it through the Python backend's own code, starts both
servers, sends every case to both and reports the differences; a write case also compares the rows the two
left behind (`doc`, the generated columns and the checksum, `contract/dbdiff.py`).

```
cd rust && cargo build -p bc-api && cd ..
# the environment of the backend tests (see .github/workflows/ci.yml, backend-tests), with DATABASE_URL naming
# a Postgres server and credentials: the harness creates and drops its own database
uv run --project backend python rust/contract/run.py --passthrough
uv run --project backend pytest rust/contract -q       # the harness's own tests
```

`--passthrough` also runs the whole corpus against an edge that serves no group, which must change nothing.
The run exits non-zero on any difference. `--group NAME` runs one group, `--report FILE` writes the result as
JSON.

Cases are data, one JSON file per route group in `contract/cases/` (the format is in `contract/corpus.py`).
A file can set environment variables for both servers (the feature switches, `TOTP_ENABLED`, ...) and says which
side must have answered each case (`served_by`), so a group that quietly falls back to Python cannot pass.

To add a route group: write its module under `bc-api/src/groups/`, add it to `groups::ALL`, add
`contract/cases/<group>.json`, and run the harness.

`contract/golden_tink.py` regenerates the ciphertext test vector of `bc-crypto`; `contract/bench.sh` runs a load
comparison with ApacheBench.
