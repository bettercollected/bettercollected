//! Read access to the Python backend's tables. This service owns no schema:
//! it reads `app.workspace_users`, `app.workspaces` and `app.allowed_origins`
//! as the Alembic chain of the Python backend defines them (head `EXPECTED_HEAD`).
//!
//! Every table is `id`, `doc` JSONB and a few columns GENERATED from `doc`
//! (common/common/db/spine.py); the queries use the generated columns exactly
//! as the Python repositories do and read the rest out of `doc`.

use serde_json::Value;
use sqlx::postgres::{PgPool, PgPoolOptions};
use sqlx::Row;

/// The Alembic revision of schema `app` this build was written against.
pub const EXPECTED_HEAD: &str = "0041";

pub async fn connect(url: &str, max: u32) -> Result<PgPool, sqlx::Error> {
    PgPoolOptions::new().max_connections(max).connect(url).await
}

/// `common/db/schema_guard.py`, reduced: refuse to start when the schema is
/// behind the revision this build needs; a database migrated past it only
/// warns (the Python backend starts too: migrations are expand-only).
pub async fn check_schema(pool: &PgPool) -> Result<(), String> {
    let row = sqlx::query("SELECT version_num FROM app.alembic_version")
        .fetch_optional(pool)
        .await
        .map_err(|e| format!("schema 'app' cannot be read: {e}"))?;
    let found: String = match row {
        Some(r) => r.get("version_num"),
        None => return Err("schema 'app' has no Alembic revision".to_string()),
    };
    if found.as_str() < EXPECTED_HEAD {
        return Err(format!(
            "schema 'app' is at {found}, this build needs {EXPECTED_HEAD}: migrate first"
        ));
    }
    if found != EXPECTED_HEAD {
        tracing::warn!("schema 'app' is at {found}, newer than this build's {EXPECTED_HEAD}");
    }
    Ok(())
}

#[derive(Debug, Clone, PartialEq)]
pub struct Membership {
    pub user_id: String,
    pub roles: Vec<Value>,
    pub disabled: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Workspace {
    pub owner_id: Option<String>,
    pub disabled: bool,
    pub sso_required: bool,
    pub require_totp: bool,
}

/// An id as the document stores it: a plain string or `{"$oid": ...}`.
fn id_text(value: Option<&Value>) -> Option<String> {
    match value? {
        Value::String(s) => Some(s.clone()),
        Value::Object(o) => o.get("$oid").and_then(Value::as_str).map(str::to_string),
        _ => None,
    }
}

fn truthy(value: Option<&Value>) -> bool {
    match value {
        Some(Value::Bool(b)) => *b,
        _ => false,
    }
}

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
pub async fn find_workspace(
    pool: &PgPool,
    workspace_id: &str,
) -> Result<Option<Workspace>, sqlx::Error> {
    let row = sqlx::query("SELECT doc FROM app.workspaces WHERE id = $1")
        .bind(workspace_id)
        .fetch_optional(pool)
        .await?;
    Ok(row.map(|r| {
        let doc: Value = r.get("doc");
        Workspace {
            owner_id: id_text(doc.get("owner_id")),
            disabled: truthy(doc.get("disabled")),
            sso_required: truthy(doc.get("sso_required")),
            require_totp: truthy(doc.get("require_totp")),
        }
    }))
}

/// `AllowedOriginsRepository.list_origins`, in id order.
pub async fn list_origins(pool: &PgPool) -> Result<Vec<String>, sqlx::Error> {
    let rows = sqlx::query("SELECT origin FROM app.allowed_origins ORDER BY id")
        .fetch_all(pool)
        .await?;
    Ok(rows
        .into_iter()
        .filter_map(|r| r.try_get::<Option<String>, _>("origin").ok().flatten())
        .collect())
}
