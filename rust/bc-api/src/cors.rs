//! Starlette `CORSMiddleware` as the backend configures it
//! (`allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`,
//! origins from the `allowed_origins` table, cached for 60 s:
//! `backend/app/middlewares/dynamic_cors_middleware.py`).

use axum::http::{header, HeaderMap, HeaderName, HeaderValue, Method, StatusCode};
use axum::response::Response;
use std::sync::Mutex;
use std::time::{Duration, Instant};

const EXPOSE: &str = "Content-Disposition, X-Open-Formulieren-Unmapped";
const ALL_METHODS: &str = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT";
const TTL: Duration = Duration::from_secs(60);

#[derive(Default)]
pub struct Origins {
    inner: Mutex<Option<(Instant, Vec<String>)>>,
}

impl Origins {
    /// The cached list, if it is still fresh.
    pub fn fresh(&self) -> Option<Vec<String>> {
        let guard = self.inner.lock().ok()?;
        match guard.as_ref() {
            Some((at, list)) if at.elapsed() < TTL => Some(list.clone()),
            _ => None,
        }
    }

    /// The cached list even when stale (used when the refresh fails).
    pub fn stale(&self) -> Vec<String> {
        self.inner
            .lock()
            .ok()
            .and_then(|g| g.as_ref().map(|(_, l)| l.clone()))
            .unwrap_or_default()
    }

    pub fn store(&self, list: Vec<String>) {
        if let Ok(mut guard) = self.inner.lock() {
            *guard = Some((Instant::now(), list));
        }
    }
}

fn set(headers: &mut HeaderMap, name: &'static str, value: &str) {
    if let Ok(v) = HeaderValue::from_str(value) {
        headers.insert(HeaderName::from_static(name), v);
    }
}

/// Add the CORS headers of a request that carried `Origin` to `response`.
pub fn simple(response: &mut Response, origin: &str, allowed: &[String]) {
    let headers = response.headers_mut();
    set(headers, "access-control-allow-credentials", "true");
    set(headers, "access-control-expose-headers", EXPOSE);
    if allowed.iter().any(|o| o == origin) {
        set(headers, "access-control-allow-origin", origin);
        // Starlette's add_vary_header: appended to an existing Vary
        let vary = match headers.get(header::VARY).and_then(|v| v.to_str().ok()) {
            Some(existing) if !existing.is_empty() => format!("{existing}, Origin"),
            _ => "Origin".to_string(),
        };
        set(headers, "vary", &vary);
    }
}

/// The answer to a preflight (`OPTIONS` with `Access-Control-Request-Method`).
pub fn preflight(request_headers: &HeaderMap, allowed: &[String]) -> Response {
    let origin = request_headers
        .get(header::ORIGIN)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let method = request_headers
        .get("access-control-request-method")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let asked = request_headers
        .get("access-control-request-headers")
        .and_then(|v| v.to_str().ok());
    let mut headers = HeaderMap::new();
    set(&mut headers, "vary", "Origin");
    set(&mut headers, "access-control-allow-methods", ALL_METHODS);
    set(&mut headers, "access-control-max-age", "600");
    set(&mut headers, "access-control-allow-credentials", "true");
    let mut failures: Vec<&str> = Vec::new();
    if allowed.iter().any(|o| o == origin) {
        set(&mut headers, "access-control-allow-origin", origin);
    } else {
        failures.push("origin");
    }
    let known = ALL_METHODS.split(", ").any(|m| m == method);
    if !known {
        failures.push("method");
    }
    if let Some(asked) = asked {
        set(&mut headers, "access-control-allow-headers", asked);
    }
    let (status, body) = if failures.is_empty() {
        (StatusCode::OK, "OK".to_string())
    } else {
        (
            StatusCode::BAD_REQUEST,
            format!("Disallowed CORS {}", failures.join(", ")),
        )
    };
    let mut response = Response::new(axum::body::Body::from(body));
    *response.status_mut() = status;
    for (k, v) in headers.iter() {
        response.headers_mut().insert(k.clone(), v.clone());
    }
    response.headers_mut().insert(
        header::CONTENT_TYPE,
        HeaderValue::from_static("text/plain; charset=utf-8"),
    );
    response
}

pub fn is_preflight(method: &Method, headers: &HeaderMap) -> bool {
    method == Method::OPTIONS && headers.contains_key("access-control-request-method")
}
