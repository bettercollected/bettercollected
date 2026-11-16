//! Workspace API keys (`services/ai/api_keys.py`): `bc_` + 64 hex characters
//! (256 random bits). Only the unkeyed SHA-256 hex of the whole token is
//! stored (`key_hash`) and looked up: the token carries enough entropy that no
//! key, salt or work factor is needed, and a stored hash gives no token.
//! The first 11 characters (`bc_` and 8 more) are kept to recognise a key.

pub const TOKEN_PREFIX: &str = "bc_";
const PREFIX_SHOWN: usize = TOKEN_PREFIX.len() + 8;

/// `_hash`: lower-case hex SHA-256 of the token's UTF-8 bytes.
pub fn hash(token: &str) -> String {
    crate::prim::sha256_hex(token.as_bytes())
}

/// A new key: the token (shown once) and what is stored.
pub struct NewKey {
    pub token: String,
    pub key_hash: String,
    pub prefix: String,
}

impl std::fmt::Debug for NewKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("NewKey(<redacted>)")
    }
}

/// `TOKEN_PREFIX + secrets.token_hex(32)`.
pub fn generate() -> NewKey {
    let token = format!("{TOKEN_PREFIX}{}", crate::random::token_hex(32));
    NewKey {
        key_hash: hash(&token),
        prefix: token[..PREFIX_SHOWN].to_string(),
        token,
    }
}

/// The only shape check `authenticate` makes before the lookup.
pub fn has_prefix(token: &str) -> bool {
    token.starts_with(TOKEN_PREFIX)
}
