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
| `bc-db` | The Postgres pool (with the Python engine's timeouts), the startup check that schema `app` is at the Alembic head, the document codec (the `doc` bytes and `_bc_checksum` exactly as the Python backend writes them), the generic record repository (get, list on a keyset, insert, upsert, `set_fields`, delete with tombstones, `FOR UPDATE`, advisory locks), the clock, and typed records for `workspaces`, `workspace_users`, `forms`, `form_responses` and `workspace_audit_events` |
| `bc-auth` | Verification of the session cookie (JWT key ring, claim rules). No session refresh |
| `bc-authz` | Roles to permissions and the effective-permissions decision, pure functions |
| `bc-crypto` | Every primitive the Python backend uses, byte-compatible and tested against vectors the Python code writes: the response ciphertext (`v1:`, Tink AES-GCM), the Fernet key ring and the envelopes sealed with it, the HMAC-derived tokens and identifiers, TOTP and recovery codes, API-key hashing, the hashes two writers must agree on (lock keys, `ETag`s, idempotency), random token shapes |
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

`SSO_ENABLED` and `TOTP_ENABLED` are also store-backed settings in the Python backend. A route group whose answers
depend on them (`permissions`) is therefore served by Rust only when **both** are set explicitly in the
environment (to any value the Python parser accepts, `false` included); otherwise every request for the group is
forwarded to Python, and the edge says so once at start. Until the settings-store reader exists, this keeps a
switch that is on only in the store from being treated as off.

## Golden vectors (cryptography)

`bc-crypto` is proven by vectors the Python code writes with throw-away keys generated for the run, committed under
`bc-crypto/tests/golden/` (never real keys). Regenerate from the repository root (no settings or database needed):

```
uv run --project backend python rust/contract/golden_crypto.py fernet  rust/bc-crypto/tests/golden/fernet_vector.json
uv run --project backend python rust/contract/golden_crypto.py derived rust/bc-crypto/tests/golden/derived_vector.json
```

and check the other direction (Rust seals or derives, Python opens or verifies):

```
cd rust && RUST_SEALED_OUT=/tmp/bc-rust cargo test -p bc-crypto && cd ..
uv run --project backend python rust/contract/golden_crypto.py check-fernet  rust/bc-crypto/tests/golden/fernet_vector.json  /tmp/bc-rust
uv run --project backend python rust/contract/golden_crypto.py check-derived rust/bc-crypto/tests/golden/derived_vector.json /tmp/bc-rust
```

Regenerating a vector changes its keys, so run the Rust tests again before the `check-` commands.

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

## The data layer (`bc-db`)

Every table of schema `app` is `id`, `doc` (JSONB, the whole document), `created_at`, `updated_at`, `_bc_source`,
`_bc_checksum` and a few columns GENERATED from `doc`. A Rust writer must produce what the Python writer
(`common/records/codec.py`) produces:

- `doc` is BSON Extended JSON (relaxed): ids `{"$oid": ...}`, binary `{"$binary": ...}`, and datetimes as ISO
  strings (`datetime.isoformat()`) on tables whose class has `bson_encoders` (29 of them, among them `workspaces`,
  `workspace_users`, `forms`, `form_responses`) or `{"$date": "...Z"}` (milliseconds) on those without (41, among them
  `workspace_audit_events`, `sessions`, the newer tables). A record type picks `Stamp` or `BsonDate` accordingly.
  Every field of the model is written (`null` for `None`, defaults written out); keys the model does not know are not.
- `_bc_checksum` is `sha256:` + hex SHA-256 of the canonical JSON of `doc` (sorted keys, compact, not ASCII-escaped,
  floats as Python's `repr`). `bc_db::canonical` does it; the 180 vectors of
  `backend/tests/fixtures/codec_golden/backend.json` pass through it in the tests.
- The write is `INSERT ... ON CONFLICT (id) DO UPDATE` of `doc`, `updated_at`, `_bc_source`, `_bc_checksum`; the
  generated columns are never written; `updated_at` moves only through `save` (as `save_document`), never through
  `upsert`, `update` or `set_fields`.
- A delete also writes a tombstone (`deletion_tombstones`, milliseconds) in the same transaction.
- A read-then-write locks the row (`FOR UPDATE`) or takes the advisory lock the Python code takes (same key, so a
  mixed fleet serialises). A lock wait past `lock_timeout` is `DbError::Busy` (Python: 409 `busy`).
- Every connection carries `statement_timeout` 30 s, `lock_timeout` 5 s and `idle_in_transaction_session_timeout`
  60 s (`DB_STATEMENT_TIMEOUT_MS`, `DB_LOCK_TIMEOUT_MS`, `DB_IDLE_IN_TRANSACTION_MS`, `DB_POOL_SIZE`,
  `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_S` as in Python).

- A new id needs the system random generator: if it cannot be read, minting fails (`DbError::NoRandomness`), never a
  zero-randomness id (two processes in that state would mint the same ids).
- A stored flag is read as pydantic reads a `bool`: JSON `true` / `false`, `0` and `1` (also `0.0`, `1.0`), and a string
  that is in any letter case `0 1 f t n y no on off yes true false` (no spaces); anything else (`2`, `0.5`, `""`,
  `"maybe"`, `" true"`, an array or object) is refused, and `null` is "not set" for an optional flag and refused for a
  plain one. The permissions group reads `workspaces` and `workspace_users` through the typed records, so a flag
  written `"true"` or `1` is enforced as Python enforces it, and a document Python cannot read at all is handed to
  Python (its answer stands). The contract cases `permissions-lax-flags.json` write such rows directly.

A part of a document that is a large model of its own (a form's fields, a theme, an answer set) is carried as
`serde_json::Value` already in document form: the data layer neither validates nor normalises it.

Tests: `cargo test -p bc-db` needs no database for the golden tests (`tests/records_golden.rs`: records written by
Rust equal the documents, checksums and timestamp columns Python wrote for the same input; Rust reads every
document Python wrote, and the old, lax or unknown-keyed documents Python reads, and refuses what Python refuses).
`tests/records_db.rs` also needs `BC_TEST_DATABASE_URL`, a throw-away migrated database whose name contains `test`
(`uv run --project backend python rust/contract/golden_records.py migrate`, with `DATABASE_URL` set); without it
those tests say so and pass. `contract/golden_records.py generate FILE` regenerates `bc-db/tests/golden/records.json`
from the Python classes.

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
A file can set environment variables for both servers (`env`: the feature switches, `TOTP_ENABLED`, ...) and for the
Python backend only (`python_env`: what Python knows and the edge cannot see, such as a setting held in the settings
store), and says which side must have answered each case (`served_by`), so a group that quietly falls back to Python
cannot pass.

To add a route group: write its module under `bc-api/src/groups/`, add it to `groups::ALL`, add
`contract/cases/<group>.json`, and run the harness.

`contract/golden_tink.py` regenerates the ciphertext test vector of `bc-crypto`; `contract/bench.sh` runs a load
comparison with ApacheBench.
