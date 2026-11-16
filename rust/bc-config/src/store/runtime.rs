//! The loader: one verified snapshot of the store per process, and the rules for
//! when the service may start on it: `common/settings/loader/{config,runtime,live,poller}.py`.
//!
//! Resolution order for a setting is the environment (set and non-empty after
//! trimming one pair of quotes), then the verified store row, then the code
//! default (the callers' own). Failure policy, as in Python:
//!
//! * Reachable store, bad row: the row is refused and the last good value (from
//!   this process) is kept; a key never accepted falls back to its default (a
//!   secret has none). The disk snapshot is not consulted.
//! * Critical keys (secrets, tier T3 and T4) that were rejected, with no last
//!   good value and nothing in the environment, stop a `required` service at
//!   start-up. After start-up nothing stops the service.
//! * A stored secret that cannot be opened, with no environment value, is
//!   refused (the setting is unset); only `required` stops the service.
//! * Unreachable store: the signed disk snapshot, re-verified and not older than
//!   `SETTINGS_SNAPSHOT_MAX_AGE_DAYS`. With no usable snapshot a `required`
//!   service starts only if the environment holds every key it cannot run
//!   without.
//! * The highest manifest revision and row versions seen (also seeded from the
//!   disk snapshot) are never accepted downwards; a `required` service refuses to
//!   start on a store below the floor its own snapshot recorded, and on a
//!   never-written store while the environment lacks a key it expects there.
//! * Class R settings are read once, at start; only class H settings, which are
//!   not secret, are read live (`live_value`), and a poller applies new revisions.
//!
//! Messages name keys and versions, never values.

use std::collections::{HashMap, HashSet};
use std::fmt;
use std::future::Future;
use std::path::PathBuf;
use std::pin::Pin;
use std::sync::{Arc, Mutex, MutexGuard, PoisonError};
use std::time::{Duration, Instant, SystemTime};

use super::crypto::SectionKeys;
use super::disk;
use super::registry::{Registry, Reload, coerce};
use super::report::{self, ServiceState};
use super::verify::{
    RawSnapshot, Rejection, Tracker, UNTRUSTED, Verification, VerifiedSettings, verify_snapshot,
};
use crate::source::{Settings, StoreStatus};

/// The setting that holds the keyset the service decrypts responses with.
const KEYSET: &str = "MASTER_ENCRYPTION_KEYSET";
/// A fresh report (heartbeat) every this long, as the Python poller does.
const HEARTBEAT: Duration = Duration::from_secs(60);

/// The service must not start. The message names keys, never values.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoreError(pub String);

impl fmt::Display for StoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for StoreError {}

/// The store could not be read (connection, timeout, permission, schema). The
/// message never holds a value or connection details.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SourceUnavailable(pub &'static str);

pub type Fetch<'a, T> = Pin<Box<dyn Future<Output = Result<T, SourceUnavailable>> + Send + 'a>>;

/// Where a loader gets its rows.
pub trait SnapshotSource: Send + Sync {
    /// The rows visible to the service and the whole signed manifest, read in
    /// one consistent transaction.
    fn fetch(&self) -> Fetch<'_, RawSnapshot>;
    /// The manifest revision only (cheap).
    fn fetch_revision(&self) -> Fetch<'_, Option<u64>>;
    /// Tells the store what this process applied (`settings.report_state`). A
    /// source that has nowhere to report (a test double) accepts it.
    fn report_state(&self, _instance: &str, _state: &ServiceState) -> Fetch<'_, ()> {
        Box::pin(async { Ok(()) })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Off,
    Auto,
    Required,
}

/// `SETTINGS_STORE` and its companions, all read from the environment only.
#[derive(Clone)]
pub struct LoaderConfig {
    pub mode: Mode,
    pub database_url: String,
    pub master_key: String,
    pub master_key_previous: String,
    pub snapshot_dir: PathBuf,
    pub snapshot_dir_explicit: bool,
    pub snapshot_max_age_days: f64,
    pub retries: u32,
    pub total_budget: Duration,
    pub poll_interval: Duration,
    pub poll_jitter: Duration,
}

impl fmt::Debug for LoaderConfig {
    // never the URL (credentials) or a key
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "LoaderConfig(mode={:?})", self.mode)
    }
}

impl LoaderConfig {
    pub fn configured(&self) -> bool {
        !self.database_url.is_empty() && !self.master_key.is_empty()
    }

    /// Whether the store is read at all.
    pub fn active(&self) -> bool {
        self.mode == Mode::Required || (self.mode == Mode::Auto && self.configured())
    }

    pub fn from_env(env: &Settings) -> Result<LoaderConfig, StoreError> {
        let text = |name: &str| env.get(name).unwrap_or_default();
        let mode = match text("SETTINGS_STORE").to_lowercase().as_str() {
            "" | "auto" => Mode::Auto,
            "off" => Mode::Off,
            "required" => Mode::Required,
            _ => {
                return Err(StoreError(
                    "SETTINGS_STORE must be off, auto or required".into(),
                ));
            }
        };
        let explicit = text("SETTINGS_SNAPSHOT_DIR");
        let snapshot_dir = if explicit.is_empty() {
            std::env::temp_dir().join(format!("bc-settings-{}", disk_uid()))
        } else {
            PathBuf::from(&explicit)
        };
        let age = text("SETTINGS_SNAPSHOT_MAX_AGE_DAYS");
        let snapshot_max_age_days = if age.is_empty() {
            7.0
        } else {
            let days: f64 = age.parse().map_err(|_| {
                StoreError("SETTINGS_SNAPSHOT_MAX_AGE_DAYS must be a number".into())
            })?;
            if !days.is_finite() || days < 1.0 {
                return Err(StoreError(
                    "SETTINGS_SNAPSHOT_MAX_AGE_DAYS must be at least 1".into(),
                ));
            }
            days
        };
        Ok(LoaderConfig {
            mode,
            database_url: text("DATABASE_URL"),
            master_key: text("SETTINGS_MASTER_KEY"),
            master_key_previous: text("SETTINGS_MASTER_KEY_PREVIOUS"),
            snapshot_dir_explicit: !explicit.is_empty(),
            snapshot_dir,
            snapshot_max_age_days,
            retries: 3,
            total_budget: Duration::from_secs(10),
            poll_interval: Duration::from_secs(10),
            poll_jitter: Duration::from_secs(3),
        })
    }
}

fn disk_uid() -> u32 {
    use std::os::unix::fs::MetadataExt;
    std::fs::metadata("/proc/self").map_or(0, |m| m.uid())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Origin {
    None,
    Store,
    Snapshot,
}

struct State {
    /// Why the store is not the source of this process's values (when it is not).
    reason: String,
    tracker: Tracker,
    current: VerifiedSettings,
    origin: Origin,
    restart_pending: bool,
    seen_revision: Option<u64>,
    last_rejections: Vec<Rejection>,
    logged: HashSet<(String, u64, String)>,
    /// The last report reached the store (or none was tried yet).
    report_ok: bool,
}

pub struct StoreRuntime {
    pub config: LoaderConfig,
    registry: &'static Registry,
    keys: Option<SectionKeys>,
    env: Settings,
    required_env_keys: Vec<String>,
    source: Option<Box<dyn SnapshotSource>>,
    critical: HashSet<String>,
    state: Mutex<State>,
}

impl fmt::Debug for StoreRuntime {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "StoreRuntime(mode={:?}, revision={})",
            self.config.mode,
            self.revision()
        )
    }
}

fn locked<T>(m: &Mutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(PoisonError::into_inner)
}

impl StoreRuntime {
    pub fn new(
        config: LoaderConfig,
        registry: &'static Registry,
        source: Option<Box<dyn SnapshotSource>>,
        required_env_keys: &[&str],
        env: Settings,
    ) -> Result<StoreRuntime, StoreError> {
        let keys = if config.master_key.is_empty() {
            None
        } else {
            let previous = (!config.master_key_previous.is_empty())
                .then_some(config.master_key_previous.as_str());
            Some(
                SectionKeys::new(&config.master_key, previous, &registry.sections()).map_err(
                    |_| StoreError("SETTINGS_MASTER_KEY (or the previous key) is not valid".into()),
                )?,
            )
        };
        Ok(StoreRuntime {
            critical: registry.critical_keys(),
            config,
            registry,
            keys,
            env,
            required_env_keys: required_env_keys.iter().map(|k| (*k).to_string()).collect(),
            source,
            state: Mutex::new(State {
                reason: "the settings store was not read".into(),
                tracker: Tracker::default(),
                current: VerifiedSettings::default(),
                origin: Origin::None,
                restart_pending: false,
                seen_revision: None,
                last_rejections: Vec::new(),
                logged: HashSet::new(),
                report_ok: true,
            }),
        })
    }

    fn env_has(&self, key: &str) -> bool {
        self.env.get(key).is_some()
    }

    pub fn revision(&self) -> u64 {
        locked(&self.state).current.revision()
    }

    pub fn origin(&self) -> Origin {
        locked(&self.state).origin
    }

    /// What became of the store at start: read and verified, the signed snapshot
    /// standing in, or neither (with the reason).
    pub fn status(&self) -> StoreStatus {
        let state = locked(&self.state);
        match state.origin {
            Origin::Store => StoreStatus::Verified,
            Origin::Snapshot => StoreStatus::Snapshot,
            Origin::None => StoreStatus::Unavailable(state.reason.clone()),
        }
    }

    fn set_reason(&self, why: &str) {
        locked(&self.state).reason = why.to_string();
    }

    pub fn restart_pending(&self) -> bool {
        locked(&self.state).restart_pending
    }

    pub fn rejections(&self) -> Vec<Rejection> {
        locked(&self.state).current.rejections.clone()
    }

    pub fn env_overrides(&self) -> Vec<String> {
        let mut out: Vec<String> = self
            .registry
            .specs()
            .filter(|s| self.env_has(&s.key))
            .map(|s| s.key.clone())
            .collect();
        out.sort();
        out
    }

    fn log_rejections(state: &mut State, rejections: &[Rejection]) {
        for r in rejections {
            let token = (r.key.clone(), r.version, r.reason.to_string());
            if state.logged.len() < 5000 && state.logged.insert(token) {
                tracing::warn!("{}", r.message());
            }
        }
    }

    // ---- verification and application

    /// The verification and whether the manifest was trusted. A store that was
    /// never written (revision 0, no rows) is trusted and empty.
    fn verify(
        &self,
        raw: &RawSnapshot,
        tracker: &Tracker,
    ) -> Result<(Verification, bool), StoreError> {
        if let Some(m) = &raw.manifest
            && m.revision == 0
            && m.sig.is_empty()
            && raw.rows.is_empty()
            && raw.malformed.is_empty()
            && tracker.revision == 0
        {
            return Ok((Verification::default(), true));
        }
        let keys = self.keys.as_ref().ok_or_else(|| {
            StoreError("SETTINGS_MASTER_KEY is required to verify the settings store".into())
        })?;
        let mut v = verify_snapshot(
            &raw.rows,
            raw.manifest.as_ref(),
            keys,
            tracker,
            self.registry,
        );
        let trusted = !v.rejections.iter().any(|r| r.key == UNTRUSTED);
        for (key, version) in &raw.malformed {
            v.rejections.push(Rejection {
                key: key.clone(),
                version: *version,
                reason: "malformed_row",
            });
        }
        Ok((v, trusted))
    }

    fn check_critical(
        &self,
        state: &State,
        rejections: &[Rejection],
        trusted: bool,
    ) -> Result<(), StoreError> {
        let bad: HashSet<&str> = rejections.iter().map(|r| r.key.as_str()).collect();
        let mut failing: Vec<&String> = self
            .critical
            .iter()
            .filter(|k| trusted_filter(trusted, bad.contains(k.as_str())))
            .filter(|k| state.current.get(k).is_none() && !self.env_has(k))
            .collect();
        failing.sort();
        if failing.is_empty() {
            return Ok(());
        }
        let why = if trusted {
            "rows were refused"
        } else {
            "the signed manifest was not trusted"
        };
        Err(StoreError(format!(
            "settings store: {why}; no usable value for critical settings: {}",
            failing
                .iter()
                .map(|k| k.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        )))
    }

    fn apply(
        &self,
        raw: &RawSnapshot,
        startup: bool,
        origin: Origin,
        check: bool,
    ) -> Result<bool, StoreError> {
        let mut state = locked(&self.state);
        let (v, trusted) = self.verify(raw, &state.tracker)?;
        let rejections = v.rejections.clone();
        Self::log_rejections(&mut state, &rejections);
        let required = self.config.mode == Mode::Required;
        if !trusted {
            state.last_rejections.clone_from(&rejections);
            if let Some(m) = &raw.manifest {
                state.seen_revision = Some(m.revision);
            }
            if startup && check && required {
                self.check_critical(&state, &rejections, false)?;
            }
            return Ok(false);
        }
        if startup && check && required {
            self.check_critical(&state, &rejections, true)?;
        }
        let new = VerifiedSettings::new(v.clone(), Some(&state.current));
        state.tracker.commit(v.accepted.values(), v.revision);
        if !startup {
            let old = state.current.clone();
            self.note_restart(&mut state, &old, &new);
        }
        state.seen_revision = Some(v.revision);
        state.current = new;
        state.origin = origin;
        Ok(true)
    }

    fn note_restart(&self, state: &mut State, old: &VerifiedSettings, new: &VerifiedSettings) {
        let keys: HashSet<&str> = old
            .rows()
            .chain(new.rows())
            .map(|r| r.key.as_str())
            .collect();
        for key in keys {
            if old.get(key).map(|r| r.version) == new.get(key).map(|r| r.version) {
                continue;
            }
            // a restart-class key changed: the value read at start is now stale
            // (class H keys are read live, so they never need one)
            if self
                .registry
                .get(key)
                .is_some_and(|s| s.reload == Reload::R)
                && !self.env_has(key)
            {
                if !state.restart_pending {
                    // names a setting, never its value; what Python shows the admin
                    // portal as `restart_pending` (see `state`)
                    tracing::warn!(
                        "settings: {key} changed in the store and is read at start; this process keeps the value it started with until it is restarted"
                    );
                }
                state.restart_pending = true;
            }
        }
    }

    fn write_disk(&self, raw: &RawSnapshot) {
        let Some(manifest) = &raw.manifest else {
            return;
        };
        if manifest.revision == 0 {
            return;
        }
        let state = locked(&self.state);
        let rows: Vec<_> = state
            .current
            .rows()
            .filter(|r| !state.current.stale_keys.contains(&r.key))
            .collect();
        if let Err(e) = disk::write_snapshot(
            &self.config.snapshot_dir,
            &self.registry.service,
            &rows,
            manifest,
            SystemTime::now(),
        ) {
            tracing::warn!("settings snapshot not written ({})", e.0);
        }
    }

    /// Remember the revision and versions of a valid snapshot so a replayed
    /// older store is refused after a restart.
    fn seed_from_disk(&self) {
        let Some(keys) = &self.keys else { return };
        let Ok((raw, _)) = disk::read_snapshot(
            &self.config.snapshot_dir,
            &self.registry.service,
            None,
            SystemTime::now(),
        ) else {
            return;
        };
        let v = verify_snapshot(
            &raw.rows,
            raw.manifest.as_ref(),
            keys,
            &Tracker::default(),
            self.registry,
        );
        if !v.rejections.iter().any(|r| r.key == UNTRUSTED) {
            locked(&self.state)
                .tracker
                .commit(v.accepted.values(), v.revision);
        }
    }

    // ---- start-up

    async fn fetch(&self) -> Result<RawSnapshot, SourceUnavailable> {
        let Some(source) = &self.source else {
            return Err(SourceUnavailable("no source"));
        };
        let start = Instant::now();
        let mut last = SourceUnavailable("unavailable");
        for attempt in 0..self.config.retries.max(1) {
            match source.fetch().await {
                Ok(raw) => return Ok(raw),
                Err(e) => {
                    tracing::warn!(
                        "settings store unavailable ({}), attempt {}",
                        e.0,
                        attempt + 1
                    );
                    last = e;
                }
            }
            let delay = Duration::from_millis(250 * (1 << attempt));
            if attempt + 1 >= self.config.retries
                || start.elapsed() + delay >= self.config.total_budget
            {
                break;
            }
            tokio::time::sleep(delay).await;
        }
        Err(last)
    }

    pub async fn start(&self) -> Result<(), StoreError> {
        let result = self.start_inner().await;
        self.warn_unset_critical();
        result
    }

    fn warn_unset_critical(&self) {
        let state = locked(&self.state);
        let mut unset: Vec<&str> = self
            .registry
            .specs()
            .filter(|s| s.is_secret || s.tier == super::registry::Tier::T3)
            .filter(|s| !self.env_has(&s.key) && state.current.get(&s.key).is_none())
            .map(|s| s.key.as_str())
            .collect();
        unset.sort_unstable();
        if !unset.is_empty() {
            tracing::warn!(
                "settings with no value from the environment or the store ({}): {}",
                unset.len(),
                unset.join(", ")
            );
        }
    }

    async fn start_inner(&self) -> Result<(), StoreError> {
        let cfg = &self.config;
        let required = cfg.mode == Mode::Required;
        if required && !cfg.configured() {
            return Err(StoreError(
                "SETTINGS_STORE=required needs DATABASE_URL and SETTINGS_MASTER_KEY".into(),
            ));
        }
        self.seed_from_disk();
        if required && !cfg.snapshot_dir_explicit {
            tracing::warn!(
                "settings: SETTINGS_SNAPSHOT_DIR is not set, so the rollback floor lives in a \
                 temporary directory and is lost with the container; mount a volume for it"
            );
        }
        if self.source.is_none() {
            self.set_reason("no database to read the settings store from");
            return self.start_without_store("no database");
        }
        let Ok(raw) = self.fetch().await else {
            self.set_reason("the settings store could not be read (no access to its views, or the database is down) and no usable snapshot exists");
            return self.start_from_snapshot();
        };
        self.refuse_rolled_back_store(&raw)?;
        if self.apply(&raw, true, Origin::Store, true)? {
            self.refuse_empty_store()?;
            self.write_disk(&raw);
        } else {
            self.set_reason("the signed manifest of the settings store is not trusted here");
        }
        tracing::info!(
            "settings loaded from the store: revision {}, {} overridden by the environment",
            self.revision(),
            self.env_overrides().len()
        );
        Ok(())
    }

    /// `required`: a store older than this service's own recorded floor is a
    /// restored or replaced database; do not start on it.
    fn refuse_rolled_back_store(&self, raw: &RawSnapshot) -> Result<(), StoreError> {
        let floor = locked(&self.state).tracker.revision;
        match &raw.manifest {
            Some(m) if self.config.mode == Mode::Required && floor > 0 && m.revision < floor => {
                Err(StoreError(format!(
                    "settings store is behind this service's record (store revision {}, recorded \
                     {floor}): the database was restored or replaced. If that is intended, remove \
                     the settings snapshot directory (SETTINGS_SNAPSHOT_DIR) and restart; otherwise \
                     restore the current database",
                    m.revision
                )))
            }
            _ => Ok(()),
        }
    }

    /// `required`: a never-written store (revision 0) is fine for a service whose
    /// environment supplies every key it cannot run without, and a wiped or wrong
    /// database for one that expected the store to hold them.
    fn refuse_empty_store(&self) -> Result<(), StoreError> {
        if self.config.mode != Mode::Required || self.revision() != 0 {
            return Ok(());
        }
        let mut missing: Vec<&str> = self
            .required_env_keys
            .iter()
            .filter(|k| !self.env_has(k))
            .map(String::as_str)
            .collect();
        missing.sort_unstable();
        if missing.is_empty() {
            return Ok(());
        }
        Err(StoreError(format!(
            "settings store is empty (revision 0) but this service expects it to hold: {}. A new \
             stack gets them from bootstrap-keys; an existing one from settings-import; otherwise \
             this is a wiped or wrong database",
            missing.join(", ")
        )))
    }

    fn start_from_snapshot(&self) -> Result<(), StoreError> {
        let read = disk::read_snapshot(
            &self.config.snapshot_dir,
            &self.registry.service,
            Some(self.config.snapshot_max_age_days),
            SystemTime::now(),
        );
        let Ok((raw, saved)) = read else {
            let why = read.err().map_or("snapshot unusable", |e| e.0);
            return self.start_without_store(&format!("snapshot {why}"));
        };
        if !self.apply(&raw, true, Origin::Snapshot, false)? {
            self.set_reason("the settings store could not be read and the snapshot is not trusted");
            return self.start_without_store("snapshot not trusted");
        }
        tracing::warn!(
            "settings store unreachable: using the signed snapshot (revision {}, saved {})",
            self.revision(),
            disk::format_timestamp(
                SystemTime::UNIX_EPOCH + Duration::from_secs(u64::try_from(saved).unwrap_or(0))
            )
            .get(..10)
            .unwrap_or("")
        );
        if self.config.mode == Mode::Required {
            let state = locked(&self.state);
            let rejections = state.current.rejections.clone();
            self.check_critical(&state, &rejections, true)?;
        }
        Ok(())
    }

    fn start_without_store(&self, why: &str) -> Result<(), StoreError> {
        let mut missing: Vec<&str> = self
            .required_env_keys
            .iter()
            .filter(|k| !self.env_has(k))
            .map(String::as_str)
            .collect();
        missing.sort_unstable();
        if self.config.mode == Mode::Required && !missing.is_empty() {
            return Err(StoreError(format!(
                "settings store unavailable ({why}) and the environment does not supply: {}",
                missing.join(", ")
            )));
        }
        tracing::warn!("settings store not used ({why}): environment and defaults only");
        Ok(())
    }

    // ---- resolution

    /// The store's value for `key` as text when the store is the source, else
    /// `None` (the environment, a key the store does not serve, a row that
    /// cannot be used). `Err` only where Python stops the service: a `required`
    /// service and a critical key whose stored value is unusable.
    pub fn resolve_key(&self, key: &str) -> Result<Option<String>, StoreError> {
        let Some(spec) = self.registry.get(key) else {
            return Ok(None);
        };
        if !spec.store_backed || self.env_has(key) {
            return Ok(None);
        }
        let row = {
            let state = locked(&self.state);
            match state.current.get(key) {
                Some(row) => row.clone(),
                None => return Ok(None),
            }
        };
        let Some(keys) = &self.keys else {
            return Ok(None);
        };
        let outcome: Result<String, &'static str> = if spec.is_secret {
            match &row.blob {
                Some(blob) => keys
                    .open(&row.section, &row.key, row.version, blob)
                    .ok_or("cannot open the stored secret"),
                None => Err("cannot open the stored secret"),
            }
        } else {
            coerce(spec, row.value.as_ref().unwrap_or(&serde_json::Value::Null))
                .map_err(|_| "stored value is invalid")
        };
        match outcome {
            Ok(value) => Ok(Some(value)),
            Err(why) => {
                let token = (key.to_string(), row.version, "unusable".to_string());
                if locked(&self.state).logged.insert(token) {
                    // refused: the setting falls back to its default (empty for a
                    // secret), never to a value from elsewhere
                    tracing::error!("{key}: {why}; refused, the code default applies");
                }
                if self.config.mode == Mode::Required && self.critical.contains(key) {
                    return Err(StoreError(format!(
                        "settings store: no usable value for critical setting {key}"
                    )));
                }
                Ok(None)
            }
        }
    }

    /// Every store-backed key resolved once, as Python's settings classes do when
    /// they are built at import: the values class R settings keep until restart.
    pub fn freeze(&self) -> Result<HashMap<String, String>, StoreError> {
        let mut out = HashMap::new();
        let mut keys: Vec<&str> = self
            .registry
            .specs()
            .filter(|s| s.store_backed)
            .map(|s| s.key.as_str())
            .collect();
        keys.sort_unstable();
        for key in keys {
            if let Some(value) = self.resolve_key(key)? {
                out.insert(key.to_string(), value);
            }
        }
        Ok(out)
    }

    /// The live value of a hot (class H), non-secret key whose row is verified and
    /// not overridden by the environment; `None` otherwise (use the value read at
    /// start).
    pub fn live_value(&self, key: &str) -> Option<String> {
        let spec = self.registry.get(key)?;
        if spec.reload != Reload::H || spec.is_secret || !spec.store_backed || self.env_has(key) {
            return None;
        }
        let state = locked(&self.state);
        let row = state.current.get(key)?;
        coerce(spec, row.value.as_ref()?).ok()
    }

    // ---- reporting

    /// The key ids the service holds, as a fingerprint (`keyset_fp`): the ids of
    /// `MASTER_ENCRYPTION_KEYSET` (environment, else the verified store row); a
    /// process without a usable keyset reports the fingerprint of the settings
    /// master key, as a Python service does.
    fn keyset_fp(&self) -> String {
        let value = self
            .env
            .get(KEYSET)
            .or_else(|| self.resolve_key(KEYSET).ok().flatten());
        match value.as_deref().and_then(report::keyset_key_ids) {
            Some(ids) => report::keyset_fingerprint(&ids),
            None => self
                .keys
                .as_ref()
                .map_or_else(String::new, |k| k.fingerprint().to_string()),
        }
    }

    /// What this process reports about itself.
    pub fn state(&self) -> ServiceState {
        let (revision, rejected, restart_pending) = {
            let state = locked(&self.state);
            let mut rejected: Vec<String> = state
                .current
                .rejections
                .iter()
                .chain(state.last_rejections.iter())
                .map(|r| r.key.clone())
                .filter(|k| report::is_setting_name(k))
                .collect();
            rejected.sort();
            rejected.dedup();
            (
                state.current.revision().max(state.tracker.revision),
                rejected,
                state.restart_pending,
            )
        };
        ServiceState {
            revision_applied: revision,
            env_overrides: self.env_overrides(),
            rejected_keys: rejected,
            restart_pending,
            keyset_fp: self.keyset_fp(),
            write_stores: report::WRITE_STORES.to_string(),
        }
    }

    /// The id of this instance in the store: `backend.edge:<hostname>`.
    pub fn instance_id(&self) -> String {
        report::instance_id(
            &self.registry.service,
            report::INSTANCE_ROLE,
            &report::hostname(),
            Some(&self.config.snapshot_dir),
        )
    }

    /// Tells the store what this process applied. Never fails the service: a
    /// refusal or an outage is logged when it starts and when it ends.
    pub async fn report_safely(&self) {
        let Some(source) = &self.source else { return };
        let outcome = source
            .report_state(&self.instance_id(), &self.state())
            .await;
        let mut state = locked(&self.state);
        match (outcome, state.report_ok) {
            (Ok(()), false) => {
                state.report_ok = true;
                tracing::info!("settings state reported again");
            }
            (Err(e), true) => {
                state.report_ok = false;
                tracing::warn!("settings state not reported ({})", e.0);
            }
            _ => {}
        }
    }

    // ---- reload

    /// Checks the manifest revision and applies a newer snapshot. True when the
    /// snapshot changed.
    pub async fn poll_once(&self) -> Result<bool, SourceUnavailable> {
        let Some(source) = &self.source else {
            return Ok(false);
        };
        let revision = source.fetch_revision().await?;
        let seen = locked(&self.state).seen_revision;
        let Some(revision) = revision else {
            return Ok(false);
        };
        if seen == Some(revision) {
            return Ok(false);
        }
        let raw = source.fetch().await?;
        locked(&self.state).last_rejections.clear();
        let applied = self
            .apply(&raw, false, Origin::Store, true)
            .unwrap_or(false);
        if applied {
            self.write_disk(&raw);
        }
        // a new revision was looked at: say what this process holds now
        self.report_safely().await;
        Ok(applied)
    }

    /// Polls in the background until the process ends: every interval plus jitter,
    /// backing off (capped) after a failure; never crashes the service.
    pub fn spawn_poller(self: &Arc<Self>) -> Option<tokio::task::JoinHandle<()>> {
        self.source.as_ref()?;
        let runtime = Arc::clone(self);
        Some(tokio::spawn(async move {
            let mut failures: u32 = 0;
            runtime.report_safely().await;
            let mut last_report = Instant::now();
            loop {
                let base = runtime.config.poll_interval;
                let base = if failures > 0 {
                    base.saturating_mul(1 << failures.min(16))
                        .min(Duration::from_secs(120))
                } else {
                    base
                };
                tokio::time::sleep(base + jitter(runtime.config.poll_jitter)).await;
                match runtime.poll_once().await {
                    Ok(_) => failures = 0,
                    Err(e) => {
                        failures = (failures + 1).min(16);
                        tracing::warn!("settings poll failed ({})", e.0);
                    }
                }
                if last_report.elapsed() >= HEARTBEAT {
                    runtime.report_safely().await;
                    last_report = Instant::now();
                }
            }
        }))
    }
}

fn trusted_filter(trusted: bool, rejected: bool) -> bool {
    !trusted || rejected
}

/// A pseudo-random share of `max` (not a secret: it only spreads the polls).
fn jitter(max: Duration) -> Duration {
    use std::hash::{BuildHasher, Hasher};
    let mut h = std::collections::hash_map::RandomState::new().build_hasher();
    h.write_u64(0);
    let share = f64::from(u32::try_from(h.finish() % 1000).unwrap_or(0)) / 1000.0;
    max.mul_f64(share)
}

/// Why the store is not read at all by a service with this environment.
pub fn why_inactive<H: std::hash::BuildHasher>(env_vars: &HashMap<String, String, H>) -> String {
    let env = Settings::from_map(
        env_vars
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect(),
    );
    match LoaderConfig::from_env(&env) {
        Ok(c) if c.mode == Mode::Off => "SETTINGS_STORE=off at this service".into(),
        Ok(c) if c.master_key.is_empty() => "no SETTINGS_MASTER_KEY at this service".into(),
        Ok(_) => "no DATABASE_URL at this service".into(),
        Err(_) => "the settings store configuration is invalid".into(),
    }
}

/// Loads the process's snapshot. `None` when the store is off (`SETTINGS_STORE=off`,
/// or `auto` without `DATABASE_URL` and `SETTINGS_MASTER_KEY`). `Err` when a
/// `required` service must not start.
pub async fn load<H: std::hash::BuildHasher>(
    env_vars: &HashMap<String, String, H>,
    registry: &'static Registry,
    source: Option<Box<dyn SnapshotSource>>,
    required_env_keys: &[&str],
) -> Result<Option<Arc<StoreRuntime>>, StoreError> {
    let config = LoaderConfig::from_env(&Settings::from_map(
        env_vars
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect(),
    ))?;
    if source.is_none() && !config.active() {
        return Ok(None);
    }
    let source = match source {
        Some(s) => Some(s),
        None if !config.database_url.is_empty() => Some(Box::new(super::pg::PgSource::new(
            &config.database_url,
            &registry.service,
        )?) as Box<dyn SnapshotSource>),
        None => None,
    };
    let runtime = StoreRuntime::new(
        config,
        registry,
        source,
        required_env_keys,
        Settings::from_map(
            env_vars
                .iter()
                .map(|(k, v)| (k.clone(), v.clone()))
                .collect(),
        ),
    )?;
    runtime.start().await?;
    Ok(Some(Arc::new(runtime)))
}
