//! Random values from the operating system's CSPRNG, in the shapes the Python
//! backend's `secrets` module produces.
//!
//! The buffers are never initialised with a value of ours: the generator fills
//! uninitialised memory (`getrandom_uninit`), so no constant can end up as an
//! IV, a nonce or a key by a path that skips the fill. A failure of the
//! operating system's generator is fatal (as in `rand`'s `OsRng`): nothing is
//! ever returned that is not random.

use std::mem::MaybeUninit;

use crate::prim::b64url;

fn fill(buffer: &mut [MaybeUninit<u8>]) -> &[u8] {
    let Ok(filled) = getrandom::getrandom_uninit(buffer) else {
        panic!("the operating system's random generator failed");
    };
    filled
}

/// `secrets.token_bytes(N)`.
pub fn bytes<const N: usize>() -> [u8; N] {
    let mut buffer = [MaybeUninit::<u8>::uninit(); N];
    let Ok(out) = <[u8; N]>::try_from(fill(&mut buffer)) else {
        unreachable!("the buffer is N bytes");
    };
    out
}

/// `secrets.token_bytes(n)` for a run-time length.
pub fn vec(n: usize) -> Vec<u8> {
    let mut buffer = vec![MaybeUninit::<u8>::uninit(); n];
    fill(&mut buffer).to_vec()
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
