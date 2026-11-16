//! Where a setting's value comes from.
//!
//! The Python services resolve a setting as: a non-empty environment value,
//! then the verified row of the settings store, then the code default. This
//! module is the seam for that order. [`Settings`] holds layers, first one
//! wins; only the environment layer exists. The settings-store reader will be
//! another [`SettingsSource`] pushed after [`EnvSource`], so no reader of a
//! single setting changes when it arrives.

use std::collections::HashMap;
use std::fmt;

use crate::ConfigError;

/// One layer of settings.
pub trait SettingsSource: Send + Sync {
    /// The raw value of `name`, if this layer has one.
    fn get(&self, name: &str) -> Option<String>;
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

/// The layers, in order of precedence.
pub struct Settings {
    layers: Vec<Box<dyn SettingsSource>>,
}

impl fmt::Debug for Settings {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Settings")
            .field("layers", &self.layers.len())
            .finish()
    }
}

impl Settings {
    pub fn new(layers: Vec<Box<dyn SettingsSource>>) -> Settings {
        Settings { layers }
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
        self.layers
            .iter()
            .find_map(|layer| normalize(layer.get(name).as_deref()))
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
    fn a_bad_flag_names_the_variable_and_not_the_value() {
        let settings = Settings::new(vec![Box::new(Fixed("F", "maybe"))]);
        let err = settings.flag("F").unwrap_err();
        assert!(err.0.contains('F') && !err.0.contains("maybe"));
    }
}
