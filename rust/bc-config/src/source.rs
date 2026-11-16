//! Where a setting's value comes from.
//!
//! The Python services resolve a setting as: a non-empty environment value,
//! then the verified row of the settings store, then the code default. This
//! module is the seam for that order. [`Settings`] holds layers, first one
//! wins: [`EnvSource`], then [`StoreSource`] (the values the verified settings
//! store holds, read once at start, see `crate::store`), so no reader of a single
//! setting knows where its value came from.

use std::collections::HashMap;
use std::fmt;

use crate::ConfigError;

/// One layer of settings.
pub trait SettingsSource: Send + Sync {
    /// The raw value of `name`, if this layer has one.
    fn get(&self, name: &str) -> Option<String>;

    /// Whether [`Settings`] trims the value and removes one pair of quotes (what
    /// an env file means), and counts an empty result as unset. True for values a
    /// person typed into the environment; false for the settings store, whose
    /// values the Python loader hands over as stored.
    fn trims(&self) -> bool {
        true
    }
}

/// The values of the verified settings store, resolved once at start (a class R
/// setting keeps its value until restart). Debug shows a count, never a value.
pub struct StoreSource(HashMap<String, String>);

impl StoreSource {
    pub fn new(values: HashMap<String, String>) -> StoreSource {
        StoreSource(values)
    }
}

impl fmt::Debug for StoreSource {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("StoreSource")
            .field("values", &self.0.len())
            .finish()
    }
}

impl SettingsSource for StoreSource {
    fn get(&self, name: &str) -> Option<String> {
        self.0.get(name).cloned()
    }

    fn trims(&self) -> bool {
        false
    }
}

/// The process environment, read once.
pub struct EnvSource(HashMap<String, String>);

impl EnvSource {
    pub fn new() -> EnvSource {
        EnvSource(std::env::vars().collect())
    }
}

impl Default for EnvSource {
    fn default() -> Self {
        EnvSource::new()
    }
}

impl fmt::Debug for EnvSource {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // values can be secrets
        f.debug_struct("EnvSource")
            .field("variables", &self.0.len())
            .finish()
    }
}

impl SettingsSource for EnvSource {
    fn get(&self, name: &str) -> Option<String> {
        self.0.get(name).cloned()
    }
}

/// A fixed map, for tests and for callers that assemble values themselves.
pub struct MapSource(HashMap<String, String>);

impl MapSource {
    pub fn new(values: HashMap<String, String>) -> MapSource {
        MapSource(values)
    }
}

impl fmt::Debug for MapSource {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("MapSource")
            .field("variables", &self.0.len())
            .finish()
    }
}

impl SettingsSource for MapSource {
    fn get(&self, name: &str) -> Option<String> {
        self.0.get(name).cloned()
    }
}

/// `common/settings/registry.py` `normalize_value`: trimmed, one pair of
/// matching quotes removed; `None` when nothing is left.
pub fn normalize(value: Option<&str>) -> Option<String> {
    let mut text = value?.trim().to_string();
    if text.len() >= 2 {
        let bytes = text.as_bytes();
        let (first, last) = (bytes[0], bytes[bytes.len() - 1]);
        if first == last && (first == b'\'' || first == b'"') {
            text = text[1..text.len() - 1].trim().to_string();
        }
    }
    if text.is_empty() { None } else { Some(text) }
}

/// pydantic's bool parsing of a string (what the Python settings classes do).
pub fn parse_bool(value: &str) -> Option<bool> {
    match value.trim().to_lowercase().as_str() {
        "1" | "on" | "t" | "true" | "y" | "yes" => Some(true),
        "0" | "off" | "f" | "false" | "n" | "no" => Some(false),
        _ => None,
    }
}

/// Where the value of a setting came from. A setting whose value is only the
/// default because the settings store could not be read or trusted here is
/// `DefaultStoreUnavailable`: Python, which may read the store, can hold another
/// value, so a decision that depends on the setting must not be taken from it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Origin {
    /// A non-empty value in the environment.
    Env,
    /// The verified settings store.
    Store,
    /// The verified, signed disk snapshot of the store (the database was down at start).
    Snapshot,
    /// No value anywhere, and the store was read and verified: the default is right.
    DefaultStoreOk,
    /// No value in the environment, and the store was not read or not trusted.
    DefaultStoreUnavailable,
}

impl Origin {
    /// Whether the value can be relied on to be the one Python resolves.
    pub fn is_known(self) -> bool {
        self != Origin::DefaultStoreUnavailable
    }
}

/// What became of the settings store at this service's start.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StoreStatus {
    /// Read and verified.
    Verified,
    /// The database could not be read; the verified signed snapshot stood in.
    Snapshot,
    /// Not read, or not trusted. The text says why (never a value).
    Unavailable(String),
}

/// The layers, in order of precedence.
pub struct Settings {
    layers: Vec<Box<dyn SettingsSource>>,
    store: StoreStatus,
}

impl fmt::Debug for Settings {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Settings")
            .field("layers", &self.layers.len())
            .field("store", &self.store)
            .finish()
    }
}

impl Settings {
    /// Layers with no knowledge of a settings store: a setting with no value
    /// in the environment has the origin `DefaultStoreUnavailable`.
    pub fn new(layers: Vec<Box<dyn SettingsSource>>) -> Settings {
        Settings {
            layers,
            store: StoreStatus::Unavailable("the settings store was not read".into()),
        }
    }

    /// What became of the settings store (decides the origin of a default).
    #[must_use]
    pub fn with_store_status(mut self, status: StoreStatus) -> Settings {
        self.store = status;
        self
    }

    pub fn store_status(&self) -> &StoreStatus {
        &self.store
    }

    /// Where the value of `name` comes from, or why it is only a default.
    pub fn origin(&self, name: &str) -> Origin {
        for layer in &self.layers {
            let Some(raw) = layer.get(name) else { continue };
            if layer.trims() {
                if normalize(Some(&raw)).is_some() {
                    return Origin::Env;
                }
            } else {
                return if self.store == StoreStatus::Snapshot {
                    Origin::Snapshot
                } else {
                    Origin::Store
                };
            }
        }
        match self.store {
            StoreStatus::Verified | StoreStatus::Snapshot => Origin::DefaultStoreOk,
            StoreStatus::Unavailable(_) => Origin::DefaultStoreUnavailable,
        }
    }

    /// The process environment as the only layer.
    pub fn from_env() -> Settings {
        Settings::new(vec![Box::new(EnvSource::new())])
    }

    pub fn from_map(values: HashMap<String, String>) -> Settings {
        Settings::new(vec![Box::new(MapSource::new(values))])
    }

    /// The first layer's non-empty, normalised value.
    pub fn get(&self, name: &str) -> Option<String> {
        self.layers.iter().find_map(|layer| {
            let raw = layer.get(name)?;
            if layer.trims() {
                normalize(Some(&raw))
            } else {
                Some(raw)
            }
        })
    }

    /// The first of several names that has a value (an alias list).
    pub fn get_any(&self, names: &[&str]) -> Option<String> {
        names.iter().find_map(|name| self.get(name))
    }

    /// A boolean setting; `None` when unset, an error when it is not a boolean.
    /// The error names the variable, never the value.
    pub fn flag(&self, name: &str) -> Result<Option<bool>, ConfigError> {
        match self.get(name) {
            None => Ok(None),
            Some(raw) => parse_bool(&raw)
                .map(Some)
                .ok_or_else(|| ConfigError(format!("{name} is not a boolean"))),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_value_counts_as_unset_and_quotes_are_removed() {
        assert_eq!(normalize(Some("  ")), None);
        assert_eq!(normalize(Some("'x'")), Some("x".to_string()));
        assert_eq!(normalize(Some("\"x'")), Some("\"x'".to_string()));
        assert_eq!(normalize(Some("\"\"")), None);
        assert_eq!(normalize(None), None);
    }

    #[test]
    fn bool_parsing_is_pydantics() {
        for t in ["1", "on", "T", "true", "Y", "yes", " TRUE "] {
            assert_eq!(parse_bool(t), Some(true), "{t}");
        }
        for f in ["0", "off", "F", "false", "N", "no"] {
            assert_eq!(parse_bool(f), Some(false), "{f}");
        }
        assert_eq!(parse_bool("maybe"), None);
    }

    struct Fixed(&'static str, &'static str);
    impl SettingsSource for Fixed {
        fn get(&self, name: &str) -> Option<String> {
            (name == self.0).then(|| self.1.to_string())
        }
    }

    #[test]
    fn the_first_layer_with_a_value_wins_and_an_empty_one_is_skipped() {
        let settings = Settings::new(vec![
            Box::new(Fixed("A", "  ")),
            Box::new(Fixed("A", "from the second layer")),
            Box::new(Fixed("A", "from the third")),
        ]);
        assert_eq!(settings.get("A").as_deref(), Some("from the second layer"));
        assert_eq!(settings.get("B"), None);
    }

    #[test]
    fn a_store_value_is_not_trimmed_and_the_environment_wins_when_it_has_a_value() {
        let store = |v: &str| {
            Box::new(StoreSource::new(HashMap::from([(
                "A".to_string(),
                v.to_string(),
            )]))) as Box<dyn SettingsSource>
        };
        let env = |v: &str| {
            Box::new(Fixed("A", Box::leak(v.to_string().into_boxed_str())))
                as Box<dyn SettingsSource>
        };
        // trimmed only when it comes from the environment
        assert_eq!(
            Settings::new(vec![store("  x  ")]).get("A").as_deref(),
            Some("  x  ")
        );
        // an empty or quote-only environment value does not shadow the store
        assert_eq!(
            Settings::new(vec![env("\"\""), store("s")])
                .get("A")
                .as_deref(),
            Some("s")
        );
        assert_eq!(
            Settings::new(vec![env("  "), store("s")])
                .get("A")
                .as_deref(),
            Some("s")
        );
        assert_eq!(
            Settings::new(vec![env("e"), store("s")])
                .get("A")
                .as_deref(),
            Some("e")
        );
        assert!(
            !format!(
                "{:?}",
                StoreSource::new(HashMap::from([("A".into(), "secret".into())]))
            )
            .contains("secret")
        );
    }

    #[test]
    fn the_origin_of_a_setting_says_where_it_came_from_or_why_it_is_only_a_default() {
        let store = || {
            Box::new(StoreSource::new(HashMap::from([(
                "S".to_string(),
                "x".to_string(),
            )]))) as Box<dyn SettingsSource>
        };
        let env = |name: &'static str, v: &'static str| {
            Box::new(Fixed(name, v)) as Box<dyn SettingsSource>
        };
        let with = |layers: Vec<Box<dyn SettingsSource>>, status: StoreStatus| {
            Settings::new(layers).with_store_status(status)
        };
        let down = || StoreStatus::Unavailable("not read".into());
        // the environment wins whatever became of the store
        for status in [StoreStatus::Verified, down()] {
            assert_eq!(
                with(vec![env("E", "v"), store()], status).origin("E"),
                Origin::Env
            );
        }
        // a store row is Store, or Snapshot when the snapshot stood in
        assert_eq!(
            with(vec![env("E", "v"), store()], StoreStatus::Verified).origin("S"),
            Origin::Store
        );
        assert_eq!(
            with(vec![env("E", "v"), store()], StoreStatus::Snapshot).origin("S"),
            Origin::Snapshot
        );
        // an empty or quote-only environment value is no value
        assert_eq!(
            with(vec![env("E", "''"), store()], StoreStatus::Verified).origin("E"),
            Origin::DefaultStoreOk
        );
        assert_eq!(
            with(vec![env("E", " ")], down()).origin("E"),
            Origin::DefaultStoreUnavailable
        );
        // no value: the default is trustworthy only when the store was read
        assert_eq!(
            with(vec![], StoreStatus::Verified).origin("N"),
            Origin::DefaultStoreOk
        );
        assert_eq!(
            with(vec![], StoreStatus::Snapshot).origin("N"),
            Origin::DefaultStoreOk
        );
        assert_eq!(
            with(vec![], down()).origin("N"),
            Origin::DefaultStoreUnavailable
        );
        assert!(
            Origin::Env.is_known()
                && Origin::DefaultStoreOk.is_known()
                && !Origin::DefaultStoreUnavailable.is_known()
        );
        // layers built without any knowledge of a store
        assert_eq!(
            Settings::from_map(HashMap::new()).origin("N"),
            Origin::DefaultStoreUnavailable
        );
    }

    #[test]
    fn a_bad_flag_names_the_variable_and_not_the_value() {
        let settings = Settings::new(vec![Box::new(Fixed("F", "maybe"))]);
        let err = settings.flag("F").unwrap_err();
        assert!(err.0.contains('F') && !err.0.contains("maybe"));
    }
}
