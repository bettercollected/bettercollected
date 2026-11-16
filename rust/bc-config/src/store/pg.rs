//! Reading the store from Postgres: `common/settings/loader/source.py`
//! `PgSnapshotSource`.
//!
//! Only the two security-barrier views of the service are read,
//! `settings.v_<service>` (the signed rows whose readers include it) and
//! `settings.v_<service>_manifest` (the whole signed manifest), in one
//! repeatable-read read-only transaction on a connection of their own. The
//! database role is the one the service already connects as (`bc_app` for the
//! backend); it holds SELECT on these two views and nothing else of the store.

use std::collections::BTreeMap;
use std::str::FromStr;
use std::time::Duration;

use serde_json::Value;
use sqlx::postgres::{PgConnectOptions, PgRow};
use sqlx::{Connection, PgConnection, Row as _};

use super::canonical::{Manifest, Row, is_canonical_timestamp};
use super::report::{REPORT_MARK, ServiceState};
use super::runtime::{Fetch, SnapshotSource, SourceUnavailable, StoreError};
use super::verify::RawSnapshot;

const CONNECT_TIMEOUT: Duration = Duration::from_secs(3);
const STATEMENT_TIMEOUT_MS: u64 = 3000;

pub struct PgSource {
    options: PgConnectOptions,
    service: String,
}

impl std::fmt::Debug for PgSource {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "PgSource(service={:?})", self.service)
    }
}

fn valid_service(name: &str) -> bool {
    // the name becomes part of a view name
    (1..=32).contains(&name.len())
        && name.as_bytes()[0].is_ascii_lowercase()
        && name
            .bytes()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_')
}

impl PgSource {
    /// `database_url` as SQLAlchemy writes it (a driver suffix is removed). The
    /// error never quotes the URL.
    pub fn new(database_url: &str, service: &str) -> Result<PgSource, StoreError> {
        if !valid_service(service) {
            return Err(StoreError("invalid service name".into()));
        }
        let options = PgConnectOptions::from_str(&crate::sqlx_url(database_url))
            .map_err(|_| StoreError("DATABASE_URL is not a Postgres URL".into()))?
            .application_name(&format!("bc-settings-{service}"))
            .options([("statement_timeout", STATEMENT_TIMEOUT_MS.to_string())]);
        Ok(PgSource {
            options,
            service: service.to_string(),
        })
    }

    async fn connect(&self) -> Result<PgConnection, SourceUnavailable> {
        match tokio::time::timeout(CONNECT_TIMEOUT, PgConnection::connect_with(&self.options)).await
        {
            Ok(Ok(conn)) => Ok(conn),
            Ok(Err(_)) => Err(SourceUnavailable("connect")),
            Err(_) => Err(SourceUnavailable("timeout")),
        }
    }

    async fn read_all(&self) -> Result<RawSnapshot, SourceUnavailable> {
        let mut conn = self.connect().await?;
        let service = &self.service;
        let mut tx = conn.begin().await.map_err(|_| SourceUnavailable("query"))?;
        sqlx::query("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            .execute(&mut *tx)
            .await
            .map_err(|_| SourceUnavailable("query"))?;
        let manifest = sqlx::query(&format!(
            "SELECT revision, entries, sig FROM settings.v_{service}_manifest"
        ))
        .fetch_optional(&mut *tx)
        .await
        .map_err(|_| SourceUnavailable("query"))?;
        let records = sqlx::query(&format!(
            "SELECT key, section, readers, is_secret, reload_class, value, blob, \
             version::bigint AS version, \
             to_char(updated_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') AS updated_at, \
             sig FROM settings.v_{service}"
        ))
        .fetch_all(&mut *tx)
        .await
        .map_err(|_| SourceUnavailable("query"))?;
        let _ = tx.rollback().await;
        let _ = conn.close().await;
        let mut raw = RawSnapshot {
            manifest: match manifest {
                Some(record) => Some(build_manifest(&record).ok_or(SourceUnavailable("manifest"))?),
                None => None,
            },
            ..RawSnapshot::default()
        };
        for record in &records {
            if let Some(row) = build_row(record) {
                raw.rows.push(row);
            } else {
                let key: String = record
                    .try_get::<String, _>("key")
                    .unwrap_or_default()
                    .chars()
                    .take(64)
                    .collect();
                let version = record
                    .try_get::<i64, _>("version")
                    .ok()
                    .and_then(|v| u64::try_from(v).ok())
                    .unwrap_or(0);
                raw.malformed.push((key, version));
            }
        }
        Ok(raw)
    }
}

fn build_row(record: &PgRow) -> Option<Row> {
    let updated_at: String = record.try_get("updated_at").ok()?;
    if !is_canonical_timestamp(&updated_at) {
        return None;
    }
    let value: Option<Value> = record.try_get("value").ok()?;
    Some(Row {
        key: record.try_get("key").ok()?,
        section: record.try_get("section").ok()?,
        readers: record.try_get("readers").ok()?,
        is_secret: record.try_get("is_secret").ok()?,
        reload_class: record.try_get("reload_class").ok()?,
        version: u64::try_from(record.try_get::<i64, _>("version").ok()?).ok()?,
        updated_at,
        value: value.filter(|v| !v.is_null()),
        blob: record.try_get("blob").ok()?,
        sig: record
            .try_get::<Option<String>, _>("sig")
            .ok()?
            .unwrap_or_default(),
    })
}

fn build_manifest(record: &PgRow) -> Option<Manifest> {
    let entries: Value = record.try_get("entries").ok()?;
    let revision = u64::try_from(record.try_get::<i64, _>("revision").ok()?).ok()?;
    let sig: Option<String> = record.try_get("sig").ok()?;
    let mut manifest = super::disk::manifest_from(&serde_json::json!({
        "revision": revision,
        "entries": entries,
        "sig": sig.unwrap_or_default(),
    }))?;
    // `dict(_loads(entries) or {})`: an empty object stays empty
    if entries.is_null() {
        manifest.entries = BTreeMap::new();
    }
    Some(manifest)
}

impl SnapshotSource for PgSource {
    fn fetch(&self) -> Fetch<'_, RawSnapshot> {
        Box::pin(async move {
            tokio::time::timeout(
                CONNECT_TIMEOUT
                    + Duration::from_millis(STATEMENT_TIMEOUT_MS)
                    + Duration::from_secs(2),
                self.read_all(),
            )
            .await
            .unwrap_or(Err(SourceUnavailable("timeout")))
        })
    }

    fn fetch_revision(&self) -> Fetch<'_, Option<u64>> {
        Box::pin(async move {
            let work = async {
                let mut conn = self.connect().await?;
                let row = sqlx::query(&format!(
                    "SELECT revision FROM settings.v_{}_manifest",
                    self.service
                ))
                .fetch_optional(&mut conn)
                .await
                .map_err(|_| SourceUnavailable("query"))?;
                let _ = conn.close().await;
                Ok(match row {
                    Some(r) => r
                        .try_get::<i64, _>("revision")
                        .ok()
                        .and_then(|v| u64::try_from(v).ok()),
                    None => None,
                })
            };
            tokio::time::timeout(
                CONNECT_TIMEOUT
                    + Duration::from_millis(STATEMENT_TIMEOUT_MS)
                    + Duration::from_secs(2),
                work,
            )
            .await
            .unwrap_or(Err(SourceUnavailable("timeout")))
        })
    }

    fn report_state(&self, instance: &str, state: &ServiceState) -> Fetch<'_, ()> {
        let instance = instance.to_string();
        let state = state.clone();
        Box::pin(async move {
            let work = async {
                let mut conn = self.connect().await?;
                let revision = i64::try_from(state.revision_applied).unwrap_or(i64::MAX);
                let fingerprint = format!("{}{REPORT_MARK}", state.keyset_fp);
                let seven = sqlx::query(
                    "SELECT settings.report_state($1::text, $2::bigint, $3::text[], $4::text[], \
                     $5::boolean, $6::text, $7::text)",
                )
                .bind(&instance)
                .bind(revision)
                .bind(&state.env_overrides)
                .bind(&state.rejected_keys)
                .bind(state.restart_pending)
                .bind(&fingerprint)
                .bind(&state.write_stores)
                .execute(&mut conn)
                .await;
                let outcome = match seven {
                    Ok(_) => Ok(()),
                    // a store from before admin revision 0018 (rolling deploy): report
                    // without the write stores
                    Err(e) if sqlstate(&e).as_deref() == Some("42883") => sqlx::query(
                        "SELECT settings.report_state($1::text, $2::bigint, $3::text[], \
                         $4::text[], $5::boolean, $6::text)",
                    )
                    .bind(&instance)
                    .bind(revision)
                    .bind(&state.env_overrides)
                    .bind(&state.rejected_keys)
                    .bind(state.restart_pending)
                    .bind(&fingerprint)
                    .execute(&mut conn)
                    .await
                    .map(|_| ())
                    .map_err(|e| report_failure(&e)),
                    Err(e) => Err(report_failure(&e)),
                };
                let _ = conn.close().await;
                outcome
            };
            tokio::time::timeout(
                CONNECT_TIMEOUT
                    + Duration::from_millis(STATEMENT_TIMEOUT_MS)
                    + Duration::from_secs(2),
                work,
            )
            .await
            .unwrap_or(Err(SourceUnavailable("timeout")))
        })
    }
}

fn sqlstate(error: &sqlx::Error) -> Option<String> {
    error
        .as_database_error()
        .and_then(sqlx::error::DatabaseError::code)
        .map(|c| c.to_string())
}

/// A reason that is the same for every failure of its kind, never the server's text.
fn report_failure(error: &sqlx::Error) -> SourceUnavailable {
    match sqlstate(error).as_deref() {
        Some("42501") => SourceUnavailable(
            "no permission to report (not a settings reader, or no EXECUTE on settings.report_state)",
        ),
        Some("42883") => SourceUnavailable("settings.report_state does not exist"),
        Some(_) => SourceUnavailable("the store refused the report"),
        None => SourceUnavailable("query"),
    }
}
