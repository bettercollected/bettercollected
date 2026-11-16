//! The bytes that are signed for one settings row and for the manifest:
//! `common/settings/canonical.py`, byte for byte.
//!
//! Length-prefixed fields under a domain tag. Rust and Python must produce the
//! same bytes, so JSON values are written the way Python's
//! `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)` writes
//! them (sorted keys, ASCII only, Python's float spelling).

use std::collections::BTreeMap;
use std::fmt::{self, Write as _};

use serde_json::Value;

pub const ROW_DOMAIN: &[u8] = b"bc-settings-row-v1";
pub const MANIFEST_DOMAIN: &[u8] = b"bc-settings-manifest-v1";

/// A row cannot be encoded. Never carries the value.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CanonicalError;

impl fmt::Display for CanonicalError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("row cannot be encoded")
    }
}

/// One stored setting. A secret carries `blob` (envelope v2 text) and no
/// `value`; any other row the reverse. `sig` is the hex HMAC.
#[derive(Clone, PartialEq)]
pub struct Row {
    pub key: String,
    pub section: String,
    pub readers: Vec<String>,
    pub is_secret: bool,
    pub reload_class: String,
    pub version: u64,
    /// `YYYY-MM-DDTHH:MM:SS.ffffffZ` (UTC, microseconds), as Python writes it.
    pub updated_at: String,
    pub value: Option<Value>,
    pub blob: Option<String>,
    pub sig: String,
}

impl fmt::Debug for Row {
    // never the value or the blob
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Row(key={:?}, version={})", self.key, self.version)
    }
}

/// The signed `key -> (version, row signature, sorted readers)` map at one
/// revision.
#[derive(Clone, PartialEq, Debug)]
pub struct Manifest {
    pub revision: u64,
    pub entries: BTreeMap<String, (u64, String, Vec<String>)>,
    pub sig: String,
}

impl Manifest {
    /// Keys the signed manifest says `service` may read.
    pub fn keys_for(&self, service: &str) -> Vec<String> {
        self.entries
            .iter()
            .filter(|(_, (_, _, readers))| readers.iter().any(|r| r == service))
            .map(|(k, _)| k.clone())
            .collect()
    }
}

fn lp(out: &mut Vec<u8>, data: &[u8]) {
    // a length over 4 GiB cannot occur: a row is at most a few kilobytes
    out.extend_from_slice(&u32::try_from(data.len()).unwrap_or(u32::MAX).to_be_bytes());
    out.extend_from_slice(data);
}

/// `YYYY-MM-DDTHH:MM:SS.ffffffZ`
pub fn is_canonical_timestamp(text: &str) -> bool {
    let b = text.as_bytes();
    if b.len() != 27 {
        return false;
    }
    b.iter().enumerate().all(|(i, c)| match i {
        4 | 7 => *c == b'-',
        10 => *c == b'T',
        13 | 16 => *c == b':',
        19 => *c == b'.',
        26 => *c == b'Z',
        _ => c.is_ascii_digit(),
    })
}

pub fn canonical_row(row: &Row) -> Result<Vec<u8>, CanonicalError> {
    if row.is_secret {
        if row.blob.is_none() || row.value.is_some() {
            return Err(CanonicalError);
        }
    } else if row.blob.is_some() {
        return Err(CanonicalError);
    }
    let mut unique: Vec<&String> = row.readers.iter().collect();
    unique.sort();
    let before = unique.len();
    unique.dedup();
    if unique.is_empty() || unique.len() != before {
        return Err(CanonicalError);
    }
    if !["B", "H", "R"].contains(&row.reload_class.as_str()) {
        return Err(CanonicalError);
    }
    if !is_canonical_timestamp(&row.updated_at) {
        return Err(CanonicalError);
    }
    let (kind, payload): (&[u8], String) = match &row.blob {
        Some(blob) => (b"b", blob.clone()),
        None => (
            b"v",
            canonical_json(row.value.as_ref().unwrap_or(&Value::Null))?,
        ),
    };
    let mut out = Vec::new();
    lp(&mut out, ROW_DOMAIN);
    lp(&mut out, row.key.as_bytes());
    lp(&mut out, row.section.as_bytes());
    out.extend_from_slice(
        &u32::try_from(unique.len())
            .map_err(|_| CanonicalError)?
            .to_be_bytes(),
    );
    for reader in &unique {
        lp(&mut out, reader.as_bytes());
    }
    lp(&mut out, if row.is_secret { b"1" } else { b"0" });
    lp(&mut out, row.reload_class.as_bytes());
    lp(&mut out, kind);
    lp(&mut out, payload.as_bytes());
    out.extend_from_slice(&row.version.to_be_bytes());
    lp(&mut out, row.updated_at.as_bytes());
    Ok(out)
}

pub fn canonical_manifest(
    manifest_revision: u64,
    entries: &BTreeMap<String, (u64, String, Vec<String>)>,
) -> Result<Vec<u8>, CanonicalError> {
    let mut lines = Vec::new();
    // BTreeMap iterates in key order, which is Python's sorted() on str for UTF-8
    for (key, (version, sig, readers)) in entries {
        if key.contains([':', ',']) || readers.iter().any(|r| r.contains([',', ':'])) {
            return Err(CanonicalError);
        }
        let mut readers = readers.clone();
        readers.sort();
        lines.push(format!("{key}:{version}:{sig}:{}", readers.join(",")));
    }
    let mut out = Vec::new();
    lp(&mut out, MANIFEST_DOMAIN);
    out.extend_from_slice(&manifest_revision.to_be_bytes());
    out.extend_from_slice(
        &u32::try_from(lines.len())
            .map_err(|_| CanonicalError)?
            .to_be_bytes(),
    );
    for line in &lines {
        lp(&mut out, line.as_bytes());
    }
    Ok(out)
}

// ----------------------------------------------------------------- JSON text

/// Python's `json.dumps(value, sort_keys=True, separators=(",", ":"),
/// ensure_ascii=True, allow_nan=False)`.
pub fn canonical_json(value: &Value) -> Result<String, CanonicalError> {
    let mut out = String::new();
    write_json(value, &mut out)?;
    Ok(out)
}

fn write_json(value: &Value, out: &mut String) -> Result<(), CanonicalError> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                out.push_str(&i.to_string());
            } else if let Some(u) = n.as_u64() {
                out.push_str(&u.to_string());
            } else if let Some(f) = n.as_f64() {
                out.push_str(&python_float_repr(f)?);
            } else {
                return Err(CanonicalError);
            }
        }
        Value::String(s) => write_string(s, out),
        Value::Array(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_json(item, out)?;
            }
            out.push(']');
        }
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            out.push('{');
            for (i, key) in keys.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_string(key, out);
                out.push(':');
                if let Some(item) = map.get(*key) {
                    write_json(item, out)?;
                }
            }
            out.push('}');
        }
    }
    Ok(())
}

/// ASCII 0x20..=0x7e as is (except `"` and `\`); everything else escaped.
fn write_string(text: &str, out: &mut String) {
    out.push('"');
    for ch in text.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            ' '..='~' => out.push(ch),
            _ => {
                let mut units = [0u16; 2];
                for unit in ch.encode_utf16(&mut units) {
                    let _ = write!(out, "\\u{unit:04x}");
                }
            }
        }
    }
    out.push('"');
}

/// `repr(float)`: shortest round-trip digits; positional for decimal exponents
/// from -4 to 15, scientific (`1e-05`, `1.5e+16`) outside; `.0` on a whole number.
pub fn python_float_repr(value: f64) -> Result<String, CanonicalError> {
    if !value.is_finite() {
        return Err(CanonicalError);
    }
    if value == 0.0 {
        return Ok(if value.is_sign_negative() {
            "-0.0"
        } else {
            "0.0"
        }
        .to_string());
    }
    let sci = format!("{:e}", value.abs());
    let (mantissa, exp) = sci.split_once('e').ok_or(CanonicalError)?;
    let exp: i32 = exp.parse().map_err(|_| CanonicalError)?;
    let digits: String = mantissa.chars().filter(char::is_ascii_digit).collect();
    let sign = if value < 0.0 { "-" } else { "" };
    let body = if !(-4..16).contains(&exp) {
        let frac = &digits[1..];
        let head = if frac.is_empty() {
            digits.clone()
        } else {
            format!("{}.{frac}", &digits[..1])
        };
        format!("{head}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs())
    } else if exp >= 0 {
        let point = usize::try_from(exp).map_err(|_| CanonicalError)? + 1;
        if digits.len() <= point {
            format!("{digits}{}.0", "0".repeat(point - digits.len()))
        } else {
            format!("{}.{}", &digits[..point], &digits[point..])
        }
    } else {
        format!(
            "0.{}{digits}",
            "0".repeat(usize::try_from(-exp - 1).map_err(|_| CanonicalError)?)
        )
    };
    Ok(format!("{sign}{body}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn floats_are_spelled_as_python_spells_them() {
        for (value, text) in [
            (15.0, "15.0"),
            (0.5, "0.5"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (1.5e-7, "1.5e-07"),
            (1e15, "1000000000000000.0"),
            (1e16, "1e+16"),
            (1.5e16, "1.5e+16"),
            (123_456.789, "123456.789"),
            (-2.5, "-2.5"),
            (-0.0, "-0.0"),
            (1e100, "1e+100"),
            (0.1 + 0.2, "0.30000000000000004"),
        ] {
            assert_eq!(python_float_repr(value).unwrap(), text, "{value}");
        }
        assert!(python_float_repr(f64::NAN).is_err());
    }

    #[test]
    fn json_is_sorted_ascii_and_compact() {
        let value = json!({"b": [1, 2.0, "é\u{1F600}\"\\\n\u{7f}"], "a": null, "c": true});
        assert_eq!(
            canonical_json(&value).unwrap(),
            "{\"a\":null,\"b\":[1,2.0,\"\\u00e9\\ud83d\\ude00\\\"\\\\\\n\\u007f\"],\"c\":true}"
        );
    }

    #[test]
    fn a_secret_row_needs_a_blob_and_a_plain_row_must_not_have_one() {
        let mut row = Row {
            key: "K".into(),
            section: "s".into(),
            readers: vec!["backend".into()],
            is_secret: true,
            reload_class: "R".into(),
            version: 1,
            updated_at: "2026-01-02T03:04:05.000006Z".into(),
            value: None,
            blob: None,
            sig: String::new(),
        };
        assert!(canonical_row(&row).is_err());
        row.blob = Some("v2:x".into());
        assert!(canonical_row(&row).is_ok());
        row.is_secret = false;
        assert!(canonical_row(&row).is_err());
        row.blob = None;
        row.value = Some(json!(true));
        assert!(canonical_row(&row).is_ok());
        row.readers = vec!["a".into(), "a".into()];
        assert!(canonical_row(&row).is_err());
    }

    #[test]
    fn the_debug_form_of_a_row_hides_its_value() {
        let row = Row {
            key: "K".into(),
            section: "s".into(),
            readers: vec!["backend".into()],
            is_secret: false,
            reload_class: "R".into(),
            version: 3,
            updated_at: "2026-01-02T03:04:05.000006Z".into(),
            value: Some(json!("hunter2")),
            blob: None,
            sig: "abc".into(),
        };
        let shown = format!("{row:?}");
        assert!(shown.contains('K') && !shown.contains("hunter2") && !shown.contains("abc"));
    }
}
