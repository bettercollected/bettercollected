//! Reading values out of a `doc`, tolerant where the Python models are.
//!
//! pydantic (the Python reader) accepts a few spellings a strict reader would
//! not: a bool written as `"true"` or `1`, an integer written as `"7"` or
//! `7.0`. The deserialisers here do the same, for fields declared `bool` or
//! `int` in the Python model; a field that is not one of those is read strictly
//! (a number for a `str` field is an error in Python too).

use serde::de::{Deserialize, Deserializer, Error as _};
use serde_json::Value;

/// An id as the document stores it: a plain string or `{"$oid": ...}`.
pub fn id_text(value: Option<&Value>) -> Option<String> {
    match value? {
        Value::String(s) => Some(s.clone()),
        Value::Object(o) => o.get("$oid").and_then(Value::as_str).map(str::to_string),
        _ => None,
    }
}

/// A stored flag as pydantic reads a `bool` field (`bool` or `Optional[bool]`),
/// which is how the Python backend reads every flag it enforces.
///
/// Accepted: JSON `true` / `false`; the integers `0` and `1` and the floats
/// `0.0` and `1.0`; a string that is, in any letter case, one of `0`, `1`, `f`,
/// `t`, `n`, `y`, `no`, `on`, `off`, `yes`, `true`, `false` (no surrounding
/// spaces: `" true"` is refused). Refused: any other number (`2`, `-1`, `0.5`),
/// any other string (`""`, `"maybe"`, `"1.0"`), an array, an object. `null` is
/// no value: false for an `Optional[bool]`, refused for a plain `bool`; this
/// reader returns `None` for a refused value and for `null`, and the caller
/// decides (see [`flag`]).
pub fn lax_bool(value: &Value) -> Option<bool> {
    lax_bool_of(value)
}

/// The three states of a stored flag.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Flag {
    /// Absent or `null`: not set.
    Unset,
    Set(bool),
    /// A value pydantic refuses: the Python backend cannot read this document.
    Unreadable,
}

/// Reads `doc[key]` as an `Optional[bool]` flag.
pub fn flag(doc: &Value, key: &str) -> Flag {
    match doc.get(key) {
        None | Some(Value::Null) => Flag::Unset,
        Some(v) => lax_bool_of(v).map_or(Flag::Unreadable, Flag::Set),
    }
}

/// A flag that is on: `true` as pydantic reads it (`"true"`, `1`, `"yes"`, ...),
/// false for an unset or unreadable one. An unreadable value is false here only
/// because the caller cannot tell; a policy that must not fail open reads
/// [`flag`] and treats `Unreadable` as "ask Python".
pub fn truthy(value: Option<&Value>) -> bool {
    value.and_then(lax_bool_of) == Some(true)
}

fn lax_bool_of(value: &Value) -> Option<bool> {
    match value {
        Value::Bool(b) => Some(*b),
        Value::Number(n) => match n.as_i64() {
            Some(0) => Some(false),
            Some(1) => Some(true),
            // 0.0 and 1.0 are the only floats pydantic accepts as a bool
            _ => match n.to_string().as_str() {
                "0.0" | "-0.0" => Some(false),
                "1.0" => Some(true),
                _ => None,
            },
        },
        Value::String(s) => match s.to_lowercase().as_str() {
            "true" | "t" | "yes" | "y" | "on" | "1" => Some(true),
            "false" | "f" | "no" | "n" | "off" | "0" => Some(false),
            _ => None,
        },
        _ => None,
    }
}

fn lax_i64_of(value: &Value) -> Option<i64> {
    match value {
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Some(i)
            } else {
                let f = n.as_f64()?;
                #[allow(clippy::cast_possible_truncation)]
                (f.fract() == 0.0 && f.abs() < 9.0e18).then_some(f as i64)
            }
        }
        Value::String(s) => {
            let s = s.trim();
            match s.split_once('.') {
                // "7.0": a decimal with a zero fraction
                Some((whole, zeros)) if !zeros.is_empty() && zeros.bytes().all(|b| b == b'0') => {
                    whole.parse().ok()
                }
                Some(_) => None,
                None => s.parse().ok(),
            }
        }
        // a bool is 0 or 1 (pydantic's lax int)
        Value::Bool(b) => Some(i64::from(*b)),
        // BSON Extended JSON of a 64-bit integer
        Value::Object(o) => o.get("$numberLong")?.as_str()?.parse().ok(),
        _ => None,
    }
}

/// `#[serde(deserialize_with = "lax::bool_")]` for a Python `bool`.
pub mod lax {
    use super::*;

    pub fn bool_<'de, D: Deserializer<'de>>(d: D) -> Result<bool, D::Error> {
        let v = Value::deserialize(d)?;
        lax_bool_of(&v).ok_or_else(|| D::Error::custom("expected a boolean"))
    }

    pub fn opt_bool<'de, D: Deserializer<'de>>(d: D) -> Result<Option<bool>, D::Error> {
        match Value::deserialize(d)? {
            Value::Null => Ok(None),
            v => lax_bool_of(&v)
                .map(Some)
                .ok_or_else(|| D::Error::custom("expected a boolean")),
        }
    }

    pub fn opt_i64<'de, D: Deserializer<'de>>(d: D) -> Result<Option<i64>, D::Error> {
        match Value::deserialize(d)? {
            Value::Null => Ok(None),
            v => lax_i64_of(&v)
                .map(Some)
                .ok_or_else(|| D::Error::custom("expected an integer")),
        }
    }
}

/// Python's default for `Optional[bool] = False`: absent is `Some(false)`.
#[allow(clippy::unnecessary_wraps)] // serde `default =` needs the field type
pub fn some_false() -> Option<bool> {
    Some(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;
    use serde_json::json;

    #[test]
    fn ids_come_as_text_or_extended_json() {
        assert_eq!(id_text(Some(&json!("a1"))).as_deref(), Some("a1"));
        assert_eq!(id_text(Some(&json!({"$oid": "a1"}))).as_deref(), Some("a1"));
        assert_eq!(id_text(Some(&json!(5))), None);
        assert_eq!(id_text(None), None);
    }

    #[test]
    fn a_flag_is_read_as_pydantic_reads_a_bool() {
        for yes in [
            json!(true),
            json!("true"),
            json!("TRUE"),
            json!("Yes"),
            json!("on"),
            json!("t"),
            json!("y"),
            json!("1"),
            json!(1),
            json!(1.0),
        ] {
            assert!(truthy(Some(&yes)), "{yes}");
            assert_eq!(lax_bool(&yes), Some(true));
        }
        for no in [
            json!(false),
            json!("false"),
            json!("off"),
            json!("n"),
            json!("0"),
            json!(0),
            json!(0.0),
            json!(-0.0),
        ] {
            assert!(!truthy(Some(&no)), "{no}");
            assert_eq!(lax_bool(&no), Some(false));
        }
        for refused in [
            json!(2),
            json!(-1),
            json!(0.5),
            json!(2.0),
            json!(" true"),
            json!("true "),
            json!(""),
            json!("maybe"),
            json!("1.0"),
            json!([]),
            json!({}),
            json!([1]),
        ] {
            assert_eq!(lax_bool(&refused), None, "{refused}");
            assert!(!truthy(Some(&refused)));
        }
        assert!(!truthy(None) && !truthy(Some(&json!(null))));
        assert_eq!(flag(&json!({}), "a"), Flag::Unset);
        assert_eq!(flag(&json!({"a": null}), "a"), Flag::Unset);
        assert_eq!(flag(&json!({"a": "yes"}), "a"), Flag::Set(true));
        assert_eq!(flag(&json!({"a": "maybe"}), "a"), Flag::Unreadable);
    }

    #[derive(Deserialize)]
    struct Probe {
        #[serde(default, deserialize_with = "lax::opt_bool")]
        flag: Option<bool>,
        #[serde(default, deserialize_with = "lax::opt_i64")]
        count: Option<i64>,
        #[serde(default, deserialize_with = "lax::bool_")]
        plain: bool,
    }

    #[test]
    fn python_lax_spellings_are_read() {
        let p: Probe =
            serde_json::from_value(json!({"flag": "true", "count": "7", "plain": 1})).unwrap();
        assert_eq!((p.flag, p.count, p.plain), (Some(true), Some(7), true));
        let p: Probe = serde_json::from_value(json!({"flag": null, "count": 7.0})).unwrap();
        assert_eq!((p.flag, p.count, p.plain), (None, Some(7), false));
        assert!(serde_json::from_value::<Probe>(json!({"count": 7.5})).is_err());
        assert!(serde_json::from_value::<Probe>(json!({"flag": "maybe"})).is_err());
    }
}
