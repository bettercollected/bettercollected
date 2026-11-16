//! Key rings and the refusal of unset or published secrets.
//!
//! Port of `common/common/configs/shipped_secrets.py` (the published-value
//! digests, `secret_problems`) and `common/common/settings/key_ring.py` (what a
//! comma in a key means). A message names the variable, never the value.

use std::fmt;

use base64::Engine;
use base64::engine::general_purpose::URL_SAFE;
use sha2::{Digest, Sha256};

use crate::source::normalize;

/// SHA-256 of every value published for these keys, never the values
/// themselves. The same list as `SHIPPED_SECRET_SHA256` in
/// `common/common/configs/shipped_secrets.py`; `tests/shipped_list.rs` checks
/// the two stay in step.
pub const SHIPPED_SECRET_SHA256: &[&str] = &[
    "a75934b93de0f24eb3da8b1f4234d7c3dfcf8f057377739a7378383898555de3",
    "af61f0e17db65ce007dccccd9165d3467e9c97c3d12e4c9507a9a06ec7aa1103",
    "dfad509a1373435ed0c21fd96e686e3a6879d30dae9796ac1eec38b6916497be",
    "4f4c538d1c81f4b9083fc33240e62f4101f1d21434b4f698f0d03f77a5d89207",
    "5a90a68596fcebfd2676d9313557584bd68b143dd234750c419ece1b8f82fe5a",
    "33d902e58f189bbb7266454cdbd9741bb3bd956a300c4a04ef0b24cd221a2da3",
    "c47af94f4a9ae7811b6d01bf1abb251f927ec915c8d78bbe07b56d513295058a",
    "0cf506f170c8c321831425c7a7cc8dc745a0104493b7e98d1ed653bb1e5f913b",
];

pub const MAX_RING_MEMBERS: usize = 2;
pub const MIN_TOKEN_MEMBER: usize = 32;

/// A value that must never be printed: its `Debug` and `Display` say so.
#[derive(Clone, PartialEq, Eq)]
pub struct Secret(String);

impl Secret {
    pub fn new(value: impl Into<String>) -> Secret {
        Secret(value.into())
    }

    /// The value. Call this only where it is used, never to log it.
    pub fn expose(&self) -> &str {
        &self.0
    }
}

impl fmt::Debug for Secret {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("Secret(<redacted>)")
    }
}

impl fmt::Display for Secret {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("<redacted>")
    }
}

/// A key ring: the current key first, then the previous one while a rotation
/// is under way. Every member verifies (or decrypts); the first one signs.
#[derive(Clone, PartialEq, Eq)]
pub struct KeyRing {
    members: Vec<Secret>,
}

impl KeyRing {
    pub fn from_members(members: Vec<String>) -> KeyRing {
        KeyRing {
            members: members.into_iter().map(Secret::new).collect(),
        }
    }

    pub fn len(&self) -> usize {
        self.members.len()
    }

    pub fn is_empty(&self) -> bool {
        self.members.is_empty()
    }

    /// The members, current first.
    pub fn members(&self) -> impl Iterator<Item = &str> {
        self.members.iter().map(Secret::expose)
    }
}

impl fmt::Debug for KeyRing {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "KeyRing({} member(s), <redacted>)", self.members.len())
    }
}

/// Lower-case hex SHA-256 of `value` as it is.
pub fn sha256_hex(value: &str) -> String {
    hex::encode(Sha256::digest(value.as_bytes()))
}

/// Whether the value is one that was published (digests of the denylist).
pub fn is_shipped_secret(value: &str, denylist: &[&str]) -> bool {
    let digest = sha256_hex(&normalize(Some(value)).unwrap_or_default());
    denylist.iter().any(|known| *known == digest)
}

/// `is_fernet_key`: 32 bytes of url-safe base64.
pub fn is_fernet_key(value: &str) -> bool {
    normalize(Some(value))
        .and_then(|v| URL_SAFE.decode(v).ok())
        .is_some_and(|bytes| bytes.len() == 32)
}

/// `fernet_members`: the keys of a Fernet ring, current first.
pub fn fernet_members(value: Option<&str>) -> Vec<String> {
    match normalize(value) {
        Some(text) => text.split(',').map(|p| p.trim().to_string()).collect(),
        None => Vec::new(),
    }
}

/// `key_ring.token_members`: two members when the value has exactly one comma
/// and both sides are at least 32 characters without whitespace; anything else
/// is ONE secret, exactly as it is.
pub fn token_members(value: Option<&str>) -> Vec<String> {
    let Some(value) = value else {
        return Vec::new();
    };
    if value.trim().is_empty() {
        return Vec::new();
    }
    let parts: Vec<&str> = value.trim().split(',').collect();
    if parts.len() == 2
        && parts
            .iter()
            .all(|p| p.chars().count() >= MIN_TOKEN_MEMBER && !p.chars().any(char::is_whitespace))
    {
        return parts.iter().map(|p| (*p).to_string()).collect();
    }
    vec![value.to_string()]
}

/// One line per unusable key, naming the variable, never its value.
/// `jwt` and `fernet` are `(variable name, value)` pairs.
pub fn secret_problems(
    jwt: &[(&str, Option<&str>)],
    fernet: &[(&str, Option<&str>)],
    denylist: &[&str],
) -> Vec<String> {
    let mut problems = Vec::new();
    for (is_jwt, group) in [(true, jwt), (false, fernet)] {
        for (name, value) in group {
            let members = if is_jwt {
                token_members(*value)
            } else {
                fernet_members(*value)
            };
            if normalize(*value).is_none() || members.is_empty() {
                problems.push(format!("{name} is not set"));
            } else if members.len() > MAX_RING_MEMBERS
                || members
                    .iter()
                    .enumerate()
                    .any(|(i, m)| members[..i].contains(m))
            {
                problems.push(format!(
                    "{name} holds more than two keys or the same key twice \
                     (current first, then the previous one)"
                ));
            } else if members.iter().any(|m| is_shipped_secret(m, denylist)) {
                problems.push(format!(
                    "{name} is a value that was published in the bettercollected \
                     repository, so anyone can use it"
                ));
            } else if !is_jwt && !members.iter().all(|m| is_fernet_key(m)) {
                problems.push(format!(
                    "{name} is not a Fernet key (32 bytes, url-safe base64)"
                ));
            }
        }
    }
    problems
}

#[cfg(test)]
mod tests {
    use super::*;

    const A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const B: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const FERNET: &str = "L5HuSlk0ijI3xzaccuy2x1jnzHNjtTw3zW53tjGHZG0=";

    #[test]
    fn key_ring_rule_matches_python() {
        let a = &A[..32];
        assert_eq!(
            token_members(Some(&format!("{a},{B}"))),
            vec![a.to_string(), B.to_string()]
        );
        // too short a side: one secret, comma included
        assert_eq!(
            token_members(Some(&format!("{a},short"))),
            vec![format!("{a},short")]
        );
        // whitespace inside: one secret
        assert_eq!(
            token_members(Some(&format!("{a} x,{B}"))),
            vec![format!("{a} x,{B}")]
        );
        // three members are never a ring
        assert_eq!(token_members(Some(&format!("{a},{B},{a}"))).len(), 1);
        assert_eq!(token_members(Some("  ")), Vec::<String>::new());
        assert_eq!(token_members(None), Vec::<String>::new());
    }

    #[test]
    fn unset_empty_and_repeated_keys_are_problems() {
        let none: &[&str] = &[];
        let unset = secret_problems(&[("AUTH_JWT_SECRET", None)], &[], none);
        assert_eq!(unset, vec!["AUTH_JWT_SECRET is not set"]);
        let empty = secret_problems(&[("AUTH_JWT_SECRET", Some("  "))], &[], none);
        assert_eq!(empty, vec!["AUTH_JWT_SECRET is not set"]);
        let twice = format!("{FERNET},{FERNET}");
        let problems = secret_problems(&[], &[("AUTH_AES_HEX_KEY", Some(&twice))], none);
        assert!(problems[0].contains("the same key twice"), "{problems:?}");
        let three = format!("{FERNET},{FERNET},{FERNET}");
        let problems = secret_problems(&[], &[("AUTH_AES_HEX_KEY", Some(&three))], none);
        assert!(problems[0].contains("more than two"));
    }

    #[test]
    fn a_published_value_is_refused_by_digest_in_either_ring_position() {
        let denylist = [sha256_hex(B)];
        let denylist: Vec<&str> = denylist.iter().map(String::as_str).collect();
        let ring = format!("{A}x,{B}");
        let problems = secret_problems(&[("AUTH_JWT_SECRET", Some(&ring))], &[], &denylist);
        assert!(problems[0].contains("published"), "{problems:?}");
        assert!(!problems[0].contains(B));
        // quotes around the value do not hide it
        let quoted = format!("\"{B}\"");
        assert!(is_shipped_secret(&quoted, &denylist));
    }

    #[test]
    fn a_fernet_key_must_be_32_bytes_of_urlsafe_base64() {
        assert!(is_fernet_key(FERNET));
        assert!(!is_fernet_key("short"));
        assert!(!is_fernet_key(&"A".repeat(43))); // wrong padding
        let none: &[&str] = &[];
        let problems = secret_problems(&[], &[("AUTH_AES_HEX_KEY", Some("not a key"))], none);
        assert!(problems[0].contains("not a Fernet key"));
        assert_eq!(
            secret_problems(&[], &[("AUTH_AES_HEX_KEY", Some(FERNET))], none),
            Vec::<String>::new()
        );
    }

    #[test]
    fn debug_and_display_never_show_a_secret() {
        let ring = KeyRing::from_members(vec![A.to_string(), B.to_string()]);
        assert!(!format!("{ring:?}").contains("aaaa"));
        let secret = Secret::new(A);
        assert!(!format!("{secret:?}{secret}").contains("aaaa"));
        assert_eq!(ring.members().count(), 2);
    }

    #[test]
    fn the_shipped_list_has_eight_digests() {
        assert_eq!(SHIPPED_SECRET_SHA256.len(), 8);
        assert!(SHIPPED_SECRET_SHA256.iter().all(|d| d.len() == 64));
    }
}
