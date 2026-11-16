//! `json.dumps` as Python writes it, for the values whose text is hashed or
//! signed: ASCII only (`ensure_ascii`), optional key sorting, and either the
//! default separators (`", "` and `": "`) or the compact ones (`","`, `":"`).
//!
//! An object's keys come out sorted (a `serde_json` map is ordered by key), so
//! `DEFAULT` and `COMPACT` differ from Python for an object written in another
//! order; anything hashed or signed from an object uses `CANONICAL`, which sorts
//! in Python too. Lists are written in order.
//!
//! Floats follow `repr(float)` (shortest round-trip digits, an exponent below
//! 1e-4 and from 1e16 on). Integers beyond 64 bits are not representable in a
//! `serde_json::Value` and are not supported.

use std::fmt::Write as _;

use serde_json::Value;

#[derive(Clone, Copy, Debug)]
pub struct Options {
    pub sort_keys: bool,
    /// `separators=(",", ":")` when true, Python's default `(", ", ": ")` when false.
    pub compact: bool,
}

/// `json.dumps(value)`.
pub const DEFAULT: Options = Options {
    sort_keys: false,
    compact: false,
};
/// `json.dumps(value, separators=(",", ":"))`.
pub const COMPACT: Options = Options {
    sort_keys: false,
    compact: true,
};
/// `json.dumps(value, sort_keys=True, separators=(",", ":"))`.
pub const CANONICAL: Options = Options {
    sort_keys: true,
    compact: true,
};

pub fn dumps(value: &Value, options: Options) -> String {
    let mut out = String::new();
    write(value, options, &mut out);
    out
}

fn write(value: &Value, options: Options, out: &mut String) {
    let (item, key) = if options.compact {
        (",", ":")
    } else {
        (", ", ": ")
    };
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                out.push_str(&i.to_string());
            } else if let Some(u) = n.as_u64() {
                out.push_str(&u.to_string());
            } else {
                out.push_str(&float_repr(n.as_f64().unwrap_or(f64::NAN)));
            }
        }
        Value::String(s) => string(s, out),
        Value::Array(items) => {
            out.push('[');
            for (i, v) in items.iter().enumerate() {
                if i > 0 {
                    out.push_str(item);
                }
                write(v, options, out);
            }
            out.push(']');
        }
        Value::Object(map) => {
            out.push('{');
            let mut entries: Vec<(&String, &Value)> = map.iter().collect();
            if options.sort_keys {
                // code point order, which is UTF-8 byte order
                entries.sort_by(|a, b| a.0.cmp(b.0));
            }
            for (i, (k, v)) in entries.into_iter().enumerate() {
                if i > 0 {
                    out.push_str(item);
                }
                string(k, out);
                out.push_str(key);
                write(v, options, out);
            }
            out.push('}');
        }
    }
}

/// A JSON string with everything outside space..`~` escaped (`ensure_ascii`).
pub fn string(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            ' '..='~' => out.push(c),
            _ => {
                let mut units = [0u16; 2];
                for unit in c.encode_utf16(&mut units) {
                    let _ = write!(out, "\\u{unit:04x}");
                }
            }
        }
    }
    out.push('"');
}

/// `json.dumps("text")` for one string.
pub fn quote(s: &str) -> String {
    let mut out = String::new();
    string(s, &mut out);
    out
}

/// `repr(float)`.
pub fn float_repr(f: f64) -> String {
    if f.is_nan() {
        return "NaN".into();
    }
    if f.is_infinite() {
        return if f < 0.0 { "-Infinity" } else { "Infinity" }.into();
    }
    let sign = if f.is_sign_negative() { "-" } else { "" };
    if f == 0.0 {
        return format!("{sign}0.0");
    }
    let sci = format!("{:e}", f.abs());
    let (mantissa, exp) = sci.split_once('e').unwrap_or((&sci, "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    if (-4..16).contains(&exp) {
        if exp >= 0 {
            let int_len = usize::try_from(exp).unwrap_or(0) + 1;
            let mut int_part = digits.clone();
            while int_part.len() < int_len {
                int_part.push('0');
            }
            let (whole, frac) = int_part.split_at(int_len);
            let frac = if frac.is_empty() { "0" } else { frac };
            format!("{sign}{whole}.{frac}")
        } else {
            format!(
                "{sign}0.{}{digits}",
                "0".repeat(usize::try_from(-exp - 1).unwrap_or(0))
            )
        }
    } else {
        let head = &digits[..1];
        let tail = &digits[1..];
        let point = if tail.is_empty() {
            String::new()
        } else {
            format!(".{tail}")
        };
        let esign = if exp < 0 { '-' } else { '+' };
        format!("{sign}{head}{point}e{esign}{:02}", exp.abs())
    }
}
