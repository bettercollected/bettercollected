//! Request signatures between systems: the webhooks the backend sends
//! (`services/webhooks/payload.py`) and the SCIM events Polis posts
//! (`services/scim/signature.py`). Both are HMAC-SHA256, keyed with the
//! shared secret as UTF-8 text, over `"<timestamp>." + raw body`.

#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss
)]
// (Unix seconds as Python's `time.time()` float: exact far beyond the year 2100;
// the casts below only move between that float and whole seconds.)

use crate::prim::{ct_eq, hmac_sha256};

fn mac(secret: &str, timestamp: i64, body: &[u8]) -> String {
    let mut message = format!("{timestamp}.").into_bytes();
    message.extend_from_slice(body);
    hex::encode(hmac_sha256(secret.as_bytes(), &message))
}

/// The outgoing webhook signature: `sha256=<hex>` (the timestamp in seconds).
pub fn webhook_sign(secret: &str, timestamp: i64, body: &[u8]) -> String {
    format!("sha256={}", mac(secret, timestamp, body))
}

/// What a receiver does, in constant time.
pub fn webhook_verify(secret: &str, timestamp: i64, body: &[u8], signature: &str) -> bool {
    ct_eq(
        webhook_sign(secret, timestamp, body).as_bytes(),
        signature.as_bytes(),
    )
}

/// Why a Polis signature was not accepted (for logs and metrics only; the
/// caller answers the same 401).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BadSignature {
    Missing,
    Malformed,
    Expired,
    NoSecret,
    Mismatch,
}

/// `BoxyHQ-Signature: t=<unix ms>,s=<64 hex>`: (timestamp, signature). The
/// first `t` and the first `s` count; other keys are ignored.
pub fn scim_parse(header: Option<&str>) -> Result<(i64, &str), BadSignature> {
    let header = header
        .filter(|h| !h.is_empty() && h.len() <= 512)
        .ok_or(BadSignature::Missing)?;
    let (mut t, mut s) = (None, None);
    for item in header.split(',') {
        let (key, value) = item.trim().split_once('=').unwrap_or((item.trim(), ""));
        if value.is_empty() {
            continue;
        }
        match key {
            "t" if t.is_none() => t = Some(value),
            "s" if s.is_none() => s = Some(value),
            _ => {}
        }
    }
    let timestamp = t
        .and_then(|t| t.trim().parse::<i64>().ok())
        .ok_or(BadSignature::Malformed)?;
    let signature = s.ok_or(BadSignature::Malformed)?;
    if signature.chars().count() != 64 {
        return Err(BadSignature::Malformed);
    }
    Ok((timestamp, signature))
}

/// `sign`: the header Polis would send (tests and local tools).
pub fn scim_sign(secret: &str, body: &[u8], timestamp_ms: i64) -> String {
    format!("t={timestamp_ms},s={}", mac(secret, timestamp_ms, body))
}

/// `verify`: the signed timestamp (ms) when the header signs `body` with
/// `secret` within `tolerance_seconds` of `now_seconds`.
pub fn scim_verify(
    header: Option<&str>,
    body: &[u8],
    secret: &str,
    tolerance_seconds: i64,
    now_seconds: f64,
) -> Result<i64, BadSignature> {
    let (timestamp, signature) = scim_parse(header)?;
    let now_ms = now_seconds * 1000.0;
    if (now_ms - timestamp as f64).abs() > (tolerance_seconds * 1000) as f64 {
        return Err(BadSignature::Expired);
    }
    if secret.is_empty() {
        return Err(BadSignature::NoSecret);
    }
    if !signature.is_ascii() {
        return Err(BadSignature::Malformed);
    }
    let expected = mac(secret, timestamp, body);
    if ct_eq(
        expected.as_bytes(),
        signature.to_ascii_lowercase().as_bytes(),
    ) {
        Ok(timestamp)
    } else {
        Err(BadSignature::Mismatch)
    }
}
