#![allow(clippy::unwrap_used, clippy::expect_used)]
//! The Rust reader against what the Python settings code produced: derived keys,
//! canonical bytes, signatures, the manifest and sealed secrets
//! (`rust/contract/golden_settings.py` wrote `golden/settings_store.json`).

mod support;

use base64::Engine;
use bc_config::store::canonical::{Manifest, canonical_manifest, canonical_row};
use bc_config::store::crypto::{SectionKeys, derive_from_master, parse_master_key};
use support::{golden, golden_keys, golden_rows};

#[test]
fn derived_keys_equal_pythons_hkdf() {
    let g = golden();
    let master = parse_master_key(g["master"].as_str().unwrap()).unwrap();
    for (name, purpose, context) in [
        ("manifest_sign", "sign", None),
        ("row_sign_features", "sign", Some("features")),
        ("wrap_auth_keys", "wrap", Some("auth_keys")),
    ] {
        assert_eq!(
            hex::encode(derive_from_master(&master, purpose, context)),
            g["derived"][name].as_str().unwrap(),
            "{name}"
        );
    }
}

#[test]
fn canonical_bytes_signatures_and_the_manifest_equal_pythons() {
    let g = golden();
    let keys = golden_keys();
    let rows = golden_rows();
    assert_eq!(rows.len(), 10);
    for (row, json) in rows.iter().zip(g["rows"].as_array().unwrap()) {
        assert_eq!(
            hex::encode(canonical_row(row).unwrap()),
            json["canonical_hex"].as_str().unwrap(),
            "canonical bytes of {}",
            row.key
        );
        assert!(keys.verify_row(row), "{} verifies", row.key);
        assert_eq!(
            keys.sign_row_current(row).unwrap(),
            row.sig,
            "{} signs the same",
            row.key
        );
    }
    let m = &g["manifest"];
    let entries = m["entries"]
        .as_object()
        .unwrap()
        .iter()
        .map(|(k, e)| {
            (
                k.clone(),
                (
                    e[0].as_u64().unwrap(),
                    e[1].as_str().unwrap().to_string(),
                    e[2].as_array()
                        .unwrap()
                        .iter()
                        .map(|r| r.as_str().unwrap().to_string())
                        .collect(),
                ),
            )
        })
        .collect();
    let manifest = Manifest {
        revision: m["revision"].as_u64().unwrap(),
        entries,
        sig: m["sig"].as_str().unwrap().to_string(),
    };
    assert_eq!(
        hex::encode(canonical_manifest(manifest.revision, &manifest.entries).unwrap()),
        m["canonical_hex"].as_str().unwrap()
    );
    assert!(keys.verify_manifest(&manifest));
    assert_eq!(keys.sign_manifest_current(&manifest).unwrap(), manifest.sig);
}

#[test]
fn a_changed_field_breaks_the_signature() {
    let keys = golden_keys();
    for change in 0..6 {
        let mut row = support::golden_row("API_FLOW_EVENTS_PER_WINDOW");
        match change {
            0 => row.value = Some(serde_json::json!(601)),
            1 => row.version += 1,
            2 => row.readers.push("auth".into()),
            3 => row.reload_class = "R".into(),
            4 => row.updated_at = "2026-11-16T09:08:07.654322Z".into(),
            _ => row.section = "features".into(),
        }
        assert!(!keys.verify_row(&row), "change {change}");
    }
    // a row of a section the reader does not hold cannot be verified at all
    let mail_only = SectionKeys::new(&support::master(), None, &["mail".to_string()]).unwrap();
    assert!(!mail_only.verify_row(&support::golden_row("FIELD_RULES_ENABLED")));
}

#[test]
fn sealed_secrets_open_with_the_current_and_the_previous_key_and_nowhere_else() {
    let g = golden();
    let keys = golden_keys(); // current key, previous accepted
    let only_current =
        SectionKeys::new(&support::master(), None, &["auth_keys".to_string()]).unwrap();
    let only_previous = SectionKeys::new(
        g["master_previous"].as_str().unwrap(),
        None,
        &["auth_keys".to_string()],
    )
    .unwrap();
    for s in g["sealed"].as_array().unwrap() {
        let (key, section, version) = (
            s["key"].as_str().unwrap(),
            s["section"].as_str().unwrap(),
            s["version"].as_u64().unwrap(),
        );
        let plain = s["plaintext"].as_str().unwrap();
        let (blob, old) = (
            s["blob"].as_str().unwrap(),
            s["blob_previous_key"].as_str().unwrap(),
        );
        assert_eq!(
            keys.open(section, key, version, blob).as_deref(),
            Some(plain)
        );
        assert_eq!(
            only_current.open(section, key, version, blob).as_deref(),
            Some(plain)
        );
        // a value sealed under the previous master key opens while the rotation lasts
        assert_eq!(
            keys.open(section, key, version, old).as_deref(),
            Some(plain)
        );
        assert_eq!(
            only_previous.open(section, key, version, old).as_deref(),
            Some(plain)
        );
        assert_eq!(only_current.open(section, key, version, old), None);
        // bound to its setting, version and section
        assert_eq!(keys.open(section, "OTHER_KEY", version, blob), None);
        assert_eq!(keys.open(section, key, version + 1, blob), None);
        assert_eq!(
            keys.open("sso", key, version, blob),
            None,
            "section not held or not the sealing one"
        );
        // a flipped byte, a cut, a wrong version tag
        let mut bytes = blob.as_bytes().to_vec();
        let last = bytes.len() - 3;
        bytes[last] = if bytes[last] == b'A' { b'B' } else { b'A' };
        assert_eq!(
            keys.open(section, key, version, std::str::from_utf8(&bytes).unwrap()),
            None
        );
        assert_eq!(
            keys.open(section, key, version, &blob[..blob.len() - 8]),
            None
        );
        assert_eq!(
            keys.open(section, key, version, &blob.replacen("v2:", "v3:", 1)),
            None
        );
    }
}

#[test]
fn a_master_key_in_the_url_safe_alphabet_derives_the_same_keys() {
    let std = base64::engine::general_purpose::STANDARD;
    let url = base64::engine::general_purpose::URL_SAFE_NO_PAD;
    let raw = std.decode(support::master()).unwrap();
    assert_eq!(parse_master_key(&url.encode(&raw)).unwrap(), raw);
}
