//! `app.workspaces` (`WorkspaceDocument`).

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::id::RecordId;
use crate::impl_record;
use crate::stamp::Stamp;
use crate::value::{lax, some_false};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Workspace {
    #[serde(rename = "_id", default)]
    pub id: Option<RecordId>,
    pub created_at: Option<Stamp>,
    pub updated_at: Option<Stamp>,

    #[serde(default)]
    pub title: Option<String>,
    pub workspace_name: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub profile_image: Option<String>,
    #[serde(default)]
    pub banner_image: Option<String>,
    #[serde(default)]
    pub custom_domain: Option<String>,
    #[serde(default)]
    pub privacy_policy: Option<String>,
    #[serde(default)]
    pub terms_of_service: Option<String>,
    /// A list of saved themes, in document form.
    #[serde(default)]
    pub custom_themes: Option<Value>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub is_pro: Option<bool>,

    #[serde(default)]
    pub custom_domain_id: Option<String>,
    #[serde(default)]
    pub custom_domain_status: Option<String>,
    #[serde(default)]
    pub custom_domain_dns_records: Option<Value>,
    #[serde(default)]
    pub custom_domain_checks: Option<Value>,
    #[serde(default)]
    pub custom_domain_updated_at: Option<Stamp>,
    #[serde(default)]
    pub custom_domain_attempt: Option<String>,

    #[serde(default = "some_false", deserialize_with = "lax::opt_bool")]
    pub ai_enabled: Option<bool>,
    #[serde(default)]
    pub ai_provider: Option<String>,
    #[serde(default)]
    pub ai_enabled_by: Option<String>,
    #[serde(default)]
    pub ai_enabled_at: Option<Stamp>,
    #[serde(default)]
    pub ai_disabled_by: Option<String>,
    #[serde(default)]
    pub ai_disabled_at: Option<Stamp>,

    #[serde(default = "some_false", deserialize_with = "lax::opt_bool")]
    pub sso_required: Option<bool>,
    #[serde(default)]
    pub sso_required_changed_by: Option<String>,
    #[serde(default)]
    pub sso_required_changed_at: Option<Stamp>,
    #[serde(default)]
    pub sso_default_role: Option<String>,
    #[serde(default = "some_false", deserialize_with = "lax::opt_bool")]
    pub require_totp: Option<bool>,
    #[serde(default, deserialize_with = "lax::opt_i64")]
    pub audit_retention_months: Option<i64>,
    #[serde(default)]
    pub embed_allowed_origins: Option<Vec<String>>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub captcha_default: Option<bool>,
    /// `daybreak` or `pigment`.
    #[serde(default)]
    pub app_theme: Option<String>,

    /// The billing owner's user id.
    #[serde(default)]
    pub owner_id: Option<String>,
    #[serde(rename = "default", default, deserialize_with = "lax::bool_")]
    pub is_default: bool,
    #[serde(default = "some_false", deserialize_with = "lax::opt_bool")]
    pub custom_domain_disabled: Option<bool>,
    #[serde(default = "some_false", deserialize_with = "lax::opt_bool")]
    pub custom_domain_verified: Option<bool>,
    #[serde(default = "some_false", deserialize_with = "lax::opt_bool")]
    pub disabled: Option<bool>,
}

impl_record!(Workspace, "workspaces", Stamp);
