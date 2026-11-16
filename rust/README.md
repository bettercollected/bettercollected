# bc-api: a Rust spike next to the Python backend

An experiment, not a product. `bc-api` is a small Rust service (axum, tokio, sqlx) that reads the **same
PostgreSQL schema** as the Python backend and verifies the **same session cookies**, and serves two routes:

- `GET /health` (spike only)
- `GET /api/v1/workspaces/{workspace_id}/permissions`: what the caller may do in a workspace. It is the backend's
  `get_workspace_permissions`: authenticated, workspace-scoped, read-only, no decryption.

It owns no schema and runs no migrations. It refuses to start when `AUTH_JWT_SECRET` is missing, when the database
cannot be reached, or when the `app` schema is behind the Alembic revision it was written against
(`EXPECTED_HEAD` in `bc-api/src/db.rs`).

## What it does with a request

1. Reads the `Authorization` cookie and verifies it exactly like the Python backend: HS256 only, every member of the
   `AUTH_JWT_SECRET` key ring (`<current>[,<previous>]`) verifies, `exp`/`nbf`/`iat` checked with no leeway, `typ` must
   be `access`, `sid` must be set.
2. Looks up the membership and the workspace and applies the role table of the Python authorization service.
3. Reports the feature switches from the environment (`FIELD_RULES_ENABLED`, `CAPTCHA_ENABLED`, ...) under the same
   names, parsed like the Python settings.
4. Answers with the same status codes, bodies and headers (CORS from the `allowed_origins` table included).

What it deliberately does **not** do (the contract test lists such requests as "delegated"): refresh a session from
a `RefreshToken` cookie, and decide single-sign-on policy. A real deployment would proxy those requests to the Python
backend. It also reads configuration from the environment only, not from the settings store of the Python services.

`src/crypto.rs` opens (and, for tests, seals) the response ciphertext of the Python backend (Tink AES-GCM keyset,
`v1:` prefix) and is tested against values the Python backend wrote.

## Run it

```
cd rust
export DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME   # a database the Python backend migrated
export AUTH_JWT_SECRET=...                                       # the same secret (ring) the Python backend uses
export BC_API_BIND=127.0.0.1:18080                               # optional
cargo run --release -p bc-api
```

## Tests

```
cd rust
cargo test                      # unit tests, request-level tests, Tink golden test
cargo clippy --all-targets -- -D warnings
cargo fmt --check
```

### Contract test (Python and Rust side by side)

`contract/` seeds a throw-away database through the Python backend's own code, then sends the same requests to both
servers and diffs status, headers and body bytes. It needs the Python backend's environment (`uv sync` in `backend/`).

```
# throw-away secrets, a database whose name contains "test"
export DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/contract_test
export AUTH_JWT_SECRET="<32+ chars>,<32+ chars>" AUTH_AES_HEX_KEY=... MASTER_ENCRYPTION_KEYSET=... RESPONDENT_IDENTITY_KEY=...
uv run --project backend python rust/contract/seed.py migrate
uv run --project backend python rust/contract/seed.py seed fixture.json
# start the Python backend on :18000 (uvicorn backend.app:get_application --factory) and bc-api on :18080, then
python3 rust/contract/contract_test.py fixture.json http://127.0.0.1:18000 http://127.0.0.1:18080
```

`contract/bench.sh` runs one ApacheBench load (50 connections, 30 s) against either server and prints throughput, latency percentiles, CPU seconds and memory.

The fixture holds throw-away ids and tokens; do not commit it. `contract/golden_tink.py` regenerates the Tink test vector
(`bc-api/tests/golden/tink_vector.json`, a keyset generated for tests only).
