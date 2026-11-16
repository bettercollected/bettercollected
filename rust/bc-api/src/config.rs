//! Configuration read from the environment, by the same variable names the
//! Python backend uses. Values are normalised like the Python settings loader
//! does (trim, one pair of matching quotes removed, empty counts as unset).
//! This spike reads the environment only: the settings store of the Python
//! services (`SETTINGS_STORE`) is not read, see rust/README.md.

use std::collections::HashMap;
use std::fmt;

#[derive(Debug)]
pub struct ConfigError(pub String);

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for ConfigError {}

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
    if text.is_empty() {
        None
    } else {
        Some(text)
    }
}

/// pydantic's bool parsing of a string (what the Python settings classes do).
pub fn parse_bool(value: &str) -> Option<bool> {
    match value.trim().to_lowercase().as_str() {
        "1" | "on" | "t" | "true" | "y" | "yes" => Some(true),
        "0" | "off" | "f" | "false" | "n" | "no" => Some(false),
        _ => None,
    }
}

/// The feature switches `GET /workspaces/{id}/permissions` reports, each
/// default off, under the names the Python settings use.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Flags {
    pub field_rules: bool,
    pub choice_logic: bool,
    pub save_drafts: bool,
    pub captcha: bool,
    pub csv_import: bool,
    pub new_question_types: bool,
    pub address_question: bool,
    pub address_lookup: bool,
    pub signature_question: bool,
    pub option_sources: bool,
    pub reusable_sections: bool,
    pub layout_containers: bool,
    pub daybreak_preset: bool,
    pub form_revisions_ui: bool,
    pub audit_log_ui: bool,
    pub response_revisions: bool,
    pub submissions_api: bool,
    pub form_embed: bool,
    pub form_access: bool,
    pub form_promotion: bool,
    pub api_key_roles: bool,
    pub reporting: bool,
    pub app_theme_pigment: bool,
}

impl Flags {
    /// `offered_gated_presets`: the gated presets whose switch is on, in the
    /// order of `constants/themes.py` `GATED_PRESETS`.
    pub fn offered_presets(&self) -> Vec<&'static str> {
        let mut out = Vec::new();
        if self.daybreak_preset {
            out.push("Daybreak");
        }
        if self.app_theme_pigment {
            out.push("Pigment");
        }
        out
    }
}

#[derive(Clone)]
pub struct Config {
    pub database_url: String,
    /// `AUTH_JWT_SECRET` as a key ring: the members that verify, current first.
    pub jwt_ring: Vec<String>,
    pub flags: Flags,
    pub sso_enabled: bool,
    pub totp_enabled: bool,
    pub bind: String,
    pub pool_max: u32,
}

impl fmt::Debug for Config {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // never prints the database URL or a secret
        f.debug_struct("Config")
            .field("jwt_ring_members", &self.jwt_ring.len())
            .field("flags", &self.flags)
            .field("bind", &self.bind)
            .finish_non_exhaustive()
    }
}

/// `common/settings/key_ring.py` `token_members`: two members when the value
/// has exactly one comma and both sides are at least 32 characters without
/// whitespace; anything else is ONE secret, exactly as it is.
pub fn token_members(value: &str) -> Vec<String> {
    if value.trim().is_empty() {
        return Vec::new();
    }
    let parts: Vec<&str> = value.trim().split(',').collect();
    if parts.len() == 2
        && parts
            .iter()
            .all(|p| p.chars().count() >= 32 && !p.chars().any(char::is_whitespace))
    {
        return parts.iter().map(|p| p.to_string()).collect();
    }
    vec![value.to_string()]
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

impl Config {
    pub fn from_env() -> Result<Config, ConfigError> {
        let vars: HashMap<String, String> = std::env::vars().collect();
        Config::from_map(&vars)
    }

    pub fn from_map(vars: &HashMap<String, String>) -> Result<Config, ConfigError> {
        let get = |name: &str| normalize(vars.get(name).map(String::as_str));
        let flag = |name: &str| -> Result<bool, ConfigError> {
            match get(name) {
                None => Ok(false),
                Some(raw) => {
                    parse_bool(&raw).ok_or_else(|| ConfigError(format!("{name} is not a boolean")))
                }
            }
        };
        // The Python backend refuses to start without a signing secret and
        // never falls back to a default one; so does this service.
        let secret = get("AUTH_JWT_SECRET").ok_or_else(|| {
            ConfigError("AUTH_JWT_SECRET is not set: refusing to start".to_string())
        })?;
        let jwt_ring = token_members(&secret);
        if jwt_ring.is_empty() {
            return Err(ConfigError(
                "AUTH_JWT_SECRET is empty: refusing to start".into(),
            ));
        }
        let database_url = get("DATABASE_URL")
            .ok_or_else(|| ConfigError("DATABASE_URL is not set".to_string()))?;
        let flags = Flags {
            field_rules: flag("FIELD_RULES_ENABLED")?,
            choice_logic: flag("CHOICE_LOGIC_ENABLED")?,
            save_drafts: flag("SAVE_DRAFTS_ENABLED")?,
            captcha: flag("CAPTCHA_ENABLED")?,
            csv_import: flag("CSV_IMPORT_ENABLED")?,
            new_question_types: flag("NEW_QUESTION_TYPES_ENABLED")?,
            address_question: flag("ADDRESS_QUESTION_ENABLED")?,
            address_lookup: flag("ADDRESS_LOOKUP_ENABLED")?,
            signature_question: flag("SIGNATURE_QUESTION_ENABLED")?,
            option_sources: flag("OPTION_SOURCES_ENABLED")?,
            reusable_sections: flag("REUSABLE_SECTIONS_ENABLED")?,
            layout_containers: flag("LAYOUT_CONTAINERS_ENABLED")?,
            daybreak_preset: flag("DAYBREAK_PRESET_ENABLED")?,
            form_revisions_ui: flag("FORM_REVISIONS_UI_ENABLED")?,
            audit_log_ui: flag("AUDIT_LOG_UI_ENABLED")?,
            response_revisions: flag("RESPONSE_REVISIONS_ENABLED")?,
            submissions_api: flag("SUBMISSIONS_API_ENABLED")?,
            form_embed: flag("FORM_EMBED_ENABLED")?,
            form_access: flag("FORM_ACCESS_ENABLED")?,
            form_promotion: flag("FORM_PROMOTION_ENABLED")?,
            api_key_roles: flag("API_KEY_ROLES_ENABLED")?,
            reporting: flag("REPORTING_ENABLED")?,
            app_theme_pigment: flag("APP_THEME_PIGMENT_ENABLED")?,
        };
        let pool_max = match get("BC_API_DB_POOL_MAX") {
            Some(v) => v
                .parse::<u32>()
                .map_err(|_| ConfigError("BC_API_DB_POOL_MAX is not a number".into()))?,
            None => 10,
        };
        Ok(Config {
            database_url: sqlx_url(&database_url),
            jwt_ring,
            flags,
            sso_enabled: flag("SSO_ENABLED")?,
            totp_enabled: flag("TOTP_ENABLED")?,
            bind: get("BC_API_BIND").unwrap_or_else(|| "127.0.0.1:18080".to_string()),
            pool_max,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vars(pairs: &[(&str, &str)]) -> HashMap<String, String> {
        pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect()
    }

    #[test]
    fn refuses_to_start_without_a_secret() {
        let err = Config::from_map(&vars(&[("DATABASE_URL", "postgresql://x/y")])).unwrap_err();
        assert!(err.0.contains("AUTH_JWT_SECRET"));
        let err = Config::from_map(&vars(&[
            ("DATABASE_URL", "postgresql://x/y"),
            ("AUTH_JWT_SECRET", "  \"\"  "),
        ]))
        .unwrap_err();
        assert!(err.0.contains("AUTH_JWT_SECRET"));
    }

    #[test]
    fn key_ring_rule_matches_python() {
        let a = "a".repeat(32);
        let b = "b".repeat(40);
        assert_eq!(
            token_members(&format!("{a},{b}")),
            vec![a.clone(), b.clone()]
        );
        // too short a side: one secret, comma included
        assert_eq!(
            token_members(&format!("{a},short")),
            vec![format!("{a},short")]
        );
        // whitespace inside: one secret
        assert_eq!(
            token_members(&format!("{a} x,{b}")),
            vec![format!("{a} x,{b}")]
        );
        // three members are never a ring
        assert_eq!(token_members(&format!("{a},{b},{a}")).len(), 1);
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

    #[test]
    fn invalid_flag_value_stops_the_start() {
        let a = "a".repeat(40);
        let err = Config::from_map(&vars(&[
            ("DATABASE_URL", "postgresql://x/y"),
            ("AUTH_JWT_SECRET", &a),
            ("CAPTCHA_ENABLED", "maybe"),
        ]))
        .unwrap_err();
        assert!(err.0.contains("CAPTCHA_ENABLED"));
        assert!(!err.0.contains("maybe"));
    }

    #[test]
    fn empty_value_counts_as_unset_and_quotes_are_removed() {
        assert_eq!(normalize(Some("  ")), None);
        assert_eq!(normalize(Some("'x'")), Some("x".to_string()));
        assert_eq!(normalize(Some("\"x'")), Some("\"x'".to_string()));
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
    fn config_debug_never_shows_secrets() {
        let secret = "s".repeat(40);
        let cfg = Config::from_map(&vars(&[
            ("DATABASE_URL", "postgresql://user:hunter2@h/d"),
            ("AUTH_JWT_SECRET", &secret),
        ]))
        .unwrap();
        let shown = format!("{cfg:?}");
        assert!(!shown.contains("hunter2") && !shown.contains(&secret));
    }
}
