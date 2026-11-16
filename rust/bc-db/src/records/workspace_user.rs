//! `app.workspace_users` (`WorkspaceUserDocument`): a user's membership.

use serde::{Deserialize, Serialize};

use crate::id::RecordId;
use crate::impl_record;
use crate::stamp::Stamp;
use crate::value::lax;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct WorkspaceUser {
    #[serde(rename = "_id", default)]
    pub id: Option<RecordId>,
    pub created_at: Option<Stamp>,
    pub updated_at: Option<Stamp>,

    pub workspace_id: RecordId,
    pub user_id: RecordId,
    /// Role names as stored (`OWNER`, `ADMIN`, `COLLABORATOR`, ...); a name this
    /// code does not know is kept and grants nothing.
    #[serde(default)]
    pub roles: Vec<String>,
    #[serde(default, deserialize_with = "lax::bool_")]
    pub disabled: bool,
    #[serde(default)]
    pub provisioned_by: Option<String>,
    #[serde(default)]
    pub disabled_reasons: Vec<String>,
}

impl_record!(WorkspaceUser, "workspace_users", Stamp);
