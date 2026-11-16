//! CORS as the backend configures Starlette's `CORSMiddleware`
//! (`backend/app/middlewares/dynamic_cors_middleware.py`): credentials
//! allowed, every method and header allowed, the origins coming from the
//! `allowed_origins` table, cached for 60 seconds.
//!
//! This module adds the headers of an answered request (`simple`). A
//! preflight (`OPTIONS` with `Access-Control-Request-Method`) is not answered
//! here: for a path the Rust side serves, the edge forwards it to the Python
//! backend, which answers it the same way for every path.

use std::sync::Mutex;
use std::time::{Duration, Instant};

use axum::http::{HeaderMap, HeaderName, HeaderValue, header};
use axum::response::Response;

/// The headers the webapp reads across origins.
pub const EXPOSE_HEADERS: &str = "Content-Disposition, X-Open-Formulieren-Unmapped";
/// How long the origins stay cached (`_cache_ttl_seconds`).
pub const TTL: Duration = Duration::from_secs(60);

/// The allowed origins, read from the database at most once per [`TTL`].
#[derive(Debug, Default)]
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

/// Adds the CORS headers of a request that carried `Origin` to `response`.
/// The credentials and expose headers always go out; the origin itself is
/// echoed only when it is on the list, and `Vary: Origin` says so.
pub fn simple(response: &mut Response, origin: &str, allowed: &[String]) {
    let headers = response.headers_mut();
    set(headers, "access-control-allow-credentials", "true");
    set(headers, "access-control-expose-headers", EXPOSE_HEADERS);
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

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;

    fn list() -> Vec<String> {
        vec!["https://app.example.test".to_string()]
    }

    #[test]
    fn an_allowed_origin_is_echoed_with_vary() {
        let mut r = Response::new(Body::empty());
        simple(&mut r, "https://app.example.test", &list());
        let h = r.headers();
        assert_eq!(h["access-control-allow-origin"], "https://app.example.test");
        assert_eq!(h["access-control-allow-credentials"], "true");
        assert_eq!(h[header::VARY], "Origin");
        assert_eq!(h["access-control-expose-headers"], EXPOSE_HEADERS);
    }

    #[test]
    fn another_origin_gets_no_allow_origin_and_the_match_is_exact() {
        for origin in [
            "https://evil.example.test",
            "null",
            "https://app.example.test/",
            "https://APP.example.test",
        ] {
            let mut r = Response::new(Body::empty());
            simple(&mut r, origin, &list());
            assert!(
                r.headers().get("access-control-allow-origin").is_none(),
                "{origin}"
            );
            assert!(r.headers().get(header::VARY).is_none());
        }
    }

    #[test]
    fn vary_is_appended_to_an_existing_one() {
        let mut r = Response::new(Body::empty());
        r.headers_mut()
            .insert(header::VARY, HeaderValue::from_static("Cookie"));
        simple(&mut r, "https://app.example.test", &list());
        assert_eq!(r.headers()[header::VARY], "Cookie, Origin");
    }

    #[test]
    fn the_cache_serves_a_stored_list_and_keeps_it_when_stale() {
        let origins = Origins::default();
        assert!(origins.fresh().is_none() && origins.stale().is_empty());
        origins.store(list());
        assert_eq!(origins.fresh(), Some(list()));
        assert_eq!(origins.stale(), list());
    }
}
