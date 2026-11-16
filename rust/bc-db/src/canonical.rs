//! The canonical bytes of a document and its checksum, as Python writes them
//! (`common/records/canonical.py`, `common/db/canonical.py`).
//!
//! `_bc_checksum` is `sha256:` plus the hex SHA-256 of
//! `json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
//! allow_nan=False)`, UTF-8. The rules that matter when another language
//! writes them:
//!
//! * keys sorted by code point (UTF-8 byte order is the same order);
//! * a string escapes only `"`, `\`, `\b \f \n \r \t` and the other control
//!   characters below U+0020 as `\u00xx` (lowercase hex); everything else,
//!   non-ASCII included, is written as it is;
//! * an integer in decimal; a float as Python's `repr`: the shortest digits
//!   that round-trip, positional notation for decimal exponents -4 to 15 and
//!   `1e+16` / `1.5e-07` style outside, always a `.0` on a whole number;
//! * NaN and the infinities are refused.

use std::fmt::Write as _;

use serde_json::{Number, Value};
use sha2::{Digest, Sha256};

pub const CHECKSUM_PREFIX: &str = "sha256:";

/// Why a value has no canonical form.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NotCanonical;

impl std::fmt::Display for NotCanonical {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("a non-finite number has no canonical JSON form")
    }
}

impl std::error::Error for NotCanonical {}

/// `canonical_json(value)` as a string.
pub fn canonical_json(value: &Value) -> Result<String, NotCanonical> {
    let mut out = String::new();
    write_value(&mut out, value)?;
    Ok(out)
}

/// `sha256:<hex>` of the canonical JSON (the `_bc_checksum` column).
pub fn checksum(value: &Value) -> Result<String, NotCanonical> {
    let text = canonical_json(value)?;
    Ok(format!(
        "{CHECKSUM_PREFIX}{}",
        hex::encode(Sha256::digest(text.as_bytes()))
    ))
}

fn write_value(out: &mut String, value: &Value) -> Result<(), NotCanonical> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(n) => write_number(out, n)?,
        Value::String(s) => write_string(out, s),
        Value::Array(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_value(out, item)?;
            }
            out.push(']');
        }
        Value::Object(map) => {
            let mut entries: Vec<(&String, &Value)> = map.iter().collect();
            entries.sort_by(|a, b| a.0.as_bytes().cmp(b.0.as_bytes()));
            out.push('{');
            for (i, (key, item)) in entries.into_iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_string(out, key);
                out.push(':');
                write_value(out, item)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

fn write_number(out: &mut String, n: &Number) -> Result<(), NotCanonical> {
    if let Some(i) = n.as_i64() {
        out.push_str(&i.to_string());
    } else if let Some(u) = n.as_u64() {
        out.push_str(&u.to_string());
    } else {
        out.push_str(&python_float_repr(n.as_f64().ok_or(NotCanonical)?)?);
    }
    Ok(())
}

fn write_string(out: &mut String, text: &str) {
    out.push('"');
    for c in text.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

/// `repr(float)`.
pub fn python_float_repr(f: f64) -> Result<String, NotCanonical> {
    if !f.is_finite() {
        return Err(NotCanonical);
    }
    if f == 0.0 {
        return Ok(if f.is_sign_negative() { "-0.0" } else { "0.0" }.to_string());
    }
    // Rust's `{:e}` is the shortest round-trip digits, `d.ddde<exp>`
    let sci = format!("{:e}", f.abs());
    let (mantissa, exponent) = sci.split_once('e').ok_or(NotCanonical)?;
    let exponent: i32 = exponent.parse().map_err(|_| NotCanonical)?;
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    let decpt = exponent + 1; // the decimal point sits after this many digits
    let sign = if f < 0.0 { "-" } else { "" };
    let n = i32::try_from(digits.len()).map_err(|_| NotCanonical)?;
    let body = if decpt <= -4 || decpt > 16 {
        let mut s = digits[..1].to_string();
        if digits.len() > 1 {
            s.push('.');
            s.push_str(&digits[1..]);
        }
        let e = decpt - 1;
        format!("{s}e{}{:02}", if e < 0 { '-' } else { '+' }, e.abs())
    } else if decpt <= 0 {
        format!(
            "0.{}{digits}",
            "0".repeat(usize::try_from(-decpt).map_err(|_| NotCanonical)?)
        )
    } else if decpt >= n {
        format!(
            "{digits}{}.0",
            "0".repeat(usize::try_from(decpt - n).map_err(|_| NotCanonical)?)
        )
    } else {
        let at = usize::try_from(decpt).map_err(|_| NotCanonical)?;
        format!("{}.{}", &digits[..at], &digits[at..])
    };
    Ok(format!("{sign}{body}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn floats_print_like_python_repr() {
        for (f, want) in [
            (0.1 + 0.2, "0.30000000000000004"),
            (1.0, "1.0"),
            (-2.5, "-2.5"),
            (100.0, "100.0"),
            (1e15, "1000000000000000.0"),
            (1e16, "1e+16"),
            (1.5e16, "1.5e+16"),
            (123_456_789_012_345_680.0, "1.2345678901234568e+17"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (1.5e-7, "1.5e-07"),
            (1e100, "1e+100"),
            (5e-324, "5e-324"),
            (f64::MAX, "1.7976931348623157e+308"),
            (0.5, "0.5"),
            (12345.678, "12345.678"),
            (-0.0, "-0.0"),
            (0.0, "0.0"),
        ] {
            assert_eq!(python_float_repr(f).unwrap(), want, "{f:?}");
        }
        assert!(python_float_repr(f64::NAN).is_err());
        assert!(python_float_repr(f64::INFINITY).is_err());
    }

    #[test]
    fn keys_sort_by_code_point_and_text_is_not_ascii_escaped() {
        let value =
            json!({"b": 1, "a": {"z": [true, null], "é": "tëxt ✓ \"q\" \\ \n\u{1}\u{7f}"}, "B": 2});
        assert_eq!(
            canonical_json(&value).unwrap(),
            "{\"B\":2,\"a\":{\"z\":[true,null],\"é\":\"tëxt ✓ \\\"q\\\" \\\\ \\n\\u0001\u{7f}\"},\"b\":1}"
        );
    }

    #[test]
    fn the_checksum_is_the_prefixed_sha256_of_the_canonical_text() {
        // python: "sha256:" + sha256(b'{"a":1}').hexdigest()
        assert_eq!(
            checksum(&json!({"a": 1})).unwrap(),
            "sha256:015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"
        );
    }
}
