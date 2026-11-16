//! Shared helpers of the request-level tests: a configuration, a fake Python
//! upstream, an edge served on a real socket and a small HTTP client.

#![allow(dead_code)]

use std::collections::HashMap;
use std::net::SocketAddr;

use axum::Router;
use axum::body::Body;
use axum::http::{HeaderMap, Method, Request, StatusCode};
use bc_api::app;
use bc_api::state::AppState;
use bc_config::{Config, Settings};
use http_body_util::BodyExt;
use hyper_util::client::legacy::Client;
use hyper_util::rt::TokioExecutor;
use sqlx::postgres::PgPoolOptions;

pub const SECRET: &str = "0123456789abcdef0123456789abcdef0123";

pub fn settings(upstream: &str, extra: &[(&str, &str)]) -> Settings {
    let mut vars: HashMap<String, String> = [
        ("DATABASE_URL", "postgres://nobody@127.0.0.1:1/none"),
        ("AUTH_JWT_SECRET", SECRET),
        ("BC_PYTHON_UPSTREAM", upstream),
    ]
    .iter()
    .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
    .collect();
    for (k, v) in extra {
        vars.insert((*k).to_string(), (*v).to_string());
    }
    Settings::from_map(vars)
}

pub fn config(upstream: &str, extra: &[(&str, &str)]) -> Config {
    Config::from_settings(&settings(upstream, extra)).unwrap()
}

/// A state whose pool never connects: every request of the DB-free tests is
/// answered before a query.
pub fn state(upstream: &str, extra: &[(&str, &str)]) -> AppState {
    let cfg = config(upstream, extra);
    let pool = PgPoolOptions::new()
        .connect_lazy("postgres://nobody@127.0.0.1:1/none")
        .unwrap();
    let state = AppState::new(cfg, pool);
    state
        .origins
        .store(vec!["https://app.example.test".to_string()]);
    state
}

/// Serves `router` on a free local port; returns its address.
pub async fn serve(router: Router) -> SocketAddr {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        let _ = axum::serve(
            listener,
            router.into_make_service_with_connect_info::<SocketAddr>(),
        )
        .await;
    });
    addr
}

/// The edge in front of `upstream`, on a real socket.
pub async fn edge(upstream: SocketAddr, extra: &[(&str, &str)]) -> SocketAddr {
    let upstream = format!("http://{upstream}");
    serve(app::router(state(&upstream, extra))).await
}

pub type TestClient = Client<hyper_util::client::legacy::connect::HttpConnector, Body>;

pub fn client() -> TestClient {
    Client::builder(TokioExecutor::new()).build_http()
}

pub struct Answer {
    pub status: StatusCode,
    pub headers: HeaderMap,
    pub body: Vec<u8>,
}

impl Answer {
    pub fn text(&self) -> String {
        String::from_utf8_lossy(&self.body).into_owned()
    }

    pub fn json(&self) -> serde_json::Value {
        serde_json::from_slice(&self.body).unwrap()
    }
}

pub async fn call(
    addr: SocketAddr,
    method: Method,
    path: &str,
    headers: &[(&str, &str)],
    body: Body,
) -> Answer {
    let mut request = Request::builder()
        .method(method)
        .uri(format!("http://{addr}{path}"));
    for (k, v) in headers {
        request = request.header(*k, *v);
    }
    let response = client().request(request.body(body).unwrap()).await.unwrap();
    let (parts, body) = response.into_parts();
    let bytes = body.collect().await.unwrap().to_bytes();
    Answer {
        status: parts.status,
        headers: parts.headers,
        body: bytes.to_vec(),
    }
}

pub async fn get(addr: SocketAddr, path: &str, headers: &[(&str, &str)]) -> Answer {
    call(addr, Method::GET, path, headers, Body::empty()).await
}
