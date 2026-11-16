//! What the settings registry says about the keys the backend reads, loaded
//! from `data/settings-registry.json` (written by `rust/contract/settings_registry.py`
//! from the Python registry, and checked against it in CI), and the typed
//! reading of a stored value: `common/settings/registry.py` `coerce_value`.

use std::collections::{HashMap, HashSet};
use std::net::IpAddr;
use std::sync::OnceLock;

use ipnet::IpNet;
use serde::Deserialize;
use serde_json::Value;

use super::canonical::python_float_repr;

const DATA: &str = include_str!("../../data/settings-registry.json");

const MAX_STRING: usize = 8192;
const MAX_SECRET: usize = 4096;
const MAX_JSON_BYTES: usize = 65536;
const MAX_URL: usize = 2048;
const MAX_PROXIES: usize = 64;
const MAX_IP_LIST: usize = 16;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
pub enum Tier {
    T1,
    T2,
    T3,
    T4,
    T5,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
pub enum Reload {
    B,
    H,
    R,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ValueType {
    Str,
    Int,
    Bool,
    Float,
    Url,
    Json,
    Enum,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Spec {
    pub key: String,
    pub section: String,
    pub readers: Vec<String>,
    pub retired_readers: Vec<String>,
    #[serde(rename = "type")]
    pub kind: ValueType,
    pub is_secret: bool,
    pub reload: Reload,
    pub tier: Tier,
    pub choices: Vec<String>,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub max_length: Option<usize>,
    pub format: String,
    /// The Python backend resolves this key from the store (see the generator).
    pub store_backed: bool,
}

#[derive(Debug, Deserialize)]
struct Data {
    service: String,
    specs: Vec<Spec>,
    other_known: Vec<String>,
    retired: Vec<String>,
}

/// The registry as the reading service sees it.
#[derive(Debug)]
pub struct Registry {
    pub service: String,
    specs: HashMap<String, Spec>,
    other_known: HashSet<String>,
    retired: HashSet<String>,
}

/// Why a stored value was refused (a short code, never the value).
pub type Refusal = &'static str;

impl Registry {
    pub fn from_json(text: &str) -> Result<Registry, String> {
        let data: Data =
            serde_json::from_str(text).map_err(|e| format!("settings registry: {e}"))?;
        Ok(Registry {
            service: data.service,
            specs: data.specs.into_iter().map(|s| (s.key.clone(), s)).collect(),
            other_known: data.other_known.into_iter().collect(),
            retired: data.retired.into_iter().collect(),
        })
    }

    /// The registry of the shipped data file (the backend's).
    pub fn shipped() -> &'static Registry {
        static REGISTRY: OnceLock<Registry> = OnceLock::new();
        REGISTRY.get_or_init(|| {
            // the file is embedded and checked by a unit test: it always parses
            Registry::from_json(DATA).unwrap_or_else(|_| Registry {
                service: "backend".into(),
                specs: HashMap::new(),
                other_known: HashSet::new(),
                retired: HashSet::new(),
            })
        })
    }

    pub fn get(&self, key: &str) -> Option<&Spec> {
        self.specs.get(key)
    }

    /// A key of any reader.
    pub fn knows(&self, key: &str) -> bool {
        self.specs.contains_key(key) || self.other_known.contains(key)
    }

    pub fn is_retired(&self, key: &str) -> bool {
        self.retired.contains(key)
    }

    pub fn specs(&self) -> impl Iterator<Item = &Spec> {
        self.specs.values()
    }

    pub fn sections(&self) -> Vec<String> {
        let mut out: Vec<String> = self
            .specs
            .values()
            .map(|s| s.section.clone())
            .collect::<HashSet<_>>()
            .into_iter()
            .collect();
        out.sort();
        out
    }

    /// Secrets and tier T3 and T4 settings: the ones a `required` service
    /// cannot start without.
    pub fn critical_keys(&self) -> HashSet<String> {
        self.specs
            .values()
            .filter(|s| s.is_secret || matches!(s.tier, Tier::T3 | Tier::T4))
            .map(|s| s.key.clone())
            .collect()
    }
}

// ------------------------------------------------------------ typed reading

fn is_control(c: char) -> bool {
    c.is_control()
        || matches!(
            c,
            '\u{2028}' | '\u{2029}' | '\u{200e}' | '\u{200f}' | '\u{061c}'
        )
        || ('\u{202a}'..='\u{202e}').contains(&c)
        || ('\u{2066}'..='\u{2069}').contains(&c)
}

fn ascii_int(text: &str) -> Option<i128> {
    let digits = text.strip_prefix(['+', '-']).unwrap_or(text);
    if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    text.parse::<i128>().ok()
}

fn ascii_float(text: &str) -> Option<f64> {
    // [+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?
    let body = text.strip_prefix(['+', '-']).unwrap_or(text);
    let (mantissa, exponent) = match body.find(['e', 'E']) {
        Some(i) => (&body[..i], Some(&body[i + 1..])),
        None => (body, None),
    };
    let (int, frac) = match mantissa.split_once('.') {
        Some((i, f)) => (i, Some(f)),
        None => (mantissa, None),
    };
    let digits = |s: &str| s.bytes().all(|b| b.is_ascii_digit());
    let ok_mantissa = match frac {
        Some(f) => digits(int) && digits(f) && !(int.is_empty() && f.is_empty()),
        None => !int.is_empty() && digits(int),
    };
    let ok_exponent = exponent.is_none_or(|e| {
        let e = e.strip_prefix(['+', '-']).unwrap_or(e);
        !e.is_empty() && digits(e)
    });
    if !ok_mantissa || !ok_exponent {
        return None;
    }
    let value: f64 = text.parse().ok()?;
    value.is_finite().then_some(value)
}

fn check_host(text: &str) -> bool {
    let inner = text
        .strip_prefix('[')
        .and_then(|t| t.strip_suffix(']'))
        .unwrap_or(text);
    if inner.parse::<IpAddr>().is_ok() {
        return true;
    }
    let labels: Vec<&str> = text.trim_end_matches('.').split('.').collect();
    !text.is_empty()
        && text.len() <= 253
        && labels.iter().all(|l| {
            let b = l.as_bytes();
            !b.is_empty()
                && b.len() <= 63
                && b.first().is_some_and(u8::is_ascii_alphanumeric)
                && b.last().is_some_and(u8::is_ascii_alphanumeric)
                && b.iter().all(|c| c.is_ascii_alphanumeric() || *c == b'-')
        })
}

fn check_cidr_list(text: &str) -> bool {
    if text.trim().is_empty() {
        return true;
    }
    let items: Vec<&str> = text.split(',').map(str::trim).collect();
    items.len() <= MAX_PROXIES
        && items
            .iter()
            .all(|i| !i.is_empty() && (i.parse::<IpNet>().is_ok() || i.parse::<IpAddr>().is_ok()))
}

fn check_ip_list(text: &str) -> bool {
    if text.trim().is_empty() {
        return true;
    }
    let items: Vec<&str> = text.split(',').map(str::trim).collect();
    items.len() <= MAX_IP_LIST
        && items
            .iter()
            .all(|i| !i.is_empty() && !i.contains('%') && i.parse::<IpAddr>().is_ok())
}

/// `coerce_value`: a stored value as the text an environment variable would
/// carry (`StoreSource` hands a bool over as `true`/`false`, a number as its
/// Python spelling), or the reason it is refused.
pub fn coerce(spec: &Spec, raw: &Value) -> Result<String, Refusal> {
    match spec.kind {
        ValueType::Bool => match raw {
            Value::Bool(b) => Ok(b.to_string()),
            Value::String(s) => match s.trim().to_lowercase().as_str() {
                "true" | "1" | "yes" | "on" => Ok("true".into()),
                "false" | "0" | "no" | "off" => Ok("false".into()),
                _ => Err("not_bool"),
            },
            _ => Err("not_bool"),
        },
        ValueType::Int => {
            let number: i128 = match raw {
                Value::String(s) => ascii_int(s.trim()).ok_or("not_number")?,
                Value::Number(n) => {
                    if let Some(i) = n.as_i64() {
                        i128::from(i)
                    } else if let Some(u) = n.as_u64() {
                        i128::from(u)
                    } else {
                        let f = n.as_f64().ok_or("not_number")?;
                        if !f.is_finite() || f.fract() != 0.0 || f.abs() > 9.0e18 {
                            return Err("not_number");
                        }
                        // whole and within range: exact
                        format!("{f:.0}")
                            .parse::<i128>()
                            .map_err(|_| "not_number")?
                    }
                }
                // a bool, null, array or object
                _ => return Err("not_number"),
            };
            #[allow(clippy::cast_possible_truncation)] // the registry's limits are whole numbers
            let bound = |limit: Option<f64>, above: bool| {
                limit.is_some_and(|l| {
                    // whole limits only (the registry's are): compare as integers
                    let l = l as i128;
                    if above { number > l } else { number < l }
                })
            };
            if bound(spec.min, false) || bound(spec.max, true) {
                return Err("out_of_range");
            }
            Ok(number.to_string())
        }
        ValueType::Float => {
            let number = match raw {
                Value::String(s) => ascii_float(s.trim()).ok_or("not_number")?,
                Value::Number(n) => n.as_f64().filter(|f| f.is_finite()).ok_or("not_number")?,
                _ => return Err("not_number"),
            };
            check_range(spec, number)?;
            python_float_repr(number).map_err(|_| "not_number")
        }
        ValueType::Json => {
            let parsed: Value = match raw {
                Value::String(s) => serde_json::from_str(s).map_err(|_| "not_json")?,
                other => other.clone(),
            };
            if !matches!(parsed, Value::Object(_) | Value::Array(_)) {
                return Err("not_json");
            }
            let text = serde_json::to_string(&parsed).map_err(|_| "not_json")?;
            if text.len() > MAX_JSON_BYTES {
                return Err("too_long");
            }
            Ok(text)
        }
        ValueType::Enum | ValueType::Str | ValueType::Url => {
            let Value::String(text) = raw else {
                return Err("not_string");
            };
            if spec.kind == ValueType::Enum {
                return if spec.choices.iter().any(|c| c == text) {
                    Ok(text.clone())
                } else {
                    Err("not_a_choice")
                };
            }
            let limit = if spec.kind == ValueType::Url {
                MAX_URL
            } else if spec.is_secret {
                MAX_SECRET
            } else {
                spec.max_length.unwrap_or(MAX_STRING)
            };
            if text.chars().count() > limit {
                return Err("too_long");
            }
            if text.chars().any(is_control) {
                return Err("control_characters");
            }
            match spec.format.as_str() {
                "cidr_list" if !check_cidr_list(text) => Err("bad_cidr_list"),
                "ip_list" if !check_ip_list(text) => Err("bad_ip_list"),
                "host" if !check_host(text) => Err("bad_host"),
                _ => Ok(text.clone()),
            }
        }
    }
}

fn check_range(spec: &Spec, number: f64) -> Result<(), Refusal> {
    if spec.min.is_some_and(|m| number < m) || spec.max.is_some_and(|m| number > m) {
        return Err("out_of_range");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn spec(kind: ValueType) -> Spec {
        Spec {
            key: "K".into(),
            section: "s".into(),
            readers: vec!["backend".into()],
            retired_readers: vec![],
            kind,
            is_secret: false,
            reload: Reload::R,
            tier: Tier::T1,
            choices: vec!["a".into(), "b".into()],
            min: Some(1.0),
            max: Some(10.0),
            max_length: Some(5),
            format: String::new(),
            store_backed: true,
        }
    }

    #[test]
    fn the_shipped_file_parses_and_knows_the_switches() {
        let registry = Registry::shipped();
        assert_eq!(registry.service, "backend");
        for key in [
            "SSO_ENABLED",
            "TOTP_ENABLED",
            "FIELD_RULES_ENABLED",
            "AUTH_JWT_SECRET",
        ] {
            assert!(registry.get(key).is_some_and(|s| s.store_backed), "{key}");
        }
        // held in the environment: never a store key
        for key in [
            "FORM_ACCESS_ENABLED",
            "REPORTING_ENABLED",
            "API_KEY_ROLES_ENABLED",
            "FORM_PROMOTION_ENABLED",
        ] {
            assert!(!registry.knows(key), "{key}");
        }
        // Python's loader skips a field with two names
        assert!(
            registry
                .get("API_TRUSTED_PROXIES")
                .is_some_and(|s| !s.store_backed)
        );
        assert!(registry.critical_keys().contains("AUTH_JWT_SECRET"));
        assert!(registry.sections().contains(&"auth_keys".to_string()));
    }

    #[test]
    fn a_bool_is_a_json_bool_or_one_of_eight_words() {
        let s = spec(ValueType::Bool);
        assert_eq!(coerce(&s, &json!(true)).unwrap(), "true");
        assert_eq!(coerce(&s, &json!(" Off ")).unwrap(), "false");
        assert_eq!(coerce(&s, &json!("yes")).unwrap(), "true");
        // pydantic accepts these in an environment variable; the registry does not
        for bad in [
            json!("t"),
            json!("y"),
            json!(1),
            json!("maybe"),
            json!(null),
        ] {
            assert_eq!(coerce(&s, &bad), Err("not_bool"), "{bad}");
        }
    }

    #[test]
    fn numbers_keep_their_range_and_python_spelling() {
        let i = spec(ValueType::Int);
        assert_eq!(coerce(&i, &json!(5)).unwrap(), "5");
        assert_eq!(coerce(&i, &json!(" +7 ")).unwrap(), "7");
        assert_eq!(coerce(&i, &json!(5.0)).unwrap(), "5");
        assert_eq!(coerce(&i, &json!(5.5)), Err("not_number"));
        assert_eq!(coerce(&i, &json!(true)), Err("not_number"));
        assert_eq!(coerce(&i, &json!("1_0")), Err("not_number"));
        assert_eq!(coerce(&i, &json!(11)), Err("out_of_range"));
        let f = spec(ValueType::Float);
        assert_eq!(coerce(&f, &json!(2.0)).unwrap(), "2.0");
        assert_eq!(coerce(&f, &json!("1e1")).unwrap(), "10.0");
        assert_eq!(coerce(&f, &json!("1e2")), Err("out_of_range"));
        assert_eq!(coerce(&f, &json!("nan")), Err("not_number"));
    }

    #[test]
    fn text_is_checked_for_length_controls_and_choices_and_not_trimmed() {
        let s = spec(ValueType::Str);
        assert_eq!(coerce(&s, &json!(" ab  ")).unwrap(), " ab  ");
        assert_eq!(coerce(&s, &json!("abcdef")), Err("too_long"));
        assert_eq!(coerce(&s, &json!("a\u{0}")), Err("control_characters"));
        assert_eq!(coerce(&s, &json!("a\u{202e}")), Err("control_characters"));
        assert_eq!(coerce(&s, &json!(1)), Err("not_string"));
        let e = spec(ValueType::Enum);
        assert_eq!(coerce(&e, &json!("a")).unwrap(), "a");
        assert_eq!(coerce(&e, &json!("c")), Err("not_a_choice"));
    }

    #[test]
    fn list_formats_follow_the_python_checks() {
        let mut s = spec(ValueType::Str);
        s.max_length = None;
        s.format = "cidr_list".into();
        assert!(coerce(&s, &json!("10.0.0.0/8, 192.168.1.1")).is_ok());
        assert_eq!(
            coerce(&s, &json!("10.0.0.0/8,,1.1.1.1")),
            Err("bad_cidr_list")
        );
        assert_eq!(coerce(&s, &json!("host.example")), Err("bad_cidr_list"));
        s.format = "host".into();
        assert!(coerce(&s, &json!("mail.example.org")).is_ok());
        assert_eq!(coerce(&s, &json!("mail.example.org:25")), Err("bad_host"));
        s.format = "ip_list".into();
        assert_eq!(coerce(&s, &json!("fe80::1%eth0")), Err("bad_ip_list"));
    }
}
