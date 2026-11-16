//! The secrets of a draft (`services/form_drafts/tokens.py`): the magic link's
//! token, the edit key and the keyed hash of an address.
//!
//! A token and an edit key are `token_urlsafe(32)` (43 characters) prefixed
//! with the draft's 24-hex id and a dot. Only a keyed hash is stored:
//! HMAC-SHA256 under `SHA-256("bettercollected form draft v1\0" + member)` of
//! the message `purpose \0 part \0 part ...`. The current ring member writes;
//! every member is tried when comparing.

use bc_config::secrets::token_members;

use crate::prim::{SubKey, ct_eq};

pub const KEY_LABEL: &[u8] = b"bettercollected form draft v1\0";
pub const TOKEN: &str = "link";
pub const EDIT_KEY: &str = "edit";
const ADDRESS: &str = "address";

pub struct DraftKeys {
    keys: Vec<SubKey>,
}

impl std::fmt::Debug for DraftKeys {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "DraftKeys({} key(s), <redacted>)", self.keys.len())
    }
}

fn mac_with(key: &SubKey, purpose: &str, parts: &[&str]) -> String {
    let mut message = purpose.to_string();
    for part in parts {
        message.push('\0');
        message.push_str(part);
    }
    key.mac_hex(message.as_bytes())
}

impl DraftKeys {
    /// `secret` is the JWT secret's key ring text.
    pub fn new(secret: &str) -> DraftKeys {
        let mut members = token_members(Some(secret));
        if members.is_empty() {
            members = vec![secret.to_string()];
        }
        DraftKeys {
            keys: members
                .iter()
                .map(|member| SubKey::hashed(member, KEY_LABEL))
                .collect(),
        }
    }

    pub fn hash_secret(&self, purpose: &str, draft_id: &str, secret: &str) -> String {
        mac_with(&self.keys[0], purpose, &[draft_id, secret])
    }

    /// Constant time; false for a draft that has no such secret set. Every
    /// key is always computed.
    pub fn matches(
        &self,
        purpose: &str,
        draft_id: &str,
        secret: &str,
        stored: Option<&str>,
    ) -> bool {
        let mut right = false;
        for key in &self.keys {
            let expected = mac_with(key, purpose, &[draft_id, secret]);
            let stored = stored
                .filter(|s| !s.is_empty())
                .map_or_else(|| "0".repeat(expected.len()), str::to_string);
            right |= ct_eq(expected.as_bytes(), stored.as_bytes());
        }
        right
    }

    /// The keyed hash of an already normalised address on one form.
    pub fn address_key(&self, form_id: &str, normalised: &str) -> String {
        mac_with(&self.keys[0], ADDRESS, &[form_id, normalised])
    }

    /// The same hash under every key, current first.
    pub fn address_keys(&self, form_id: &str, normalised: &str) -> Vec<String> {
        self.keys
            .iter()
            .map(|key| mac_with(key, ADDRESS, &[form_id, normalised]))
            .collect()
    }
}

/// `new_secret`: 256 random bits as 43 URL-safe characters.
pub fn new_secret() -> String {
    crate::random::token_urlsafe(32)
}

/// `compose`.
pub fn compose(draft_id: &str, secret: &str) -> String {
    format!("{draft_id}.{secret}")
}

/// `split`: (draft id, secret) of a value shaped like `<24 hex>.<43 url-safe>`,
/// else `None` (nothing is looked up then).
pub fn split(value: &str) -> Option<(&str, &str)> {
    if value.len() != 24 + 1 + 43 {
        return None;
    }
    let (id, rest) = value.split_at(24);
    let secret = rest.strip_prefix('.')?;
    (id.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
        && secret
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-'))
    .then_some((id, secret))
}

/// `normalised_address` for the addresses whose result does not depend on
/// Unicode tables: ASCII text is trimmed (as Python's `str.strip` does) and
/// lower-cased on both sides of the last `@`. `None` for anything else: NFC
/// normalisation, full case folding and IDNA 2003 encoding of the domain are
/// not reproduced, so such an address must not be hashed here.
///
/// An address without an `@` normalises to the empty string: Python's
/// `rpartition("@")` puts the whole text in the domain slot and the function
/// returns the (empty) local part. That quirk is kept, because stored keys
/// were made with it.
pub fn normalised_ascii_address(address: &str) -> Option<String> {
    if !address.is_ascii() {
        return None;
    }
    let trimmed = address.trim_matches(|c: char| {
        c.is_ascii_whitespace() || ('\x1c'..='\x1f').contains(&c) || c == '\x0b'
    });
    if !trimmed.contains('@') {
        return Some(String::new());
    }
    Some(trimmed.to_ascii_lowercase())
}
