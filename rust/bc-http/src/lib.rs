//! HTTP pieces every route group of the Rust API needs, written to behave as
//! the Python backend does (equal after JSON parse: status codes, field names,
//! values and the security and caching headers; not key order or whitespace).
//!
//! * [`error`]: the error bodies of `backend/app/exceptions` and FastAPI.
//! * [`cors`]: CORS headers from the `allowed_origins` table, cached 60 s.
//! * [`client_ip`]: the client address behind trusted proxies, the rules of
//!   `common/common/utils/client_ip.py`.
//! * [`json_depth`]: the 422 `body_too_deep` for a request body nested too deeply.
//! * [`privacy`]: what a log line may say about a request, and which responses
//!   must never be cached (`middlewares/request_privacy.py`).

pub mod client_ip;
pub mod cors;
pub mod error;
pub mod json_depth;
pub mod privacy;
