//! The primitives every derived value is built from: HMAC-SHA256, SHA-256,
//! constant-time comparison, URL-safe base64 as Python's `base64` module reads
//! and writes it, and the sub-key derivation of `common/settings/key_ring.py`.

use base64::Engine;
use base64::alphabet;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::engine::{GeneralPurpose, GeneralPurposeConfig};
use bc_config::secrets::KeyRing;
use hmac::{Hmac, Mac};
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;
use zeroize::Zeroizing;

type HmacSha256 = Hmac<Sha256>;

/// `hmac.new(key, message, sha256).digest()`.
pub fn hmac_sha256(key: &[u8], message: &[u8]) -> [u8; 32] {
    // HMAC accepts a key of any length, so this cannot fail
    let mut mac = HmacSha256::new_from_slice(key).unwrap_or_else(|_| unreachable!());
    mac.update(message);
    mac.finalize().into_bytes().into()
}

/// Lower-case hex SHA-256.
pub fn sha256_hex(data: &[u8]) -> String {
    hex::encode(Sha256::digest(data))
}

/// `hmac.compare_digest`: the time taken does not depend on where two values of
/// the same length differ (a different length answers false at once, as it
/// does in Python).
pub fn ct_eq(a: &[u8], b: &[u8]) -> bool {
    a.ct_eq(b).into()
}

/// A key derived from a ring member for one purpose. Never printed.
pub struct SubKey(Zeroizing<[u8; 32]>);

impl SubKey {
    /// `key_ring.derive(member, label)`: HMAC-SHA256 keyed with the member's
    /// text (UTF-8 bytes, as it is), over the purpose label.
    pub fn derive(member: &str, label: &[u8]) -> SubKey {
        SubKey(Zeroizing::new(hmac_sha256(member.as_bytes(), label)))
    }

    /// `hashlib.sha256(label + member.encode()).digest()`, the older pattern
    /// the draft secrets and the rate limiter use.
    pub fn hashed(member: &str, label: &[u8]) -> SubKey {
        let mut input = Zeroizing::new(label.to_vec());
        input.extend_from_slice(member.as_bytes());
        SubKey(Zeroizing::new(Sha256::digest(&*input).into()))
    }

    /// `hmac.new(raw, label, sha256).digest()` for a raw key (the respondent
    /// identity key).
    pub fn derive_raw(key: &[u8], label: &[u8]) -> SubKey {
        SubKey(Zeroizing::new(hmac_sha256(key, label)))
    }

    pub fn mac(&self, message: &[u8]) -> [u8; 32] {
        hmac_sha256(&*self.0, message)
    }

    pub fn mac_hex(&self, message: &[u8]) -> String {
        hex::encode(self.mac(message))
    }

    /// The signature of the signed tokens: URL-safe base64 of the MAC, no
    /// padding, over the ASCII text.
    pub fn mac_b64(&self, text: &str) -> String {
        b64url(&self.mac(text.as_bytes()))
    }
}

impl std::fmt::Debug for SubKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("SubKey(<redacted>)")
    }
}

/// `key_ring.derive_all`: one sub-key per member, current first.
pub fn derive_all(ring: &KeyRing, label: &[u8]) -> Vec<SubKey> {
    ring.members()
        .map(|member| SubKey::derive(member, label))
        .collect()
}

/// Whether `signature` is the MAC of `text` under any of the keys. Every key is
/// always computed and compared (no early exit), as the Python callers do.
pub fn verifies_b64(keys: &[SubKey], text: &str, signature: &str) -> bool {
    let mut ok = false;
    for key in keys {
        ok |= ct_eq(key.mac_b64(text).as_bytes(), signature.as_bytes());
    }
    ok
}

/// `base64.urlsafe_b64encode(data).rstrip(b"=")`.
pub fn b64url(data: &[u8]) -> String {
    URL_SAFE_NO_PAD.encode(data)
}

/// `base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))`, the `_unb64` of
/// the signed-token modules.
pub fn unb64url(text: &str) -> Option<Vec<u8>> {
    let mut padded = text.to_string();
    padded.push_str(&"=".repeat((4 - text.len() % 4) % 4));
    py_urlsafe_b64decode(&padded)
}

/// `base64.urlsafe_b64decode(text)` for every input a Python-written value can
/// be: bytes outside the base64 alphabet (a newline, a space) are skipped, as
/// `CPython` skips them, and what remains must be canonical padded base64 (the
/// URL-safe and the standard alphabet both read). `CPython` also tolerates
/// padding in odd places (`YQ====`, a leading `=`) and its behaviour there has
/// changed between releases; those are refused here. `None` where Python
/// raises, and for those forms.
pub fn py_urlsafe_b64decode(text: &str) -> Option<Vec<u8>> {
    if !text.is_ascii() {
        return None;
    }
    let mut chars: Vec<u8> = Vec::with_capacity(text.len());
    let mut pads = 0usize;
    for &byte in text.as_bytes() {
        match byte {
            b'=' => {
                pads += 1;
                chars.push(b'=');
            }
            b'-' => chars.push(b'+'),
            b'_' => chars.push(b'/'),
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'+' | b'/' => {
                if pads > 0 {
                    return None; // data after the padding
                }
                chars.push(byte);
            }
            _ => {}
        }
    }
    if pads > 2 || !chars.len().is_multiple_of(4) {
        return None;
    }
    // CPython does not check the unused trailing bits
    let engine = GeneralPurpose::new(
        &alphabet::STANDARD,
        GeneralPurposeConfig::new().with_decode_allow_trailing_bits(true),
    );
    engine.decode(&chars).ok()
}
