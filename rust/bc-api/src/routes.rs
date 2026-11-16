//! The HTTP surface of the spike: `GET /health` (spike only) and
//! `GET /api/v1/workspaces/{workspace_id}/permissions`, the Python backend's
//! `get_workspace_permissions` (backend/app/controllers/workspace_router.py).

use std::sync::Arc;

use axum::body::Body;
use axum::extract::{Path, Request, State};
use axum::http::{header, HeaderMap, HeaderValue, Method, StatusCode};
use axum::middleware::{self, Next};
use axum::response::Response;
use axum::routing::any;
use axum::Router;
use serde::Serialize;
use sqlx::PgPool;

use crate::auth::{self, User, ACCESS_COOKIE, REFRESH_COOKIE};
use crate::authz::{self, Perms};
use crate::config::Config;
use crate::cors::{self, Origins};
use crate::db;

pub struct AppState {
    pub cfg: Config,
    pub pool: PgPool,
    pub origins: Origins,
}

impl AppState {
    async fn allowed_origins(&self) -> Vec<String> {
        if let Some(list) = self.origins.fresh() {
            return list;
        }
        match db::list_origins(&self.pool).await {
            Ok(list) => {
                self.origins.store(list.clone());
                list
            }
            Err(error) => {
                tracing::error!("allowed origins not read: {}", error);
                self.origins.stale()
            }
        }
    }
}

pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/health", any(health_route))
        .route(
            "/api/v1/workspaces/{workspace_id}/permissions",
            any(permissions_route),
        )
        .fallback(not_found)
        .layer(middleware::from_fn_with_state(state.clone(), cors_layer))
        .with_state(state)
}

// ---------------------------------------------------------------- responses

fn json_response(status: StatusCode, body: Vec<u8>) -> Response {
    let mut response = Response::new(Body::from(body));
    *response.status_mut() = status;
    response.headers_mut().insert(
        header::CONTENT_TYPE,
        HeaderValue::from_static("application/json"),
    );
    response
}

/// The backend's `HTTPException(status, "message")`: the bare JSON string.
fn http_error(status: StatusCode, message: &str) -> Response {
    json_response(status, serde_json::to_vec(message).unwrap_or_default())
}

fn detail(status: StatusCode, message: &str) -> Response {
    json_response(
        status,
        serde_json::to_vec(&serde_json::json!({ "detail": message })).unwrap_or_default(),
    )
}

fn plain(status: StatusCode, text: &'static str) -> Response {
    let mut response = Response::new(Body::from(text));
    *response.status_mut() = status;
    response.headers_mut().insert(
        header::CONTENT_TYPE,
        HeaderValue::from_static("text/plain; charset=utf-8"),
    );
    response
}

async fn method_not_allowed() -> Response {
    let mut response = detail(StatusCode::METHOD_NOT_ALLOWED, "Method Not Allowed");
    response
        .headers_mut()
        .insert(header::ALLOW, HeaderValue::from_static("GET"));
    response
}

/// Unknown path: Starlette first tries the other spelling of the trailing
/// slash (307), then answers FastAPI's 404.
async fn not_found(request: Request) -> Response {
    let path = request.uri().path();
    let wanted = path.strip_suffix('/').unwrap_or("");
    if path != "/" && path.ends_with('/') && is_permissions_path(wanted) {
        let host = request
            .headers()
            .get(header::HOST)
            .and_then(|h| h.to_str().ok())
            .unwrap_or("localhost");
        let query = request
            .uri()
            .query()
            .map(|q| format!("?{q}"))
            .unwrap_or_default();
        let mut response = Response::new(Body::empty());
        *response.status_mut() = StatusCode::TEMPORARY_REDIRECT;
        if let Ok(v) = HeaderValue::from_str(&format!("http://{host}{wanted}{query}")) {
            response.headers_mut().insert(header::LOCATION, v);
        }
        return response;
    }
    detail(StatusCode::NOT_FOUND, "Not Found")
}

fn is_permissions_path(path: &str) -> bool {
    let parts: Vec<&str> = path.split('/').collect();
    parts.len() == 6
        && parts[0].is_empty()
        && parts[1] == "api"
        && parts[2] == "v1"
        && parts[3] == "workspaces"
        && !parts[4].is_empty()
        && parts[5] == "permissions"
}

// The routes take every method and answer 405 themselves (as Starlette does,
// HEAD included); axum's own method routing would answer HEAD with GET's
// handler and add an `Allow` header to a CORS preflight.
async fn health_route(method: Method) -> Response {
    if method != Method::GET {
        return method_not_allowed().await;
    }
    json_response(StatusCode::OK, br#"{"status":"ok"}"#.to_vec())
}

async fn permissions_route(
    method: Method,
    state: State<Arc<AppState>>,
    path: Path<String>,
    headers: HeaderMap,
) -> Response {
    if method != Method::GET {
        return method_not_allowed().await;
    }
    permissions(state, path, headers).await
}

// --------------------------------------------------------------------- CORS

async fn cors_layer(State(state): State<Arc<AppState>>, request: Request, next: Next) -> Response {
    let origin = request
        .headers()
        .get(header::ORIGIN)
        .and_then(|v| v.to_str().ok())
        .map(str::to_string);
    let Some(origin) = origin else {
        return next.run(request).await;
    };
    let allowed = state.allowed_origins().await;
    if cors::is_preflight(request.method(), request.headers()) {
        return cors::preflight(request.headers(), &allowed);
    }
    let mut response = next.run(request).await;
    cors::simple(&mut response, &origin, &allowed);
    response
}

// -------------------------------------------------------------- permissions

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PermissionsOut {
    permissions: Vec<&'static str>,
    field_rules_enabled: bool,
    choice_logic_enabled: bool,
    save_drafts_enabled: bool,
    captcha_enabled: bool,
    csv_import_enabled: bool,
    new_question_types_enabled: bool,
    address_question_enabled: bool,
    address_lookup_enabled: bool,
    signature_question_enabled: bool,
    option_sources_enabled: bool,
    reusable_sections_enabled: bool,
    layout_containers_enabled: bool,
    offered_gated_presets: Vec<&'static str>,
    form_revisions_ui_enabled: bool,
    audit_log_ui_enabled: bool,
    response_revisions_enabled: bool,
    submissions_api_enabled: bool,
    form_embed_enabled: bool,
    form_access_enabled: bool,
    form_promotion_enabled: bool,
    api_key_roles_enabled: bool,
    reporting_enabled: bool,
    app_theme_enabled: bool,
}

impl PermissionsOut {
    pub fn new(perms: Perms, cfg: &Config) -> PermissionsOut {
        let f = &cfg.flags;
        PermissionsOut {
            permissions: perms.sorted_values(),
            field_rules_enabled: f.field_rules,
            choice_logic_enabled: f.choice_logic,
            save_drafts_enabled: f.save_drafts,
            captcha_enabled: f.captcha,
            csv_import_enabled: f.csv_import,
            new_question_types_enabled: f.new_question_types,
            address_question_enabled: f.address_question,
            // both switches: address_lookup_enabled() = address question AND lookup
            address_lookup_enabled: f.address_question && f.address_lookup,
            signature_question_enabled: f.signature_question,
            option_sources_enabled: f.option_sources,
            reusable_sections_enabled: f.reusable_sections,
            layout_containers_enabled: f.layout_containers,
            offered_gated_presets: f.offered_presets(),
            form_revisions_ui_enabled: f.form_revisions_ui,
            audit_log_ui_enabled: f.audit_log_ui,
            response_revisions_enabled: f.response_revisions,
            submissions_api_enabled: f.submissions_api,
            form_embed_enabled: f.form_embed,
            form_access_enabled: f.form_access,
            form_promotion_enabled: f.form_promotion,
            api_key_roles_enabled: f.api_key_roles,
            reporting_enabled: f.reporting,
            app_theme_enabled: f.app_theme_pigment,
        }
    }
}

/// What a request needs that this service does not do. The deployed design
/// proxies such a request to the Python backend; the spike answers 501 so a
/// contract run can name it instead of hiding it.
fn needs_python(why: &str) -> Response {
    detail(StatusCode::NOT_IMPLEMENTED, why)
}

fn valid_object_id(value: &str) -> bool {
    value.len() == 24 && value.bytes().all(|b| b.is_ascii_hexdigit())
}

/// The 422 FastAPI answers for a path id that is not 24 hex characters.
fn invalid_id() -> Response {
    json_response(
        StatusCode::UNPROCESSABLE_ENTITY,
        br#"{"detail":[{"loc":["path","workspace_id"],"msg":"Value error, Id must be of type PydanticObjectId","type":"value_error"}]}"#
            .to_vec(),
    )
}

enum Authn {
    User(User),
    Reply(Response),
}

/// `get_logged_user`: a live access token is trusted as it is; without one the
/// Python backend refreshes the session from the `RefreshToken` cookie (a
/// session read plus a call to the auth service), which is out of this spike.
fn authenticate(headers: &HeaderMap, cfg: &Config, path_workspace_id: &str) -> Authn {
    let cookies = headers
        .get(header::COOKIE)
        .and_then(|v| v.to_str().ok())
        .map(auth::parse_cookies)
        .unwrap_or_default();
    let access = cookies.get(ACCESS_COOKIE).map(String::as_str);
    match auth::user_from_access_token(access, &cfg.jwt_ring) {
        Some(user) => {
            // `_in_scope`: a respondent-scoped session acts on its own workspace only
            if user.session_scope.as_deref() == Some("respondent") {
                let scope = user.scope_workspace_id.as_deref().unwrap_or("None");
                if path_workspace_id != scope {
                    if cfg.sso_enabled {
                        return Authn::Reply(needs_python(
                            "respondent session on another workspace: SSO policy lookup",
                        ));
                    }
                    return Authn::Reply(http_error(
                        StatusCode::UNAUTHORIZED,
                        "Sign in to this workspace.",
                    ));
                }
            }
            Authn::User(user)
        }
        None => {
            let refresh = cookies
                .get(REFRESH_COOKIE)
                .map(String::as_str)
                .unwrap_or("");
            if refresh.is_empty() {
                Authn::Reply(http_error(StatusCode::UNAUTHORIZED, "No user logged in."))
            } else {
                Authn::Reply(needs_python("session refresh (RefreshToken cookie)"))
            }
        }
    }
}

enum Decision {
    Perms(Perms),
    Python(&'static str),
}

/// `AuthorizationService.effective_permissions(user, workspace_id)` with no form.
async fn effective_permissions(
    state: &AppState,
    user: &User,
    workspace_id: &str,
) -> Result<Decision, sqlx::Error> {
    // `_object_id`: ObjectId.is_valid(str(value)), then the lower-case hex form
    if !valid_object_id(workspace_id) || !valid_object_id(&user.id) {
        return Ok(Decision::Perms(Perms::NONE));
    }
    let workspace_id = workspace_id.to_ascii_lowercase();
    let user_id = user.id.to_ascii_lowercase();
    if user.session_scope.as_deref() == Some("respondent") {
        return Ok(Decision::Perms(Perms::NONE));
    }
    let membership = match db::find_membership(&state.pool, &workspace_id, &user_id).await? {
        Some(m) if !m.disabled => m,
        _ => return Ok(Decision::Perms(Perms::NONE)),
    };
    let workspace = match db::find_workspace(&state.pool, &workspace_id).await? {
        Some(w) => w,
        None => return Ok(Decision::Perms(Perms::NONE)),
    };
    // is_owner_membership: the billing owner, or a member holding OWNER
    let billing_owner = workspace.owner_id.as_deref() == Some(membership.user_id.as_str());
    let is_owner = billing_owner || authz::has_owner_role(&membership.roles);
    // SSO policy (services/sso/policy.py blocks_session): only when SSO is on
    // and the workspace requires it, and then it reads domain claims
    if state.cfg.sso_enabled && !workspace.disabled && workspace.sso_required {
        return Ok(Decision::Python("workspace requires single sign-on"));
    }
    // authenticator-app policy (services/mfa/policy.py blocks_session)
    if state.cfg.totp_enabled && workspace.require_totp {
        let exempt = user.mfa
            || user.auth_method.as_deref() == Some("api_key")
            || (user.auth_method.as_deref() == Some("sso")
                && user.sso_workspace_id.as_deref() == Some(workspace_id.as_str()));
        if !exempt {
            return Ok(Decision::Perms(Perms::NONE));
        }
    }
    let perms = if workspace.disabled {
        if is_owner {
            authz::disabled_workspace_owner_permissions()
        } else {
            Perms::NONE
        }
    } else {
        authz::permissions_for(&membership.roles, is_owner)
    };
    Ok(Decision::Perms(perms))
}

async fn permissions(
    State(state): State<Arc<AppState>>,
    Path(workspace_id): Path<String>,
    headers: HeaderMap,
) -> Response {
    let user = match authenticate(&headers, &state.cfg, &workspace_id) {
        Authn::User(user) => user,
        Authn::Reply(response) => return response,
    };
    if !valid_object_id(&workspace_id) {
        return invalid_id();
    }
    match effective_permissions(&state, &user, &workspace_id).await {
        Ok(Decision::Perms(perms)) => {
            let body = PermissionsOut::new(perms, &state.cfg);
            json_response(
                StatusCode::OK,
                serde_json::to_vec(&body).unwrap_or_default(),
            )
        }
        Ok(Decision::Python(why)) => needs_python(why),
        Err(error) => {
            tracing::error!("permissions read failed: {}", error);
            plain(StatusCode::INTERNAL_SERVER_ERROR, "Internal Server Error")
        }
    }
}
