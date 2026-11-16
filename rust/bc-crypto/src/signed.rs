//! The signed, client-held tokens: `<version>.<base64url(claims JSON)>.<signature>`.
//!
//! The signature is the URL-safe, unpadded base64 of HMAC-SHA256 over the
//! ASCII text `<version>.<payload>` (the response-list cursor appends
//! `|<filter fingerprint>`, which is signed but never in the token), keyed with
//! a sub-key of one member of the JWT key ring (`key_ring.derive(member,
//! label)`). Member 0 mints; every member verifies, every member is always
//! computed. What the claims must say (the form, the time window) is checked by
//! the module that owns the token, with [`within_window`].

use bc_config::secrets::KeyRing;
use serde_json::Value;

use crate::prim::{SubKey, b64url, derive_all, unb64url, verifies_b64};
use crate::pyjson;

/// One kind of token: its key-derivation label and its version prefix.
#[derive(Clone, Copy, Debug)]
pub struct Purpose {
    pub label: &'static [u8],
    pub version: &'static str,
}

/// `services/response_cursor.py`.
pub const RESPONSE_CURSOR: Purpose = Purpose {
    label: b"bettercollected/response-list-cursor/v1",
    version: "c1",
};
/// `services/ai/notice_token.py`.
pub const AI_NOTICE: Purpose = Purpose {
    label: b"bettercollected/ai-insights-notice-token/v1",
    version: "v1",
};
/// `services/option_sources/share_token.py`.
pub const OPTION_SHARE: Purpose = Purpose {
    label: b"bettercollected/option-share-notice-token/v1",
    version: "v1",
};

pub const TOKEN_TTL_MS: i64 = 24 * 3600 * 1000;
pub const CLOCK_SKEW_MS: i64 = 2 * 60 * 1000;
pub const MAX_CURSOR_LENGTH: usize = 2048;
pub const MAX_NOTICE_LENGTH: usize = 2048;
pub const MAX_QUESTIONS: usize = 100;
pub const MAX_ID_LENGTH: usize = 64;
/// `share_token.MAX_TOKEN_LENGTH`.
pub const MAX_OPTION_SHARE_LENGTH: usize =
    4 * (MAX_QUESTIONS * (MAX_ID_LENGTH + 3) + 512).div_ceil(3) + 64;

/// The sub-keys of a purpose, current first (empty for an empty ring: the
/// server then issues and accepts nothing).
pub fn keys(ring: &KeyRing, purpose: Purpose) -> Vec<SubKey> {
    derive_all(ring, purpose.label)
}

/// Mints a token with `keys[0]`; `None` without a key. `signed_suffix` is text
/// that is signed but not carried (the cursor's filter fingerprint).
pub fn issue(
    keys: &[SubKey],
    purpose: Purpose,
    claims: &Value,
    signed_suffix: Option<&str>,
) -> Option<String> {
    let key = keys.first()?;
    let payload = b64url(pyjson::dumps(claims, pyjson::COMPACT).as_bytes());
    let body = format!("{}.{payload}", purpose.version);
    let signed = signed_text(&body, signed_suffix);
    Some(format!("{body}.{}", key.mac_b64(&signed)))
}

/// The claims of a token whose signature is good under any key. `None` for
/// anything else (wrong shape, wrong version, bad signature, claims that are
/// not a JSON object): the caller refuses without saying why.
pub fn open(
    keys: &[SubKey],
    purpose: Purpose,
    token: &str,
    signed_suffix: Option<&str>,
    max_length: usize,
) -> Option<Value> {
    if keys.is_empty() || token.len() > max_length {
        return None;
    }
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 || parts[0] != purpose.version {
        return None;
    }
    let body = format!("{}.{}", parts[0], parts[1]);
    if !verifies_b64(keys, &signed_text(&body, signed_suffix), parts[2]) {
        return None;
    }
    let claims: Value = serde_json::from_slice(&unb64url(parts[1])?).ok()?;
    claims.is_object().then_some(claims)
}

fn signed_text(body: &str, suffix: Option<&str>) -> String {
    match suffix {
        Some(suffix) => format!("{body}|{suffix}"),
        None => body.to_string(),
    }
}

/// The freshness rule the tokens share: not issued more than `skew_ms` in the
/// future, not older than `ttl_ms`.
pub fn within_window(issued_ms: i64, now_ms: i64, ttl_ms: i64, skew_ms: i64) -> bool {
    !(issued_ms > now_ms + skew_ms || now_ms - issued_ms > ttl_ms)
}
