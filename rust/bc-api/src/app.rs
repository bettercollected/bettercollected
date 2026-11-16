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
        if group.needs_policy_switches {
            let unknown = state.cfg.unknown_policy_switches();
            if !unknown.is_empty() {
                // fail closed: the switch may be on in the store this service could
                // not read or trust, and the answer would then be wrong. Class R: the
                // decision is taken at start, as the switch's own value is
                tracing::warn!(
                    "route group {} stays on the Python backend: {} {} not known here ({}); set {} in the environment of this service, or give it access to the settings store",
                    group.name,
                    unknown
                        .iter()
                        .map(|(n, _)| *n)
                        .collect::<Vec<_>>()
                        .join(" and "),
                    if unknown.len() == 1 { "is" } else { "are" },
                    unknown.first().map_or("", |(_, why)| why.as_str()),
                    if unknown.len() == 1 { "it" } else { "them" },
                );
                continue;
            }
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
