//! `app.workspace_audit_events` (`WorkspaceAuditEventDocument`): ids and enum
//! values only, never a name, an address or a value. The time is `created_at`.

use serde::{Deserialize, Serialize};

use crate::id::RecordId;
use crate::impl_record;
use crate::stamp::Stamp;
use crate::value::lax;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct WorkspaceAuditEvent {
    #[serde(rename = "_id", default)]
    pub id: Option<RecordId>,
    pub created_at: Option<Stamp>,
    pub updated_at: Option<Stamp>,

    pub workspace_id: RecordId,
    pub user_id: String,
    #[serde(default)]
    pub session_id: Option<String>,
    pub event: String,
    #[serde(default)]
    pub method: Option<String>,
    #[serde(default)]
    pub path: Option<String>,
    #[serde(default)]
    pub form_id: Option<String>,
    #[serde(default)]
    pub response_id: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_i64")]
    pub revision: Option<i64>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub required: Option<bool>,
    #[serde(default)]
    pub target_user_id: Option<String>,
    #[serde(default)]
    pub to_user_id: Option<String>,
    #[serde(default)]
    pub group_id: Option<String>,
    #[serde(default)]
    pub grant_role: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub grant_export: Option<bool>,
    #[serde(default)]
    pub access_mode: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_i64")]
    pub count: Option<i64>,
    #[serde(default)]
    pub scim_group_id: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub linked: Option<bool>,
    #[serde(default)]
    pub invitation_id: Option<String>,
    #[serde(default)]
    pub role: Option<String>,
    #[serde(default)]
    pub previous_role: Option<String>,
    #[serde(default)]
    pub export_id: Option<String>,
    #[serde(default)]
    pub export_channel: Option<String>,
    #[serde(default)]
    pub export_format: Option<String>,
    #[serde(default)]
    pub key_id: Option<String>,
    #[serde(default)]
    pub reason: Option<String>,
    #[serde(default)]
    pub key_role: Option<String>,
    #[serde(default)]
    pub key_role_before: Option<String>,
    #[serde(default)]
    pub form_scope: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub widened: Option<bool>,
    #[serde(default)]
    pub connection_id: Option<String>,
    #[serde(default)]
    pub connection_type: Option<String>,
    #[serde(default)]
    pub domain_id: Option<String>,
    #[serde(default)]
    pub directory_id: Option<String>,
    #[serde(default)]
    pub directory_type: Option<String>,
    #[serde(default)]
    pub directory_group_id: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub enabled: Option<bool>,
    #[serde(default)]
    pub provider: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_i64")]
    pub retention_months: Option<i64>,
    #[serde(default, deserialize_with = "lax::opt_i64")]
    pub previous_retention_months: Option<i64>,
    #[serde(default)]
    pub app_theme: Option<String>,
    #[serde(default)]
    pub previous_app_theme: Option<String>,
    #[serde(default)]
    pub action_id: Option<String>,
    #[serde(default)]
    pub service_id: Option<String>,
    #[serde(default)]
    pub changed: Option<Vec<String>>,
    #[serde(default)]
    pub view_id: Option<String>,
    #[serde(default)]
    pub view_scope: Option<String>,
    #[serde(default)]
    pub source_workspace_id: Option<String>,
    #[serde(default)]
    pub source_form_id: Option<String>,
    #[serde(default)]
    pub target_workspace_id: Option<String>,
    #[serde(default)]
    pub target_form_id: Option<String>,
    #[serde(default)]
    pub export_filters: Option<Vec<String>>,
}

impl_record!(WorkspaceAuditEvent, "workspace_audit_events", Stamp);
