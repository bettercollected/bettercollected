#![allow(dead_code, clippy::unwrap_used, clippy::expect_used)]
//! Shared by the settings-store tests: the golden vector (signed and sealed by the
//! Python code) and a store that tests can change.

use std::collections::{BTreeMap, HashMap};
use std::sync::{Arc, Mutex};

use bc_config::store::canonical::Manifest;
pub use bc_config::store::canonical::Row;
use bc_config::store::crypto::SectionKeys;
use bc_config::store::registry::Registry;
use bc_config::store::runtime::{Fetch, SnapshotSource, SourceUnavailable};
use bc_config::store::verify::RawSnapshot;
use serde_json::Value;

pub const GOLDEN: &str = include_str!("../golden/settings_store.json");

pub fn golden() -> Value {
    serde_json::from_str(GOLDEN).unwrap()
}

pub fn row_from(v: &Value) -> Row {
    Row {
        key: v["key"].as_str().unwrap().into(),
        section: v["section"].as_str().unwrap().into(),
        readers: v["readers"]
            .as_array()
            .unwrap()
            .iter()
            .map(|r| r.as_str().unwrap().into())
            .collect(),
        is_secret: v["is_secret"].as_bool().unwrap(),
        reload_class: v["reload_class"].as_str().unwrap().into(),
        version: v["version"].as_u64().unwrap(),
        updated_at: v["updated_at"].as_str().unwrap().into(),
        value: Some(v["value"].clone()).filter(|x| !x.is_null()),
        blob: v["blob"].as_str().map(str::to_string),
        sig: v["sig"].as_str().unwrap().into(),
    }
}

pub fn golden_rows() -> Vec<Row> {
    golden()["rows"]
        .as_array()
        .unwrap()
        .iter()
        .map(row_from)
        .collect()
}

pub fn golden_keys() -> SectionKeys {
    let g = golden();
    // every section the backend reads (the keys of a section are independent)
    SectionKeys::new(
        g["master"].as_str().unwrap(),
        g["master_previous"].as_str(),
        &Registry::shipped().sections(),
    )
    .unwrap()
}

/// What the Python signer wrote: its ten rows and its manifest (revision 7).
pub fn golden_snapshot() -> RawSnapshot {
    let m = &golden()["manifest"];
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
    RawSnapshot {
        rows: golden_rows(),
        manifest: Some(Manifest {
            revision: m["revision"].as_u64().unwrap(),
            entries,
            sig: m["sig"].as_str().unwrap().to_string(),
        }),
        malformed: vec![],
    }
}

/// An unsigned plain row for a real setting, shaped as its registry entry says.
pub fn row_for(key: &str, version: u64, value: Value) -> Row {
    let spec = Registry::shipped().get(key).unwrap();
    assert!(!spec.is_secret);
    let mut readers: Vec<&str> = spec.readers.iter().map(String::as_str).collect();
    readers.sort_unstable();
    plain(
        key,
        &spec.section,
        &readers,
        &format!("{:?}", spec.reload),
        version,
        value,
    )
}

/// The golden master key, the form the environment carries it in.
pub fn master() -> String {
    golden()["master"].as_str().unwrap().into()
}

/// A plain row, unsigned.
pub fn plain(
    key: &str,
    section: &str,
    readers: &[&str],
    reload: &str,
    version: u64,
    value: Value,
) -> Row {
    Row {
        key: key.into(),
        section: section.into(),
        readers: readers.iter().map(|r| (*r).into()).collect(),
        is_secret: false,
        reload_class: reload.into(),
        version,
        updated_at: "2026-11-16T09:08:07.654321Z".into(),
        value: Some(value),
        blob: None,
        sig: String::new(),
    }
}

/// Signs `rows` (those with an empty `sig`; a row that has one keeps it) and a
/// manifest over all of them, as the admin portal's writer does.
pub fn signed(rows: Vec<Row>, revision: u64) -> RawSnapshot {
    let keys = golden_keys();
    let rows: Vec<Row> = rows
        .into_iter()
        .map(|mut r| {
            if r.sig.is_empty() {
                r.sig = keys.sign_row_current(&r).unwrap();
            }
            r
        })
        .collect();
    let entries: BTreeMap<String, (u64, String, Vec<String>)> = rows
        .iter()
        .map(|r| {
            let mut readers = r.readers.clone();
            readers.sort();
            (r.key.clone(), (r.version, r.sig.clone(), readers))
        })
        .collect();
    let mut manifest = Manifest {
        revision,
        entries,
        sig: String::new(),
    };
    manifest.sig = keys.sign_manifest_current(&manifest).unwrap();
    RawSnapshot {
        rows,
        manifest: Some(manifest),
        malformed: vec![],
    }
}

pub fn golden_row(key: &str) -> Row {
    golden_rows().into_iter().find(|r| r.key == key).unwrap()
}

/// A store whose content the test can replace.
#[derive(Clone)]
pub struct FakeStore(Arc<Mutex<Result<RawSnapshot, SourceUnavailable>>>);

impl FakeStore {
    pub fn new(content: RawSnapshot) -> FakeStore {
        FakeStore(Arc::new(Mutex::new(Ok(content))))
    }

    pub fn down() -> FakeStore {
        FakeStore(Arc::new(Mutex::new(Err(SourceUnavailable("connect")))))
    }

    pub fn set(&self, content: RawSnapshot) {
        *self.0.lock().unwrap() = Ok(content);
    }

    pub fn boxed(&self) -> Box<dyn SnapshotSource> {
        Box::new(self.clone())
    }
}

impl SnapshotSource for FakeStore {
    fn fetch(&self) -> Fetch<'_, RawSnapshot> {
        Box::pin(async move { self.0.lock().unwrap().clone() })
    }

    fn fetch_revision(&self) -> Fetch<'_, Option<u64>> {
        Box::pin(async move {
            self.0
                .lock()
                .unwrap()
                .clone()
                .map(|raw| raw.manifest.map(|m| m.revision))
        })
    }
}

/// The environment of a service that reads the store: the master key, the
/// database URL, and the extras.
pub fn env(extra: &[(&str, &str)]) -> HashMap<String, String> {
    let mut vars: HashMap<String, String> = [
        (
            "DATABASE_URL",
            "postgresql+asyncpg://u:pw-not-logged@127.0.0.1:1/none",
        ),
        ("SETTINGS_MASTER_KEY", master().as_str()),
        ("BC_PYTHON_UPSTREAM", "http://backend:8000"),
    ]
    .iter()
    .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
    .collect();
    for (k, v) in extra {
        vars.insert((*k).to_string(), (*v).to_string());
    }
    vars
}

/// A scratch directory for a snapshot, empty.
pub fn scratch(name: &str) -> String {
    let dir = std::env::temp_dir().join(format!("bc-config-store-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    dir.to_string_lossy().into_owned()
}
