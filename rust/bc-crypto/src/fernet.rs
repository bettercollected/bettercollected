//! The Fernet key ring of the Python backend (`common/configs/crypto.py`).
//!
//! `AUTH_AES_HEX_KEY` holds one Fernet key or two (`<current>,<previous>`).
//! Everything is sealed with the first; a value sealed with any member opens
//! (`MultiFernet`). A token is `0x80`, an 8-byte big-endian timestamp, a
//! 16-byte IV, the AES-128-CBC ciphertext (PKCS7) and a 32-byte HMAC-SHA256
//! tag, all URL-safe base64 with padding. The key is 32 bytes: the first 16
//! sign, the last 16 encrypt.
//!
//! Where Python's `cryptography` is lenient (base64 reading), so is this; where
//! it refuses (a time limit, a token from the future), so does this. Every
//! failure is the same `InvalidToken`: nothing says which check failed.

use aes::Aes128;
use base64::Engine;
use base64::engine::general_purpose::URL_SAFE;
use bc_config::secrets::KeyRing;
use cbc::cipher::block_padding::Pkcs7;
use cbc::cipher::{BlockDecryptMut, BlockEncryptMut, KeyIvInit};
use hmac::{Hmac, Mac};
use sha2::Sha256;
use zeroize::Zeroizing;

use crate::CryptoError;
use crate::prim::py_urlsafe_b64decode;

const VERSION: u8 = 0x80;
/// `cryptography`'s `_MAX_CLOCK_SKEW`: with a time limit, a token stamped more
/// than this far ahead of the clock is refused.
const MAX_CLOCK_SKEW: u64 = 60;
const MAC_LEN: usize = 32;
const HEADER_LEN: usize = 1 + 8 + 16;

/// One Fernet key. Never printed.
pub struct FernetKey {
    signing: Zeroizing<[u8; 16]>,
    encryption: Zeroizing<[u8; 16]>,
}

impl FernetKey {
    /// `Fernet(key)`: URL-safe base64 of exactly 32 bytes.
    pub fn parse(text: &str) -> Result<FernetKey, CryptoError> {
        let raw = py_urlsafe_b64decode(text)
            .map(Zeroizing::new)
            .ok_or(CryptoError::Key("a Fernet key must be url-safe base64"))?;
        if raw.len() != 32 {
            return Err(CryptoError::Key("a Fernet key must be 32 bytes"));
        }
        let mut signing = Zeroizing::new([0u8; 16]);
        let mut encryption = Zeroizing::new([0u8; 16]);
        signing.copy_from_slice(&raw[..16]);
        encryption.copy_from_slice(&raw[16..]);
        Ok(FernetKey {
            signing,
            encryption,
        })
    }

    fn mac(&self, data: &[u8]) -> Hmac<Sha256> {
        // a 16-byte key is always accepted
        let mut mac =
            Hmac::<Sha256>::new_from_slice(&*self.signing).unwrap_or_else(|_| unreachable!());
        mac.update(data);
        mac
    }

    fn seal_at(&self, plaintext: &[u8], now: u64, iv: [u8; 16]) -> String {
        let ciphertext = cbc::Encryptor::<Aes128>::new(&(*self.encryption).into(), &iv.into())
            .encrypt_padded_vec_mut::<Pkcs7>(plaintext);
        let mut data = Vec::with_capacity(HEADER_LEN + ciphertext.len() + MAC_LEN);
        data.push(VERSION);
        data.extend_from_slice(&now.to_be_bytes());
        data.extend_from_slice(&iv);
        data.extend_from_slice(&ciphertext);
        let tag = self.mac(&data).finalize().into_bytes();
        data.extend_from_slice(&tag);
        URL_SAFE.encode(data)
    }

    /// `_decrypt_data` of `cryptography`, on the already-decoded token.
    fn open(&self, data: &[u8], ttl: Option<u64>, now: u64) -> Option<Vec<u8>> {
        if data.len() < HEADER_LEN + MAC_LEN {
            return None;
        }
        let timestamp = u64::from_be_bytes(data[1..9].try_into().ok()?);
        if let Some(ttl) = ttl {
            if timestamp.checked_add(ttl)? < now {
                return None;
            }
            if now + MAX_CLOCK_SKEW < timestamp {
                return None;
            }
        }
        let (signed, tag) = data.split_at(data.len() - MAC_LEN);
        // verify_slice is constant time
        self.mac(signed).verify_slice(tag).ok()?;
        let iv: [u8; 16] = signed[9..HEADER_LEN].try_into().ok()?;
        let ciphertext = &signed[HEADER_LEN..];
        if ciphertext.is_empty() || ciphertext.len() % 16 != 0 {
            return None;
        }
        cbc::Decryptor::<Aes128>::new(&(*self.encryption).into(), &iv.into())
            .decrypt_padded_vec_mut::<Pkcs7>(ciphertext)
            .ok()
    }
}

impl std::fmt::Debug for FernetKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("FernetKey(<redacted>)")
    }
}

/// `Crypto`: the ring of Fernet keys, current first.
#[derive(Debug)]
pub struct FernetRing {
    ring: KeyRing,
    keys: Vec<FernetKey>,
}

/// Seconds since the epoch: the clock Fernet stamps and checks with
/// (`int(time.time())`).
pub fn unix_now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs())
}

impl FernetRing {
    /// The ring of an `AUTH_AES_HEX_KEY` value (`<current>[,<previous>]`, the
    /// text as an env file means it: trimmed, one pair of quotes removed). A
    /// bad or empty key fails here, as `Fernet()` always has.
    pub fn parse(value: &str) -> Result<FernetRing, CryptoError> {
        let members = bc_config::secrets::fernet_members(Some(value));
        if members.is_empty() {
            return Err(CryptoError::Key("no Fernet key"));
        }
        FernetRing::from_ring(KeyRing::from_members(members))
    }

    pub fn from_ring(ring: KeyRing) -> Result<FernetRing, CryptoError> {
        let keys = ring
            .members()
            .map(FernetKey::parse)
            .collect::<Result<Vec<_>, _>>()?;
        if keys.is_empty() {
            return Err(CryptoError::Key("no Fernet key"));
        }
        Ok(FernetRing { ring, keys })
    }

    /// How many keys the ring holds (`member_count`).
    pub fn member_count(&self) -> usize {
        self.keys.len()
    }

    /// `Crypto.encrypt`: sealed with the first key, now, with a fresh IV from
    /// the operating system.
    pub fn seal(&self, plaintext: &[u8]) -> String {
        self.seal_at(plaintext, unix_now(), crate::random::bytes::<16>())
    }

    /// Sealed at a given time with a given IV. Reusing an IV is harmless for
    /// Fernet's confidentiality only when the plaintext differs; only tests
    /// call this, to make a token reproducible.
    #[doc(hidden)]
    pub fn seal_at(&self, plaintext: &[u8], now: u64, iv: [u8; 16]) -> String {
        self.keys[0].seal_at(plaintext, now, iv)
    }

    /// `Crypto.decrypt` (without a time limit when `ttl` is `None`).
    pub fn open(&self, token: &str, ttl: Option<u64>) -> Result<Vec<u8>, CryptoError> {
        self.open_at(token, ttl, unix_now())
    }

    /// `Crypto.decrypt`, as text; a plaintext that is not UTF-8 is a refusal
    /// (Python raises `UnicodeDecodeError`, a `ValueError`, which every caller
    /// treats as an unreadable value).
    pub fn open_str(&self, token: &str, ttl: Option<u64>) -> Result<String, CryptoError> {
        String::from_utf8(self.open(token, ttl)?).map_err(|_| CryptoError::InvalidToken)
    }

    #[doc(hidden)]
    pub fn open_at(&self, token: &str, ttl: Option<u64>, now: u64) -> Result<Vec<u8>, CryptoError> {
        self.opening(token, ttl, now)
            .map(|(_, plain)| plain)
            .ok_or(CryptoError::InvalidToken)
    }

    /// `Crypto.opening_position`: 0 for the current key, 1 for the previous
    /// one, `None` when neither opens `token`.
    pub fn opening_position(&self, token: &str, ttl: Option<u64>) -> Option<usize> {
        self.opening(token, ttl, unix_now())
            .map(|(position, _)| position)
    }

    /// `Crypto.opening_member`: the ring member (a key, text) that opens
    /// `token`. For values derived from the key that sealed them (the PKCE
    /// verifier); never log it.
    pub fn opening_member(&self, token: &str, ttl: Option<u64>) -> Option<&str> {
        let position = self.opening_position(token, ttl)?;
        self.ring.members().nth(position)
    }

    /// The members as text, current first (for the derivations that key on the
    /// Fernet key itself).
    pub fn ring(&self) -> &KeyRing {
        &self.ring
    }

    fn opening(&self, token: &str, ttl: Option<u64>, now: u64) -> Option<(usize, Vec<u8>)> {
        let data = py_urlsafe_b64decode(token)?;
        if data.first() != Some(&VERSION) {
            return None;
        }
        // every key is tried in order, as MultiFernet does
        self.keys
            .iter()
            .enumerate()
            .find_map(|(position, key)| key.open(&data, ttl, now).map(|plain| (position, plain)))
    }
}

/// A fresh Fernet key, as `Fernet.generate_key()` writes one (tests and tools).
pub fn generate_key() -> String {
    URL_SAFE.encode(crate::random::bytes::<32>())
}
