//! Random values from the operating system's CSPRNG, in the shapes the Python
//! backend's `secrets` module produces.

use aes_gcm::aead::OsRng;
use aes_gcm::aead::rand_core::RngCore;

use crate::prim::b64url;

/// `secrets.token_bytes(N)`.
pub fn bytes<const N: usize>() -> [u8; N] {
    let mut out = [0u8; N];
    OsRng.fill_bytes(&mut out);
    out
}

/// `secrets.token_bytes(n)` for a run-time length.
pub fn vec(n: usize) -> Vec<u8> {
    let mut out = vec![0u8; n];
    OsRng.fill_bytes(&mut out);
    out
}

/// `secrets.token_hex(n)`: `2n` lower-case hex digits.
pub fn token_hex(n: usize) -> String {
    hex::encode(vec(n))
}

/// `secrets.token_urlsafe(n)`: URL-safe base64 of `n` random bytes, no padding
/// (43 characters for the usual 32).
pub fn token_urlsafe(n: usize) -> String {
    b64url(&vec(n))
}
