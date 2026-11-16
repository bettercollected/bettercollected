//! The router: `GET /health`, the route groups that are switched on, and the
//! pass-through for everything else.

use std::sync::Arc;

use axum::Router;
use axum::extract::{Request, State};
use axum::http::Method;
use axum::http::StatusCode;
use axum::http::{HeaderName, HeaderValue};
use axum::response::Response;
use axum::routing::any;
use bc_http::error::json_response;
use serde_json::json;

use crate::groups::{self, Shared};
use crate::state::AppState;

/// A `BC_RUST_ROUTES` that names a group that does not exist.
pub fn unknown_groups(requested: &[String]) -> Vec<String> {
    requested
        .iter()
        .filter(|name| !groups::ALL.iter().any(|g| g.name == name.as_str()))
        .cloned()
        .collect()
}

pub fn router(state: AppState) -> Router {
    let state: Shared = Arc::new(state);
    let mut router: Router<Shared> = Router::new().route(
        "/health",
        // the edge's own liveness; it does not ask the upstream. Other methods
        // of the path are the upstream's.
        any(|state: State<Shared>, request: Request| async move {
            if request.method() == Method::GET {
                health()
            } else {
                groups::forward(state, request).await
            }
        }),
    );
    for group in groups::ALL {
        if !state
            .cfg
            .edge
            .rust_routes
            .iter()
            .any(|name| name == group.name)
        {
            continue;
        }
        router = (group.mount)(router, &state);
    }
    router.fallback(groups::forward).with_state(state)
}

fn health() -> Response {
    let mut response = json_response(StatusCode::OK, &json!({"status": "ok"}));
    response.headers_mut().insert(
        HeaderName::from_static("cache-control"),
        HeaderValue::from_static("no-store"),
    );
    response
}
