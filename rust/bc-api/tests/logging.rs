#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::needless_pass_by_value,
    clippy::format_collect
)]
//! What the log may say about a forwarded request. A test file of its own: it
//! installs a log subscriber for the thread, and tests running beside it in
//! one process would race it for the log call sites.

mod support;

use std::sync::Arc;

use axum::body::Body;
use axum::http::{Method, StatusCode};
use support::{call, edge};

// ------------------------------------------------------------------ logging

/// A tracing writer that collects every line.
#[derive(Clone, Default)]
struct Capture(Arc<std::sync::Mutex<Vec<u8>>>);

impl std::io::Write for Capture {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        self.0.lock().unwrap().extend_from_slice(buf);
        Ok(buf.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

impl<'a> tracing_subscriber::fmt::MakeWriter<'a> for Capture {
    type Writer = Capture;
    fn make_writer(&'a self) -> Capture {
        self.clone()
    }
}

#[tokio::test]
async fn a_failed_forward_logs_neither_the_query_nor_a_cookie_nor_a_body() {
    let capture = Capture::default();
    let subscriber = tracing_subscriber::fmt()
        .with_writer(capture.clone())
        .with_max_level(tracing::Level::DEBUG)
        .finish();
    let _guard = tracing::subscriber::set_default(subscriber);
    let free = {
        let l = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        l.local_addr().unwrap()
    };
    let edge_addr = edge(free, &[]).await;
    let a = call(
        edge_addr,
        Method::POST,
        "/api/v1/workspaces/w/submissions/by-uuid/123e4567-receipt?email=person%40example.test&q=secretquery",
        &[
            ("cookie", "Authorization=secretcookie"),
            ("authorization", "Bearer secrettoken"),
            ("x-forwarded-for", "198.51.100.77"),
        ],
        Body::from("secretbody"),
    )
    .await;
    assert_eq!(a.status, StatusCode::BAD_GATEWAY);
    let logged = String::from_utf8(capture.0.lock().unwrap().clone()).unwrap();
    assert!(logged.contains("upstream connect failed"), "{logged}");
    assert!(logged.contains("/by-uuid/<redacted>"), "{logged}");
    for secret in [
        "person",
        "secretquery",
        "secretcookie",
        "secrettoken",
        "secretbody",
        "198.51.100.77",
        "123e4567-receipt",
    ] {
        assert!(!logged.contains(secret), "the log holds {secret}: {logged}");
    }
}
