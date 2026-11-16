//! Keys derived from `SETTINGS_MASTER_KEY`, row and manifest signatures, and the
//! envelope that seals a stored secret: `common/settings/{keys,signing}.py` and
//! `common/settings/crypto/{keys,envelope}.py`.
//!
//! Rows are signed with a per-section key, the manifest with a section-less one,
//! and a secret's data key is wrapped under a per-section key. A reader holds
//! the keys of the sections its service reads and nothing else. Every key is
//! derived from the current master key and, during a rotation, from the
//! previous one too: verification and opening try the current key first.

use std::collections::HashMap;
use std::fmt;

use aes_gcm::aead::{Aead, KeyInit, Payload};
use aes_gcm::{Aes256Gcm, Nonce};
use base64::Engine;
use base64::alphabet;
use base64::engine::general_purpose::{GeneralPurpose, GeneralPurposeConfig};
use hkdf::Hkdf;
use hmac::{Hmac, Mac};
use sha2::Sha256;

use super::canonical::{CanonicalError, Manifest, Row, canonical_manifest, canonical_row};

const HKDF_SALT: &[u8] = b"bettercollected/admin/hkdf-salt/v1";
const NAMESPACE: &str = "settings";
const MIN_MASTER_KEY_BYTES: usize = 32;
const MIN_DISTINCT_KEY_BYTES: usize = 8;
const KEY_BYTES: usize = 32;
const NONCE_BYTES: usize = 12;

type Key = [u8; KEY_BYTES];

/// The master key is unusable. The message never shows it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KeyError(pub &'static str);

impl fmt::Display for KeyError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.0)
    }
}

/// Standard base64 and the URL-safe alphabet, padding required, non-canonical
/// trailing bits tolerated (Python's decoder does).
const fn lenient(alphabet: &alphabet::Alphabet, padded: bool) -> GeneralPurpose {
    GeneralPurpose::new(
        alphabet,
        GeneralPurposeConfig::new()
            .with_decode_allow_trailing_bits(true)
            .with_decode_padding_mode(if padded {
                base64::engine::DecodePaddingMode::RequireCanonical
            } else {
                base64::engine::DecodePaddingMode::RequireNone
            }),
    )
}

const STANDARD: GeneralPurpose = lenient(&alphabet::STANDARD, true);
const URL_SAFE: GeneralPurpose = lenient(&alphabet::URL_SAFE, true);
const URL_SAFE_NO_PAD: GeneralPurpose = lenient(&alphabet::URL_SAFE, false);

/// `parse_master_key`: base64 (either alphabet) of at least 32 bytes that do
/// not repeat a pattern.
pub fn parse_master_key(raw: &str) -> Result<Vec<u8>, KeyError> {
    let value = raw.trim();
    if value.is_empty() {
        return Err(KeyError("SETTINGS_MASTER_KEY is not set"));
    }
    let mut padded = value.to_string();
    while !padded.len().is_multiple_of(4) {
        padded.push('=');
    }
    let key = STANDARD
        .decode(&padded)
        .or_else(|_| URL_SAFE.decode(&padded))
        .map_err(|_| KeyError("SETTINGS_MASTER_KEY is not valid base64"))?;
    if key.len() < MIN_MASTER_KEY_BYTES {
        return Err(KeyError("SETTINGS_MASTER_KEY is too short"));
    }
    let mut seen = [false; 256];
    for byte in &key {
        seen[usize::from(*byte)] = true;
    }
    if seen.iter().filter(|s| **s).count() < MIN_DISTINCT_KEY_BYTES {
        return Err(KeyError("SETTINGS_MASTER_KEY does not look random"));
    }
    Ok(key)
}

/// `derive_from_master`: HKDF-SHA256 with the fixed salt and
/// `info = namespace/purpose/v<version>[/context]`.
pub fn derive_from_master(master: &[u8], purpose: &str, context: Option<&str>) -> Key {
    let info = match context {
        Some(c) => format!("{NAMESPACE}/{purpose}/v1/{c}"),
        None => format!("{NAMESPACE}/{purpose}/v1"),
    };
    let hk = Hkdf::<Sha256>::new(Some(HKDF_SALT), master);
    let mut out = [0u8; KEY_BYTES];
    // 32 bytes is far below the HKDF-SHA256 limit: this cannot fail
    if hk.expand(info.as_bytes(), &mut out).is_err() {
        out = [0u8; KEY_BYTES];
    }
    out
}

fn mac_hex(key: &Key, message: &[u8]) -> String {
    // HMAC accepts a key of any length
    let Ok(mut mac) = <Hmac<Sha256> as Mac>::new_from_slice(key) else {
        return String::new();
    };
    mac.update(message);
    hex::encode(mac.finalize().into_bytes())
}

/// Constant time on the bytes (the lengths of two signatures are public).
fn same(a: &str, b: &str) -> bool {
    let (a, b) = (a.as_bytes(), b.as_bytes());
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

pub fn sign_row(row: &Row, key: &[u8; 32]) -> Result<String, CanonicalError> {
    Ok(mac_hex(key, &canonical_row(row)?))
}

pub fn sign_manifest(manifest: &Manifest, key: &[u8; 32]) -> Result<String, CanonicalError> {
    Ok(mac_hex(
        key,
        &canonical_manifest(manifest.revision, &manifest.entries)?,
    ))
}

/// The settings keys of a reader of `sections`.
pub struct SectionKeys {
    sign: Vec<Key>,
    row_sign: HashMap<String, Vec<Key>>,
    wrap: HashMap<String, Vec<Key>>,
    fingerprint: String,
}

impl fmt::Debug for SectionKeys {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let mut sections: Vec<&String> = self.row_sign.keys().collect();
        sections.sort();
        write!(f, "SectionKeys(sections={sections:?})")
    }
}

impl SectionKeys {
    pub fn new(
        master: &str,
        previous: Option<&str>,
        sections: &[String],
    ) -> Result<SectionKeys, KeyError> {
        let mut masters = vec![parse_master_key(master)?];
        if let Some(previous) = previous.filter(|p| !p.trim().is_empty()) {
            let previous = parse_master_key(previous)?;
            if previous != masters[0] {
                masters.push(previous);
            }
        }
        let valid = |s: &str| {
            (1..=64).contains(&s.len())
                && s.bytes()
                    .all(|c| c.is_ascii_alphanumeric() || b"_.:-".contains(&c))
        };
        if sections.iter().any(|s| !valid(s)) {
            return Err(KeyError("section has unsupported characters"));
        }
        let sign = masters
            .iter()
            .map(|m| derive_from_master(m, "sign", None))
            .collect();
        let per_section = |purpose: &str| -> HashMap<String, Vec<Key>> {
            sections
                .iter()
                .map(|s| {
                    (
                        s.clone(),
                        masters
                            .iter()
                            .map(|m| derive_from_master(m, purpose, Some(s)))
                            .collect(),
                    )
                })
                .collect()
        };
        let fingerprint = hex::encode(&derive_from_master(&masters[0], "fp", None)[..6]);
        Ok(SectionKeys {
            sign,
            row_sign: per_section("sign"),
            wrap: per_section("wrap"),
            fingerprint,
        })
    }

    /// A short, non-reversible id of the current master key, for reports.
    pub fn fingerprint(&self) -> &str {
        &self.fingerprint
    }

    pub fn verify_row(&self, row: &Row) -> bool {
        let Some(keys) = self.row_sign.get(&row.section) else {
            return false;
        };
        keys.iter()
            .any(|k| sign_row(row, k).is_ok_and(|expected| same(&row.sig, &expected)))
    }

    pub fn verify_manifest(&self, manifest: &Manifest) -> bool {
        self.sign.iter().any(|k| {
            sign_manifest(manifest, k).is_ok_and(|expected| same(&manifest.sig, &expected))
        })
    }

    /// Signs a row with the current key (tests and the harness's golden checks).
    pub fn sign_row_current(&self, row: &Row) -> Option<String> {
        sign_row(row, self.row_sign.get(&row.section)?.first()?).ok()
    }

    pub fn sign_manifest_current(&self, manifest: &Manifest) -> Option<String> {
        sign_manifest(manifest, self.sign.first()?).ok()
    }

    /// The plaintext of a secret row's blob; the current key first, then the
    /// previous one. `None` for any failure (the cause is never reported).
    pub fn open(&self, section: &str, key: &str, version: u64, blob: &str) -> Option<String> {
        self.wrap
            .get(section)?
            .iter()
            .find_map(|kek| decrypt_v2(blob, kek, key, version, section))
    }
}

// ------------------------------------------------------------- envelope v2
//
// v2:<kek_id>:<dek_nonce>:<wrapped_dek>:<nonce>:<ciphertext>, base64url without
// padding. The value is sealed under a data key with AAD "v2|key|version|section";
// the data key is wrapped under the section key with AAD "v2|kek_id|key|version".

fn b64(text: &str) -> Option<Vec<u8>> {
    if text.is_empty()
        || !text
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'_' || c == b'-')
    {
        return None;
    }
    URL_SAFE_NO_PAD.decode(text).ok()
}

fn open_gcm(key: &[u8], nonce: &[u8], data: &[u8], aad: &[u8]) -> Option<Vec<u8>> {
    let cipher = Aes256Gcm::new_from_slice(key).ok()?;
    cipher
        .decrypt(Nonce::from_slice(nonce), Payload { msg: data, aad })
        .ok()
}

/// `envelope.decrypt_v2` + a UTF-8 decode.
pub fn decrypt_v2(
    blob: &str,
    kek: &[u8; 32],
    key: &str,
    version: u64,
    section: &str,
) -> Option<String> {
    let parts: Vec<&str> = blob.split(':').collect();
    if parts.len() != 6 || parts[0] != "v2" {
        return None;
    }
    let kek_id = parts[1];
    if !(1..=32).contains(&kek_id.len())
        || !kek_id
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"_.-".contains(&c))
    {
        return None;
    }
    let dek_nonce = b64(parts[2])?;
    let wrapped = b64(parts[3])?;
    let nonce = b64(parts[4])?;
    let ciphertext = b64(parts[5])?;
    if dek_nonce.len() != NONCE_BYTES
        || nonce.len() != NONCE_BYTES
        || wrapped.len() != KEY_BYTES + 16
    {
        return None;
    }
    let dek = open_gcm(
        kek,
        &dek_nonce,
        &wrapped,
        format!("v2|{kek_id}|{key}|{version}").as_bytes(),
    )?;
    let plain = open_gcm(
        &dek,
        &nonce,
        &ciphertext,
        format!("v2|{key}|{version}|{section}").as_bytes(),
    )?;
    String::from_utf8(plain).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn master() -> String {
        base64::engine::general_purpose::STANDARD.encode((0u8..48).collect::<Vec<_>>())
    }

    #[test]
    fn a_master_key_must_be_long_enough_and_look_random() {
        assert!(parse_master_key(&master()).is_ok());
        assert!(parse_master_key("").is_err());
        assert!(parse_master_key("not base64 !!").is_err());
        let short = base64::engine::general_purpose::STANDARD.encode((0u8..16).collect::<Vec<_>>());
        assert!(parse_master_key(&short).is_err());
        let flat = base64::engine::general_purpose::STANDARD.encode([7u8; 48]);
        assert!(parse_master_key(&flat).is_err());
        // the URL-safe alphabet and a missing padding are accepted
        let url = base64::engine::general_purpose::URL_SAFE_NO_PAD
            .encode((200u8..248).collect::<Vec<_>>());
        assert!(parse_master_key(&url).is_ok());
    }

    #[test]
    fn errors_never_show_the_key() {
        let flat = base64::engine::general_purpose::STANDARD.encode([7u8; 48]);
        let err = parse_master_key(&flat).unwrap_err();
        assert!(!err.to_string().contains(&flat));
    }

    #[test]
    fn a_section_the_reader_does_not_hold_cannot_be_verified_or_opened() {
        let keys = SectionKeys::new(&master(), None, &["mail".to_string()]).unwrap();
        assert!(keys.open("sso", "K", 1, "v2:a:b:c:d:e").is_none());
        assert!(format!("{keys:?}").contains("mail"));
    }
}
