//! The database side every service of this workspace shares: the pool and the
//! startup check of the schema revision. Nothing else yet. This workspace owns
//! no schema and runs no migrations: the Python backend's Alembic chain does.

use sqlx::Row;
use sqlx::postgres::{PgPool, PgPoolOptions};

/// The Alembic revision of schema `app` this build was written against. Move
/// it only together with a review of every query for the migrations in
/// between (migrations are expand-only, so a build keeps running on a newer
/// schema, but it knows nothing of what that schema added).
pub const EXPECTED_HEAD: &str = "0041";

/// Opens the pool. The error can quote the connection string, so the caller
/// must not print it.
pub async fn connect(url: &str, max_connections: u32) -> Result<PgPool, sqlx::Error> {
    PgPoolOptions::new()
        .max_connections(max_connections)
        .connect(url)
        .await
}

/// How the database's revision stands against the one this build needs.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HeadStatus {
    Current,
    /// Migrated past this build: the Python backend starts too (a rollback or
    /// a reschedule after a newer release migrated), so this only warns.
    Ahead,
    Behind,
    /// The revision ids cannot be ordered (not numbers) and differ.
    Unknown,
}

/// `common/db/schema_guard.py`, reduced to one schema.
pub fn compare_head(found: &str, expected: &str) -> HeadStatus {
    if found == expected {
        return HeadStatus::Current;
    }
    match (found.parse::<u64>(), expected.parse::<u64>()) {
        (Ok(f), Ok(e)) if f > e => HeadStatus::Ahead,
        (Ok(_), Ok(_)) => HeadStatus::Behind,
        _ => HeadStatus::Unknown,
    }
}

/// Refuses (an `Err` with the reason) when schema `app` is behind, missing or
/// unreadable; warns when it is ahead.
pub async fn check_schema(pool: &PgPool) -> Result<(), String> {
    let row = sqlx::query("SELECT version_num FROM app.alembic_version")
        .fetch_optional(pool)
        .await
        .map_err(|e| format!("schema 'app' cannot be read: {e}"))?;
    let found: String = match row {
        Some(r) => r.get("version_num"),
        None => return Err("schema 'app' has no Alembic revision".to_string()),
    };
    match compare_head(&found, EXPECTED_HEAD) {
        HeadStatus::Current => Ok(()),
        HeadStatus::Ahead => {
            tracing::warn!("schema 'app' is at {found}, newer than this build's {EXPECTED_HEAD}");
            Ok(())
        }
        HeadStatus::Behind | HeadStatus::Unknown => Err(format!(
            "schema 'app' is at {found}, this build needs {EXPECTED_HEAD}: migrate first"
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_revision_is_compared_as_a_number() {
        assert_eq!(compare_head("0041", "0041"), HeadStatus::Current);
        assert_eq!(compare_head("0042", "0041"), HeadStatus::Ahead);
        assert_eq!(compare_head("0040", "0041"), HeadStatus::Behind);
        assert_eq!(
            compare_head("0100", "0041"),
            HeadStatus::Ahead,
            "not a text order"
        );
        assert_eq!(compare_head("abc", "0041"), HeadStatus::Unknown);
    }
}
