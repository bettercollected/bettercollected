//! Connection settings, with the timeouts the Python engine sets
//! (`common/db/engine.py`): applied by the server on every connection, so no
//! request, worker or migration can hold a statement, a lock or an idle
//! transaction indefinitely.

use std::str::FromStr;
use std::time::Duration;

use sqlx::postgres::{PgConnectOptions, PgPool, PgPoolOptions};

/// Python: pool of 5 and an overflow of 5.
pub const DEFAULT_POOL_SIZE: u32 = 5;
pub const DEFAULT_MAX_OVERFLOW: u32 = 5;
pub const DEFAULT_POOL_TIMEOUT_S: u64 = 10;
pub const DEFAULT_STATEMENT_TIMEOUT_MS: u64 = 30_000;
pub const DEFAULT_LOCK_TIMEOUT_MS: u64 = 5_000;
pub const DEFAULT_IDLE_IN_TRANSACTION_MS: u64 = 60_000;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DbSettings {
    pub max_connections: u32,
    pub acquire_timeout: Duration,
    pub statement_timeout_ms: u64,
    pub lock_timeout_ms: u64,
    pub idle_in_transaction_ms: u64,
    pub application_name: String,
}

impl DbSettings {
    pub fn new(application_name: &str) -> Self {
        Self {
            max_connections: DEFAULT_POOL_SIZE + DEFAULT_MAX_OVERFLOW,
            acquire_timeout: Duration::from_secs(DEFAULT_POOL_TIMEOUT_S),
            statement_timeout_ms: DEFAULT_STATEMENT_TIMEOUT_MS,
            lock_timeout_ms: DEFAULT_LOCK_TIMEOUT_MS,
            idle_in_transaction_ms: DEFAULT_IDLE_IN_TRANSACTION_MS,
            application_name: application_name.to_string(),
        }
    }

    /// The Python names: `DB_POOL_SIZE` + `DB_MAX_OVERFLOW`,
    /// `DB_POOL_TIMEOUT_S`, `DB_STATEMENT_TIMEOUT_MS`, `DB_LOCK_TIMEOUT_MS`,
    /// `DB_IDLE_IN_TRANSACTION_MS`. An empty value is unset; one that is not a
    /// number is an error (as in Python).
    pub fn from_lookup(
        application_name: &str,
        get: impl Fn(&str) -> Option<String>,
    ) -> Result<Self, String> {
        fn number(
            get: &impl Fn(&str) -> Option<String>,
            key: &str,
            default: u64,
        ) -> Result<u64, String> {
            match get(key).filter(|v| !v.is_empty()) {
                None => Ok(default),
                Some(raw) => raw
                    .trim()
                    .parse()
                    .map_err(|_| format!("{key} must be an integer")),
            }
        }
        let pool = number(&get, "DB_POOL_SIZE", u64::from(DEFAULT_POOL_SIZE))?;
        let overflow = number(&get, "DB_MAX_OVERFLOW", u64::from(DEFAULT_MAX_OVERFLOW))?;
        Ok(Self {
            max_connections: u32::try_from(pool + overflow)
                .map_err(|_| "pool size too large".to_string())?
                .max(1),
            acquire_timeout: Duration::from_secs(number(
                &get,
                "DB_POOL_TIMEOUT_S",
                DEFAULT_POOL_TIMEOUT_S,
            )?),
            statement_timeout_ms: number(
                &get,
                "DB_STATEMENT_TIMEOUT_MS",
                DEFAULT_STATEMENT_TIMEOUT_MS,
            )?,
            lock_timeout_ms: number(&get, "DB_LOCK_TIMEOUT_MS", DEFAULT_LOCK_TIMEOUT_MS)?,
            idle_in_transaction_ms: number(
                &get,
                "DB_IDLE_IN_TRANSACTION_MS",
                DEFAULT_IDLE_IN_TRANSACTION_MS,
            )?,
            application_name: application_name.to_string(),
        })
    }

    /// The server settings sent at connection start.
    pub fn server_options(&self) -> Vec<(&'static str, String)> {
        vec![
            ("statement_timeout", self.statement_timeout_ms.to_string()),
            ("lock_timeout", self.lock_timeout_ms.to_string()),
            (
                "idle_in_transaction_session_timeout",
                self.idle_in_transaction_ms.to_string(),
            ),
        ]
    }
}

/// Opens a pool whose every connection carries the timeouts. The error can
/// quote the connection string, so the caller must not print it.
pub async fn connect_with(url: &str, settings: &DbSettings) -> Result<PgPool, sqlx::Error> {
    let options = PgConnectOptions::from_str(url)?
        .application_name(&settings.application_name)
        .options(settings.server_options());
    PgPoolOptions::new()
        .max_connections(settings.max_connections)
        .acquire_timeout(settings.acquire_timeout)
        .connect_with(options)
        .await
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn lookup(pairs: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> {
        let map: HashMap<String, String> = pairs
            .iter()
            .map(|(k, v)| ((*k).into(), (*v).into()))
            .collect();
        move |k| map.get(k).cloned()
    }

    #[test]
    fn the_defaults_are_the_python_engines() {
        let s = DbSettings::from_lookup("bc-api", lookup(&[])).unwrap();
        assert_eq!(s.max_connections, 10);
        assert_eq!(s.statement_timeout_ms, 30_000);
        assert_eq!(s.lock_timeout_ms, 5_000);
        assert_eq!(s.idle_in_transaction_ms, 60_000);
        assert_eq!(s.acquire_timeout, Duration::from_secs(10));
        assert_eq!(
            s.server_options()[0],
            ("statement_timeout", "30000".to_string())
        );
    }

    #[test]
    fn the_python_names_override() {
        let s = DbSettings::from_lookup(
            "x",
            lookup(&[
                ("DB_POOL_SIZE", "2"),
                ("DB_MAX_OVERFLOW", "1"),
                ("DB_LOCK_TIMEOUT_MS", ""),
                ("DB_STATEMENT_TIMEOUT_MS", "100"),
            ]),
        )
        .unwrap();
        assert_eq!(
            (s.max_connections, s.statement_timeout_ms, s.lock_timeout_ms),
            (3, 100, 5_000)
        );
        assert!(DbSettings::from_lookup("x", lookup(&[("DB_POOL_SIZE", "many")])).is_err());
    }
}
