//! The primitives of the proof-of-work challenge (`services/captcha/challenge.py`).
//!
//! A challenge is `<base64url(claims JSON)>.<signature>` (the signature is the
//! signed-token one, over the payload alone, label below); the proof header
//! `X-BC-Captcha` is `<challenge>.<8 counters>`. A counter solves a sub-puzzle
//! when SHA-256 of `"<challenge>:<index>:<counter>"` has enough leading zero
//! bits. The claims' policy (purpose, form, expiry, difficulty range) is the
//! captcha service's.

use bc_config::secrets::KeyRing;
use sha2::{Digest, Sha256};

use crate::prim::{SubKey, b64url, derive_all, hmac_sha256};

pub const LABEL: &[u8] = b"bettercollected/captcha-challenge/v1";
pub const SUBPUZZLES: usize = 8;
pub const SUBPUZZLE_SHIFT: i64 = 3;
pub const MAX_HEADER_LENGTH: usize = 1024;
pub const MAX_COUNTER_DIGITS: usize = 12;
pub const TAG_BYTES: usize = 8;

pub fn keys(ring: &KeyRing) -> Vec<SubKey> {
    derive_all(ring, LABEL)
}

/// The UTC day number a challenge was issued on.
pub fn day_number(unix_seconds: i64) -> i64 {
    unix_seconds.div_euclid(86400)
}

/// `ip_tag`: a short tag of the client's network that only the server can
/// compute, salted per UTC day; empty for an unknown client.
pub fn ip_tag(key: &SubKey, day: i64, client: &str) -> String {
    if client.is_empty() {
        return String::new();
    }
    let salt = key.mac(format!("captcha-ip-salt|{day}").as_bytes());
    let tag = hmac_sha256(&salt, client.as_bytes());
    hex::encode(&tag[..TAG_BYTES])
}

/// `payload.signature`, signed by `key`.
pub fn sign_payload(key: &SubKey, claims_json: &str) -> String {
    let payload = b64url(claims_json.as_bytes());
    format!("{payload}.{}", key.mac_b64(&payload))
}

/// The three parts of a proof header, or `None` when it is too long, not
/// ASCII or not three dot-separated parts.
pub fn split_header(header: &str) -> Option<(&str, &str, &str)> {
    if header.len() > MAX_HEADER_LENGTH || !header.is_ascii() {
        return None;
    }
    let mut parts = header.split('.');
    let (payload, signature, counters) = (parts.next()?, parts.next()?, parts.next()?);
    parts
        .next()
        .is_none()
        .then_some((payload, signature, counters))
}

/// Which key (by position) signed `payload`, comparing every key.
pub fn signing_key_position(keys: &[SubKey], payload: &str, signature: &str) -> Option<usize> {
    let mut found = None;
    for (position, key) in keys.iter().enumerate() {
        if crate::prim::ct_eq(key.mac_b64(payload).as_bytes(), signature.as_bytes()) {
            found = Some(position);
        }
    }
    found
}

/// `leading_zero_bits`.
pub fn leading_zero_bits(digest: &[u8]) -> u32 {
    let mut bits = 0;
    for byte in digest {
        if *byte == 0 {
            bits += 8;
        } else {
            return bits + byte.leading_zeros();
        }
    }
    bits
}

/// `subpuzzle_bits`.
pub fn subpuzzle_bits(bits: i64) -> i64 {
    bits - SUBPUZZLE_SHIFT
}

/// Whether the counters solve every sub-puzzle of `solved` (`payload.signature`)
/// at `bits` of difficulty: eight counters of 1 to 12 ASCII digits.
pub fn proof_solves(solved: &str, counters: &str, bits: i64) -> bool {
    let values: Vec<&str> = counters.split(',').collect();
    if values.len() != SUBPUZZLES
        || !values.iter().all(|v| {
            (1..=MAX_COUNTER_DIGITS).contains(&v.len()) && v.bytes().all(|b| b.is_ascii_digit())
        })
    {
        return false;
    }
    let need = subpuzzle_bits(bits);
    values.iter().enumerate().all(|(index, value)| {
        let digest = Sha256::digest(format!("{solved}:{index}:{value}").as_bytes());
        i64::from(leading_zero_bits(&digest)) >= need
    })
}

/// The counters that solve `challenge` (what the browser does; for tests and
/// tools).
pub fn solve(challenge: &str, bits: i64) -> Vec<u64> {
    let need = subpuzzle_bits(bits);
    (0..SUBPUZZLES)
        .map(|index| {
            let mut counter = 0u64;
            loop {
                let digest = Sha256::digest(format!("{challenge}:{index}:{counter}").as_bytes());
                if i64::from(leading_zero_bits(&digest)) >= need {
                    return counter;
                }
                counter += 1;
            }
        })
        .collect()
}

/// The id a spent nonce is remembered under: SHA-256 hex of the nonce with
/// non-ASCII characters dropped (`encode("ascii", "ignore")`).
pub fn spent_nonce_id(nonce: &str) -> String {
    let ascii: String = nonce.chars().filter(char::is_ascii).collect();
    crate::prim::sha256_hex(ascii.as_bytes())
}
