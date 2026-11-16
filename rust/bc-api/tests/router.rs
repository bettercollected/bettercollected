//! Request-level tests that need no database: authentication, the id check,
//! the error shapes, CORS and the health route. (The database-backed cases
//! are the contract test's: rust/contract/.)

use std::sync::Arc;

use axum::body::Body;
use axum::http::{header, Request, StatusCode};
use bc_api::config::Config;
use bc_api::cors::Origins;
use bc_api::routes::{router, AppState};
use http_body_util::BodyExt;
use jsonwebtoken::{encode, EncodingKey, Header};
use sqlx::postgres::PgPoolOptions;
use tower::ServiceExt;

const SECRET: &str = "0123456789abcdef0123456789abcdef0123";

fn app() -> axum::Router {
    let cfg = Config::from_map(
        &[
            ("DATABASE_URL", "postgres://nobody@127.0.0.1:1/none"),
            ("AUTH_JWT_SECRET", SECRET),
        ]
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect(),
    )
    .unwrap();
    // never connects: every request in this file is answered before a query
    let pool = PgPoolOptions::new()
        .connect_lazy("postgres://nobody@127.0.0.1:1/none")
        .unwrap();
    let origins = Origins::default();
    origins.store(vec!["https://app.example.test".to_string()]);
    router(Arc::new(AppState { cfg, pool, origins }))
}

async fn send(req: Request<Body>) -> (StatusCode, axum::http::HeaderMap, String) {
    let response = app().oneshot(req).await.unwrap();
    let (parts, body) = response.into_parts();
    let bytes = body.collect().await.unwrap().to_bytes();
    (
        parts.status,
        parts.headers,
        String::from_utf8_lossy(&bytes).to_string(),
    )
}

fn token(claims: serde_json::Value) -> String {
    encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(SECRET.as_bytes()),
    )
    .unwrap()
}

fn live(extra: serde_json::Value) -> String {
    let mut c = serde_json::json!({"id":"6a0000000000000000000001","sub":"a@example.test",
        "typ":"access","sid":"s","exp": 4_102_444_800u64});
    for (k, v) in extra.as_object().unwrap() {
        c[k] = v.clone();
    }
    token(c)
}

const PATH: &str = "/api/v1/workspaces/6a0000000000000000000009/permissions";

#[tokio::test]
async fn health_is_ok() {
    let (status, _, body) = send(Request::get("/health").body(Body::empty()).unwrap()).await;
    assert_eq!(
        (status, body.as_str()),
        (StatusCode::OK, r#"{"status":"ok"}"#)
    );
}

#[tokio::test]
async fn no_cookie_is_401_with_the_backends_body() {
    let (status, headers, body) = send(Request::get(PATH).body(Body::empty()).unwrap()).await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);
    assert_eq!(body, r#""No user logged in.""#);
    assert_eq!(headers[header::CONTENT_TYPE], "application/json");
}

#[tokio::test]
async fn bad_id_is_422_only_after_authentication() {
    let bad = "/api/v1/workspaces/nope/permissions";
    let (status, _, _) = send(Request::get(bad).body(Body::empty()).unwrap()).await;
    assert_eq!(status, StatusCode::UNAUTHORIZED, "401 comes before the 422");
    let req = Request::get(bad)
        .header(
            header::COOKIE,
            format!("Authorization={}", live(serde_json::json!({}))),
        )
        .body(Body::empty())
        .unwrap();
    let (status, _, body) = send(req).await;
    assert_eq!(status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(body.contains("Id must be of type PydanticObjectId"));
}

#[tokio::test]
async fn expired_token_without_refresh_cookie_is_401() {
    let expired = live(serde_json::json!({"exp": 1}));
    let req = Request::get(PATH)
        .header(header::COOKIE, format!("Authorization={expired}"))
        .body(Body::empty())
        .unwrap();
    let (status, _, body) = send(req).await;
    assert_eq!(
        (status, body.as_str()),
        (StatusCode::UNAUTHORIZED, r#""No user logged in.""#)
    );
}

#[tokio::test]
async fn expired_token_with_refresh_cookie_is_left_to_python() {
    let expired = live(serde_json::json!({"exp": 1}));
    let req = Request::get(PATH)
        .header(
            header::COOKIE,
            format!("Authorization={expired}; RefreshToken=r"),
        )
        .body(Body::empty())
        .unwrap();
    let (status, _, _) = send(req).await;
    assert_eq!(status, StatusCode::NOT_IMPLEMENTED);
}

#[tokio::test]
async fn respondent_session_elsewhere_is_401_sign_in_to_this_workspace() {
    let t = live(
        serde_json::json!({"session_scope":"respondent","scope_workspace_id":"6a00000000000000000000aa"}),
    );
    let req = Request::get(PATH)
        .header(header::COOKIE, format!("Authorization={t}"))
        .body(Body::empty())
        .unwrap();
    let (status, _, body) = send(req).await;
    assert_eq!(
        (status, body.as_str()),
        (StatusCode::UNAUTHORIZED, r#""Sign in to this workspace.""#)
    );
}

#[tokio::test]
async fn unknown_path_404_and_wrong_method_405() {
    let (status, _, body) = send(Request::get("/nope").body(Body::empty()).unwrap()).await;
    assert_eq!(
        (status, body.as_str()),
        (StatusCode::NOT_FOUND, r#"{"detail":"Not Found"}"#)
    );
    let (status, headers, body) = send(Request::post(PATH).body(Body::empty()).unwrap()).await;
    assert_eq!(status, StatusCode::METHOD_NOT_ALLOWED);
    assert_eq!(headers[header::ALLOW], "GET");
    assert_eq!(body, r#"{"detail":"Method Not Allowed"}"#);
}

#[tokio::test]
async fn trailing_slash_redirects_like_starlette() {
    let req = Request::get(format!("{PATH}/?x=1"))
        .header(header::HOST, "h:1")
        .body(Body::empty())
        .unwrap();
    let (status, headers, _) = send(req).await;
    assert_eq!(status, StatusCode::TEMPORARY_REDIRECT);
    assert_eq!(headers[header::LOCATION], format!("http://h:1{PATH}?x=1"));
}

#[tokio::test]
async fn cors_headers_follow_the_allowed_origins() {
    let req = Request::get(PATH)
        .header(header::ORIGIN, "https://app.example.test")
        .body(Body::empty())
        .unwrap();
    let (_, headers, _) = send(req).await;
    assert_eq!(
        headers["access-control-allow-origin"],
        "https://app.example.test"
    );
    assert_eq!(headers["access-control-allow-credentials"], "true");
    assert_eq!(headers[header::VARY], "Origin");
    let req = Request::get(PATH)
        .header(header::ORIGIN, "https://evil.example.test")
        .body(Body::empty())
        .unwrap();
    let (_, headers, _) = send(req).await;
    assert!(headers.get("access-control-allow-origin").is_none());
    let req = Request::options(PATH)
        .header(header::ORIGIN, "https://evil.example.test")
        .header("access-control-request-method", "GET")
        .body(Body::empty())
        .unwrap();
    let (status, _, body) = send(req).await;
    assert_eq!(
        (status, body.as_str()),
        (StatusCode::BAD_REQUEST, "Disallowed CORS origin")
    );
}
