//! One-time passwords and recovery codes (`common/security/totp.py`,
//! `common/security/recovery.py`, `services/mfa/sealing.py`): RFC 6238 TOTP
//! (HMAC-SHA-1, 6 digits, 30-second step, one step of drift) and the unkeyed
//! SHA-256 of a recovery code bound to its user.

use hmac::{Hmac, Mac};
use sha1::Sha1;
use subtle::ConstantTimeEq;

use crate::prim::sha256_hex;

pub const DIGITS: u32 = 6;
pub const STEP_SECONDS: u64 = 30;
pub const DRIFT_STEPS: u64 = 1;
const SECRET_BYTES: usize = 20;
const RECOVERY_CHARS: usize = 16;
const HASH_LABEL: &[u8] = b"bettercollected recovery code v1\0";
const B32: &[u8; 32] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

/// `generate_secret`: 20 random bytes as 32 base32 characters.
pub fn generate_secret() -> String {
    b32_encode(&crate::random::bytes::<SECRET_BYTES>())
}

fn b32_encode(data: &[u8]) -> String {
    let mut out = String::new();
    let (mut buffer, mut bits) = (0u32, 0u32);
    for byte in data {
        buffer = (buffer << 8) | u32::from(*byte);
        bits += 8;
        while bits >= 5 {
            out.push(B32[((buffer >> (bits - 5)) & 31) as usize] as char);
            bits -= 5;
        }
    }
    if bits > 0 {
        out.push(B32[((buffer << (5 - bits)) & 31) as usize] as char);
    }
    out
}

/// `decode_secret`: case, whitespace and padding tolerated; `None` for
/// anything that is not base32 (Python raises `ValueError`).
pub fn decode_secret(secret: &str) -> Option<Vec<u8>> {
    let cleaned: String = secret
        .split_whitespace()
        .collect::<String>()
        .to_uppercase()
        .trim_end_matches('=')
        .to_string();
    if cleaned.is_empty() {
        return None;
    }
    let (mut buffer, mut bits) = (0u32, 0u32);
    let mut out = Vec::new();
    for c in cleaned.bytes() {
        let value = u32::try_from(B32.iter().position(|b| *b == c)?).ok()?;
        buffer = (buffer << 5) | value;
        bits += 5;
        if bits >= 8 {
            out.push(u8::try_from(buffer >> (bits - 8)).ok()?);
            bits -= 8;
            buffer &= (1 << bits) - 1;
        }
    }
    // a base32 text of 1, 3 or 6 characters (mod 8) is not a whole number of bytes
    matches!(cleaned.len() % 8, 0 | 2 | 4 | 5 | 7).then_some(out)
}

/// `hotp`: RFC 4226 with HMAC-SHA-1.
pub fn hotp(key: &[u8], counter: u64) -> String {
    let mut mac = Hmac::<Sha1>::new_from_slice(key).unwrap_or_else(|_| unreachable!());
    mac.update(&counter.to_be_bytes());
    let digest = mac.finalize().into_bytes();
    let offset = (digest[19] & 0x0f) as usize;
    let value = u32::from_be_bytes([
        digest[offset],
        digest[offset + 1],
        digest[offset + 2],
        digest[offset + 3],
    ]) & 0x7fff_ffff;
    format!(
        "{:0width$}",
        value % 10u32.pow(DIGITS),
        width = DIGITS as usize
    )
}

/// `code_at`.
pub fn code_at(secret: &str, unix_seconds: f64) -> Option<String> {
    Some(hotp(&decode_secret(secret)?, step_for(unix_seconds)))
}

#[allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss
)]
pub fn step_for(unix_seconds: f64) -> u64 {
    // Unix seconds as a float are exact far beyond the year 2100
    (unix_seconds / STEP_SECONDS as f64).floor().max(0.0) as u64
}

/// `verify`: the matched step when the code is valid within the drift, else
/// `None`. Never fails on malformed input; every candidate step is compared in
/// constant time whatever an earlier one gave.
pub fn verify(secret: &str, code: &str, unix_seconds: f64, drift: u64) -> Option<u64> {
    let candidate: String = code.split_whitespace().collect();
    if candidate.len() != DIGITS as usize || !candidate.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let key = decode_secret(secret)?;
    let now_step = step_for(unix_seconds);
    let mut matched = None;
    for step in now_step.saturating_sub(drift)..=now_step + drift {
        let equal: bool = hotp(&key, step)
            .as_bytes()
            .ct_eq(candidate.as_bytes())
            .into();
        if equal && matched.is_none() {
            matched = Some(step);
        }
    }
    matched
}

/// `next_last_used_step`: the step to store, or `None` for a replay.
pub fn next_last_used_step(last_used: Option<u64>, matched: u64) -> Option<u64> {
    match last_used {
        Some(last) if matched <= last => None,
        _ => Some(matched),
    }
}

/// `normalise`: upper-case with spaces, dashes, tabs and newlines removed.
pub fn normalise_recovery_code(code: &str) -> String {
    code.to_uppercase()
        .chars()
        .filter(|c| !" -\t\r\n".contains(*c))
        .collect()
}

/// `is_well_formed`.
pub fn recovery_code_well_formed(code: &str) -> bool {
    let norm = normalise_recovery_code(code);
    norm.len() == RECOVERY_CHARS && norm.bytes().all(|b| B32.contains(&b))
}

/// `generate_code`: 80 random bits as four groups of four base32 characters.
pub fn generate_recovery_code() -> String {
    let raw = b32_encode(&crate::random::bytes::<10>());
    raw.as_bytes()
        .chunks(4)
        .map(|c| String::from_utf8_lossy(c).into_owned())
        .collect::<Vec<_>>()
        .join("-")
}

/// `hash_recovery_code`: SHA-256 hex of `label + user id + NUL + normalised code`.
pub fn hash_recovery_code(user_id: &str, code: &str) -> String {
    let mut message = HASH_LABEL.to_vec();
    message.extend_from_slice(user_id.as_bytes());
    message.push(0);
    message.extend_from_slice(normalise_recovery_code(code).as_bytes());
    sha256_hex(&message)
}
