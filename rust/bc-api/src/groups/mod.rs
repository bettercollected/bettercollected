//! Route groups.
//!
//! A group is a set of routes that move from Python to Rust together and can
//! move back with one setting: `BC_RUST_ROUTES=permissions,...` lists the
//! groups the Rust side serves, and nothing else is. A group lives in its own
//! module and adds itself to [`ALL`] with one line.
//!
//! Writing a group:
//!
//! * mount each route with [`served`], not with axum's own method routing: it
//!   answers only the methods you name, forwards every other method of the
//!   same path to Python (a `HEAD` or `OPTIONS` Python answers differently, or
//!   a `405` with its own body), and puts the Rust-side response headers
//!   (CORS, no-store for response data, the debug marker) on what you return;
//! * read the path from the request and decide what is yours: whatever you are
//!   not sure of, return `state.proxy.forward(request).await`; the answer is
//!   then exactly Python's;
//! * add cases to `rust/contract/cases/<group>.json`: the contract harness
//!   sends them to both servers and fails on any difference.

use std::sync::Arc;

use axum::Router;
use axum::extract::{Request, State};
use axum::http::{HeaderName, HeaderValue, header};
use axum::middleware::{self, Next};
use axum::response::Response;
use axum::routing::{MethodFilter, MethodRouter, on};
use bc_http::{cors, privacy};

use crate::proxy::FromUpstream;
use crate::state::AppState;

pub mod permissions;

pub type Shared = Arc<AppState>;

/// One switchable group of routes.
#[derive(Debug, Clone, Copy)]
pub struct Group {
    /// The name used in `BC_RUST_ROUTES` (lower case).
    pub name: &'static str,
    /// Adds the group's routes to the router.
    pub mount: fn(Router<Shared>, &Shared) -> Router<Shared>,
}

/// Every group that exists. Only the ones named in `BC_RUST_ROUTES` are mounted.
pub const ALL: &[Group] = &[Group {
    name: "permissions",
    mount: permissions::mount,
}];

/// The names of the groups that exist, for messages.
pub fn names() -> Vec<&'static str> {
    ALL.iter().map(|g| g.name).collect()
}

/// A route the Rust side serves for `filter`'s methods; every other method of
/// the path is forwarded to Python.
pub fn served<H, T>(filter: MethodFilter, handler: H, state: &Shared) -> MethodRouter<Shared>
where
    H: axum::handler::Handler<T, Shared>,
    T: 'static,
{
    on(filter, handler)
        .layer(middleware::from_fn_with_state(state.clone(), rust_response))
        .fallback(forward)
        // axum answers a HEAD with the GET handler unless told otherwise;
        // Python does not, so a HEAD is always Python's (do not pass HEAD in
        // `filter`)
        .head(forward)
}

/// Forwards the request to the Python backend (the router's fallback too).
pub async fn forward(State(state): State<Shared>, request: Request) -> Response {
    state.proxy.forward(request).await
}

/// The headers of a response the Rust side produced. A response that came
/// from Python already has its own (CORS, no-store) and is left alone.
async fn rust_response(State(state): State<Shared>, request: Request, next: Next) -> Response {
    let origin = request
        .headers()
        .get(header::ORIGIN)
        .and_then(|v| v.to_str().ok())
        .map(str::to_string);
    let path = request.uri().path().to_string();
    let mut response = next.run(request).await;
    if response.extensions().get::<FromUpstream>().is_some() {
        return response;
    }
    if let Some(origin) = origin {
        let allowed = state.allowed_origins().await;
        cors::simple(&mut response, &origin, &allowed);
    }
    privacy::apply_no_store(&mut response, &path);
    if state.cfg.edge.served_by_header {
        response.headers_mut().insert(
            HeaderName::from_static("x-bc-served-by"),
            HeaderValue::from_static("rust"),
        );
    }
    response
}
