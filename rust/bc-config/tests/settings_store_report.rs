#![allow(clippy::unwrap_used, clippy::expect_used)]
//! What the service tells the settings store about itself (`settings.report_state`):
//! the same fields and the same values a Python service reports, against the
//! fingerprints the Python code computes (`golden/settings_store.json`,
//! "fingerprints").

mod support;

use base64::Engine;
use bc_config::Config;
use bc_config::store::report::{self, ServiceState};
use serde_json::json;
use support::{FakeStore, env, golden, golden_snapshot, row_for, scratch, signed};

async fn load(extra: &[(&str, &str)], store: &FakeStore) -> Config {
    Config::load_with(env(extra), Some(store.boxed()), &[])
        .await
        .unwrap()
}

fn keyset_json(ids: &[u32]) -> String {
    let keys: Vec<_> = ids
        .iter()
        .map(|id| json!({"keyData": {"typeUrl": "t", "value": "not-key-material"}, "status": "ENABLED", "keyId": id, "outputPrefixType": "TINK"}))
        .collect();
    json!({"primaryKeyId": ids[0], "key": keys}).to_string()
}

#[test]
fn fingerprints_equal_the_ones_python_computes() {
    let g = &golden()["fingerprints"];
    assert_eq!(g["report_mark"].as_str().unwrap(), report::REPORT_MARK);
    for case in g["keyset_ids"].as_array().unwrap() {
        let ids: Vec<String> = case["ids"]
            .as_array()
            .unwrap()
            .iter()
            .map(|i| i.as_u64().unwrap().to_string())
            .collect();
        assert_eq!(
            report::keyset_fingerprint(&ids),
            case["fp"].as_str().unwrap(),
            "{ids:?}"
        );
    }
    let sections = bc_config::store::registry::Registry::shipped().sections();
    let master = golden()["master"].as_str().unwrap().to_string();
    let previous = golden()["master_previous"].as_str().unwrap().to_string();
    let fp = |m: &str, p: Option<&str>| {
        bc_config::store::crypto::SectionKeys::new(m, p, &sections)
            .unwrap()
            .fingerprint()
            .to_string()
    };
    assert_eq!(fp(&master, None), g["master"].as_str().unwrap());
    assert_eq!(
        fp(&master, Some(&previous)),
        g["master_with_previous"].as_str().unwrap()
    );
    assert_eq!(fp(&previous, None), g["previous_only"].as_str().unwrap());
    assert_ne!(g["master"], g["previous_only"]);
}

#[tokio::test]
async fn a_report_carries_what_a_python_service_reports() {
    let store = FakeStore::new(golden_snapshot());
    let cfg = load(
        &[("SETTINGS_SNAPSHOT_DIR", &scratch("report-basic"))],
        &store,
    )
    .await;
    let rt = cfg.store.clone().unwrap();
    rt.report_safely().await;
    let (instance, state) = store.last_report();
    assert!(instance.starts_with("backend.edge:"), "{instance}");
    assert!(
        instance.len() <= 64
            && instance
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || "_.:-".contains(c))
    );
    assert_eq!(instance, rt.instance_id());
    assert_eq!(state.revision_applied, 7);
    assert!(!state.restart_pending);
    assert_eq!(state.write_stores, "postgres");
    // the golden store also holds four rows for keys that are not settings: refused, and named
    // (the database function keeps only the names the service may read)
    assert_eq!(
        state.rejected_keys,
        ["HUGE_FLOAT", "NESTED", "TEXT", "TINY_FLOAT"]
    );
    // no keyset at this service (the golden store's keyset value is not a keyset): the
    // fingerprint of the settings master key, as a Python service without one reports
    assert_eq!(
        state.keyset_fp,
        golden()["fingerprints"]["master"].as_str().unwrap()
    );
    // the name of a key is reported, never a value
    assert!(!format!("{state:?}").contains("golden-jwt-secret"));
}

#[tokio::test]
async fn the_keyset_fingerprint_is_that_of_the_key_ids_in_the_environment_or_the_store() {
    let g = &golden()["fingerprints"]["keyset_ids"];
    let expected = |ids: &[u32]| {
        g.as_array()
            .unwrap()
            .iter()
            .find(|c| {
                c["ids"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|i| i.as_u64().unwrap())
                    .collect::<Vec<_>>()
                    == ids.iter().map(|i| u64::from(*i)).collect::<Vec<_>>()
            })
            .map(|c| c["fp"].as_str().unwrap().to_string())
            .unwrap()
    };
    let b64 = |ids: &[u32]| base64::engine::general_purpose::STANDARD.encode(keyset_json(ids));
    // from the environment, base64 of the JSON (the env format) or the JSON itself
    for value in [b64(&[300, 7]), keyset_json(&[300, 7])] {
        let store = FakeStore::new(golden_snapshot());
        let cfg = load(
            &[
                ("SETTINGS_SNAPSHOT_DIR", &scratch("report-keyset-env")),
                ("MASTER_ENCRYPTION_KEYSET", value.as_str()),
            ],
            &store,
        )
        .await;
        cfg.store.as_ref().unwrap().report_safely().await;
        let (_, state) = store.last_report();
        assert_eq!(state.keyset_fp, expected(&[300, 7]));
        assert!(
            state
                .env_overrides
                .contains(&"MASTER_ENCRYPTION_KEYSET".to_string()),
            "{:?}",
            state.env_overrides
        );
    }
    // an unusable keyset falls back to the master key's fingerprint
    let store = FakeStore::new(golden_snapshot());
    let cfg = load(
        &[
            ("SETTINGS_SNAPSHOT_DIR", &scratch("report-keyset-bad")),
            ("MASTER_ENCRYPTION_KEYSET", "not a keyset"),
        ],
        &store,
    )
    .await;
    cfg.store.as_ref().unwrap().report_safely().await;
    assert_eq!(
        store.last_report().1.keyset_fp,
        golden()["fingerprints"]["master"].as_str().unwrap()
    );
}

#[tokio::test]
async fn an_environment_value_is_listed_as_an_override_of_the_store() {
    let store = FakeStore::new(golden_snapshot());
    let cfg = load(
        &[
            ("SETTINGS_SNAPSHOT_DIR", &scratch("report-override")),
            ("FIELD_RULES_ENABLED", "false"),
        ],
        &store,
    )
    .await;
    cfg.store.as_ref().unwrap().report_safely().await;
    let (_, state) = store.last_report();
    assert_eq!(state.env_overrides, vec!["FIELD_RULES_ENABLED".to_string()]);
    assert!(
        state.env_overrides.windows(2).all(|w| w[0] < w[1]),
        "sorted"
    );
}

#[tokio::test]
async fn a_changed_restart_class_setting_shows_as_restart_pending_in_the_next_report() {
    let store = FakeStore::new(golden_snapshot());
    let cfg = load(
        &[("SETTINGS_SNAPSHOT_DIR", &scratch("report-restart"))],
        &store,
    )
    .await;
    let rt = cfg.store.clone().unwrap();
    rt.report_safely().await;
    assert!(!store.last_report().1.restart_pending);
    let before = store.reports().len();
    let mut rows = vec![support::golden_row("AUTH_JWT_SECRET")];
    rows.push(row_for("FIELD_RULES_ENABLED", 3, json!(false)));
    store.set(signed(rows, 8));
    assert!(rt.poll_once().await.unwrap());
    // a poll that saw a new revision reported at once, without waiting for the heartbeat
    assert_eq!(store.reports().len(), before + 1);
    let (_, state) = store.last_report();
    assert!(state.restart_pending);
    assert_eq!(state.revision_applied, 8);
    assert!(rt.restart_pending());
}

#[tokio::test]
async fn refused_rows_are_reported_by_name_and_the_revision_is_the_highest_accepted() {
    let mut snap = golden_snapshot();
    for row in &mut snap.rows {
        if row.key == "FIELD_RULES_ENABLED" {
            row.value = Some(json!(false)); // signed true: refused
        }
    }
    let store = FakeStore::new(snap);
    let cfg = load(
        &[("SETTINGS_SNAPSHOT_DIR", &scratch("report-rejected"))],
        &store,
    )
    .await;
    cfg.store.as_ref().unwrap().report_safely().await;
    let (_, state) = store.last_report();
    assert!(
        state
            .rejected_keys
            .contains(&"FIELD_RULES_ENABLED".to_string())
    );
    assert_eq!(state.rejected_keys.len(), 5);
    assert!(
        state
            .rejected_keys
            .iter()
            .all(|k| report::is_setting_name(k))
    );
    assert_eq!(state.revision_applied, 7);
}

#[tokio::test]
async fn a_refused_report_never_stops_the_service_and_reporting_resumes() {
    let store = FakeStore::new(golden_snapshot());
    let cfg = load(
        &[("SETTINGS_SNAPSHOT_DIR", &scratch("report-refused"))],
        &store,
    )
    .await;
    let rt = cfg.store.clone().unwrap();
    store.refuse_reports(true);
    rt.report_safely().await;
    rt.report_safely().await;
    assert_eq!(store.reports().len(), 0);
    store.refuse_reports(false);
    rt.report_safely().await;
    assert_eq!(store.reports().len(), 1);
}

#[test]
fn the_state_is_made_of_names_and_counts() {
    let state = ServiceState {
        revision_applied: 1,
        env_overrides: vec![],
        rejected_keys: vec![],
        restart_pending: false,
        keyset_fp: String::new(),
        write_stores: report::WRITE_STORES.into(),
    };
    assert_eq!(state.write_stores, "postgres");
}
