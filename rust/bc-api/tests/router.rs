#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::needless_pass_by_value,
    clippy::format_collect
)]
//! Request-level tests of the permissions group that need no database:
//! authentication, the id check, the error shapes, CORS, the per-group switch
//! and what is handed to Python. (The database-backed cases are the contract
//! harness's: rust/contract/.)

mod support;

use std::net::SocketAddr;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use axum::Router;
use axum::http::{Method, StatusCode, header};
use axum::response::IntoResponse;
use axum::routing::any;
use jsonwebtoken::{EncodingKey, Header, encode};
use support::{SECRET, call, edge, get, serve};

const PATH: &str = "/api/v1/workspaces/6a0000000000000000000009/permissions";

/// An upstream that answers 299 "from python" and counts what it saw.
async fn python() -> (SocketAddr, Arc<AtomicUsize>) {
    let seen = Arc::new(AtomicUsize::new(0));
    let counter = seen.clone();
    let router = Router::new().fallback(any(move || {
        let counter = counter.clone();
        async move {
            counter.fetch_add(1, Ordering::SeqCst);
            (StatusCode::from_u16(299).unwrap(), "from python").into_response()
        }
    }));
    (serve(router).await, seen)
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

fn cookie(t: &str) -> String {
    format!("Authorization={t}")
}

const ON: &[(&str, &str)] = &[
    ("BC_RUST_ROUTES", "permissions"),
    ("BC_SERVED_BY_HEADER", "true"),
];

#[tokio::test]
async fn with_the_group_off_everything_goes_to_python() {
    let (upstream, seen) = python().await;
    let edge = edge(upstream, &[("BC_SERVED_BY_HEADER", "true")]).await;
    let a = get(edge, PATH, &[]).await;
    assert_eq!((a.status.as_u16(), a.text().as_str()), (299, "from python"));
    assert_eq!(a.headers["x-bc-served-by"], "python");
    assert_eq!(seen.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn with_the_group_on_rust_answers_and_python_is_not_asked() {
    let (upstream, seen) = python().await;
    let edge = edge(upstream, ON).await;
    let a = get(edge, PATH, &[]).await;
    assert_eq!(a.status, StatusCode::UNAUTHORIZED);
    assert_eq!(a.text(), r#""No user logged in.""#);
    assert_eq!(a.headers[header::CONTENT_TYPE], "application/json");
    assert_eq!(a.headers["x-bc-served-by"], "rust");
    assert_eq!(seen.load(Ordering::SeqCst), 0);
}

#[tokio::test]
async fn without_both_policy_switches_in_the_environment_the_group_stays_on_python() {
    // the settings store (not read here) may hold them: fail closed
    for extra in [
        vec![("SSO_ENABLED", ""), ("TOTP_ENABLED", "")],
        vec![("SSO_ENABLED", "false"), ("TOTP_ENABLED", "")],
        vec![("SSO_ENABLED", ""), ("TOTP_ENABLED", "true")],
    ] {
        let (upstream, seen) = python().await;
        let mut all = vec![
            ("BC_RUST_ROUTES", "permissions"),
            ("BC_SERVED_BY_HEADER", "true"),
        ];
        all.extend(extra.clone());
        let edge = edge(upstream, &all).await;
        let a = get(edge, PATH, &[]).await;
        assert_eq!(a.status.as_u16(), 299, "{extra:?}");
        assert_eq!(a.headers["x-bc-served-by"], "python", "{extra:?}");
        assert_eq!(seen.load(Ordering::SeqCst), 1);
    }
}

#[tokio::test]
async fn with_both_policy_switches_explicit_in_any_accepted_spelling_rust_serves() {
    for (sso, totp) in [
        ("false", "false"),
        ("off", "yes"),
        ("1", "0"),
        ("TRUE", "n"),
    ] {
        let (upstream, seen) = python().await;
        let edge = edge(
            upstream,
            &[
                ("BC_RUST_ROUTES", "permissions"),
                ("SSO_ENABLED", sso),
                ("TOTP_ENABLED", totp),
            ],
        )
        .await;
        let a = get(edge, PATH, &[]).await;
        assert_eq!(a.status, StatusCode::UNAUTHORIZED, "{sso} {totp}");
        assert_eq!(seen.load(Ordering::SeqCst), 0);
    }
}

#[tokio::test]
async fn the_marker_header_is_off_unless_asked_for() {
    let (upstream, _) = python().await;
    let edge = edge(upstream, &[("BC_RUST_ROUTES", "permissions")]).await;
    let a = get(edge, PATH, &[]).await;
    assert!(a.headers.get("x-bc-served-by").is_none());
}

#[tokio::test]
async fn other_methods_and_paths_of_a_served_route_are_pythons() {
    let (upstream, seen) = python().await;
    let edge = edge(upstream, ON).await;
    for (method, path) in [
        (Method::POST, PATH.to_string()),
        (Method::HEAD, PATH.to_string()),
        (Method::OPTIONS, PATH.to_string()),
        (Method::GET, format!("{PATH}/")),
        (
            Method::GET,
            "/api/v1/workspaces//6a0000000000000000000009/permissions".to_string(),
        ),
        (
            Method::GET,
            "/api/v1/workspaces/a%2Fb/permissions".to_string(),
        ),
        (
            Method::GET,
            "/api/v1/workspaces/6a0000000000000000000009/permissionz".to_string(),
        ),
        (Method::GET, "/nope".to_string()),
    ] {
        let a = call(edge, method.clone(), &path, &[], axum::body::Body::empty()).await;
        assert_eq!(a.status.as_u16(), 299, "{method} {path}");
    }
    assert_eq!(seen.load(Ordering::SeqCst), 8);
}

#[tokio::test]
async fn a_bad_id_is_422_only_after_authentication() {
    let (upstream, _) = python().await;
    let edge = edge(upstream, ON).await;
    let bad = "/api/v1/workspaces/nope/permissions";
    let a = get(edge, bad, &[]).await;
    assert_eq!(
        a.status,
        StatusCode::UNAUTHORIZED,
        "401 comes before the 422"
    );
    let c = cookie(&live(serde_json::json!({})));
    let a = get(edge, bad, &[("cookie", &c)]).await;
    assert_eq!(a.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert_eq!(
        a.json(),
        serde_json::json!({"detail":[{"loc":["path","workspace_id"],
            "msg":"Value error, Id must be of type PydanticObjectId","type":"value_error"}]})
    );
}

#[tokio::test]
async fn an_expired_token_without_a_refresh_cookie_is_401_and_with_one_is_pythons() {
    let (upstream, seen) = python().await;
    let edge = edge(upstream, ON).await;
    let expired = live(serde_json::json!({"exp": 1}));
    let a = get(edge, PATH, &[("cookie", &cookie(&expired))]).await;
    assert_eq!(
        (a.status, a.text().as_str()),
        (StatusCode::UNAUTHORIZED, r#""No user logged in.""#)
    );
    let with_refresh = format!("Authorization={expired}; RefreshToken=r");
    let a = get(edge, PATH, &[("cookie", &with_refresh)]).await;
    assert_eq!(a.status.as_u16(), 299, "the session refresh is Python's");
    assert_eq!(seen.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn a_respondent_session_elsewhere_is_401_sign_in_to_this_workspace() {
    let (upstream, _) = python().await;
    let edge = edge(upstream, ON).await;
    let t = live(
        serde_json::json!({"session_scope":"respondent","scope_workspace_id":"6a00000000000000000000aa"}),
    );
    let a = get(edge, PATH, &[("cookie", &cookie(&t))]).await;
    assert_eq!(
        (a.status, a.text().as_str()),
        (StatusCode::UNAUTHORIZED, r#""Sign in to this workspace.""#)
    );
}

#[tokio::test]
async fn with_sso_on_a_respondent_session_elsewhere_is_pythons_to_decide() {
    let (upstream, _) = python().await;
    let edge = edge(
        upstream,
        &[("BC_RUST_ROUTES", "permissions"), ("SSO_ENABLED", "true")],
    )
    .await;
    let t = live(
        serde_json::json!({"session_scope":"respondent","scope_workspace_id":"6a00000000000000000000aa"}),
    );
    let a = get(edge, PATH, &[("cookie", &cookie(&t))]).await;
    assert_eq!(a.status.as_u16(), 299);
}

#[tokio::test]
async fn a_respondent_session_on_its_own_workspace_holds_no_permissions() {
    let (upstream, _) = python().await;
    let edge = edge(upstream, ON).await;
    let t = live(
        serde_json::json!({"session_scope":"respondent","scope_workspace_id":"6a0000000000000000000009"}),
    );
    let a = get(edge, PATH, &[("cookie", &cookie(&t))]).await;
    assert_eq!(a.status, StatusCode::OK);
    assert_eq!(a.json()["permissions"], serde_json::json!([]));
    assert_eq!(a.json()["captchaEnabled"], false);
}

#[tokio::test]
async fn the_switches_are_reported_under_their_python_names() {
    let (upstream, _) = python().await;
    let edge = edge(
        upstream,
        &[
            ("BC_RUST_ROUTES", "permissions"),
            ("CAPTCHA_ENABLED", "true"),
            ("ADDRESS_QUESTION_ENABLED", "true"),
            ("DAYBREAK_PRESET_ENABLED", "true"),
        ],
    )
    .await;
    // a respondent session on its own workspace is answered without a query
    let t = live(
        serde_json::json!({"session_scope":"respondent","scope_workspace_id":"6a0000000000000000000009"}),
    );
    let a = get(edge, PATH, &[("cookie", &cookie(&t))]).await;
    let j = a.json();
    assert_eq!(j["captchaEnabled"], true);
    assert_eq!(j["addressQuestionEnabled"], true);
    assert_eq!(j["addressLookupEnabled"], false, "both switches are needed");
    assert_eq!(j["offeredGatedPresets"], serde_json::json!(["Daybreak"]));
}

#[tokio::test]
async fn cors_headers_follow_the_allowed_origins_on_what_rust_answers() {
    let (upstream, _) = python().await;
    let edge = edge(upstream, ON).await;
    let a = get(edge, PATH, &[("origin", "https://app.example.test")]).await;
    assert_eq!(
        a.headers["access-control-allow-origin"],
        "https://app.example.test"
    );
    assert_eq!(a.headers["access-control-allow-credentials"], "true");
    assert_eq!(a.headers[header::VARY], "Origin");
    let a = get(edge, PATH, &[("origin", "https://evil.example.test")]).await;
    assert!(a.headers.get("access-control-allow-origin").is_none());
    assert_eq!(a.headers["access-control-allow-credentials"], "true");
}

#[tokio::test]
async fn a_forwarded_answer_gets_no_second_set_of_cors_headers() {
    // the upstream's own CORS headers are the only ones
    let router = Router::new().fallback(any(|| async {
        (
            [
                ("access-control-allow-origin", "https://python.example.test"),
                ("vary", "Origin"),
            ],
            "python",
        )
            .into_response()
    }));
    let upstream = serve(router).await;
    let edge = edge(upstream, ON).await;
    let a = call(
        edge,
        Method::OPTIONS,
        PATH,
        &[
            ("origin", "https://app.example.test"),
            ("access-control-request-method", "GET"),
        ],
        axum::body::Body::empty(),
    )
    .await;
    assert_eq!(
        a.headers
            .get_all("access-control-allow-origin")
            .iter()
            .count(),
        1
    );
    assert_eq!(
        a.headers["access-control-allow-origin"],
        "https://python.example.test"
    );
    assert_eq!(a.headers.get_all(header::VARY).iter().count(), 1);
    assert!(a.headers.get("access-control-allow-credentials").is_none());
    // nothing of axum's own routing shows through (it would add `Allow`)
    assert!(a.headers.get(header::ALLOW).is_none());
}

#[tokio::test]
async fn a_group_that_does_not_exist_is_reported_by_name() {
    let unknown = bc_api::app::unknown_groups(&["permissions".into(), "permisions".into()]);
    assert_eq!(unknown, vec!["permisions".to_string()]);
}
