#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::needless_pass_by_value,
    clippy::cast_possible_truncation
)]
//! The body-nesting rule on a route Rust serves: `served` puts the guard in
//! front of every handler. The test route is a stand-in POST/PUT route that
//! answers 200 with the size of the body it was given (so a replayed body can be
//! checked byte for byte), next to the real Python-side rules: 422
//! `body_too_deep` at 129 levels and not at 128, whatever the content type
//! declares among the JSON-like ones, chunked or sized, a body past 1 MiB, and
//! the answer of a route that has already answered.

mod support;

use std::sync::Arc;

use axum::Router;
use axum::body::{Body, Bytes};
use axum::extract::Request;
use axum::http::{Method, StatusCode, header};
use axum::response::IntoResponse;
use bc_api::groups::{Shared, served};
use bc_http::json_depth::{MAX_BUFFERED_BYTES, message};
use futures_util::stream;
use http_body_util::BodyExt;
use support::{Answer, call, serve, state};

fn arrays(n: usize) -> String {
    format!("{}{}", "[".repeat(n), "]".repeat(n))
}

/// Reads the whole body and says how long it was and a cheap checksum.
async fn echo(request: Request) -> axum::response::Response {
    match request.into_body().collect().await {
        Ok(collected) => {
            let bytes = collected.to_bytes();
            let sum: u64 = bytes.iter().map(|&b| u64::from(b)).sum();
            format!("{} {sum}", bytes.len()).into_response()
        }
        Err(_) => (StatusCode::BAD_REQUEST, "the body went away").into_response(),
    }
}

/// Answers before it reads anything, as a route with its own size cap does.
async fn too_big() -> axum::response::Response {
    (StatusCode::PAYLOAD_TOO_LARGE, "its own 413").into_response()
}

async fn edge() -> std::net::SocketAddr {
    let state: Shared = Arc::new(state(
        "http://127.0.0.1:1",
        &[("BC_SERVED_BY_HEADER", "true")],
    ));
    let router: Router = Router::new()
        .route(
            "/echo",
            served(&[Method::POST, Method::PUT, Method::GET], echo, &state),
        )
        .route("/mcp/echo", served(&[Method::POST], echo, &state))
        .route("/capped", served(&[Method::POST], too_big, &state))
        .with_state(state);
    serve(router).await
}

async fn post(addr: std::net::SocketAddr, path: &str, ct: Option<&str>, body: String) -> Answer {
    let mut headers = vec![];
    if let Some(ct) = ct {
        headers.push(("content-type", ct));
    }
    call(addr, Method::POST, path, &headers, Body::from(body)).await
}

fn refused(answer: &Answer) {
    assert_eq!(
        answer.status,
        StatusCode::UNPROCESSABLE_ENTITY,
        "{}",
        answer.text()
    );
    assert_eq!(answer.headers[header::CONTENT_TYPE], "application/json");
    let json = answer.json();
    assert_eq!(json["code"], "body_too_deep");
    assert_eq!(json["message"], message());
    assert!(json.get("error").is_none());
    assert_eq!(json.as_object().unwrap().len(), 2);
    assert_eq!(answer.headers["x-bc-served-by"], "rust");
}

#[tokio::test]
async fn a_body_at_the_limit_is_read_and_one_level_more_is_refused() {
    let addr = edge().await;
    for ct in [
        Some("application/json"),
        Some("text/plain"),
        Some("application/scim+json"),
        None,
    ] {
        let at = arrays(128);
        let answer = post(addr, "/echo", ct, at.clone()).await;
        assert_eq!(answer.status, StatusCode::OK, "{ct:?}");
        assert_eq!(
            answer.text().split(' ').next().unwrap(),
            at.len().to_string()
        );
        refused(&post(addr, "/echo", ct, arrays(129)).await);
    }
    let objects = |n: usize| format!("{}1{}", "{\"a\":".repeat(n), "}".repeat(n));
    assert_eq!(
        post(addr, "/echo", Some("application/json"), objects(128))
            .await
            .status,
        StatusCode::OK
    );
    refused(&post(addr, "/echo", Some("application/json"), objects(129)).await);
}

#[tokio::test]
async fn the_body_reaches_the_route_unchanged() {
    let addr = edge().await;
    let body = format!("{{\"a\":[1,2,\"]]]\",{{\"b\":null}}]}}{}", " ".repeat(3000));
    let sum: u64 = body.bytes().map(u64::from).sum();
    let answer = post(addr, "/echo", Some("application/json"), body.clone()).await;
    assert_eq!(answer.text(), format!("{} {sum}", body.len()));
}

#[tokio::test]
async fn only_json_like_bodies_of_body_methods_are_scanned() {
    let addr = edge().await;
    let deep = arrays(500);
    for ct in [
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=x",
        "image/png",
    ] {
        let answer = post(addr, "/echo", Some(ct), deep.clone()).await;
        assert_eq!(answer.status, StatusCode::OK, "{ct}");
    }
    // a GET is not a body method
    let answer = call(
        addr,
        Method::GET,
        "/echo",
        &[("content-type", "application/json")],
        Body::from(deep.clone()),
    )
    .await;
    assert_eq!(answer.status, StatusCode::OK);
    let put = call(
        addr,
        Method::PUT,
        "/echo",
        &[("content-type", "application/json")],
        Body::from(deep),
    )
    .await;
    refused(&put);
}

#[tokio::test]
async fn it_refuses_before_the_route_whatever_the_route_would_answer() {
    let addr = edge().await;
    refused(&post(addr, "/capped", Some("application/json"), arrays(129)).await);
    // under the limit the route's own answer stands
    let answer = post(addr, "/capped", Some("application/json"), arrays(5)).await;
    assert_eq!(answer.status, StatusCode::PAYLOAD_TOO_LARGE);
}

#[tokio::test]
async fn the_mcp_endpoint_carries_its_own_error_field_too() {
    let addr = edge().await;
    let answer = post(addr, "/mcp/echo", Some("application/json"), arrays(129)).await;
    assert_eq!(answer.status, StatusCode::UNPROCESSABLE_ENTITY);
    let json = answer.json();
    assert_eq!(json["code"], "body_too_deep");
    assert_eq!(json["error"], json["message"]);
}

#[tokio::test]
async fn a_chunked_body_is_scanned_too() {
    let addr = edge().await;
    let chunked = |text: String| {
        let pieces: Vec<Result<Bytes, std::io::Error>> = text
            .as_bytes()
            .chunks(7)
            .map(|c| Ok(Bytes::copy_from_slice(c)))
            .collect();
        Body::from_stream(stream::iter(pieces))
    };
    let ok = call(
        addr,
        Method::POST,
        "/echo",
        &[("content-type", "application/json")],
        chunked(arrays(128)),
    )
    .await;
    assert_eq!(ok.status, StatusCode::OK);
    let deep = call(
        addr,
        Method::POST,
        "/echo",
        &[("content-type", "application/json")],
        chunked(arrays(129)),
    )
    .await;
    refused(&deep);
}

#[tokio::test]
async fn nesting_hidden_behind_more_than_a_mebibyte_of_padding_is_still_found() {
    let addr = edge().await;
    let pad = " ".repeat(MAX_BUFFERED_BYTES + 100);
    // padding in front, the deep part past the cap; sized
    let body = format!("{pad}{}", arrays(129));
    refused(&post(addr, "/echo", Some("application/json"), body).await);
    // the same at the limit is read to the end
    let body = format!("{pad}{}", arrays(128));
    let n = body.len();
    let answer = post(addr, "/echo", Some("application/json"), body).await;
    assert_eq!(answer.status, StatusCode::OK);
    assert_eq!(answer.text().split(' ').next().unwrap(), n.to_string());
    // a string that holds the brackets is not nesting
    let body = format!("[\"{}\"]", "[".repeat(MAX_BUFFERED_BYTES + 100));
    assert_eq!(
        post(addr, "/echo", Some("application/json"), body)
            .await
            .status,
        StatusCode::OK
    );
    // padding inside, the deep part before it
    let body = format!("{}{pad}", arrays(129));
    refused(&post(addr, "/echo", Some("application/json"), body).await);
}

#[tokio::test]
async fn a_chunked_body_that_grows_past_the_cap_is_scanned_to_the_end() {
    let addr = edge().await;
    let pad = vec![b' '; 64 * 1024];
    let make = |tail: String| {
        let mut pieces: Vec<Result<Bytes, std::io::Error>> =
            (0..20).map(|_| Ok(Bytes::from(pad.clone()))).collect();
        for piece in tail.as_bytes().chunks(5) {
            pieces.push(Ok(Bytes::copy_from_slice(piece)));
        }
        Body::from_stream(stream::iter(pieces))
    };
    let heads = [("content-type", "application/json")];
    refused(&call(addr, Method::POST, "/echo", &heads, make(arrays(129))).await);
    let ok = call(addr, Method::POST, "/echo", &heads, make(arrays(128))).await;
    assert_eq!(ok.status, StatusCode::OK);
    assert_eq!(
        ok.text().split(' ').next().unwrap(),
        (20 * 64 * 1024 + 256).to_string()
    );
}

#[tokio::test]
async fn a_route_that_answers_without_reading_keeps_its_answer_on_a_huge_body() {
    let addr = edge().await;
    // past the cap and the route never reads: nothing deep was seen, its 413 stands
    let body = " ".repeat(MAX_BUFFERED_BYTES + 100);
    let answer = post(addr, "/capped", Some("application/json"), body).await;
    assert_eq!(answer.status, StatusCode::PAYLOAD_TOO_LARGE);
}
