//! The workspace permission rules of
//! `backend/app/services/authorization_service.py` (docs/enterprise-access-model.md
//! §2), for the workspace-level answer with no form: which permissions a
//! member holds from their roles, and the decision around it (respondent
//! sessions, disabled members and workspaces, the single-sign-on and
//! authenticator-app policies).
//!
//! Pure: no database, no clock. A caller looks up what [`begin`] asks for and
//! hands it to [`finish`].

use bc_auth::User;
use serde_json::Value;

/// `Permission` of `backend/app/models/enum/permission.py`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum Permission {
    WorkspaceManage,
    WorkspaceBilling,
    MembersManage,
    SecurityManage,
    AiManage,
    AuditRead,
    FormCreate,
    FormRead,
    FormEdit,
    FormDelete,
    FormShare,
    ResponseRead,
    ResponseAnnotate,
    ResponseExport,
    ResponseImport,
    ResponseDelete,
    ResponseEdit,
    PrivacyManage,
    AnalyticsRead,
}

#[allow(clippy::enum_glob_use)] // the table below reads better without the prefix
use Permission::*;

pub const ALL: [Permission; 19] = [
    WorkspaceManage,
    WorkspaceBilling,
    MembersManage,
    SecurityManage,
    AiManage,
    AuditRead,
    FormCreate,
    FormRead,
    FormEdit,
    FormDelete,
    FormShare,
    ResponseRead,
    ResponseAnnotate,
    ResponseExport,
    ResponseImport,
    ResponseDelete,
    ResponseEdit,
    PrivacyManage,
    AnalyticsRead,
];

impl Permission {
    pub fn value(self) -> &'static str {
        match self {
            WorkspaceManage => "workspace.manage",
            WorkspaceBilling => "workspace.billing",
            MembersManage => "members.manage",
            SecurityManage => "security.manage",
            AiManage => "ai.manage",
            AuditRead => "audit.read",
            FormCreate => "form.create",
            FormRead => "form.read",
            FormEdit => "form.edit",
            FormDelete => "form.delete",
            FormShare => "form.share",
            ResponseRead => "response.read",
            ResponseAnnotate => "response.annotate",
            ResponseExport => "response.export",
            ResponseImport => "response.import",
            ResponseDelete => "response.delete",
            ResponseEdit => "response.edit",
            PrivacyManage => "privacy.manage",
            AnalyticsRead => "analytics.read",
        }
    }
}

/// A set of permissions (19 bits).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Perms(u32);

impl Perms {
    pub const NONE: Perms = Perms(0);

    pub fn of(items: &[Permission]) -> Perms {
        Perms(items.iter().fold(0, |acc, p| acc | (1 << (*p as u8))))
    }

    pub fn all() -> Perms {
        Perms::of(&ALL)
    }

    #[must_use]
    pub fn union(self, other: Perms) -> Perms {
        Perms(self.0 | other.0)
    }

    #[must_use]
    pub fn minus(self, other: Perms) -> Perms {
        Perms(self.0 & !other.0)
    }

    pub fn contains(self, p: Permission) -> bool {
        self.0 & (1 << (p as u8)) != 0
    }

    /// The values, sorted as Python's `sorted(..., key=lambda p: p.value)`.
    pub fn sorted_values(self) -> Vec<&'static str> {
        let mut out: Vec<&'static str> = ALL
            .iter()
            .filter(|p| self.contains(**p))
            .map(|p| p.value())
            .collect();
        out.sort_unstable();
        out
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    Owner,
    Admin,
    Editor,
    Reviewer,
    Viewer,
    PrivacyOfficer,
}

/// `canonical_role`: `COLLABORATOR` is the stored spelling of Editor; a role
/// the code does not know is `None`. Case-sensitive, like the Python enum.
pub fn canonical_role(stored: &str) -> Option<Role> {
    match stored {
        "OWNER" => Some(Role::Owner),
        "ADMIN" => Some(Role::Admin),
        "EDITOR" | "COLLABORATOR" => Some(Role::Editor),
        "REVIEWER" => Some(Role::Reviewer),
        "VIEWER" => Some(Role::Viewer),
        "PRIVACY_OFFICER" => Some(Role::PrivacyOfficer),
        _ => None,
    }
}

fn editor() -> Perms {
    Perms::of(&[
        FormCreate,
        FormRead,
        FormEdit,
        FormDelete,
        FormShare,
        ResponseRead,
        ResponseAnnotate,
        ResponseExport,
        ResponseDelete,
        ResponseEdit,
        AnalyticsRead,
    ])
}

fn role_permissions(role: Role) -> Perms {
    match role {
        Role::Owner => Perms::all(),
        Role::Admin => Perms::all().minus(Perms::of(&[WorkspaceBilling])),
        Role::Editor => editor(),
        Role::Reviewer => Perms::of(&[FormRead, ResponseRead, ResponseAnnotate, AnalyticsRead]),
        Role::Viewer => Perms::of(&[FormRead, ResponseRead, AnalyticsRead]),
        Role::PrivacyOfficer => Perms::of(&[FormRead, PrivacyManage, AnalyticsRead, AuditRead]),
    }
}

const ANSWER: [Permission; 4] = [ResponseRead, ResponseAnnotate, ResponseExport, ResponseEdit];

/// The stored roles of a membership. Anything that is not a string (a
/// document the Python models would refuse) counts as an unknown role.
pub fn role_names(roles: &[Value]) -> Vec<Option<Role>> {
    roles
        .iter()
        .map(|r| r.as_str().and_then(canonical_role))
        .collect()
}

pub fn has_owner_role(roles: &[Value]) -> bool {
    role_names(roles).contains(&Some(Role::Owner))
}

/// `permissions_for`: an active membership's permissions. `[]` (before roles
/// existed) is an Editor; an unknown role grants nothing; a Privacy officer
/// never holds the answer permissions, whatever else the membership holds.
pub fn permissions_for(roles: &[Value], is_owner: bool) -> Perms {
    if is_owner || has_owner_role(roles) {
        return Perms::all();
    }
    if roles.is_empty() {
        return editor();
    }
    let known = role_names(roles);
    let mut granted = Perms::NONE;
    for role in known.iter().flatten() {
        granted = granted.union(role_permissions(*role));
    }
    if known.contains(&Some(Role::PrivacyOfficer)) {
        granted = granted.minus(Perms::of(&ANSWER));
    }
    granted
}

/// What a disabled workspace leaves its owners (a downgrade never disables an
/// owner's membership); every other member gets nothing.
pub fn disabled_workspace_owner_permissions() -> Perms {
    Perms::of(&[
        FormRead,
        ResponseRead,
        ResponseExport,
        ResponseDelete,
        PrivacyManage,
        AnalyticsRead,
    ])
}

// ------------------------------------------------------------------ decision

/// What `find_workspace_user` returns, reduced to what the decision reads.
#[derive(Debug, Clone, PartialEq)]
pub struct Membership {
    pub user_id: String,
    pub roles: Vec<Value>,
    pub disabled: bool,
}

/// What `find_by_id` of a workspace returns, reduced to what the decision reads.
#[derive(Debug, Clone, PartialEq, Eq)]
#[allow(clippy::struct_excessive_bools)]
pub struct WorkspaceFacts {
    pub owner_id: Option<String>,
    pub disabled: bool,
    pub sso_required: bool,
    pub require_totp: bool,
}

/// The two switches the policies depend on (`SSO_ENABLED`, `TOTP_ENABLED`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Policies {
    pub sso_enabled: bool,
    pub totp_enabled: bool,
}

/// The answer, or the case Rust does not decide.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Permissions(Perms),
    /// The decision needs something this crate does not do yet (the
    /// single-sign-on policy reads domain claims). The route hands the request
    /// to the Python backend. The text says why, for logs and tests.
    NeedsPython(&'static str),
}

/// The normalised ids to look up.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Lookup {
    pub workspace_id: String,
    pub user_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Step {
    /// Decided without a lookup.
    Done(Decision),
    /// Look up this membership and (when it exists and is enabled) this
    /// workspace, then call [`finish`].
    Lookup(Lookup),
}

/// `ObjectId.is_valid`: 24 hexadecimal characters.
fn valid_object_id(value: &str) -> bool {
    value.len() == 24 && value.bytes().all(|b| b.is_ascii_hexdigit())
}

/// `AuthorizationService.effective_permissions(user, workspace_id)` with no
/// form, first half: ids that are not `ObjectId`s and respondent sessions hold
/// nothing; otherwise the lookup to make (ids in their lower-case form, as
/// `_object_id` returns them).
pub fn begin(user: &User, workspace_id: &str) -> Step {
    if !valid_object_id(workspace_id) || !valid_object_id(&user.id) {
        return Step::Done(Decision::Permissions(Perms::NONE));
    }
    if user.session_scope.as_deref() == Some("respondent") {
        return Step::Done(Decision::Permissions(Perms::NONE));
    }
    Step::Lookup(Lookup {
        workspace_id: workspace_id.to_ascii_lowercase(),
        user_id: user.id.to_ascii_lowercase(),
    })
}

/// Second half. `workspace` may be `None` when `membership` is missing or
/// disabled (then it is not read at all).
pub fn finish(
    lookup: &Lookup,
    user: &User,
    membership: Option<&Membership>,
    workspace: Option<&WorkspaceFacts>,
    policies: Policies,
) -> Decision {
    let none = Decision::Permissions(Perms::NONE);
    let Some(membership) = membership.filter(|m| !m.disabled) else {
        return none;
    };
    let Some(workspace) = workspace else {
        return none;
    };
    // is_owner_membership: the billing owner, or a member holding OWNER
    let billing_owner = workspace.owner_id.as_deref() == Some(membership.user_id.as_str());
    let is_owner = billing_owner || has_owner_role(&membership.roles);
    // SSO policy (services/sso/policy.py blocks_session): only when SSO is on
    // and the workspace requires it, and then it reads domain claims
    if policies.sso_enabled && !workspace.disabled && workspace.sso_required {
        return Decision::NeedsPython("workspace requires single sign-on");
    }
    // authenticator-app policy (services/mfa/policy.py blocks_session)
    if policies.totp_enabled && workspace.require_totp {
        let exempt = user.mfa
            || user.auth_method.as_deref() == Some("api_key")
            || (user.auth_method.as_deref() == Some("sso")
                && user.sso_workspace_id.as_deref() == Some(lookup.workspace_id.as_str()));
        if !exempt {
            return none;
        }
    }
    let perms = if workspace.disabled {
        if is_owner {
            disabled_workspace_owner_permissions()
        } else {
            Perms::NONE
        }
    } else {
        permissions_for(&membership.roles, is_owner)
    };
    Decision::Permissions(perms)
}

#[cfg(test)]
mod tests {
    #![allow(clippy::match_wildcard_for_single_variants)]
    use super::*;
    use serde_json::json;

    fn roles(items: &[&str]) -> Vec<Value> {
        items.iter().map(|s| json!(s)).collect()
    }

    #[test]
    fn owner_and_owner_role_hold_everything() {
        assert_eq!(permissions_for(&roles(&["VIEWER"]), true), Perms::all());
        assert_eq!(permissions_for(&roles(&["OWNER"]), false), Perms::all());
    }

    #[test]
    fn admin_is_everything_but_billing() {
        let p = permissions_for(&roles(&["ADMIN"]), false);
        assert!(!p.contains(WorkspaceBilling));
        assert_eq!(p.sorted_values().len(), 18);
    }

    #[test]
    fn collaborator_is_editor_and_empty_roles_are_editor() {
        assert_eq!(
            permissions_for(&roles(&["COLLABORATOR"]), false),
            permissions_for(&roles(&["EDITOR"]), false)
        );
        assert_eq!(
            permissions_for(&[], false),
            permissions_for(&roles(&["EDITOR"]), false)
        );
    }

    #[test]
    fn unknown_role_grants_nothing() {
        assert_eq!(permissions_for(&roles(&["SUPERHERO"]), false), Perms::NONE);
        assert_eq!(
            permissions_for(&roles(&["admin"]), false),
            Perms::NONE,
            "case matters"
        );
        assert_eq!(permissions_for(&[json!(5)], false), Perms::NONE);
    }

    #[test]
    fn privacy_officer_never_reads_answers() {
        let p = permissions_for(&roles(&["PRIVACY_OFFICER", "EDITOR"]), false);
        for a in ANSWER {
            assert!(!p.contains(a));
        }
        assert!(p.contains(FormEdit));
        let p = permissions_for(&roles(&["REVIEWER", "PRIVACY_OFFICER"]), false);
        assert!(!p.contains(ResponseRead) && p.contains(AuditRead));
    }

    #[test]
    fn values_are_sorted_like_python() {
        let v = Perms::all().sorted_values();
        let mut s = v.clone();
        s.sort_unstable();
        assert_eq!(v, s);
        assert_eq!(v[0], "ai.manage");
    }

    // ------------------------------------------------------------ decision

    fn user(extra: impl FnOnce(&mut User)) -> User {
        let mut u = User {
            id: "6a0000000000000000000001".into(),
            sub: "a@example.test".into(),
            session_scope: None,
            scope_workspace_id: None,
            auth_method: None,
            sso_workspace_id: None,
            mfa: false,
        };
        extra(&mut u);
        u
    }

    const WS: &str = "6a0000000000000000000009";

    fn member(roles: &[&str], disabled: bool) -> Membership {
        Membership {
            user_id: "6a0000000000000000000001".into(),
            roles: roles.iter().map(|s| json!(s)).collect(),
            disabled,
        }
    }

    fn workspace(disabled: bool, sso: bool, totp: bool) -> WorkspaceFacts {
        WorkspaceFacts {
            owner_id: Some("6a00000000000000000000ff".into()),
            disabled,
            sso_required: sso,
            require_totp: totp,
        }
    }

    fn lookup_for(u: &User) -> Lookup {
        match begin(u, WS) {
            Step::Lookup(l) => l,
            other => panic!("expected a lookup, got {other:?}"),
        }
    }

    fn perms(d: Decision) -> Perms {
        match d {
            Decision::Permissions(p) => p,
            other => panic!("expected permissions, got {other:?}"),
        }
    }

    #[test]
    fn ids_that_are_not_object_ids_and_respondent_sessions_hold_nothing() {
        let u = user(|_| {});
        for bad in ["nope", "", &"g".repeat(24), &format!("{WS}0")] {
            assert_eq!(
                begin(&u, bad),
                Step::Done(Decision::Permissions(Perms::NONE)),
                "{bad}"
            );
        }
        let bad_user = user(|u| u.id = "not-an-id".into());
        assert_eq!(
            begin(&bad_user, WS),
            Step::Done(Decision::Permissions(Perms::NONE))
        );
        let respondent = user(|u| u.session_scope = Some("respondent".into()));
        assert_eq!(
            begin(&respondent, WS),
            Step::Done(Decision::Permissions(Perms::NONE))
        );
    }

    #[test]
    fn ids_are_looked_up_in_lower_case() {
        let u = user(|u| u.id = "6A0000000000000000000001".into());
        let Step::Lookup(l) = begin(&u, &WS.to_uppercase()) else {
            panic!("lookup expected")
        };
        assert_eq!(
            (l.workspace_id.as_str(), l.user_id.as_str()),
            (WS, "6a0000000000000000000001")
        );
    }

    #[test]
    fn a_missing_or_disabled_member_or_workspace_holds_nothing() {
        let u = user(|_| {});
        let l = lookup_for(&u);
        let ws = workspace(false, false, false);
        let p = Policies::default();
        assert_eq!(perms(finish(&l, &u, None, Some(&ws), p)), Perms::NONE);
        assert_eq!(
            perms(finish(
                &l,
                &u,
                Some(&member(&["ADMIN"], true)),
                Some(&ws),
                p
            )),
            Perms::NONE
        );
        assert_eq!(
            perms(finish(&l, &u, Some(&member(&["ADMIN"], false)), None, p)),
            Perms::NONE
        );
    }

    #[test]
    fn the_billing_owner_holds_everything_even_with_a_viewer_role() {
        let u = user(|_| {});
        let l = lookup_for(&u);
        let mut ws = workspace(false, false, false);
        ws.owner_id = Some("6a0000000000000000000001".into());
        let d = finish(
            &l,
            &u,
            Some(&member(&["VIEWER"], false)),
            Some(&ws),
            Policies::default(),
        );
        assert_eq!(perms(d), Perms::all());
    }

    #[test]
    fn a_disabled_workspace_leaves_owners_read_access_and_others_nothing() {
        let u = user(|_| {});
        let l = lookup_for(&u);
        let ws = workspace(true, false, false);
        let p = Policies::default();
        let owner = finish(&l, &u, Some(&member(&["OWNER"], false)), Some(&ws), p);
        assert_eq!(perms(owner), disabled_workspace_owner_permissions());
        let admin = finish(&l, &u, Some(&member(&["ADMIN"], false)), Some(&ws), p);
        assert_eq!(perms(admin), Perms::NONE);
    }

    #[test]
    fn single_sign_on_is_python_s_to_decide_only_when_on_and_required_and_enabled() {
        let u = user(|_| {});
        let l = lookup_for(&u);
        let m = member(&["ADMIN"], false);
        let sso_on = Policies {
            sso_enabled: true,
            totp_enabled: false,
        };
        let required = workspace(false, true, false);
        assert!(matches!(
            finish(&l, &u, Some(&m), Some(&required), sso_on),
            Decision::NeedsPython(_)
        ));
        // switch off: ignored; workspace disabled: ignored (owners keep read access)
        assert!(matches!(
            finish(&l, &u, Some(&m), Some(&required), Policies::default()),
            Decision::Permissions(_)
        ));
        let disabled = workspace(true, true, false);
        assert!(matches!(
            finish(&l, &u, Some(&m), Some(&disabled), sso_on),
            Decision::Permissions(_)
        ));
    }

    type Edit = fn(&mut User);

    #[test]
    fn the_authenticator_policy_exempts_second_factor_api_keys_and_own_sso() {
        let totp = Policies {
            sso_enabled: false,
            totp_enabled: true,
        };
        let ws = workspace(false, false, true);
        let m = member(&["ADMIN"], false);
        let cases: [(Edit, bool); 5] = [
            (|_| {}, false),
            (|u| u.mfa = true, true),
            (|u| u.auth_method = Some("api_key".into()), true),
            (
                |u| {
                    u.auth_method = Some("sso".into());
                    u.sso_workspace_id = Some(WS.into());
                },
                true,
            ),
            (
                |u| {
                    u.auth_method = Some("sso".into());
                    u.sso_workspace_id = Some("other".into());
                },
                false,
            ),
        ];
        for (i, (edit, allowed)) in cases.into_iter().enumerate() {
            let u = user(edit);
            let l = lookup_for(&u);
            let got = perms(finish(&l, &u, Some(&m), Some(&ws), totp));
            assert_eq!(got != Perms::NONE, allowed, "case {i}");
        }
    }
}
