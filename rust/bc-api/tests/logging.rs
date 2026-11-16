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

/// The tests of this file install a log subscriber each; they run one at a time.
static ONE_AT_A_TIME: tokio::sync::Mutex<()> = tokio::sync::Mutex::const_new(());

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
    let _serial = ONE_AT_A_TIME.lock().await;
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

fn capture_logs() -> (Capture, tracing::subscriber::DefaultGuard) {
    let capture = Capture::default();
    let subscriber = tracing_subscriber::fmt()
        .with_writer(capture.clone())
        .with_max_level(tracing::Level::DEBUG)
        .finish();
    let guard = tracing::subscriber::set_default(subscriber);
    (capture, guard)
}

const ENCODED_RECEIPT_PATHS: [&str; 8] = [
    "/api/v1/workspaces/w/submissions/by%2Duuid/RECEIPTONE?q=1",
    "/api/v1/workspaces/w/submissions/by%2duuid/RECEIPTONE",
    "/api/v1/workspaces/w/submissions/b%79%2Duu%69d/RECEIPTONE",
    "/api/v1/workspaces/w/submissions/by-uuid%2FRECEIPTONE",
    "/api/v1/workspaces/w/submissions/by-uuid%2fRECEIPTONE",
    "/api/v1/workspaces/w/submissions/by%252Duuid/RECEIPTONE",
    "/api/v1/workspaces/w/submissions/by-uuid/RECEIPT%4FNE",
    "/api/v1/workspaces/w/%73ubmissions/by-uuid/RECEIPTONE",
];

#[tokio::test]
async fn a_percent_encoded_receipt_path_is_redacted_in_the_log_of_a_502() {
    let _serial = ONE_AT_A_TIME.lock().await;
    let (capture, _guard) = capture_logs();
    let free = {
        let l = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        l.local_addr().unwrap()
    };
    let edge_addr = edge(free, &[]).await;
    for path in ENCODED_RECEIPT_PATHS {
        let a = call(edge_addr, Method::GET, path, &[], Body::empty()).await;
        assert_eq!(a.status, StatusCode::BAD_GATEWAY, "{path}");
    }
    let logged = String::from_utf8(capture.0.lock().unwrap().clone()).unwrap();
    assert_eq!(
        logged.matches("upstream connect failed").count(),
        ENCODED_RECEIPT_PATHS.len()
    );
    assert_eq!(
        logged.matches("/by-uuid/<redacted>").count(),
        ENCODED_RECEIPT_PATHS.len(),
        "{logged}"
    );
    for secret in ["RECEIPTONE", "RECEIPT", "ONE"] {
        assert!(!logged.contains(secret), "the log holds {secret}: {logged}");
    }
}

#[tokio::test]
async fn a_percent_encoded_receipt_path_is_redacted_in_the_log_of_a_504() {
    let _serial = ONE_AT_A_TIME.lock().await;
    let (capture, _guard) = capture_logs();
    // accepts the connection and never answers
    let silent = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let silent_addr = silent.local_addr().unwrap();
    tokio::spawn(async move {
        let mut held = Vec::new();
        while let Ok((stream, _)) = silent.accept().await {
            held.push(stream);
        }
    });
    let edge_addr = edge(silent_addr, &[("BC_PYTHON_UPSTREAM_TIMEOUT_SECS", "1")]).await;
    let a = call(
        edge_addr,
        Method::GET,
        "/api/v1/workspaces/w/submissions/by%2Duuid/RECEIPTONE",
        &[],
        Body::empty(),
    )
    .await;
    assert_eq!(a.status, StatusCode::GATEWAY_TIMEOUT);
    let logged = String::from_utf8(capture.0.lock().unwrap().clone()).unwrap();
    assert!(logged.contains("upstream timeout"), "{logged}");
    assert!(logged.contains("/by-uuid/<redacted>"), "{logged}");
    assert!(!logged.contains("RECEIPT"), "{logged}");
}
