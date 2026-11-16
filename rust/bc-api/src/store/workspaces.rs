//! `app.workspace_users` and `app.workspaces`.
//!
//! Both documents are read through the typed records of `bc-db`
//! (`WorkspaceUser`, `Workspace`), which accept exactly what the Python
//! models accept: a flag stored as `"true"` or `1` is `true`, an unknown key is
//! ignored. A document Python cannot read (a flag spelled `"maybe"`, a role
//! that is a number, a missing name) is [`StoreError::Unreadable`]: the caller
//! does not decide on it, it hands the request to Python, so a policy flag is
//! never read as "off" because the edge could not read it.

use bc_authz::{Membership, WorkspaceFacts};
use bc_db::Clock;
use bc_db::clock::SystemClock;
use bc_db::codec::decode;
use bc_db::records::{Workspace, WorkspaceUser};
use serde_json::Value;
use sqlx::{PgPool, Row};

/// Why a lookup gave no answer.
#[derive(Debug)]
pub enum StoreError {
    Db(sqlx::Error),
    /// The stored document does not read as Python reads it.
    Unreadable,
}

impl From<sqlx::Error> for StoreError {
    fn from(error: sqlx::Error) -> Self {
        StoreError::Db(error)
    }
}

impl std::fmt::Display for StoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            StoreError::Db(e) => write!(f, "{e}"),
            StoreError::Unreadable => f.write_str("a stored document does not read"),
        }
    }
}

/// `PostgresWorkspaceUserRepository.find_workspace_user`.
pub async fn find_membership(
    pool: &PgPool,
    workspace_id: &str,
    user_id: &str,
) -> Result<Option<Membership>, StoreError> {
    let row = sqlx::query(
        "SELECT doc FROM app.workspace_users WHERE workspace_id = $1 AND user_id = $2 LIMIT 1",
    )
    .bind(workspace_id)
    .bind(user_id)
    .fetch_optional(pool)
    .await?;
    let Some(row) = row else { return Ok(None) };
    let doc: Value = row.try_get("doc")?;
    let member: WorkspaceUser =
        decode(doc, SystemClock.now()).map_err(|_| StoreError::Unreadable)?;
    Ok(Some(Membership {
        user_id: member.user_id.to_string(),
        roles: member.roles.into_iter().map(Value::String).collect(),
        disabled: member.disabled,
    }))
}

/// `PostgresWorkspaceRepository.find_by_id`.
pub async fn find_by_id(
    pool: &PgPool,
    workspace_id: &str,
) -> Result<Option<WorkspaceFacts>, StoreError> {
    let row = sqlx::query("SELECT doc FROM app.workspaces WHERE id = $1")
        .bind(workspace_id)
        .fetch_optional(pool)
        .await?;
    let Some(row) = row else { return Ok(None) };
    let doc: Value = row.try_get("doc")?;
    let workspace: Workspace =
        decode(doc, SystemClock.now()).map_err(|_| StoreError::Unreadable)?;
    Ok(Some(WorkspaceFacts {
        owner_id: workspace.owner_id,
        // `Optional[bool]`: null is off
        disabled: workspace.disabled.unwrap_or(false),
        sso_required: workspace.sso_required.unwrap_or(false),
        require_totp: workspace.require_totp.unwrap_or(false),
    }))
}
