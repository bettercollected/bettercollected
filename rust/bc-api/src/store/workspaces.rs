//! `app.workspace_users` and `app.workspaces`.

use bc_authz::{Membership, WorkspaceFacts};
use serde_json::Value;
use sqlx::{PgPool, Row};

use super::doc::{id_text, truthy};

/// `PostgresWorkspaceUserRepository.find_workspace_user`.
pub async fn find_membership(
    pool: &PgPool,
    workspace_id: &str,
    user_id: &str,
) -> Result<Option<Membership>, sqlx::Error> {
    let row = sqlx::query(
        "SELECT doc FROM app.workspace_users WHERE workspace_id = $1 AND user_id = $2 LIMIT 1",
    )
    .bind(workspace_id)
    .bind(user_id)
    .fetch_optional(pool)
    .await?;
    Ok(row.map(|r| {
        let doc: Value = r.get("doc");
        Membership {
            user_id: id_text(doc.get("user_id")).unwrap_or_default(),
            roles: doc
                .get("roles")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default(),
            disabled: truthy(doc.get("disabled")),
        }
    }))
}

/// `PostgresWorkspaceRepository.find_by_id`.
pub async fn find_by_id(
    pool: &PgPool,
    workspace_id: &str,
) -> Result<Option<WorkspaceFacts>, sqlx::Error> {
    let row = sqlx::query("SELECT doc FROM app.workspaces WHERE id = $1")
        .bind(workspace_id)
        .fetch_optional(pool)
        .await?;
    Ok(row.map(|r| {
        let doc: Value = r.get("doc");
        WorkspaceFacts {
            owner_id: id_text(doc.get("owner_id")),
            disabled: truthy(doc.get("disabled")),
            sso_required: truthy(doc.get("sso_required")),
            require_totp: truthy(doc.get("require_totp")),
        }
    }))
}
