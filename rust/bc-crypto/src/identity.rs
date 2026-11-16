//! The respondent identity (`app/utils/respondent_identity.py`).
//!
//! A stored identity is `v2:` + hex HMAC-SHA256 under the respondent identity
//! key of the lower-case hex MD5 of the email (the older, unkeyed value, still
//! the input of the keyed one). The key is hex or base64 text of at least 32
//! bytes (`decode_identity_key`). Whether a key is random enough is the start-up
//! check's business (`common/settings/secret_checks.py`); a key that passed it
//! decodes here to the same bytes.

use base64::Engine;
use base64::alphabet;
use base64::engine::{DecodePaddingMode, GeneralPurpose, GeneralPurposeConfig};
use md5::{Digest, Md5};
use zeroize::Zeroizing;

use crate::CryptoError;
use crate::prim::{ct_eq, hmac_sha256};

pub const PREFIX: &str = "v2:";
pub const KEY_CHECK_LABEL: &[u8] = b"bettercollected/respondent-identity/key-check/v1";
pub const MIN_KEY_BYTES: usize = 32;

/// The respondent identity key. Never printed.
pub struct IdentityKey(Zeroizing<Vec<u8>>);

impl IdentityKey {
    /// `decode_identity_key` (its decoding rules; not its randomness checks):
    /// surrounding whitespace ignored; text of only hex digits is hex (an odd
    /// length is refused, hex is never read as base64); anything else is
    /// base64, standard or URL-safe alphabet, padding optional, strict.
    pub fn parse(configured: &str) -> Result<IdentityKey, CryptoError> {
        let text = configured.trim();
        let raw = if !text.is_empty() && text.bytes().all(|b| b.is_ascii_hexdigit()) {
            if text.len() % 2 == 1 {
                return Err(CryptoError::Key("unusable identity key"));
            }
            hex::decode(text).map_err(|_| CryptoError::Key("unusable identity key"))?
        } else {
            let padded = format!("{text}{}", "=".repeat((4 - text.len() % 4) % 4));
            let standard = padded.replace('-', "+").replace('_', "/");
            // Python's strict decoder does not check the unused trailing bits
            GeneralPurpose::new(
                &alphabet::STANDARD,
                GeneralPurposeConfig::new()
                    .with_decode_allow_trailing_bits(true)
                    .with_decode_padding_mode(DecodePaddingMode::RequireCanonical),
            )
            .decode(standard)
            .map_err(|_| CryptoError::Key("unusable identity key"))?
        };
        if raw.len() < MIN_KEY_BYTES {
            return Err(CryptoError::Key("unusable identity key"));
        }
        Ok(IdentityKey(Zeroizing::new(raw)))
    }

    pub fn from_bytes(raw: &[u8]) -> IdentityKey {
        IdentityKey(Zeroizing::new(raw.to_vec()))
    }

    pub fn bytes(&self) -> &[u8] {
        &self.0
    }

    /// `key_check_value`: HMAC-SHA256(key, label) hex; says which key
    /// converted the stored identities without being the key.
    pub fn check_value(&self) -> String {
        hex::encode(hmac_sha256(&self.0, KEY_CHECK_LABEL))
    }

    /// `derive`: `v2:` + `HMAC-SHA256(key, md5_hex)`, lower-case hex.
    pub fn derive(&self, legacy_md5_hex: &str) -> String {
        format!(
            "{PREFIX}{}",
            hex::encode(hmac_sha256(&self.0, legacy_md5_hex.as_bytes()))
        )
    }

    /// `identity_of`: the value stored for the signed-in email.
    pub fn identity_of(&self, email: &str) -> String {
        self.derive(&md5_hex(email))
    }

    /// `matches`: constant time; empty or not `v2:` never matches.
    pub fn matches(&self, stored: &str, email: &str) -> bool {
        is_v2(stored) && ct_eq(stored.as_bytes(), self.identity_of(email).as_bytes())
    }

    /// `convert_legacy`: a v2 value is returned as it is.
    pub fn convert_legacy(&self, stored: &str) -> String {
        if is_v2(stored) {
            stored.to_string()
        } else {
            self.derive(stored)
        }
    }
}

impl std::fmt::Debug for IdentityKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("IdentityKey(<redacted>)")
    }
}

pub fn is_v2(stored: &str) -> bool {
    stored.starts_with(PREFIX)
}

/// `hash_string`: lower-case hex MD5 of the UTF-8 text (the legacy identity;
/// the input of the keyed one, never a secret by itself).
pub fn md5_hex(text: &str) -> String {
    hex::encode(Md5::digest(text.as_bytes()))
}
