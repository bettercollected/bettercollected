//! Which stored rows are accepted: `common/settings/snapshot.py` `verify_snapshot`,
//! `VerifiedSettings` and `signing.MonotonicTracker`.
//!
//! A row is accepted only when its key is known, its section, secrecy, reload
//! class and readers match the registry, the signed manifest lists it with the
//! same version, signature and readers, its own signature verifies, and its
//! version is not lower than one already seen. A manifest that is missing,
//! badly signed or older than one already seen rejects every row. Nothing here
//! carries a value.

use std::collections::{BTreeMap, HashMap, HashSet};

use super::canonical::{Manifest, Row};
use super::crypto::SectionKeys;
use super::registry::Registry;

/// The key of the rejection that says the manifest itself was not trusted.
pub const UNTRUSTED: &str = "*";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Rejection {
    pub key: String,
    pub version: u64,
    pub reason: &'static str,
}

impl Rejection {
    pub fn message(&self) -> String {
        format!(
            "setting {} version {} rejected: {}",
            self.key, self.version, self.reason
        )
    }
}

/// What the store returned, before any verification.
#[derive(Debug, Default, Clone)]
pub struct RawSnapshot {
    pub rows: Vec<Row>,
    pub manifest: Option<Manifest>,
    /// `(key, version)` of rows that could not even be read.
    pub malformed: Vec<(String, u64)>,
}

#[derive(Debug, Clone, Default)]
pub struct Verification {
    pub accepted: BTreeMap<String, Row>,
    pub rejections: Vec<Rejection>,
    /// Of the manifest; 0 when it was not trusted.
    pub revision: u64,
}

/// The highest versions and manifest revision seen: a lower one is a rollback.
#[derive(Debug, Default, Clone)]
pub struct Tracker {
    pub versions: HashMap<String, u64>,
    pub revision: u64,
}

impl Tracker {
    pub fn is_rollback(&self, key: &str, version: u64) -> bool {
        version < self.versions.get(key).copied().unwrap_or(0)
    }

    pub fn revision_rolled_back(&self, revision: u64) -> bool {
        revision < self.revision
    }

    pub fn commit<'a>(&mut self, rows: impl IntoIterator<Item = &'a Row>, revision: u64) {
        for row in rows {
            let seen = self.versions.entry(row.key.clone()).or_insert(0);
            if row.version > *seen {
                *seen = row.version;
            }
        }
        self.revision = self.revision.max(revision);
    }
}

pub fn verify_snapshot(
    rows: &[Row],
    manifest: Option<&Manifest>,
    keys: &SectionKeys,
    seen: &Tracker,
    registry: &Registry,
) -> Verification {
    let service = registry.service.as_str();
    let mut accepted = BTreeMap::new();
    let mut rejected = Vec::new();
    let reject = |rejected: &mut Vec<Rejection>, row: &Row, reason: &'static str| {
        rejected.push(Rejection {
            key: row.key.clone(),
            version: row.version,
            reason,
        });
    };

    let trusted =
        manifest.filter(|m| keys.verify_manifest(m) && !seen.revision_rolled_back(m.revision));
    let Some(manifest) = trusted else {
        for row in rows {
            reject(&mut rejected, row, "manifest_mismatch");
        }
        // also when there are no rows: the loader must learn the manifest is untrusted
        rejected.push(Rejection {
            key: UNTRUSTED.into(),
            version: 0,
            reason: "manifest_mismatch",
        });
        return Verification {
            accepted,
            rejections: rejected,
            revision: 0,
        };
    };

    for row in rows {
        let Some(spec) = registry.get(&row.key) else {
            if registry.knows(&row.key) {
                // a setting of another service: its readers never include this one
                reject(&mut rejected, row, "spec_mismatch");
            } else if !registry.is_retired(&row.key) {
                reject(&mut rejected, row, "unknown_key");
            }
            continue;
        };
        let allowed: HashSet<&String> = spec.readers.iter().chain(&spec.retired_readers).collect();
        if row.section != spec.section
            || row.is_secret != spec.is_secret
            || row.reload_class != format!("{:?}", spec.reload)
            || !row.readers.iter().all(|r| allowed.contains(r))
        {
            reject(&mut rejected, row, "spec_mismatch");
            continue;
        }
        if !row.readers.iter().any(|r| r == service) || !spec.readers.iter().any(|r| r == service) {
            reject(&mut rejected, row, "reader_not_allowed");
            continue;
        }
        let Some((version, sig, readers)) = manifest.entries.get(&row.key) else {
            reject(&mut rejected, row, "manifest_missing_key");
            continue;
        };
        let mut sorted = row.readers.clone();
        sorted.sort();
        if *version != row.version || *sig != row.sig || *readers != sorted {
            reject(&mut rejected, row, "manifest_mismatch");
            continue;
        }
        if !keys.verify_row(row) {
            reject(&mut rejected, row, "bad_signature");
            continue;
        }
        if seen.is_rollback(&row.key, row.version) {
            reject(&mut rejected, row, "version_rollback");
            continue;
        }
        accepted.insert(row.key.clone(), row.clone());
    }

    let presented: HashSet<&str> = rows.iter().map(|r| r.key.as_str()).collect();
    for key in manifest.keys_for(service) {
        if presented.contains(key.as_str()) {
            continue;
        }
        if registry.get(&key).is_none() {
            continue;
        }
        let version = manifest.entries.get(&key).map_or(0, |e| e.0);
        rejected.push(Rejection {
            key,
            version,
            reason: "row_missing",
        });
    }
    Verification {
        accepted,
        rejections: rejected,
        revision: manifest.revision,
    }
}

/// The accepted rows, with the last good row kept for a key that is rejected
/// or missing now (`previous`).
#[derive(Debug, Default, Clone)]
pub struct VerifiedSettings {
    rows: BTreeMap<String, Row>,
    revision: u64,
    pub rejections: Vec<Rejection>,
    pub stale_keys: Vec<String>,
}

impl VerifiedSettings {
    pub fn new(
        verification: Verification,
        previous: Option<&VerifiedSettings>,
    ) -> VerifiedSettings {
        let mut rows = verification.accepted;
        let mut stale = Vec::new();
        if let Some(previous) = previous {
            for (key, row) in &previous.rows {
                if !rows.contains_key(key) && verification.rejections.iter().any(|r| &r.key == key)
                {
                    rows.insert(key.clone(), row.clone());
                    stale.push(key.clone());
                }
            }
        }
        stale.sort();
        VerifiedSettings {
            rows,
            revision: verification.revision,
            rejections: verification.rejections,
            stale_keys: stale,
        }
    }

    pub fn revision(&self) -> u64 {
        self.revision
    }

    pub fn get(&self, key: &str) -> Option<&Row> {
        self.rows.get(key)
    }

    pub fn rows(&self) -> impl Iterator<Item = &Row> {
        self.rows.values()
    }
}
