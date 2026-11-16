#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::needless_pass_by_value,
    clippy::format_collect
)]
//! The pass-through, against a fake Python upstream on a real socket: status,
//! headers (repeated `Set-Cookie` included), `X-Forwarded-For`, streaming of a
//! large body in both directions, a client that disconnects, upstream
//! failures, and what the log may say.

mod support;

use std::convert::Infallible;
use std::net::SocketAddr;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use axum::Router;
use axum::body::{Body, Bytes};
use axum::extract::{Path, Request, State};
use axum::http::{HeaderMap, HeaderValue, Method, StatusCode, header};
use axum::response::{IntoResponse, Response};
use axum::routing::{any, get as route_get, post};
use futures_util::stream::{self, StreamExt};
use http_body_util::BodyExt;
use sha2::{Digest, Sha256};
use support::{call, client, edge, get, serve};
use tokio::sync::{Notify, mpsc};

#[derive(Clone, Default)]
struct Gates {
    first_chunk_seen: Arc<Notify>,
    release: Arc<Notify>,
    stream_dropped: Arc<Notify>,
    dropped_flag: Arc<AtomicBool>,
}

/// Sets `flag` and wakes `notify` when the response body is dropped, which is
/// what happens when the connection to the upstream is closed.
struct DropSignal {
    notify: Arc<Notify>,
    flag: Arc<AtomicBool>,
}

impl Drop for DropSignal {
    fn drop(&mut self) {
        self.flag.store(true, Ordering::SeqCst);
        self.notify.notify_one();
    }
}

fn chunk(i: u32) -> Bytes {
    // deterministic, not compressible by luck: 64 KiB per chunk
    let mut v = Vec::with_capacity(65536);
    for j in 0..65536u32 {
        v.push(((i.wrapping_mul(31)).wrapping_add(j.wrapping_mul(7)) % 251) as u8);
    }
    Bytes::from(v)
}

async fn echo(request: Request) -> Response {
    let (parts, body) = request.into_parts();
    let bytes = body.collect().await.unwrap().to_bytes();
    let headers: Vec<(String, String)> = parts
        .headers
        .iter()
        .map(|(k, v)| {
            (
                k.as_str().to_string(),
                String::from_utf8_lossy(v.as_bytes()).into_owned(),
            )
        })
        .collect();
    axum::Json(serde_json::json!({
        "method": parts.method.as_str(),
        "path_and_query": parts.uri.path_and_query().map(ToString::to_string),
        "headers": headers,
        "body_len": bytes.len(),
        "body": String::from_utf8_lossy(&bytes),
    }))
    .into_response()
}

async fn cookies() -> Response {
    let mut response = Response::new(Body::from("cookies"));
    let h = response.headers_mut();
    h.append(
        header::SET_COOKIE,
        HeaderValue::from_static("Authorization=a; Path=/; HttpOnly; Secure"),
    );
    h.append(
        header::SET_COOKIE,
        HeaderValue::from_static("RefreshToken=b; Path=/; HttpOnly; Secure"),
    );
    h.append("x-multi", HeaderValue::from_static("one"));
    h.append("x-multi", HeaderValue::from_static("two"));
    h.insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    h.insert(header::VARY, HeaderValue::from_static("Origin"));
    response
}

async fn status(Path(code): Path<u16>) -> Response {
    let mut response = Response::new(Body::from(format!("status {code}")));
    *response.status_mut() = StatusCode::from_u16(code).unwrap();
    response
}

async fn redirect() -> Response {
    let mut response = Response::new(Body::empty());
    *response.status_mut() = StatusCode::TEMPORARY_REDIRECT;
    response.headers_mut().insert(
        header::LOCATION,
        HeaderValue::from_static("http://app.example.test/elsewhere"),
    );
    response
}

async fn big_down() -> Response {
    let s = stream::iter((0..512u32).map(|i| Ok::<_, Infallible>(chunk(i))));
    Response::new(Body::from_stream(s))
}

async fn big_up(request: Request) -> Response {
    let mut stream = request.into_body().into_data_stream();
    let mut hasher = Sha256::new();
    let mut len = 0usize;
    while let Some(item) = stream.next().await {
        let bytes = item.unwrap();
        len += bytes.len();
        hasher.update(&bytes);
    }
    axum::Json(serde_json::json!({"len": len, "sha256": hex(&hasher.finalize())})).into_response()
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

async fn stream_gate(State(g): State<Gates>) -> Response {
    let release = g.release.clone();
    let s = stream::once(async { Ok::<_, Infallible>(Bytes::from_static(b"first")) }).chain(
        stream::once(async move {
            release.notified().await;
            Ok::<_, Infallible>(Bytes::from_static(b"second"))
        }),
    );
    Response::new(Body::from_stream(s))
}

async fn upload_gate(State(g): State<Gates>, request: Request) -> Response {
    let mut stream = request.into_body().into_data_stream();
    let mut total = 0usize;
    let mut first = true;
    while let Some(item) = stream.next().await {
        total += item.unwrap().len();
        if first {
            first = false;
            g.first_chunk_seen.notify_one();
        }
    }
    axum::Json(serde_json::json!({"total": total})).into_response()
}

async fn hang(State(g): State<Gates>) -> Response {
    let signal = DropSignal {
        notify: g.stream_dropped.clone(),
        flag: g.dropped_flag.clone(),
    };
    let s = stream::once(async { Ok::<_, Infallible>(Bytes::from_static(b"start")) }).chain(
        stream::once(async move {
            let _keep = signal;
            std::future::pending::<()>().await;
            Ok::<_, Infallible>(Bytes::new())
        }),
    );
    Response::new(Body::from_stream(s))
}

async fn slow_headers() -> Response {
    tokio::time::sleep(Duration::from_secs(10)).await;
    Response::new(Body::from("late"))
}

fn upstream_router(gates: Gates) -> Router {
    Router::new()
        .route("/echo", any(echo))
        .route("/echo/{*rest}", any(echo))
        .route("/cookies", route_get(cookies))
        .route("/status/{code}", any(status))
        .route("/redirect", route_get(redirect))
        .route("/big-down", route_get(big_down))
        .route("/big-up", post(big_up))
        .route("/stream-gate", route_get(stream_gate))
        .route("/upload-gate", post(upload_gate))
        .route("/hang", route_get(hang))
        .route("/slow-headers", route_get(slow_headers))
        .with_state(gates)
}

async fn up() -> (SocketAddr, Gates) {
    let gates = Gates::default();
    (serve(upstream_router(gates.clone())).await, gates)
}

#[tokio::test]
async fn status_body_and_unknown_headers_come_back_as_they_are() {
    let (upstream, _) = up().await;
    let edge = edge(upstream, &[]).await;
    for code in [200u16, 201, 204, 400, 401, 404, 409, 422, 500, 503] {
        let a = get(edge, &format!("/status/{code}"), &[]).await;
        assert_eq!(a.status.as_u16(), code);
        if code != 204 {
            assert_eq!(a.text(), format!("status {code}"));
        }
    }
}

#[tokio::test]
async fn repeated_headers_and_set_cookie_survive_the_hop() {
    let (upstream, _) = up().await;
    let edge = edge(upstream, &[]).await;
    let a = get(edge, "/cookies", &[]).await;
    let cookies: Vec<&str> = a
        .headers
        .get_all(header::SET_COOKIE)
        .iter()
        .map(|v| v.to_str().unwrap())
        .collect();
    assert_eq!(
        cookies,
        vec![
            "Authorization=a; Path=/; HttpOnly; Secure",
            "RefreshToken=b; Path=/; HttpOnly; Secure"
        ]
    );
    assert_eq!(a.headers.get_all("x-multi").iter().count(), 2);
    assert_eq!(a.headers[header::CACHE_CONTROL], "no-store");
    assert_eq!(a.headers[header::VARY], "Origin");
    assert_eq!(a.text(), "cookies");
}

#[tokio::test]
async fn the_request_arrives_with_its_method_path_query_headers_and_body() {
    let (upstream, _) = up().await;
    let edge = edge(upstream, &[]).await;
    let a = call(
        edge,
        Method::PATCH,
        "/echo/a%20b/c?x=1&y=%C3%A9&x=2",
        &[
            ("cookie", "Authorization=t; a=1"),
            ("authorization", "Bearer k"),
            ("origin", "https://app.example.test"),
            ("x-custom", "kept"),
            ("connection", "keep-alive, x-private"),
            ("x-private", "hop"),
            ("content-type", "application/json"),
        ],
        Body::from(r#"{"k":"v"}"#),
    )
    .await;
    let seen = a.json();
    assert_eq!(seen["method"], "PATCH");
    assert_eq!(seen["path_and_query"], "/echo/a%20b/c?x=1&y=%C3%A9&x=2");
    assert_eq!(seen["body"], r#"{"k":"v"}"#);
    let headers = seen["headers"].as_array().unwrap();
    let has = |name: &str, value: &str| headers.iter().any(|h| h[0] == name && h[1] == value);
    assert!(has("cookie", "Authorization=t; a=1"));
    assert!(has("authorization", "Bearer k"));
    assert!(has("origin", "https://app.example.test"));
    assert!(has("x-custom", "kept"));
    assert!(has("content-type", "application/json"));
    assert!(
        headers.iter().all(|h| h[0] != "x-private"),
        "named by Connection: dropped"
    );
    let host = headers
        .iter()
        .find(|h| h[0] == "host")
        .expect("host forwarded");
    assert_eq!(
        host[1],
        edge.to_string(),
        "the original Host reaches the backend"
    );
}

#[tokio::test]
async fn forwarded_for_gets_the_peer_appended_to_what_the_client_sent() {
    let (upstream, _) = up().await;
    let edge = edge(upstream, &[]).await;
    let a = get(
        edge,
        "/echo",
        &[("x-forwarded-for", "198.51.100.9, 192.0.2.4")],
    )
    .await;
    let headers = a.json()["headers"].clone();
    let xff: Vec<String> = headers
        .as_array()
        .unwrap()
        .iter()
        .filter(|h| h[0] == "x-forwarded-for")
        .map(|h| h[1].as_str().unwrap().to_string())
        .collect();
    assert_eq!(xff, vec!["198.51.100.9, 192.0.2.4, 127.0.0.1".to_string()]);
    // without one the chain starts with the peer
    let a = get(edge, "/echo", &[]).await;
    let xff = a.json()["headers"]
        .as_array()
        .unwrap()
        .iter()
        .find(|h| h[0] == "x-forwarded-for")
        .map(|h| h[1].as_str().unwrap().to_string());
    assert_eq!(xff.as_deref(), Some("127.0.0.1"));
}

#[tokio::test]
async fn a_redirect_is_not_followed() {
    let (upstream, _) = up().await;
    let edge = edge(upstream, &[]).await;
    let a = get(edge, "/redirect", &[]).await;
    assert_eq!(a.status, StatusCode::TEMPORARY_REDIRECT);
    assert_eq!(
        a.headers[header::LOCATION],
        "http://app.example.test/elsewhere"
    );
}

#[tokio::test]
async fn a_large_download_arrives_whole_and_unchanged() {
    let (upstream, _) = up().await;
    let edge = edge(upstream, &[]).await;
    let response = client()
        .request(
            axum::http::Request::get(format!("http://{edge}/big-down"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let mut hasher = Sha256::new();
    let mut len = 0usize;
    let mut stream = response.into_body().into_data_stream();
    while let Some(item) = stream.next().await {
        let bytes = item.unwrap();
        len += bytes.len();
        hasher.update(&bytes);
    }
    let mut expected = Sha256::new();
    for i in 0..512u32 {
        expected.update(chunk(i));
    }
    assert_eq!(len, 512 * 65536);
    assert_eq!(hasher.finalize(), expected.finalize());
}

#[tokio::test]
async fn a_large_upload_arrives_whole_and_unchanged_as_a_stream() {
    let (upstream, _) = up().await;
    let edge = edge(upstream, &[]).await;
    let s = stream::iter((0..512u32).map(|i| Ok::<_, Infallible>(chunk(i))));
    let a = call(edge, Method::POST, "/big-up", &[], Body::from_stream(s)).await;
    let mut expected = Sha256::new();
    for i in 0..512u32 {
        expected.update(chunk(i));
    }
    assert_eq!(a.json()["len"], 512 * 65536);
    assert_eq!(a.json()["sha256"], hex(&expected.finalize()));
}

#[tokio::test]
async fn the_response_is_streamed_not_buffered() {
    let (upstream, gates) = up().await;
    let edge = edge(upstream, &[]).await;
    let response = client()
        .request(
            axum::http::Request::get(format!("http://{edge}/stream-gate"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let mut body = response.into_body();
    // the first chunk arrives while the upstream is still holding the second back
    let first = tokio::time::timeout(Duration::from_secs(5), body.frame())
        .await
        .expect("the first chunk must not wait for the end of the body")
        .unwrap()
        .unwrap();
    assert_eq!(first.into_data().unwrap(), Bytes::from_static(b"first"));
    gates.release.notify_one();
    let second = body.frame().await.unwrap().unwrap();
    assert_eq!(second.into_data().unwrap(), Bytes::from_static(b"second"));
}

#[tokio::test]
async fn the_request_body_is_streamed_not_buffered() {
    let (upstream, gates) = up().await;
    let edge = edge(upstream, &[]).await;
    let (tx, rx) = mpsc::channel::<Bytes>(4);
    let body = Body::from_stream(stream::unfold(rx, |mut rx| async {
        rx.recv().await.map(|b| (Ok::<_, Infallible>(b), rx))
    }));
    let pending =
        tokio::spawn(async move { call(edge, Method::POST, "/upload-gate", &[], body).await });
    tx.send(Bytes::from_static(b"hello ")).await.unwrap();
    // the upstream has the first chunk while the client has not finished sending
    tokio::time::timeout(Duration::from_secs(5), gates.first_chunk_seen.notified())
        .await
        .expect("the upstream must see the first chunk before the upload ends");
    tx.send(Bytes::from_static(b"world")).await.unwrap();
    drop(tx);
    let a = pending.await.unwrap();
    assert_eq!(a.json()["total"], 11);
}

#[tokio::test]
async fn a_client_that_disconnects_closes_the_upstream_connection() {
    let (upstream, gates) = up().await;
    let edge = edge(upstream, &[]).await;
    let response = client()
        .request(
            axum::http::Request::get(format!("http://{edge}/hang"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let mut body = response.into_body();
    let first = body.frame().await.unwrap().unwrap();
    assert_eq!(first.into_data().unwrap(), Bytes::from_static(b"start"));
    assert!(
        !gates.dropped_flag.load(Ordering::SeqCst),
        "still streaming"
    );
    // the client goes away
    drop(body);
    drop(client());
    tokio::time::timeout(Duration::from_secs(5), gates.stream_dropped.notified())
        .await
        .expect("the upstream request must be cancelled when the client disconnects");
}

#[tokio::test]
async fn an_upstream_that_is_down_is_a_502_without_details() {
    // a port nothing listens on
    let free = {
        let l = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        l.local_addr().unwrap()
    };
    let edge = edge(free, &[]).await;
    let a = get(edge, "/anything?secret=1", &[]).await;
    assert_eq!(a.status, StatusCode::BAD_GATEWAY);
    assert_eq!(a.text(), "Bad Gateway");
    assert!(!a.text().contains(&free.to_string()));
}

#[tokio::test]
async fn an_upstream_that_does_not_answer_in_time_is_a_504() {
    let (upstream, _) = up().await;
    let edge = edge(upstream, &[("BC_PYTHON_UPSTREAM_TIMEOUT_SECS", "1")]).await;
    let started = std::time::Instant::now();
    let a = get(edge, "/slow-headers", &[]).await;
    assert_eq!(a.status, StatusCode::GATEWAY_TIMEOUT);
    assert!(started.elapsed() < Duration::from_secs(5));
}

#[tokio::test]
async fn health_is_the_edges_own_and_does_not_ask_the_upstream() {
    let free = {
        let l = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        l.local_addr().unwrap()
    };
    let edge = edge(free, &[]).await;
    let a = get(edge, "/health", &[]).await;
    assert_eq!(
        (a.status, a.text().as_str()),
        (StatusCode::OK, r#"{"status":"ok"}"#)
    );
}

#[tokio::test]
async fn forwarded_headers_object_is_not_confused_with_a_hop_header() {
    // `Forwarded`, `Via` and `X-Real-IP` are the client's or a proxy's own words:
    // they pass through, the backend decides whether to read them
    let (upstream, _) = up().await;
    let edge = edge(upstream, &[]).await;
    let mut h = HeaderMap::new();
    h.insert("forwarded", HeaderValue::from_static("for=203.0.113.1"));
    let a = get(
        edge,
        "/echo",
        &[
            ("forwarded", "for=203.0.113.1"),
            ("x-real-ip", "203.0.113.2"),
        ],
    )
    .await;
    let headers = a.json()["headers"].clone();
    let names: Vec<&str> = headers
        .as_array()
        .unwrap()
        .iter()
        .map(|h| h[0].as_str().unwrap())
        .collect();
    assert!(names.contains(&"forwarded") && names.contains(&"x-real-ip"));
}
