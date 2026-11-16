//! Links and tokens of the form `<expiry>.<hex HMAC-SHA256>` over a JSON list.
//!
//! - the response export link (`services/response_export/links.py`): key
//!   `key_ring.derive(member, "bettercollected/response-export/link/v1")` over
//!   the JWT ring, message `json.dumps([export, workspace, form, user, expiry])`
//!   (Python's default separators), valid for five minutes;
//! - the action run token (`services/action_run_token.py`): key
//!   `HMAC(respondent identity key, "bettercollected/action-run/token/v2")`,
//!   message `json.dumps([workspace, form, action, response, expiry])`, valid
//!   for 24 hours.
//!
//! Times are passed in (seconds, as Python's `time.time()` float).

#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss
)]
// (Unix seconds as Python's `time.time()` float: exact far beyond the year 2100;
// the casts below only move between that float and whole seconds.)

use bc_config::secrets::KeyRing;
use serde_json::Value;

use crate::prim::{SubKey, ct_eq, derive_all};
use crate::pyjson;

pub const EXPORT_LABEL: &[u8] = b"bettercollected/response-export/link/v1";
pub const EXPORT_TTL_SECONDS: u64 = 5 * 60;
pub const RUN_TOKEN_LABEL: &[u8] = b"bettercollected/action-run/token/v2";
pub const RUN_TOKEN_TTL_SECONDS: u64 = 24 * 3600;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Check {
    Valid,
    /// Ours, past its time.
    Expired,
    /// Anything else: malformed, another subject, tampered.
    Invalid,
}

fn message(ids: &[&str], expiry: u64) -> Vec<u8> {
    let mut items: Vec<Value> = ids.iter().map(|id| Value::from(*id)).collect();
    items.push(Value::from(expiry));
    pyjson::dumps(&Value::Array(items), pyjson::DEFAULT).into_bytes()
}

fn sign(key: &SubKey, ids: &[&str], expiry: u64) -> String {
    key.mac_hex(&message(ids, expiry))
}

fn issue(key: &SubKey, ids: &[&str], now: f64, ttl: u64) -> String {
    let expiry = (now + ttl as f64) as u64;
    format!("{expiry}.{}", sign(key, ids, expiry))
}

fn check(keys: &[SubKey], token: &str, ids: &[&str], now: f64, ascii_only: bool) -> Check {
    let (expiry_text, signature) = token.split_once('.').unwrap_or((token, ""));
    if (ascii_only && !expiry_text.is_ascii())
        || expiry_text.is_empty()
        || !expiry_text.bytes().all(|b| b.is_ascii_digit())
        || signature.is_empty()
    {
        return Check::Invalid;
    }
    let Ok(expiry) = expiry_text.parse::<u64>() else {
        return Check::Invalid;
    };
    let mut right = false;
    for key in keys {
        right |= ct_eq(signature.as_bytes(), sign(key, ids, expiry).as_bytes());
    }
    if !right {
        Check::Invalid
    } else if now > expiry as f64 {
        Check::Expired
    } else {
        Check::Valid
    }
}

pub fn export_keys(ring: &KeyRing) -> Vec<SubKey> {
    derive_all(ring, EXPORT_LABEL)
}

pub fn issue_export_link(keys: &[SubKey], ids: [&str; 4], now: f64) -> Option<String> {
    Some(issue(keys.first()?, &ids, now, EXPORT_TTL_SECONDS))
}

/// `ids` are export, workspace, form and user.
pub fn check_export_link(keys: &[SubKey], token: &str, ids: [&str; 4], now: f64) -> Check {
    check(keys, token, &ids, now, true)
}

/// The run-token key of a respondent identity key.
pub fn run_token_key(identity_key: &[u8]) -> SubKey {
    SubKey::derive_raw(identity_key, RUN_TOKEN_LABEL)
}

/// `ids` are workspace, form, action and response.
pub fn run_token(key: &SubKey, ids: [&str; 4], now: f64) -> String {
    issue(key, &ids, now, RUN_TOKEN_TTL_SECONDS)
}

pub fn check_run_token(key: &SubKey, token: &str, ids: [&str; 4], now: f64) -> Check {
    check(std::slice::from_ref(key), token, &ids, now, false)
}

/// `run_lock`: the queueing lock of a run.
pub fn run_lock(action_id: &str, form_id: &str, response_id: &str) -> String {
    format!("action_{action_id}{form_id}{response_id}")
}
