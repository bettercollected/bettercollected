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

/// `true` only for a JSON `true`; absent, null and anything else are false.
pub fn truthy(value: Option<&Value>) -> bool {
    matches!(value, Some(Value::Bool(true)))
}

fn lax_bool_of(value: &Value) -> Option<bool> {
    match value {
        Value::Bool(b) => Some(*b),
        Value::Number(n) => match n.as_i64() {
            Some(0) => Some(false),
            Some(1) => Some(true),
            // 0.0 and 1.0 are the only floats pydantic accepts as a bool
            _ => match n.to_string().as_str() {
                "0.0" => Some(false),
                "1.0" => Some(true),
                _ => None,
            },
        },
        Value::String(s) => match s.trim().to_lowercase().as_str() {
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
        Value::String(s) => s.trim().parse().ok(),
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
    fn only_a_json_true_is_true() {
        assert!(truthy(Some(&json!(true))));
        for no in [json!(false), json!(null), json!("true"), json!(1)] {
            assert!(!truthy(Some(&no)));
        }
        assert!(!truthy(None));
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
