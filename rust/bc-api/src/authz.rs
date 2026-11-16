//! The workspace permission rules of
//! `backend/app/services/authorization_service.py` (docs/enterprise-access-model.md
//! §2), for the workspace-level answer with no form: which permissions a
//! member holds from their roles. A role table, nothing else.

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

    pub fn union(self, other: Perms) -> Perms {
        Perms(self.0 | other.0)
    }

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

#[cfg(test)]
mod tests {
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
        s.sort();
        assert_eq!(v, s);
        assert_eq!(v[0], "ai.manage");
    }
}
