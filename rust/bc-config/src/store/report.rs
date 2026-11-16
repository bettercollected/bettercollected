//! What this process tells the settings store about itself, so the admin portal
//! lists it among the running services (`settings.report_state`):
//! `common/settings/snapshot.py` (`ServiceState`), `loader/source.py`
//! (`instance_id`, `report_state`), `loader/runtime.py` (`state`, `keyset_fp`).
//!
//! Names and counts only: no value, no row content.
//!
//! The database role that reports decides which service the row belongs to
//! (`settings.reader_roles`: `bc_app` is the backend), so the edge's row sits
//! with the backend's, under an instance id of its own (`backend.edge:<host>`).
//! The portal's key tasks look at every live instance of a service: a
//! reporting instance that has not restarted onto a rotated key, or that
//! overrides it from its environment, holds the task back, which is what
//! these tasks exist to check.

use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hasher};
use std::io::Write as _;
use std::os::unix::fs::OpenOptionsExt as _;
use std::path::Path;

use sha2::{Digest, Sha256};

/// Appended to the fingerprint of every build that reads key rings
/// (`common/settings/key_ring.py` `REPORT_MARK`): `authkeys.add_key` refuses
/// while a live instance does not carry it.
pub const REPORT_MARK: &str = ".r1";

/// The component name in the instance id (`^[a-z][a-z0-9]{0,15}$`).
pub const INSTANCE_ROLE: &str = "edge";

/// The data stores this process writes (`DB_WRITE_MODE`): the edge has no
/// other store than Postgres.
pub const WRITE_STORES: &str = "postgres";

/// `ServiceState`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ServiceState {
    /// The highest revision this process has accepted (its floor).
    pub revision_applied: u64,
    /// Settings whose value comes from the environment, so a stored one is ignored.
    pub env_overrides: Vec<String>,
    /// Settings whose stored row was refused.
    pub rejected_keys: Vec<String>,
    /// A restart-class setting changed in the store after this process started.
    pub restart_pending: bool,
    /// Without the [`REPORT_MARK`], which the reporter appends.
    pub keyset_fp: String,
    pub write_stores: String,
}

/// `keyset_fingerprint`: a short hash of the key ids of a keyset (ids only).
pub fn keyset_fingerprint(key_ids: &[String]) -> String {
    let mut ids: Vec<&str> = key_ids.iter().map(String::as_str).collect();
    ids.sort_unstable();
    let digest = Sha256::digest(format!("bc-keyset-v1|{}", ids.join(",")).as_bytes());
    format!("ks-{}", &hex::encode(digest)[..12])
}

/// The key ids of `MASTER_ENCRYPTION_KEYSET` (never key material): the value is
/// base64 of the Tink JSON keyset, or the JSON itself (`parse_keyset`). `None`
/// for anything that is not a usable keyset, which the caller reports as it
/// reports a service without one.
pub fn keyset_key_ids(value: &str) -> Option<Vec<String>> {
    use base64::Engine as _;
    let text = value.trim();
    let json: serde_json::Value = if text.starts_with('{') {
        serde_json::from_str(text).ok()?
    } else {
        // `b64decode(validate=False)`: characters outside the alphabet are dropped
        let kept: String = text
            .chars()
            .filter(|c| c.is_ascii_alphanumeric() || matches!(c, '+' | '/' | '='))
            .collect();
        let engine = base64::engine::GeneralPurpose::new(
            &base64::alphabet::STANDARD,
            base64::engine::GeneralPurposeConfig::new()
                .with_decode_allow_trailing_bits(true)
                .with_decode_padding_mode(base64::engine::DecodePaddingMode::Indifferent),
        );
        let bytes = engine.decode(kept.trim_end_matches('=')).ok()?;
        serde_json::from_slice(&bytes).ok()?
    };
    let id = |v: &serde_json::Value| -> Option<u64> {
        v.as_u64()
            .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
            .filter(|n| u32::try_from(*n).is_ok())
    };
    let keys = json.get("key")?.as_array()?;
    let ids: Vec<u64> = keys
        .iter()
        .map(|k| id(k.get("keyId")?))
        .collect::<Option<_>>()?;
    let primary = id(json.get("primaryKeyId")?)?;
    (!ids.is_empty() && ids.contains(&primary))
        .then(|| ids.iter().map(ToString::to_string).collect())
}

fn clean(raw: &str) -> String {
    raw.chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '_' | '.' | ':' | '-') {
                c
            } else {
                '-'
            }
        })
        .collect()
}

/// A stable id per container (`instance_id`): `service.role:hostname`; without a
/// usable hostname a random id kept in `directory` (mode 600), else one for this
/// process. Letters, digits and `_.:-` only, at most 64 characters.
pub fn instance_id(service: &str, role: &str, hostname: &str, directory: Option<&Path>) -> String {
    let name = format!("{service}.{role}");
    let host = clean(hostname.trim()).trim_matches('-').to_string();
    let cut = |text: String| text.chars().take(64).collect::<String>();
    if !host.is_empty()
        && !matches!(
            host.to_lowercase().as_str(),
            "localhost" | "localhost.localdomain"
        )
    {
        return cut(format!("{name}:{host}"));
    }
    if let Some(directory) = directory {
        let path = directory.join(format!("instance-{name}"));
        if let Ok(saved) = std::fs::read_to_string(&path) {
            let saved = clean(saved.trim());
            if !saved.is_empty() {
                return cut(format!("{name}:{saved}"));
            }
        }
        let token = random_token();
        let _ = std::fs::create_dir_all(directory);
        if let Ok(mut file) = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&path)
        {
            let _ = file.write_all(token.as_bytes());
        }
        return cut(format!("{name}:{token}"));
    }
    cut(format!("{name}:{}", random_token()))
}

/// Sixteen hex characters, only to tell two processes apart (not a secret).
fn random_token() -> String {
    let mut hasher = RandomState::new().build_hasher();
    hasher.write_u64(u64::from(std::process::id()));
    format!("{:016x}", hasher.finish())
}

/// This machine's name (a container's lives as long as the container).
pub fn hostname() -> String {
    std::fs::read_to_string("/proc/sys/kernel/hostname")
        .map(|h| h.trim().to_string())
        .unwrap_or_default()
}

/// A setting name as the report function accepts it (`^[A-Z][A-Z0-9_]{0,63}$`).
pub fn is_setting_name(name: &str) -> bool {
    let b = name.as_bytes();
    (1..=64).contains(&b.len())
        && b[0].is_ascii_uppercase()
        && b.iter()
            .all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || *c == b'_')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_instance_id_is_the_name_and_the_host() {
        assert_eq!(
            instance_id("backend", "edge", "web-1.example", None),
            "backend.edge:web-1.example"
        );
        assert_eq!(
            instance_id("backend", "edge", " we b/1 ", None),
            "backend.edge:we-b-1"
        );
        let long = "h".repeat(100);
        assert_eq!(instance_id("backend", "edge", &long, None).len(), 64);
    }

    #[test]
    fn without_a_host_the_id_is_random_and_kept_in_the_directory() {
        let a = instance_id("backend", "edge", "localhost", None);
        assert!(
            a.starts_with("backend.edge:") && a.len() == "backend.edge:".len() + 16,
            "{a}"
        );
        let dir = std::env::temp_dir().join(format!("bc-instance-test-{}", random_token()));
        let first = instance_id("backend", "edge", "", Some(&dir));
        assert_eq!(first, instance_id("backend", "edge", "", Some(&dir)));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn setting_names_follow_the_database_check() {
        assert!(is_setting_name("AUTH_JWT_SECRET") && is_setting_name("A"));
        assert!(
            !is_setting_name("auth")
                && !is_setting_name("1A")
                && !is_setting_name("")
                && !is_setting_name(&"A".repeat(65))
        );
    }

    #[test]
    fn key_ids_come_from_the_keyset_text_and_never_its_material() {
        use base64::Engine as _;
        let json = r#"{"primaryKeyId":300,"key":[{"keyData":{"typeUrl":"x","value":"secret"},"status":"ENABLED","keyId":300,"outputPrefixType":"TINK"},{"keyData":{"value":"s2"},"keyId":"7"}]}"#;
        let expected = Some(vec!["300".to_string(), "7".to_string()]);
        assert_eq!(keyset_key_ids(json), expected);
        let encoded = base64::engine::general_purpose::STANDARD.encode(json);
        assert_eq!(keyset_key_ids(&encoded), expected);
        assert_eq!(keyset_key_ids(&format!("  {encoded}\n")), expected);
        for bad in [
            "",
            "not base64 !!",
            "{}",
            r#"{"primaryKeyId":1,"key":[]}"#,
            r#"{"primaryKeyId":9,"key":[{"keyId":1}]}"#,
            r#"{"primaryKeyId":1,"key":[{"keyId":-1}]}"#,
            r#"{"primaryKeyId":1,"key":[{"keyId":4294967296}]}"#,
            r#"{"primaryKeyId":1,"key":[{"nokey":1}]}"#,
        ] {
            assert_eq!(keyset_key_ids(bad), None, "{bad}");
        }
    }
}
