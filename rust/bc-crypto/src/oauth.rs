//! Derived values of the sign-in and consent flows.
//!
//! - the PKCE verifier of the Google Sheets consent
//!   (`services/google_sheets_oauth.py`): derived from the OAuth `state` with
//!   a Fernet ring member, so the authorisation URL and the code exchange (two
//!   requests, maybe two replicas) agree without storing anything;
//! - the hashes that bind a callback to the browser that started it: the
//!   integration OAuth state nonce and the SSO nonce cookie.

use crate::prim::{b64url, ct_eq, hmac_sha256, sha256_hex};

pub const PKCE_LABEL: &[u8] = b"google-sheets-pkce-v1|";
const NONCE_LABEL: &[u8] = b"integration-oauth-state-v1|";
/// The age after which an OAuth state is refused (`STATE_MAX_AGE_SECONDS`).
pub const STATE_MAX_AGE_SECONDS: u64 = 3600;

/// `pkce_code_verifier`: 43 URL-safe characters. `member` is the Fernet key
/// (text) of the ring: the current one when the request starts, the one that
/// opens the state at the exchange ([`crate::fernet::FernetRing::opening_member`]).
pub fn pkce_code_verifier(member: &str, state: &str) -> String {
    let mut message = PKCE_LABEL.to_vec();
    message.extend_from_slice(state.as_bytes());
    b64url(&hmac_sha256(member.as_bytes(), &message))
}

/// `pkce_code_challenge` (S256).
pub fn pkce_code_challenge(verifier: &str) -> String {
    use sha2::{Digest, Sha256};
    b64url(&Sha256::digest(verifier.as_bytes()))
}

/// `state_nonce_hash` of the integration OAuth state.
pub fn integration_nonce_hash(nonce: &str) -> String {
    let mut message = NONCE_LABEL.to_vec();
    message.extend_from_slice(nonce.as_bytes());
    sha256_hex(&message)
}

/// SSO `nonce_hash`: SHA-256 hex of the nonce (empty for none).
pub fn sso_nonce_hash(nonce: &str) -> String {
    sha256_hex(nonce.as_bytes())
}

/// The SSO callback's check: the cookie's nonce hashes to the value kept in
/// the flow context (constant time).
pub fn sso_nonce_matches(nonce: &str, expected_hash: &str) -> bool {
    !nonce.is_empty() && ct_eq(sso_nonce_hash(nonce).as_bytes(), expected_hash.as_bytes())
}
