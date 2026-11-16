//! Group `permissions`: `GET /api/v1/workspaces/{workspace_id}/permissions`,
//! the backend's `get_workspace_permissions`
//! (`backend/app/controllers/workspace_router.py`): what the caller may do in
//! a workspace. Authenticated, workspace-scoped, read-only, no decryption.

use axum::Router;
use axum::extract::{Request, State};
use axum::http::{Method, StatusCode, header};
use axum::response::Response;
use bc_auth::{ACCESS_COOKIE, REFRESH_COOKIE, User, parse_cookies, user_from_access_token};
use bc_authz::{Decision, Perms, Policies, Step, begin, finish};
use bc_config::Config;
use bc_http::error::{http_error, internal_error, invalid_object_id, is_object_id, json_response};
use percent_encoding::percent_decode_str;
use serde::Serialize;

use super::{Shared, served};
use crate::store::workspaces::{self, StoreError};

const PATH_PREFIX: &str = "/api/v1/workspaces/";
const PATH_SUFFIX: &str = "/permissions";

pub fn mount(router: Router<Shared>, state: &Shared) -> Router<Shared> {
    router.route(
        "/api/v1/workspaces/{workspace_id}/permissions",
        served(&[Method::GET], permissions, state),
    )
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
#[allow(clippy::struct_excessive_bools)]
struct PermissionsOut {
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
    fn new(perms: Perms, cfg: &Config) -> PermissionsOut {
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

/// The workspace id of the path as Starlette sees it: percent-decoded (bad
/// UTF-8 replaced, as `unquote` does). `None` when the path is not this
/// route's after decoding (an encoded `/` splits the segment in Starlette and
/// the route does not match: Python answers 404, so Python decides).
fn workspace_id_of(path: &str) -> Option<String> {
    let raw = path.strip_prefix(PATH_PREFIX)?.strip_suffix(PATH_SUFFIX)?;
    if raw.is_empty() || raw.contains('/') {
        return None;
    }
    let decoded = percent_decode_str(raw).decode_utf8_lossy().into_owned();
    (!decoded.contains('/')).then_some(decoded)
}

enum Authn {
    User(User),
    Reply(Response),
    /// Not Rust's to decide.
    Python(&'static str),
}

/// `get_logged_user`: a live access token is trusted as it is; without one the
/// Python backend refreshes the session from the `RefreshToken` cookie (a
/// session read plus a call to the auth service), which is not done here.
fn authenticate(request: &Request, cfg: &Config, path_workspace_id: &str) -> Authn {
    let cookies = request
        .headers()
        .get(header::COOKIE)
        .map(|v| String::from_utf8_lossy(v.as_bytes()).into_owned())
        .map(|raw| parse_cookies(&raw))
        .unwrap_or_default();
    let access = cookies.get(ACCESS_COOKIE).map(String::as_str);
    if let Some(user) = user_from_access_token(access, &cfg.jwt_ring) {
        // `_in_scope`: a respondent-scoped session acts on its own workspace only
        if user.session_scope.as_deref() == Some("respondent") {
            let scope = user.scope_workspace_id.as_deref().unwrap_or("None");
            if path_workspace_id != scope {
                if cfg.sso_enabled {
                    return Authn::Python(
                        "respondent session on another workspace: SSO policy lookup",
                    );
                }
                return Authn::Reply(http_error(
                    StatusCode::UNAUTHORIZED,
                    "Sign in to this workspace.",
                ));
            }
        }
        return Authn::User(user);
    }
    let refresh = cookies.get(REFRESH_COOKIE).map_or("", String::as_str);
    if refresh.is_empty() {
        Authn::Reply(http_error(StatusCode::UNAUTHORIZED, "No user logged in."))
    } else {
        Authn::Python("session refresh (RefreshToken cookie)")
    }
}

async fn permissions(State(state): State<Shared>, request: Request) -> Response {
    let Some(workspace_id) = workspace_id_of(request.uri().path()) else {
        return state.proxy.forward(request).await;
    };
    let user = match authenticate(&request, &state.cfg, &workspace_id) {
        Authn::User(user) => user,
        Authn::Reply(response) => return response,
        Authn::Python(_why) => return state.proxy.forward(request).await,
    };
    if !is_object_id(&workspace_id) {
        return invalid_object_id("path", "workspace_id");
    }
    let policies = Policies {
        sso_enabled: state.cfg.sso_enabled,
        totp_enabled: state.cfg.totp_enabled,
    };
    let decision = match begin(&user, &workspace_id) {
        Step::Done(decision) => decision,
        Step::Lookup(lookup) => {
            let facts = async {
                let membership =
                    workspaces::find_membership(&state.pool, &lookup.workspace_id, &lookup.user_id)
                        .await?;
                // the workspace is read only for an enabled member
                let workspace = match &membership {
                    Some(m) if !m.disabled => {
                        workspaces::find_by_id(&state.pool, &lookup.workspace_id).await?
                    }
                    _ => None,
                };
                Ok::<_, StoreError>((membership, workspace))
            };
            match facts.await {
                Ok((membership, workspace)) => finish(
                    &lookup,
                    &user,
                    membership.as_ref(),
                    workspace.as_ref(),
                    policies,
                ),
                // the document is one Python cannot read either: its answer stands
                Err(StoreError::Unreadable) => return state.proxy.forward(request).await,
                Err(StoreError::Db(error)) => {
                    tracing::error!("permissions read failed: {error}");
                    return internal_error();
                }
            }
        }
    };
    match decision {
        Decision::Permissions(perms) => {
            let body =
                serde_json::to_value(PermissionsOut::new(perms, &state.cfg)).unwrap_or_default();
            json_response(StatusCode::OK, &body)
        }
        Decision::NeedsPython(_why) => state.proxy.forward(request).await,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_workspace_id_is_read_as_starlette_reads_it() {
        let p = |id: &str| format!("/api/v1/workspaces/{id}/permissions");
        assert_eq!(workspace_id_of(&p("abc")).as_deref(), Some("abc"));
        assert_eq!(workspace_id_of(&p("%20")).as_deref(), Some(" "));
        assert_eq!(workspace_id_of(&p("%C3%A9")).as_deref(), Some("é"));
        // invalid UTF-8 becomes U+FFFD instead of failing the request
        assert_eq!(workspace_id_of(&p("%FF")).as_deref(), Some("\u{fffd}"));
        // anything that splits the segment is not this route
        assert_eq!(workspace_id_of(&p("a%2Fb")), None);
        assert_eq!(workspace_id_of(&p("a/b")), None);
        assert_eq!(workspace_id_of(&p("")), None);
        assert_eq!(workspace_id_of("/api/v1/workspaces/x/other"), None);
    }
}
