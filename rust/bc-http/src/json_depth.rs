//! How deeply a JSON request body may nest, checked before anything parses it.
//!
//! The Python backend refuses a request body nested deeper than
//! `MAX_JSON_DEPTH` (128) levels with `422` and the code `body_too_deep`
//! (`backend/app/utils/json_depth.py`, applied by
//! `backend/app/middlewares/json_depth.py` to every route). This module is the
//! same rule for the routes Rust serves, byte for byte in what it counts:
//!
//! * [`DepthScanner`] counts `[` and `{` outside strings as they arrive, in
//!   pieces of any size, keeping only a counter and two flags (whether it is
//!   inside a string, and whether the last piece ended on the backslash of an
//!   escape). A closer never takes the count below zero. The input need not be
//!   valid JSON. [`too_deep`] is the same scan over a whole value.
//! * [`guard`] is the middleware: it looks at POST, PUT, PATCH and DELETE
//!   requests that declare `application/json`, `application/*+json`,
//!   `text/plain` or no content type (several routes read the raw body whatever
//!   it says) and have a body. Form posts (urlencoded, multipart) are never
//!   touched here; the JSON a form field carries is checked where the field is
//!   parsed, with [`too_deep`].
//!
//! The guard works in the same two phases as the Python middleware:
//!
//! 1. A body that declares at most [`MAX_BUFFERED_BYTES`] (or declares nothing,
//!    chunked) is read here and scanned as it comes, up to that many bytes, then
//!    replayed to the route unchanged; a deep one is refused at once.
//! 2. Beyond that the pieces go straight on to the route, each scanned on the
//!    way. When a piece takes the nesting past the limit the route's body ends
//!    in an error (the client "went away") and the 422 is sent in place of
//!    whatever the route answers. A route that answered before reading that
//!    far (its own 413 on the declared size, say) keeps its answer.
//!
//! It sits inside the CORS handling, so the refusal can be read from another
//! origin, and before the route is chosen: nothing else (authentication, a
//! malformed path) can be answered first for a body that is too deep.
//! Requests that are forwarded to the Python backend are not scanned here;
//! Python applies the same rule to them.

use std::io;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use axum::body::{Body, Bytes};
use axum::extract::Request;
use axum::http::{HeaderMap, Method, StatusCode, header};
use axum::middleware::Next;
use axum::response::Response;
use futures_util::{StreamExt, stream};
use serde_json::{Value, json};

use crate::error::json_response;

/// Mirrors `MAX_JSON_DEPTH` of the Python backend: change both together.
pub const MAX_JSON_DEPTH: usize = 128;
/// The most of a body held before the route runs (Python's `MAX_BUFFERED_BYTES`).
pub const MAX_BUFFERED_BYTES: usize = 1024 * 1024;
/// The error code of the refusal.
pub const CODE: &str = "body_too_deep";

/// The message of the refusal (Python's `MESSAGE`).
pub fn message() -> String {
    format!("The request body is nested too deeply (at most {MAX_JSON_DEPTH} levels).")
}

/// The scan of a body that arrives in pieces: [`feed`](Self::feed) each piece
/// in order and it says as soon as the nesting passes the limit.
#[derive(Debug, Clone)]
pub struct DepthScanner {
    limit: usize,
    depth: usize,
    in_string: bool,
    /// The last piece ended on a backslash inside a string.
    escaped: bool,
}

impl Default for DepthScanner {
    fn default() -> Self {
        Self::new(MAX_JSON_DEPTH)
    }
}

impl DepthScanner {
    pub fn new(limit: usize) -> Self {
        Self {
            limit,
            depth: 0,
            in_string: false,
            escaped: false,
        }
    }

    /// Whether the body so far nests deeper than the limit.
    pub fn feed(&mut self, chunk: &[u8]) -> bool {
        for &byte in chunk {
            if self.in_string {
                if self.escaped {
                    self.escaped = false;
                } else if byte == b'\\' {
                    self.escaped = true;
                } else if byte == b'"' {
                    self.in_string = false;
                }
                continue;
            }
            match byte {
                b'"' => self.in_string = true,
                b'[' | b'{' => {
                    self.depth += 1;
                    if self.depth > self.limit {
                        return true;
                    }
                }
                b']' | b'}' => self.depth = self.depth.saturating_sub(1),
                _ => {}
            }
        }
        false
    }
}

/// Whether `raw` nests arrays and objects deeper than `limit` (Python's
/// `too_deep`). Linear, never copies, and does not need valid JSON.
pub fn too_deep(raw: &[u8], limit: usize) -> bool {
    DepthScanner::new(limit).feed(raw)
}

/// The refusal: 422 `{"code", "message"}`; the MCP endpoint's own errors are
/// `{"error": ...}`, so a path with an `mcp` segment carries that too.
pub fn refusal(path: &str) -> Response {
    let mut payload: Value = json!({"code": CODE, "message": message()});
    if path.split('/').any(|segment| segment == "mcp") {
        payload["error"] = Value::String(message());
    }
    json_response(StatusCode::UNPROCESSABLE_ENTITY, &payload)
}

/// `None` when the request cannot carry a JSON document; otherwise its declared
/// length (`None` inside: it declares none, chunked). The same rules, in the
/// same order, as `_carries_json` in the Python middleware.
pub fn carries_json(method: &Method, headers: &HeaderMap) -> Option<Option<usize>> {
    if !matches!(
        *method,
        Method::POST | Method::PUT | Method::PATCH | Method::DELETE
    ) {
        return None;
    }
    let mut declared: Option<usize> = None;
    let mut content_type: &[u8] = b"";
    let mut chunked = false;
    for (name, value) in headers {
        if name == header::CONTENT_LENGTH {
            let digits = value.as_bytes().trim_ascii();
            declared = (!digits.is_empty() && digits.iter().all(u8::is_ascii_digit)).then(|| {
                // a length beyond what fits is beyond the cap all the same
                std::str::from_utf8(digits)
                    .ok()
                    .and_then(|d| d.parse().ok())
                    .unwrap_or(usize::MAX)
            });
        } else if name == header::CONTENT_TYPE {
            content_type = value.as_bytes();
        } else if name == header::TRANSFER_ENCODING {
            chunked = true;
        }
    }
    if declared == Some(0) || (declared.is_none() && !chunked) {
        return None;
    }
    let media = content_type
        .split(|&b| b == b';')
        .next()
        .unwrap_or_default()
        .trim_ascii()
        .to_ascii_lowercase();
    let json_like = media.is_empty()
        || media == b"application/json"
        || media == b"text/plain"
        || (media.starts_with(b"application/") && media.ends_with(b"+json"));
    json_like.then_some(declared)
}

/// The middleware (`axum::middleware::from_fn(json_depth::guard)`).
pub async fn guard(request: Request, next: Next) -> Response {
    let Some(declared) = carries_json(request.method(), request.headers()) else {
        return next.run(request).await;
    };
    let path = request.uri().path().to_string();
    let (parts, body) = request.into_parts();
    let mut incoming = body.into_data_stream();
    let mut scanner = DepthScanner::default();

    // phase 1: hold the body (and scan it) while it is within the cap
    let mut held: Vec<Bytes> = Vec::new();
    let mut failure: Option<io::Error> = None;
    let mut finished = false;
    if declared.is_none_or(|n| n <= MAX_BUFFERED_BYTES) {
        let mut size = 0;
        while size <= MAX_BUFFERED_BYTES {
            match incoming.next().await {
                None => {
                    finished = true;
                    break;
                }
                Some(Err(error)) => {
                    failure = Some(io::Error::other(error));
                    break;
                }
                Some(Ok(chunk)) => {
                    if chunk.is_empty() {
                        continue;
                    }
                    if scanner.feed(&chunk) {
                        return refusal(&path);
                    }
                    size += chunk.len();
                    held.push(chunk);
                }
            }
        }
    }

    // phase 2: what is left goes on, scanned on the way
    let violated = Arc::new(AtomicBool::new(false));
    let flag = violated.clone();
    let rest = incoming.map(move |item| {
        if flag.load(Ordering::SeqCst) {
            return Err(io::Error::new(io::ErrorKind::ConnectionAborted, "too deep"));
        }
        let chunk = item.map_err(io::Error::other)?;
        if scanner.feed(&chunk) {
            flag.store(true, Ordering::SeqCst);
            return Err(io::Error::new(io::ErrorKind::ConnectionAborted, "too deep"));
        }
        Ok(chunk)
    });
    let replay = stream::iter(held.into_iter().map(Ok).chain(failure.map(Err)));
    let body = if finished {
        Body::from_stream(replay)
    } else {
        Body::from_stream(replay.chain(rest))
    };
    let response = next.run(Request::from_parts(parts, body)).await;
    if violated.load(Ordering::SeqCst) {
        return refusal(&path);
    }
    response
}
