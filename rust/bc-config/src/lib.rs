//! Configuration of the Rust services, read by the variable names the Python
//! backend uses.
//!
//! The pieces:
//!
//! * [`source`]: where a value comes from: the process environment, then the
//!   settings store of the Python services ([`source::StoreSource`]), then the
//!   caller's default. Layers of [`source::Settings`]; no reader below knows which
//!   one answered.
//! * [`store`]: the settings store reader: verified, signed rows of the admin
//!   settings store (schema `settings`), secrets opened with keys derived from
//!   `SETTINGS_MASTER_KEY`, exactly as `common/settings` does for the backend.
//!   [`Config::load`] reads it at start; class H values stay readable live.
//! * [`secrets`]: key rings and the refusal of unset or published secrets, the
//!   rules of `common/configs/shipped_secrets.py` and
//!   `common/settings/key_ring.py`.
//! * [`flags`]: the feature switches the API reports.
//! * [`network`]: the proxy trust settings behind the client address.
//! * [`edge`]: the edge's own settings (`BC_*`): the Python upstream, the
//!   per-group switch, timeouts.
//!
//! A value that is empty counts as unset, one pair of matching quotes is
//! removed, and a secret never has a default.

pub mod edge;
pub mod flags;
pub mod network;
pub mod secrets;
pub mod source;
pub mod store;

use std::collections::HashMap;
use std::fmt;
use std::sync::Arc;

pub use edge::EdgeConfig;
pub use flags::Flags;
pub use network::NetworkConfig;
pub use secrets::{KeyRing, Secret};
pub use source::{
    EnvSource, MapSource, Origin, Settings, SettingsSource, StoreSource, StoreStatus,
};
pub use store::{StoreError, StoreRuntime};

/// A configuration problem. The text names a variable, never a value.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConfigError(pub String);

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for ConfigError {}

/// Everything a Rust service of this workspace needs to start.
#[derive(Clone)]
pub struct Config {
    /// `DATABASE_URL`, as sqlx reads it (the driver suffix is removed). It
    /// can hold a password: it is never printed.
    pub database_url: Secret,
    /// `AUTH_JWT_SECRET` as a key ring: every member verifies, the first signs.
    pub jwt_ring: KeyRing,
    /// `AUTH_AES_HEX_KEY` (a Fernet key ring), when set. Services that need it
    /// check for it themselves.
    pub fernet_ring: Option<KeyRing>,
    pub flags: Flags,
    pub sso_enabled: bool,
    pub totp_enabled: bool,
    /// Where each switch (`SSO_ENABLED`, `TOTP_ENABLED` and the feature switches)
    /// got its value, or why it is only a default. A decision that depends on a
    /// switch must not be taken from one whose origin is
    /// [`Origin::DefaultStoreUnavailable`]: Python may hold another value.
    pub origins: std::collections::BTreeMap<&'static str, Origin>,
    /// What became of the settings store at start (the reason for an unknown origin).
    pub store_status: StoreStatus,
    /// The settings store this configuration was read with; `None` when the
    /// store is off. Class H settings are read live through
    /// [`StoreRuntime::live_value`].
    pub store: Option<Arc<StoreRuntime>>,
    pub network: NetworkConfig,
    pub edge: EdgeConfig,
    pub bind: String,
    pub pool_max: u32,
}

impl fmt::Debug for Config {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // never prints the database URL or a secret
        f.debug_struct("Config")
            .field("jwt_ring_members", &self.jwt_ring.len())
            .field("flags", &self.flags)
            .field("store", &self.store)
            .field("store_status", &self.store_status)
            .field("network", &self.network)
            .field("edge", &self.edge)
            .field("bind", &self.bind)
            .finish_non_exhaustive()
    }
}

/// SQLAlchemy URLs name a driver (`postgresql+asyncpg://`); sqlx does not.
pub fn sqlx_url(url: &str) -> String {
    match url.split_once("://") {
        Some((scheme, rest)) => {
            let base = scheme.split('+').next().unwrap_or(scheme);
            let base = if base == "postgresql" {
                "postgres"
            } else {
                base
            };
            format!("{base}://{rest}")
        }
        None => url.to_string(),
    }
}

/// What the backend cannot start without when its store is `required` and empty
/// (`backend/config/application.py`).
pub const REQUIRED_ENV_KEYS: &[&str] = &["AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY"];

impl Config {
    /// From the process environment only: the settings store is not read.
    pub fn from_env() -> Result<Config, ConfigError> {
        Config::from_settings(&Settings::from_env())
    }

    /// From the process environment and the settings store, as the Python backend
    /// resolves its settings: a non-empty environment value, then the verified
    /// store value, then the default. Refuses to start where Python does
    /// (`SETTINGS_STORE=required` and a store that cannot be trusted).
    pub async fn load() -> Result<Config, ConfigError> {
        Config::load_with(
            std::env::vars().collect(),
            None,
            secrets::SHIPPED_SECRET_SHA256,
        )
        .await
    }

    /// `load` with the environment, the store's source and the list of published
    /// secrets given (tests, the harness).
    pub async fn load_with(
        env: HashMap<String, String>,
        source: Option<Box<dyn store::SnapshotSource>>,
        denylist: &[&str],
    ) -> Result<Config, ConfigError> {
        // the store's own messages already begin with "settings store"
        let named = |e: StoreError| {
            ConfigError(if e.0.starts_with("settings") {
                e.0
            } else {
                format!("settings store: {}", e.0)
            })
        };
        let runtime = store::load(
            &env,
            store::registry::Registry::shipped(),
            source,
            REQUIRED_ENV_KEYS,
        )
        .await
        .map_err(named)?;
        let status = match &runtime {
            Some(runtime) => runtime.status(),
            None => StoreStatus::Unavailable(store::runtime::why_inactive(&env)),
        };
        let mut layers: Vec<Box<dyn SettingsSource>> = vec![Box::new(MapSource::new(env))];
        if let Some(runtime) = &runtime {
            let values = runtime.freeze().map_err(named)?;
            layers.push(Box::new(StoreSource::new(values)));
        }
        let mut cfg = Config::from_settings_with_denylist(
            &Settings::new(layers).with_store_status(status),
            denylist,
        )?;
        cfg.store = runtime;
        Ok(cfg)
    }

    /// The two policy switches whose origin is unknown here (neither in the
    /// environment nor read from a verified store or snapshot), with the reason.
    /// A route group whose answers depend on `SSO_ENABLED` and `TOTP_ENABLED`
    /// (`bc_api::groups::Group::needs_policy_switches`) is served by Rust only when
    /// this is empty: otherwise Python, which may read them from the store, decides.
    pub fn unknown_policy_switches(&self) -> Vec<(&'static str, String)> {
        let why = match &self.store_status {
            StoreStatus::Unavailable(why) => why.clone(),
            _ => String::new(),
        };
        ["SSO_ENABLED", "TOTP_ENABLED"]
            .into_iter()
            .filter(|name| !self.origins.get(name).is_some_and(|o| o.is_known()))
            .map(|name| (name, why.clone()))
            .collect()
    }

    pub fn from_settings(settings: &Settings) -> Result<Config, ConfigError> {
        Config::from_settings_with_denylist(settings, secrets::SHIPPED_SECRET_SHA256)
    }

    /// `from_settings` with the list of published secrets (SHA-256 digests)
    /// given: the shipped list in production, a made-up one in tests.
    pub fn from_settings_with_denylist(
        settings: &Settings,
        denylist: &[&str],
    ) -> Result<Config, ConfigError> {
        // The Python services refuse to start without a signing secret and
        // never fall back to a default one; so does this one.
        let jwt_value = settings.get("AUTH_JWT_SECRET");
        let fernet_value = settings.get_any(&["AUTH_AES_HEX_KEY", "AES_HEX_KEY"]);
        let problems = secrets::secret_problems(
            &[("AUTH_JWT_SECRET", jwt_value.as_deref())],
            // the Fernet key is optional here: checked only when it is set
            &fernet_value
                .as_deref()
                .map(|v| vec![("AUTH_AES_HEX_KEY", Some(v))])
                .unwrap_or_default(),
            denylist,
        );
        if !problems.is_empty() {
            return Err(ConfigError(format!(
                "refusing to start: {}",
                problems.join("; ")
            )));
        }
        let jwt_ring = KeyRing::from_members(secrets::token_members(jwt_value.as_deref()));
        let fernet_ring = fernet_value
            .as_deref()
            .map(|v| KeyRing::from_members(secrets::fernet_members(Some(v))));
        let database_url = settings
            .get("DATABASE_URL")
            .ok_or_else(|| ConfigError("DATABASE_URL is not set".to_string()))?;
        let pool_max =
            match settings.get("BC_API_DB_POOL_MAX") {
                Some(v) => v.parse::<u32>().ok().filter(|n| *n >= 1).ok_or_else(|| {
                    ConfigError("BC_API_DB_POOL_MAX is not a positive number".into())
                })?,
                None => 10,
            };
        Ok(Config {
            database_url: Secret::new(sqlx_url(&database_url)),
            jwt_ring,
            fernet_ring,
            flags: Flags::from_settings(settings)?,
            sso_enabled: settings.flag("SSO_ENABLED")?.unwrap_or(false),
            totp_enabled: settings.flag("TOTP_ENABLED")?.unwrap_or(false),
            origins: std::iter::once("SSO_ENABLED")
                .chain(std::iter::once("TOTP_ENABLED"))
                .chain(flags::NAMES.iter().copied())
                .map(|name| (name, settings.origin(name)))
                .collect(),
            store_status: settings.store_status().clone(),
            store: None,
            network: NetworkConfig::from_settings(settings)?,
            edge: EdgeConfig::from_settings(settings)?,
            bind: settings
                .get("BC_API_BIND")
                .unwrap_or_else(|| "127.0.0.1:8080".to_string()),
            pool_max,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    pub(crate) fn settings(pairs: &[(&str, &str)]) -> Settings {
        Settings::from_map(
            pairs
                .iter()
                .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
                .collect(),
        )
    }

    fn valid<'a>(extra: &[(&'a str, &'a str)]) -> Vec<(&'a str, &'a str)> {
        let mut v = vec![
            ("DATABASE_URL", "postgresql://user:hunter2@h/d"),
            (
                "AUTH_JWT_SECRET",
                "0123456789abcdef0123456789abcdef0123456789",
            ),
            ("BC_PYTHON_UPSTREAM", "http://backend:8000"),
        ];
        v.extend_from_slice(extra);
        v
    }

    #[test]
    fn refuses_to_start_without_a_secret() {
        let err = Config::from_settings(&settings(&[
            ("DATABASE_URL", "postgresql://x/y"),
            ("BC_PYTHON_UPSTREAM", "http://b:1"),
        ]))
        .unwrap_err();
        assert!(err.0.contains("AUTH_JWT_SECRET is not set"), "{err}");
        let err = Config::from_settings(&settings(&[
            ("DATABASE_URL", "postgresql://x/y"),
            ("AUTH_JWT_SECRET", "  \"\"  "),
        ]))
        .unwrap_err();
        assert!(err.0.contains("AUTH_JWT_SECRET"), "{err}");
    }

    #[test]
    fn refuses_a_published_secret_without_naming_it() {
        // the real list holds digests only; a made-up value stands in for a
        // published one by putting its digest on the list
        let published = "made-up-published-secret-0123456789abcdef";
        let digest = secrets::sha256_hex(published);
        let err = Config::from_settings_with_denylist(
            &settings(&[
                ("DATABASE_URL", "postgresql://x/y"),
                ("AUTH_JWT_SECRET", published),
                ("BC_PYTHON_UPSTREAM", "http://b:1"),
            ]),
            &[digest.as_str()],
        )
        .unwrap_err();
        assert!(err.0.contains("published"), "{err}");
        assert!(!err.0.contains(published));
    }

    #[test]
    fn a_missing_database_url_stops_the_start() {
        let err = Config::from_settings(&settings(&[(
            "AUTH_JWT_SECRET",
            "0123456789abcdef0123456789abcdef0123456789",
        )]))
        .unwrap_err();
        assert!(err.0.contains("DATABASE_URL"));
    }

    #[test]
    fn database_url_loses_the_driver() {
        assert_eq!(
            sqlx_url("postgresql+asyncpg://u:p@h:1/d"),
            "postgres://u:p@h:1/d"
        );
        assert_eq!(sqlx_url("postgres://u@h/d"), "postgres://u@h/d");
    }

    #[test]
    fn a_valid_configuration_has_safe_defaults() {
        let cfg = Config::from_settings(&settings(&valid(&[]))).unwrap();
        assert_eq!(cfg.bind, "127.0.0.1:8080");
        assert_eq!(cfg.pool_max, 10);
        assert!(
            cfg.edge.rust_routes.is_empty(),
            "nothing is served by Rust unless named"
        );
        assert!(
            cfg.network.trusted_proxies.is_empty(),
            "no proxy is trusted by default"
        );
        assert!(!cfg.flags.captcha);
    }

    #[test]
    fn config_debug_never_shows_secrets() {
        let cfg = Config::from_settings(&settings(&valid(&[]))).unwrap();
        let shown = format!("{cfg:?}");
        assert!(!shown.contains("hunter2"), "{shown}");
        assert!(!shown.contains("0123456789abcdef"), "{shown}");
    }

    #[test]
    fn pool_size_must_be_a_positive_number() {
        for bad in ["0", "x", "-1"] {
            let err = Config::from_settings(&settings(&valid(&[("BC_API_DB_POOL_MAX", bad)])))
                .unwrap_err();
            assert!(err.0.contains("BC_API_DB_POOL_MAX"));
        }
    }
}
