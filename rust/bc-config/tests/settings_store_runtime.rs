#![allow(clippy::unwrap_used, clippy::expect_used, clippy::too_many_lines)]
//! The settings store reader at the level a service uses it: `Config::load_with`
//! over a store whose rows the Python signer (golden) or the tests sign. Precedence,
//! trimming, an unverifiable row, a missing store, rollback, live (class H) values,
//! and that no value reaches a log line.

mod support;

use std::io::Write;
use std::sync::{Arc, Mutex};

use base64::Engine;
use bc_config::store::verify::RawSnapshot;
use bc_config::{Config, ConfigError};
use serde_json::json;
use support::{FakeStore, env, golden_row, golden_snapshot, row_for, scratch, signed};

const JWT: &str = "golden-jwt-secret-0123456789abcdef0123456789abcdef";

async fn load(extra: &[(&str, &str)], store: &FakeStore) -> Result<Config, ConfigError> {
    Config::load_with(env(extra), Some(store.boxed()), &[]).await
}

/// A store with the JWT secret (sealed by Python) and the given plain rows.
fn store_with(rows: Vec<support::Row>, revision: u64) -> RawSnapshot {
    let mut all = vec![golden_row("AUTH_JWT_SECRET")];
    all.extend(rows);
    signed(all, revision)
}

fn dir(name: &str) -> String {
    scratch(name)
}

// ---------------------------------------------------------------- precedence

#[tokio::test]
async fn the_store_supplies_what_the_environment_does_not() {
    let store = FakeStore::new(golden_snapshot());
    let cfg = load(&[("SETTINGS_SNAPSHOT_DIR", &dir("supplies"))], &store)
        .await
        .unwrap();
    // the JWT secret is only in the store, sealed; a switch too
    assert_eq!(cfg.jwt_ring.len(), 1);
    assert!(cfg.flags.field_rules);
    assert!(!cfg.sso_enabled && !cfg.totp_enabled);
    assert_eq!(cfg.store.as_ref().unwrap().revision(), 7);
}

#[tokio::test]
async fn a_non_empty_environment_value_beats_the_store_and_an_empty_one_does_not() {
    let rows = vec![
        row_for("SSO_ENABLED", 1, json!(true)),
        row_for("TOTP_ENABLED", 1, json!(true)),
        row_for("FIELD_RULES_ENABLED", 1, json!(true)),
    ];
    let store = FakeStore::new(store_with(rows, 3));
    for (env_value, sso) in [
        (None, true),
        (Some(""), true),
        (Some("   "), true),
        (Some("\"\""), true),
        (Some("''"), true),
        (Some("false"), false),
        (Some(" off "), false),
        (Some("'no'"), false),
        (Some("1"), true),
    ] {
        let mut extra = vec![(
            "SETTINGS_SNAPSHOT_DIR",
            Box::leak(dir("prec").into_boxed_str()) as &str,
        )];
        if let Some(v) = env_value {
            extra.push(("SSO_ENABLED", v));
        }
        let cfg = load(&extra, &store).await.unwrap();
        assert_eq!(cfg.sso_enabled, sso, "{env_value:?}");
        assert!(cfg.totp_enabled, "untouched switches follow the store");
    }
}

#[tokio::test]
async fn the_environment_secret_beats_the_stored_one() {
    let store = FakeStore::new(golden_snapshot());
    let ring = "environment-secret-0123456789abcdef0123456789";
    let cfg = load(
        &[
            ("AUTH_JWT_SECRET", ring),
            ("SETTINGS_SNAPSHOT_DIR", &dir("envsecret")),
        ],
        &store,
    )
    .await
    .unwrap();
    assert_eq!(cfg.jwt_ring.len(), 1);
    let from_store = load(&[("SETTINGS_SNAPSHOT_DIR", &dir("envsecret2"))], &store)
        .await
        .unwrap();
    assert_ne!(
        cfg.jwt_ring.members().next(),
        from_store.jwt_ring.members().next()
    );
    assert_eq!(from_store.jwt_ring.members().next(), Some(JWT));
}

#[tokio::test]
async fn a_stored_text_is_handed_over_as_stored_and_an_environment_text_is_trimmed() {
    let store = FakeStore::new(store_with(
        vec![row_for("DEFAULT_WORKSPACE_ID", 1, json!("  abc  "))],
        3,
    ));
    let cfg = load(&[("SETTINGS_SNAPSHOT_DIR", &dir("trim"))], &store)
        .await
        .unwrap();
    let rt = cfg.store.as_ref().unwrap();
    assert_eq!(
        rt.resolve_key("DEFAULT_WORKSPACE_ID").unwrap().as_deref(),
        Some("  abc  ")
    );
    // set in the environment, in any spelling that is not empty: the store is not asked
    let cfg = load(
        &[
            ("DEFAULT_WORKSPACE_ID", "  xyz  "),
            ("SETTINGS_SNAPSHOT_DIR", &dir("trim2")),
        ],
        &store,
    )
    .await
    .unwrap();
    assert_eq!(
        cfg.store
            .as_ref()
            .unwrap()
            .resolve_key("DEFAULT_WORKSPACE_ID")
            .unwrap(),
        None
    );
    let cfg = load(
        &[
            ("DEFAULT_WORKSPACE_ID", "''"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("trim3")),
        ],
        &store,
    )
    .await
    .unwrap();
    assert_eq!(
        cfg.store
            .as_ref()
            .unwrap()
            .resolve_key("DEFAULT_WORKSPACE_ID")
            .unwrap()
            .as_deref(),
        Some("  abc  ")
    );
}

#[tokio::test]
async fn a_stored_switch_is_a_bool_or_one_of_the_registry_words() {
    for (stored, expected) in [
        (json!(true), Some(true)),
        (json!("Yes"), Some(true)),
        (json!("off"), Some(false)),
        (json!("t"), None),
        (json!(1), None),
        (json!("maybe"), None),
    ] {
        let store = FakeStore::new(store_with(
            vec![row_for("CAPTCHA_ENABLED", 1, stored.clone())],
            3,
        ));
        let cfg = load(&[("SETTINGS_SNAPSHOT_DIR", &dir("words"))], &store)
            .await
            .unwrap();
        // a value the registry refuses is refused as Python refuses it: the default (off) applies
        assert_eq!(cfg.flags.captcha, expected == Some(true), "{stored}");
    }
}

#[tokio::test]
async fn keys_python_does_not_read_from_the_store_are_not_read_by_rust_either() {
    let held = signed(
        vec![
            golden_row("AUTH_JWT_SECRET"),
            // held in the environment until released: never a store key
            support::plain(
                "FORM_ACCESS_ENABLED",
                "security",
                &["backend", "jobs"],
                "R",
                1,
                json!(true),
            ),
            support::plain(
                "REPORTING_ENABLED",
                "features",
                &["backend"],
                "R",
                1,
                json!(true),
            ),
            // a registry key, but its Python field has two names and the loader skips it
            row_for("API_TRUSTED_PROXIES", 1, json!("10.0.0.0/8")),
        ],
        3,
    );
    let cfg = load(
        &[("SETTINGS_SNAPSHOT_DIR", &dir("held"))],
        &FakeStore::new(held),
    )
    .await
    .unwrap();
    assert!(!cfg.flags.form_access && !cfg.flags.reporting);
    assert_eq!(cfg.network.trusted_proxies, "");
    let reasons: Vec<_> = cfg
        .store
        .as_ref()
        .unwrap()
        .rejections()
        .iter()
        .map(|r| (r.key.clone(), r.reason))
        .collect();
    assert!(
        reasons.contains(&("FORM_ACCESS_ENABLED".to_string(), "unknown_key")),
        "{reasons:?}"
    );
}

// ------------------------------------------------------- unverifiable rows

#[tokio::test]
async fn a_tampered_row_is_refused_and_the_rest_of_the_store_still_applies() {
    let mut snap = golden_snapshot();
    for row in &mut snap.rows {
        if row.key == "FIELD_RULES_ENABLED" {
            row.value = Some(json!(false)); // signed true
        }
    }
    let cfg = load(
        &[("SETTINGS_SNAPSHOT_DIR", &dir("tamper"))],
        &FakeStore::new(snap),
    )
    .await
    .unwrap();
    assert!(!cfg.flags.field_rules, "refused: the default applies");
    assert_eq!(cfg.jwt_ring.len(), 1, "the other rows are fine");
    let rejected = cfg.store.as_ref().unwrap().rejections();
    assert!(
        rejected
            .iter()
            .any(|r| r.key == "FIELD_RULES_ENABLED" && r.reason == "bad_signature")
    );
}

#[tokio::test]
async fn a_tampered_secret_stops_a_required_service_and_an_auto_one_has_no_secret() {
    let mut snap = golden_snapshot();
    for row in &mut snap.rows {
        if row.key == "AUTH_JWT_SECRET" {
            let blob = row.blob.clone().unwrap();
            row.blob = Some(blob.replacen("v2:", "v2:x", 1));
        }
    }
    let store = FakeStore::new(snap);
    let err = load(
        &[
            ("SETTINGS_STORE", "required"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("tamper-required")),
        ],
        &store,
    )
    .await
    .unwrap_err();
    assert!(err.0.contains("AUTH_JWT_SECRET"), "{err}");
    assert!(!err.0.contains(JWT));
    // auto: nothing stops the load, and the service then lacks its signing secret
    let err = load(&[("SETTINGS_SNAPSHOT_DIR", &dir("tamper-auto"))], &store)
        .await
        .unwrap_err();
    assert!(err.0.contains("AUTH_JWT_SECRET is not set"), "{err}");
    // the environment supplies it: the bad row does not matter
    let cfg = load(
        &[
            ("AUTH_JWT_SECRET", JWT),
            ("AUTH_AES_HEX_KEY", "x"),
            ("SETTINGS_STORE", "required"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("tamper-env")),
        ],
        &store,
    )
    .await;
    assert!(cfg.is_ok() || !cfg.unwrap_err().0.contains("critical"));
}

#[tokio::test]
async fn a_sealed_secret_that_cannot_be_opened_is_refused_even_when_its_signature_is_good() {
    // signed correctly, sealed under nothing the reader holds
    let mut row = golden_row("AUTH_JWT_SECRET");
    row.blob = Some("v2:w1-00000000:AAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAAAA".into());
    row.sig = String::new();
    let store = FakeStore::new(signed(vec![row], 3));
    let err = load(
        &[
            ("SETTINGS_STORE", "required"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("noopen")),
        ],
        &store,
    )
    .await
    .unwrap_err();
    assert!(
        err.0
            .contains("no usable value for critical setting AUTH_JWT_SECRET"),
        "{err}"
    );
}

#[tokio::test]
async fn an_untrusted_manifest_rejects_every_row() {
    let mut snap = golden_snapshot();
    snap.manifest.as_mut().unwrap().sig = "0".repeat(64);
    let store = FakeStore::new(snap);
    let err = load(
        &[
            ("SETTINGS_STORE", "required"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("untrusted-req")),
        ],
        &store,
    )
    .await
    .unwrap_err();
    assert!(
        err.0.contains("manifest was not trusted") && err.0.contains("AUTH_JWT_SECRET"),
        "{err}"
    );
    // auto: nothing from the store applies; the environment is all there is
    let cfg = load(
        &[
            (
                "AUTH_JWT_SECRET",
                "environment-secret-0123456789abcdef0123456789",
            ),
            ("SETTINGS_SNAPSHOT_DIR", &dir("untrusted-auto")),
        ],
        &store,
    )
    .await
    .unwrap();
    assert!(!cfg.flags.field_rules);
}

#[tokio::test]
async fn a_store_signed_with_another_master_key_is_not_trusted() {
    let store = FakeStore::new(golden_snapshot());
    let other = base64::engine::general_purpose::STANDARD.encode((20u8..68).collect::<Vec<_>>());
    let other = other.as_str();
    let err = load(
        &[
            ("SETTINGS_MASTER_KEY", other),
            ("SETTINGS_STORE", "required"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("otherkey")),
        ],
        &store,
    )
    .await
    .unwrap_err();
    assert!(err.0.contains("settings store"), "{err}");
    assert!(!err.0.contains(other));
}

#[tokio::test]
async fn a_row_the_manifest_does_not_match_or_does_not_list_is_refused() {
    let mut snap = golden_snapshot();
    // the manifest is genuine, but a row was swapped for an older signed copy
    for row in &mut snap.rows {
        if row.key == "API_FLOW_EVENTS_PER_WINDOW" {
            row.version = 1;
        }
    }
    snap.rows.push(golden_row("FIELD_RULES_ENABLED"));
    let cfg = load(
        &[("SETTINGS_SNAPSHOT_DIR", &dir("mismatch"))],
        &FakeStore::new(snap),
    )
    .await
    .unwrap();
    let reasons: Vec<_> = cfg
        .store
        .as_ref()
        .unwrap()
        .rejections()
        .iter()
        .map(|r| (r.key.clone(), r.reason))
        .collect();
    assert!(
        reasons.contains(&(
            "API_FLOW_EVENTS_PER_WINDOW".to_string(),
            "manifest_mismatch"
        )),
        "{reasons:?}"
    );
    // a row the signed manifest lists for this reader but the view withheld
    let mut snap = golden_snapshot();
    snap.rows.retain(|r| r.key != "FIELD_RULES_ENABLED");
    let cfg = load(
        &[("SETTINGS_SNAPSHOT_DIR", &dir("withheld"))],
        &FakeStore::new(snap),
    )
    .await
    .unwrap();
    let reasons: Vec<_> = cfg
        .store
        .as_ref()
        .unwrap()
        .rejections()
        .iter()
        .map(|r| (r.key.clone(), r.reason))
        .collect();
    assert!(
        reasons.contains(&("FIELD_RULES_ENABLED".to_string(), "row_missing")),
        "{reasons:?}"
    );
    assert!(!cfg.flags.field_rules);
}

// ----------------------------------------------------- a missing store

#[tokio::test]
async fn a_store_that_cannot_be_read_leaves_environment_and_defaults() {
    let down = FakeStore::down();
    let secret = (
        "AUTH_JWT_SECRET",
        "environment-secret-0123456789abcdef0123456789",
    );
    let cfg = load(
        &[secret, ("SETTINGS_SNAPSHOT_DIR", &dir("down-auto"))],
        &down,
    )
    .await
    .unwrap();
    assert_eq!(cfg.store.as_ref().unwrap().revision(), 0);
    assert!(!cfg.flags.field_rules);
    // required: only when the environment holds every key the service cannot run without
    let err = load(
        &[
            secret,
            ("SETTINGS_STORE", "required"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("down-req")),
        ],
        &down,
    )
    .await
    .unwrap_err();
    assert!(
        err.0.contains("AUTH_AES_HEX_KEY") && !err.0.contains("AUTH_JWT_SECRET,"),
        "{err}"
    );
    let ok = load(
        &[
            secret,
            (
                "AUTH_AES_HEX_KEY",
                "L5HuSlk0ijI3xzaccuy2x1jnzHNjtTw3zW53tjGHZG0=",
            ),
            ("SETTINGS_STORE", "required"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("down-req2")),
        ],
        &down,
    )
    .await;
    assert!(ok.is_ok(), "{:?}", ok.err());
}

#[tokio::test]
async fn the_signed_snapshot_stands_in_while_the_database_is_down() {
    let snapshots = dir("snapshot");
    let store = FakeStore::new(golden_snapshot());
    let first = load(&[("SETTINGS_SNAPSHOT_DIR", &snapshots)], &store)
        .await
        .unwrap();
    assert!(first.flags.field_rules);
    // the database goes away: a restart reads the snapshot the first start wrote
    let second = load(
        &[
            ("SETTINGS_SNAPSHOT_DIR", &snapshots),
            ("SETTINGS_STORE", "required"),
        ],
        &FakeStore::down(),
    )
    .await
    .unwrap();
    assert!(second.flags.field_rules);
    assert_eq!(second.jwt_ring.len(), 1);
    assert_eq!(
        second.store.as_ref().unwrap().origin(),
        bc_config::store::Origin::Snapshot
    );
    // a snapshot is not trusted blindly: tampered on disk, it is refused
    let path = std::path::Path::new(&snapshots).join("settings-backend.json");
    let text = std::fs::read_to_string(&path)
        .unwrap()
        .replace("\"value\":true", "\"value\":false");
    std::fs::write(&path, text).unwrap();
    let third = load(
        &[
            ("SETTINGS_SNAPSHOT_DIR", &snapshots),
            (
                "AUTH_JWT_SECRET",
                "environment-secret-0123456789abcdef0123456789",
            ),
        ],
        &FakeStore::down(),
    )
    .await
    .unwrap();
    assert!(!third.flags.field_rules);
}

#[tokio::test]
async fn the_store_is_off_when_off_or_unconfigured_and_required_needs_its_settings() {
    let none = Config::load_with(
        env(&[
            ("SETTINGS_STORE", "off"),
            (
                "AUTH_JWT_SECRET",
                "environment-secret-0123456789abcdef0123456789",
            ),
        ]),
        None,
        &[],
    )
    .await
    .unwrap();
    assert!(none.store.is_none());
    // auto without the master key: environment and defaults only
    let mut vars = env(&[(
        "AUTH_JWT_SECRET",
        "environment-secret-0123456789abcdef0123456789",
    )]);
    vars.remove("SETTINGS_MASTER_KEY");
    assert!(
        Config::load_with(vars.clone(), None, &[])
            .await
            .unwrap()
            .store
            .is_none()
    );
    vars.insert("SETTINGS_STORE".into(), "required".into());
    let err = Config::load_with(vars, None, &[]).await.unwrap_err();
    assert!(
        err.0.contains("needs DATABASE_URL and SETTINGS_MASTER_KEY"),
        "{err}"
    );
    let err = Config::load_with(env(&[("SETTINGS_STORE", "sometimes")]), None, &[])
        .await
        .unwrap_err();
    assert!(err.0.contains("off, auto or required"), "{err}");
}

#[tokio::test]
async fn a_never_written_store_is_empty_and_trusted_until_the_service_expects_keys_in_it() {
    let empty = || RawSnapshot {
        rows: vec![],
        manifest: Some(bc_config::store::canonical::Manifest {
            revision: 0,
            entries: std::collections::BTreeMap::new(),
            sig: String::new(),
        }),
        malformed: vec![],
    };
    let store = FakeStore::new(empty());
    let secret = (
        "AUTH_JWT_SECRET",
        "environment-secret-0123456789abcdef0123456789",
    );
    assert!(
        load(
            &[secret, ("SETTINGS_SNAPSHOT_DIR", &dir("empty-auto"))],
            &store
        )
        .await
        .is_ok()
    );
    let err = load(
        &[
            secret,
            ("SETTINGS_STORE", "required"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("empty-req")),
        ],
        &store,
    )
    .await
    .unwrap_err();
    assert!(
        err.0.contains("empty (revision 0)") && err.0.contains("AUTH_AES_HEX_KEY"),
        "{err}"
    );
}

// ------------------------------------------------------------- rollback

#[tokio::test]
async fn a_store_older_than_the_recorded_revision_is_refused_at_start() {
    let snapshots = dir("floor");
    let first = load(
        &[("SETTINGS_SNAPSHOT_DIR", &snapshots)],
        &FakeStore::new(golden_snapshot()),
    )
    .await
    .unwrap();
    assert_eq!(first.store.as_ref().unwrap().revision(), 7);
    // the database was restored from a backup: revision 5 (genuinely signed)
    let older = FakeStore::new(store_with(
        vec![row_for("FIELD_RULES_ENABLED", 1, json!(false))],
        5,
    ));
    let err = load(
        &[
            ("SETTINGS_SNAPSHOT_DIR", &snapshots),
            ("SETTINGS_STORE", "required"),
        ],
        &older,
    )
    .await
    .unwrap_err();
    assert!(err.0.contains("behind this service's record"), "{err}");
    // auto: the older manifest is refused as a rollback and nothing applies
    let cfg = load(
        &[
            ("SETTINGS_SNAPSHOT_DIR", &snapshots),
            (
                "AUTH_JWT_SECRET",
                "environment-secret-0123456789abcdef0123456789",
            ),
        ],
        &older,
    )
    .await
    .unwrap();
    assert!(!cfg.flags.field_rules);
}

#[tokio::test]
async fn a_running_service_never_accepts_an_older_revision_or_version() {
    let store = FakeStore::new(golden_snapshot());
    let cfg = load(&[("SETTINGS_SNAPSHOT_DIR", &dir("running"))], &store)
        .await
        .unwrap();
    let rt = cfg.store.clone().unwrap();
    // revision 6 < 7 seen
    store.set(store_with(
        vec![row_for("API_FLOW_EVENTS_PER_WINDOW", 9, json!(50))],
        6,
    ));
    assert!(!rt.poll_once().await.unwrap());
    assert_eq!(
        rt.live_value("API_FLOW_EVENTS_PER_WINDOW").as_deref(),
        Some("600")
    );
    // a newer revision carrying an older version of a row
    store.set(store_with(
        vec![row_for("API_FLOW_EVENTS_PER_WINDOW", 1, json!(50))],
        8,
    ));
    rt.poll_once().await.unwrap();
    assert_eq!(
        rt.live_value("API_FLOW_EVENTS_PER_WINDOW").as_deref(),
        Some("600"),
        "the last good value is kept"
    );
    assert!(
        rt.rejections()
            .iter()
            .any(|r| r.reason == "version_rollback")
    );
}

// ----------------------------------------------------- reload classes

#[tokio::test]
async fn class_h_follows_the_store_while_class_r_waits_for_a_restart() {
    let store = FakeStore::new(golden_snapshot());
    let cfg = load(&[("SETTINGS_SNAPSHOT_DIR", &dir("live"))], &store)
        .await
        .unwrap();
    let rt = cfg.store.clone().unwrap();
    assert_eq!(
        rt.live_value("API_FLOW_EVENTS_PER_WINDOW").as_deref(),
        Some("600")
    );
    assert!(!rt.restart_pending());
    store.set(store_with(
        vec![
            row_for("API_FLOW_EVENTS_PER_WINDOW", 5, json!(700)),
            row_for("FIELD_RULES_ENABLED", 3, json!(false)),
        ],
        8,
    ));
    assert!(rt.poll_once().await.unwrap());
    assert_eq!(
        rt.live_value("API_FLOW_EVENTS_PER_WINDOW").as_deref(),
        Some("700")
    );
    assert!(
        cfg.flags.field_rules,
        "a class R setting keeps its value until restart"
    );
    assert!(rt.restart_pending());
    assert_eq!(rt.live_value("FIELD_RULES_ENABLED"), None, "not hot");
    assert_eq!(
        rt.live_value("AUTH_JWT_SECRET"),
        None,
        "a secret is never live"
    );
    // nothing new: no work
    assert!(!rt.poll_once().await.unwrap());
}

#[tokio::test]
async fn an_environment_value_pins_a_hot_setting() {
    let store = FakeStore::new(golden_snapshot());
    let cfg = load(
        &[
            ("API_FLOW_EVENTS_PER_WINDOW", "5"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("pinned")),
        ],
        &store,
    )
    .await
    .unwrap();
    assert_eq!(
        cfg.store
            .as_ref()
            .unwrap()
            .live_value("API_FLOW_EVENTS_PER_WINDOW"),
        None
    );
}

// ------------------------------------------------------------- logging

#[derive(Clone, Default)]
struct Captured(Arc<Mutex<Vec<u8>>>);

impl Write for Captured {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        self.0.lock().unwrap().extend_from_slice(buf);
        Ok(buf.len())
    }

    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

/// One subscriber for the whole test binary (a thread-local one races with the
/// other tests' first use of a callsite). Every test's log lines land in it, so
/// the assertion below covers all of them.
fn capture_logs() -> Captured {
    static SINK: std::sync::OnceLock<Captured> = std::sync::OnceLock::new();
    SINK.get_or_init(|| {
        let sink = Captured::default();
        let writer = sink.clone();
        let _ = tracing_subscriber::fmt()
            .with_writer(move || writer.clone())
            .with_ansi(false)
            .with_max_level(tracing::Level::TRACE)
            .try_init();
        sink
    })
    .clone()
}

#[tokio::test]
async fn no_value_reaches_the_logs_or_the_error_and_debug_text() {
    let captured = capture_logs();

    let mut texts = Vec::new();
    // every failure path that logs: tampered rows, an unusable secret, an untrusted
    // manifest, a store that is down, a rollback, a poll
    let mut tampered = golden_snapshot();
    for row in &mut tampered.rows {
        if row.key == "FIELD_RULES_ENABLED" {
            row.value = Some(json!("super-secret-switch-value"));
        }
    }
    let store = FakeStore::new(tampered);
    let secret = "environment-secret-0123456789abcdef0123456789";
    let cfg = load(
        &[
            ("AUTH_JWT_SECRET", secret),
            ("SETTINGS_SNAPSHOT_DIR", &dir("logs1")),
        ],
        &store,
    )
    .await
    .unwrap();
    texts.push(format!("{cfg:?}"));
    texts.push(format!("{:?}", cfg.store));
    let mut unopenable = golden_row("AUTH_JWT_SECRET");
    unopenable.blob = Some(unopenable.blob.clone().unwrap().replacen("v2:", "v2:z", 1));
    unopenable.sig = String::new();
    let unopen_store = FakeStore::new(signed(
        vec![
            unopenable,
            row_for("DEFAULT_WORKSPACE_ID", 1, json!("plain-text-value-1")),
        ],
        4,
    ));
    let err = load(
        &[
            ("SETTINGS_STORE", "required"),
            ("SETTINGS_SNAPSHOT_DIR", &dir("logs2")),
        ],
        &unopen_store,
    )
    .await
    .unwrap_err();
    texts.push(err.to_string());
    let _ = load(
        &[
            ("AUTH_JWT_SECRET", secret),
            ("SETTINGS_SNAPSHOT_DIR", &dir("logs3")),
        ],
        &unopen_store,
    )
    .await;
    let _ = load(
        &[
            ("AUTH_JWT_SECRET", secret),
            ("SETTINGS_SNAPSHOT_DIR", &dir("logs4")),
        ],
        &FakeStore::down(),
    )
    .await;
    let rt = cfg.store.clone().unwrap();
    store.set(signed(
        vec![row_for("API_FLOW_EVENTS_PER_WINDOW", 1, json!(31337))],
        2,
    ));
    let _ = rt.poll_once().await;

    texts.push(String::from_utf8_lossy(&captured.0.lock().unwrap()).into_owned());
    let all = texts.join("\n");
    assert!(
        all.contains("rejected") || all.contains("refused"),
        "something was logged: {all}"
    );
    let blob = golden_row("AUTH_JWT_SECRET").blob.unwrap();
    for needle in [
        JWT,
        secret,
        blob.as_str(),
        "super-secret-switch-value",
        "plain-text-value-1",
        "pw-not-logged",
        "31337",
        support::master().as_str(),
    ] {
        assert!(
            !all.contains(needle),
            "a value reached the logs or an error: {needle}"
        );
    }
}
