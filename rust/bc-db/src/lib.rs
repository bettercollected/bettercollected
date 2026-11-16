//! The database side every service of this workspace shares: the pool and the
//! startup check of the schema revision, the document codec, the generic record
//! repository and the clock. This workspace owns no schema and runs no
//! migrations: the Python backend's Alembic chain does.
//!
//! * [`canonical`]: the canonical bytes of a `doc` and its `_bc_checksum`, as
//!   Python writes them;
//! * [`codec`]: [`codec::Record`], and what a write puts in a row;
//! * [`repo`]: [`repo::Db`], the repository (get, list with a keyset, insert,
//!   upsert, `set_fields`, delete with tombstones, `FOR UPDATE`, advisory locks);
//! * [`stamp`], [`id`], [`value`]: the document's datetimes, ids and lax reads;
//! * [`clock`]: the one clock; [`settings`]: the pool and its timeouts;
//! * [`records`]: typed documents of the tables the first route groups use.

pub mod canonical;
pub mod clock;
pub mod codec;
pub mod error;
pub mod id;
pub mod records;
pub mod repo;
pub mod settings;
pub mod stamp;
pub mod value;

pub use clock::{Clock, FixedClock, SharedClock, SystemClock};
pub use codec::Record;
pub use error::DbError;
pub use id::RecordId;
pub use repo::{Db, Filter, Keyset, Order, Page};
pub use settings::{DbSettings, connect_with};

use sqlx::Row;
use sqlx::postgres::PgPool;

/// The Alembic revision of schema `app` this build was written against. Move
/// it only together with a review of every query for the migrations in
/// between (migrations are expand-only, so a build keeps running on a newer
/// schema, but it knows nothing of what that schema added).
pub const EXPECTED_HEAD: &str = "0041";

/// Opens the pool. The error can quote the connection string, so the caller
/// must not print it.
///
/// Every connection carries the Python engine's server-side timeouts
/// (`statement_timeout` 30 s, `lock_timeout` 5 s, `idle_in_transaction` 60 s,
/// each overridable by the `DB_*` names through [`DbSettings`]).
pub async fn connect(url: &str, max_connections: u32) -> Result<PgPool, sqlx::Error> {
    let mut settings = DbSettings::new("bc-api");
    settings.max_connections = max_connections;
    connect_with(url, &settings).await
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
