//! Byte-compatible opening of the response ciphertext the Python backend
//! writes (`common/common/services/keyset.py`).
//!
//! `MASTER_ENCRYPTION_KEYSET` is a Tink JSON keyset (base64 of the JSON).
//! A stored value is the bytes `v1:` followed by a Tink AES-GCM ciphertext
//! with output prefix TINK: `0x01`, the key id (4 bytes, big endian), a
//! 12-byte nonce, the ciphertext and a 16-byte tag. The associated data is
//! the UTF-8 text `"{workspace_id}|{form_id}|"` followed by a per-field
//! context. Only AES-GCM keys with prefix TINK are understood; anything else
//! is refused, never guessed.
//!
//! The format is proven by `tests/tink_golden.rs`: values the Python backend
//! sealed open here, and a value sealed here opens in Python.

use aes_gcm::AeadCore;
use aes_gcm::aead::{Aead, KeyInit, OsRng, Payload};
use aes_gcm::{Aes128Gcm, Aes256Gcm, Nonce};
use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use serde_json::Value;

pub const PREFIX: &[u8] = b"v1:";
const AES_GCM_TYPE_URL: &str = "type.googleapis.com/google.crypto.tink.AesGcmKey";

#[derive(Debug, PartialEq, Eq)]
pub enum CryptoError {
    Keyset(&'static str),
    NotCiphertext,
    Unreadable,
}

impl std::fmt::Display for CryptoError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CryptoError::Keyset(why) => write!(f, "unusable keyset: {why}"),
            CryptoError::NotCiphertext => f.write_str("not a v1 ciphertext"),
            // never says why, never quotes the value (as UnreadableCiphertext)
            CryptoError::Unreadable => f.write_str("stored value could not be decrypted"),
        }
    }
}

impl std::error::Error for CryptoError {}

struct Key {
    id: u32,
    material: Vec<u8>,
}

/// The keys of a Tink keyset. Never printed: `Debug` shows counts only.
pub struct Keyset {
    keys: Vec<Key>,
    primary: u32,
}

impl std::fmt::Debug for Keyset {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Keyset")
            .field("keys", &self.keys.len())
            .field("primary", &self.primary)
            .finish()
    }
}

/// The `key_value` (field 3) of a serialized `AesGcmKey` proto.
fn aes_gcm_key_value(proto: &[u8]) -> Option<Vec<u8>> {
    let mut i = 0;
    while i < proto.len() {
        let tag = proto[i];
        i += 1;
        let (field, wire) = (tag >> 3, tag & 7);
        match wire {
            0 => {
                while i < proto.len() && proto[i] & 0x80 != 0 {
                    i += 1;
                }
                i += 1;
            }
            2 => {
                let mut len = 0usize;
                let mut shift = 0;
                loop {
                    let b = *proto.get(i)?;
                    i += 1;
                    len |= ((b & 0x7f) as usize) << shift;
                    shift += 7;
                    if b & 0x80 == 0 {
                        break;
                    }
                }
                let value = proto.get(i..i + len)?;
                i += len;
                if field == 3 {
                    return Some(value.to_vec());
                }
            }
            _ => return None,
        }
    }
    None
}

impl Keyset {
    /// `parse_keyset`: base64 of the JSON keyset, or the JSON itself.
    pub fn parse(value: &str) -> Result<Keyset, CryptoError> {
        let text = value.trim();
        let json = if text.starts_with('{') {
            text.to_string()
        } else {
            let raw = STANDARD
                .decode(text)
                .map_err(|_| CryptoError::Keyset("neither base64 nor JSON"))?;
            String::from_utf8(raw).map_err(|_| CryptoError::Keyset("neither base64 nor JSON"))?
        };
        let doc: Value = serde_json::from_str(&json)
            .map_err(|_| CryptoError::Keyset("not a Tink JSON keyset"))?;
        let primary = doc
            .get("primaryKeyId")
            .and_then(Value::as_u64)
            .and_then(|id| u32::try_from(id).ok())
            .ok_or(CryptoError::Keyset("no primary key"))?;
        let mut keys = Vec::new();
        for entry in doc
            .get("key")
            .and_then(Value::as_array)
            .ok_or(CryptoError::Keyset("no keys"))?
        {
            if entry.get("status").and_then(Value::as_str) != Some("ENABLED") {
                continue;
            }
            let data = entry
                .get("keyData")
                .ok_or(CryptoError::Keyset("key without data"))?;
            if data.get("typeUrl").and_then(Value::as_str) != Some(AES_GCM_TYPE_URL) {
                return Err(CryptoError::Keyset("a key that is not AES-GCM"));
            }
            if entry.get("outputPrefixType").and_then(Value::as_str) != Some("TINK") {
                return Err(CryptoError::Keyset("an output prefix other than TINK"));
            }
            let id = entry
                .get("keyId")
                .and_then(Value::as_u64)
                .and_then(|id| u32::try_from(id).ok())
                .ok_or(CryptoError::Keyset("key without id"))?;
            let proto = STANDARD
                .decode(data.get("value").and_then(Value::as_str).unwrap_or(""))
                .map_err(|_| CryptoError::Keyset("key value is not base64"))?;
            let material =
                aes_gcm_key_value(&proto).ok_or(CryptoError::Keyset("no key material"))?;
            if material.len() != 16 && material.len() != 32 {
                return Err(CryptoError::Keyset("unsupported key size"));
            }
            keys.push(Key { id, material });
        }
        if !keys.iter().any(|k| k.id == primary) {
            return Err(CryptoError::Keyset(
                "the primary key is not one of the keys",
            ));
        }
        Ok(Keyset { keys, primary })
    }

    pub fn primary_key_id(&self) -> u32 {
        self.primary
    }

    fn aad(workspace_id: &str, form_id: &str, context: &[u8]) -> Vec<u8> {
        let mut aad = format!("{workspace_id}|{form_id}|").into_bytes();
        aad.extend_from_slice(context);
        aad
    }

    fn seal_or_open(
        key: &Key,
        nonce: &[u8],
        data: &[u8],
        aad: &[u8],
        seal: bool,
    ) -> Option<Vec<u8>> {
        let nonce = Nonce::from_slice(nonce);
        let payload = Payload { msg: data, aad };
        macro_rules! run {
            ($cipher:ty) => {{
                let cipher = <$cipher>::new_from_slice(&key.material).ok()?;
                if seal {
                    cipher.encrypt(nonce, payload).ok()
                } else {
                    cipher.decrypt(nonce, payload).ok()
                }
            }};
        }
        if key.material.len() == 32 {
            run!(Aes256Gcm)
        } else {
            run!(Aes128Gcm)
        }
    }

    /// `CryptoService.decrypt`: a value without the `v1:` prefix is not
    /// ciphertext (Python returns it unchanged); here that is `NotCiphertext`.
    pub fn decrypt(
        &self,
        workspace_id: &str,
        form_id: &str,
        data: &[u8],
        context: &[u8],
    ) -> Result<Vec<u8>, CryptoError> {
        let body = data
            .strip_prefix(PREFIX)
            .ok_or(CryptoError::NotCiphertext)?;
        // 1 (version byte) + 4 (key id) + 12 (nonce) + 16 (tag)
        if body.len() < 33 || body[0] != 1 {
            return Err(CryptoError::Unreadable);
        }
        let id = u32::from_be_bytes([body[1], body[2], body[3], body[4]]);
        let key = self
            .keys
            .iter()
            .find(|k| k.id == id)
            .ok_or(CryptoError::Unreadable)?;
        let aad = Keyset::aad(workspace_id, form_id, context);
        Keyset::seal_or_open(key, &body[5..17], &body[17..], &aad, false)
            .ok_or(CryptoError::Unreadable)
    }

    /// `CryptoService.encrypt`: the primary key seals, with a nonce drawn
    /// from the operating system's CSPRNG. The result is the bytes `v1:` plus
    /// the Tink ciphertext, as the Python backend stores them.
    pub fn seal(
        &self,
        workspace_id: &str,
        form_id: &str,
        plaintext: &[u8],
        context: &[u8],
    ) -> Result<Vec<u8>, CryptoError> {
        let nonce = Aes256Gcm::generate_nonce(&mut OsRng);
        let mut bytes = [0u8; 12];
        bytes.copy_from_slice(&nonce);
        self.seal_with_nonce(workspace_id, form_id, plaintext, context, bytes)
    }

    /// Seals with a caller-chosen nonce. Reusing a nonce under one key breaks
    /// AES-GCM: only tests call this, to make a value reproducible.
    #[doc(hidden)]
    pub fn seal_with_nonce_for_tests(
        &self,
        workspace_id: &str,
        form_id: &str,
        plaintext: &[u8],
        context: &[u8],
        nonce: [u8; 12],
    ) -> Result<Vec<u8>, CryptoError> {
        self.seal_with_nonce(workspace_id, form_id, plaintext, context, nonce)
    }

    fn seal_with_nonce(
        &self,
        workspace_id: &str,
        form_id: &str,
        plaintext: &[u8],
        context: &[u8],
        nonce: [u8; 12],
    ) -> Result<Vec<u8>, CryptoError> {
        let key = self
            .keys
            .iter()
            .find(|k| k.id == self.primary)
            .ok_or(CryptoError::Unreadable)?;
        let aad = Keyset::aad(workspace_id, form_id, context);
        let sealed = Keyset::seal_or_open(key, &nonce, plaintext, &aad, true)
            .ok_or(CryptoError::Unreadable)?;
        let mut out = PREFIX.to_vec();
        out.push(1);
        out.extend_from_slice(&key.id.to_be_bytes());
        out.extend_from_slice(&nonce);
        out.extend_from_slice(&sealed);
        Ok(out)
    }
}
