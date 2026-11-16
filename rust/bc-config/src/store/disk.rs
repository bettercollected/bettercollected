//! The signed disk snapshot used when the database cannot be read at start-up:
//! `common/settings/loader/disk.py`, same file name and format (so either side
//! reads what the other wrote).
//!
//! The accepted rows are written exactly as they came from the store (secrets
//! stay ciphertext) with the signed manifest. Nothing in the file is trusted:
//! on read every row is verified again. The save time is not signed; the
//! protection of the file is its location, a directory owned by the service's
//! user (mode 700), a file of mode 600, no symlinks, written by an atomic rename.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde_json::{Value, json};

use super::canonical::{Manifest, Row, is_canonical_timestamp};
use super::verify::RawSnapshot;

const FORMAT: u64 = 1;
const MAX_BYTES: u64 = 8 * 1024 * 1024;
const FUTURE_SLACK_SECS: i64 = 5 * 60;

/// The snapshot is unusable; `reason` is a short code, never content.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SnapshotError(pub &'static str);

pub fn snapshot_path(directory: &Path, service: &str) -> PathBuf {
    directory.join(format!("settings-{service}.json"))
}

// -------------------------------------------------------------------- time

/// Days from 1970-01-01 to a civil date (proleptic Gregorian).
fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * (if m > 2 { m - 3 } else { m + 9 }) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe - 719_468
}

fn civil_from_days(z: i64) -> (i64, i64, i64) {
    let z = z + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// Seconds since the epoch of `YYYY-MM-DDTHH:MM:SS.ffffffZ`.
pub fn parse_timestamp(text: &str) -> Option<i64> {
    if !is_canonical_timestamp(text) {
        return None;
    }
    let num = |range: std::ops::Range<usize>| text.get(range)?.parse::<i64>().ok();
    let (y, mo, d) = (num(0..4)?, num(5..7)?, num(8..10)?);
    let (h, mi, s) = (num(11..13)?, num(14..16)?, num(17..19)?);
    if !(1..=12).contains(&mo) || !(1..=31).contains(&d) || h > 23 || mi > 59 || s > 60 {
        return None;
    }
    Some(days_from_civil(y, mo, d) * 86_400 + h * 3600 + mi * 60 + s)
}

pub fn format_timestamp(now: SystemTime) -> String {
    let (secs, micros) = match now.duration_since(UNIX_EPOCH) {
        Ok(d) => (i64::try_from(d.as_secs()).unwrap_or(0), d.subsec_micros()),
        Err(_) => (0, 0),
    };
    let (y, m, d) = civil_from_days(secs.div_euclid(86_400));
    let rest = secs.rem_euclid(86_400);
    format!(
        "{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}.{micros:06}Z",
        rest / 3600,
        rest % 3600 / 60,
        rest % 60
    )
}

fn epoch(now: SystemTime) -> i64 {
    now.duration_since(UNIX_EPOCH)
        .ok()
        .and_then(|d| i64::try_from(d.as_secs()).ok())
        .unwrap_or(0)
}

// ------------------------------------------------------------------- files

/// This process's effective user id. `/proc/self` belongs to it; elsewhere the
/// owner check is skipped (the mode checks stay).
#[cfg(unix)]
fn euid() -> Option<u32> {
    use std::os::unix::fs::MetadataExt;
    fs::metadata("/proc/self").ok().map(|m| m.uid())
}

fn row_json(row: &Row) -> Value {
    json!({
        "key": row.key,
        "section": row.section,
        "readers": row.readers,
        "is_secret": row.is_secret,
        "reload_class": row.reload_class,
        "version": row.version,
        "updated_at": row.updated_at,
        "value": row.value,
        "blob": row.blob,
        "sig": row.sig,
    })
}

fn row_from(data: &Value) -> Option<Row> {
    let text = |name: &str| data.get(name)?.as_str().map(str::to_string);
    let updated_at = text("updated_at")?;
    if !is_canonical_timestamp(&updated_at) {
        return None;
    }
    Some(Row {
        key: text("key")?,
        section: text("section")?,
        readers: data
            .get("readers")?
            .as_array()?
            .iter()
            .map(|r| r.as_str().map(str::to_string))
            .collect::<Option<Vec<_>>>()?,
        is_secret: data.get("is_secret")?.as_bool()?,
        reload_class: text("reload_class")?,
        version: data.get("version")?.as_u64()?,
        updated_at,
        value: data.get("value").filter(|v| !v.is_null()).cloned(),
        blob: text("blob"),
        sig: text("sig").unwrap_or_default(),
    })
}

pub fn manifest_json(manifest: &Manifest) -> Value {
    let entries: serde_json::Map<String, Value> = manifest
        .entries
        .iter()
        .map(|(k, (v, s, r))| (k.clone(), json!([v, s, r])))
        .collect();
    json!({"revision": manifest.revision, "entries": entries, "sig": manifest.sig})
}

/// The manifest of a JSON object `{"revision", "entries": {key: [version, sig,
/// readers]}, "sig"}`; `None` when it is malformed.
pub fn manifest_from(data: &Value) -> Option<Manifest> {
    let mut entries = std::collections::BTreeMap::new();
    for (key, entry) in data.get("entries")?.as_object()? {
        let entry = entry.as_array()?;
        if entry.len() != 3 {
            return None;
        }
        let mut readers = entry[2]
            .as_array()?
            .iter()
            .map(|r| r.as_str().map(str::to_string))
            .collect::<Option<Vec<_>>>()?;
        readers.sort();
        entries.insert(
            key.clone(),
            (entry[0].as_u64()?, entry[1].as_str()?.to_string(), readers),
        );
    }
    Some(Manifest {
        revision: data.get("revision")?.as_u64()?,
        entries,
        sig: data.get("sig")?.as_str()?.to_string(),
    })
}

#[cfg(unix)]
fn ensure_directory(directory: &Path) -> Result<(), SnapshotError> {
    use std::os::unix::fs::{DirBuilderExt, MetadataExt, PermissionsExt};
    fs::DirBuilder::new()
        .recursive(true)
        .mode(0o700)
        .create(directory)
        .map_err(|_| SnapshotError("directory_unavailable"))?;
    let info = fs::symlink_metadata(directory).map_err(|_| SnapshotError("directory_unsafe"))?;
    if !info.is_dir() || euid().is_some_and(|u| info.uid() != u) {
        return Err(SnapshotError("directory_unsafe"));
    }
    if info.mode() & 0o077 != 0 {
        // a directory we own that is too open (a fresh volume mount is 755): close it
        fs::set_permissions(directory, fs::Permissions::from_mode(0o700))
            .map_err(|_| SnapshotError("directory_unsafe"))?;
    }
    Ok(())
}

/// Writes atomically (a temporary file in the same directory, flushed, renamed).
#[cfg(unix)]
pub fn write_snapshot(
    directory: &Path,
    service: &str,
    accepted: &[&Row],
    manifest: &Manifest,
    now: SystemTime,
) -> Result<(), SnapshotError> {
    use std::os::unix::fs::OpenOptionsExt;
    ensure_directory(directory)?;
    let mut rows: Vec<&&Row> = accepted.iter().collect();
    rows.sort_by(|a, b| a.key.cmp(&b.key));
    let body = serde_json::to_vec(&json!({
        "format": FORMAT,
        "service": service,
        "saved_at": format_timestamp(now),
        "manifest": manifest_json(manifest),
        "rows": rows.iter().map(|r| row_json(r)).collect::<Vec<_>>(),
    }))
    .map_err(|_| SnapshotError("malformed"))?;
    let final_path = snapshot_path(directory, service);
    let mut nonce = [0u8; 8];
    // not a secret: only keeps two writers' temporary files apart
    nonce.copy_from_slice(&epoch_nanos().to_be_bytes());
    let temp = directory.join(format!(
        ".settings-{}-{}.tmp",
        std::process::id(),
        hex::encode(nonce)
    ));
    let result = (|| -> std::io::Result<()> {
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&temp)?;
        file.write_all(&body)?;
        file.flush()?;
        file.sync_all()?;
        fs::rename(&temp, &final_path)?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temp);
        return Err(SnapshotError("write_failed"));
    }
    if let Ok(dir) = fs::File::open(directory) {
        let _ = dir.sync_all(); // make the rename durable; not every filesystem allows it
    }
    Ok(())
}

fn epoch_nanos() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .ok()
        .and_then(|d| u64::try_from(d.as_nanos()).ok())
        .unwrap_or(0)
}

/// The unverified content and its save time (seconds). `max_age_days: None`
/// skips the age check (it is used to seed the version tracker).
#[cfg(unix)]
pub fn read_snapshot(
    directory: &Path,
    service: &str,
    max_age_days: Option<f64>,
    now: SystemTime,
) -> Result<(RawSnapshot, i64), SnapshotError> {
    use std::io::Read;
    use std::os::unix::fs::MetadataExt;
    let dir_info = fs::symlink_metadata(directory).map_err(|_| SnapshotError("missing"))?;
    if !dir_info.is_dir() {
        return Err(SnapshotError("insecure"));
    }
    let path = snapshot_path(directory, service);
    // no symlinks: the path itself must be the regular file that is opened (checked
    // by device and inode, so no platform's O_NOFOLLOW value is assumed)
    let link_info = fs::symlink_metadata(&path).map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            SnapshotError("missing")
        } else {
            SnapshotError("insecure")
        }
    })?;
    if !link_info.is_file() {
        return Err(SnapshotError("insecure"));
    }
    let file = fs::File::open(&path).map_err(|_| SnapshotError("insecure"))?;
    let info = file.metadata().map_err(|_| SnapshotError("insecure"))?;
    if !info.is_file()
        || info.len() > MAX_BYTES
        || info.ino() != link_info.ino()
        || info.dev() != link_info.dev()
    {
        return Err(SnapshotError("insecure"));
    }
    if let Some(uid) = euid()
        && (info.uid() != uid
            || info.mode() & 0o077 != 0
            || dir_info.uid() != uid
            || dir_info.mode() & 0o022 != 0)
    {
        return Err(SnapshotError("insecure"));
    }
    let mut data = Vec::new();
    file.take(MAX_BYTES + 1)
        .read_to_end(&mut data)
        .map_err(|_| SnapshotError("insecure"))?;
    let doc: Value = serde_json::from_slice(&data).map_err(|_| SnapshotError("malformed"))?;
    if doc.get("format").and_then(Value::as_u64) != Some(FORMAT) {
        return Err(SnapshotError("malformed"));
    }
    if doc.get("service").and_then(Value::as_str) != Some(service) {
        return Err(SnapshotError("wrong_service"));
    }
    let saved = doc
        .get("saved_at")
        .and_then(Value::as_str)
        .and_then(parse_timestamp)
        .ok_or(SnapshotError("malformed"))?;
    let rows = doc
        .get("rows")
        .and_then(Value::as_array)
        .and_then(|rows| rows.iter().map(row_from).collect::<Option<Vec<_>>>())
        .ok_or(SnapshotError("malformed"))?;
    let manifest = doc
        .get("manifest")
        .and_then(manifest_from)
        .ok_or(SnapshotError("malformed"))?;
    let now = epoch(now);
    if saved > now + FUTURE_SLACK_SECS {
        return Err(SnapshotError("expired"));
    }
    // a whole number of seconds is enough for an age in days
    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
    let limit = max_age_days.map(|days| (days * 86_400.0) as u64);
    if let Some(limit) = limit
        && (now - saved).max(0).unsigned_abs() > limit
    {
        return Err(SnapshotError("expired"));
    }
    Ok((
        RawSnapshot {
            rows,
            manifest: Some(manifest),
            malformed: Vec::new(),
        },
        saved,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;
    use std::time::Duration;

    fn row(key: &str) -> Row {
        Row {
            key: key.into(),
            section: "features".into(),
            readers: vec!["backend".into()],
            is_secret: false,
            reload_class: "R".into(),
            version: 2,
            updated_at: "2026-03-04T05:06:07.000008Z".into(),
            value: Some(json!(true)),
            blob: None,
            sig: "ab".repeat(32),
        }
    }

    fn scratch(name: &str) -> PathBuf {
        let dir =
            std::env::temp_dir().join(format!("bc-config-disk-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        dir
    }

    #[test]
    fn timestamps_round_trip_and_match_the_known_epoch() {
        assert_eq!(parse_timestamp("1970-01-01T00:00:00.000000Z"), Some(0));
        assert_eq!(
            parse_timestamp("2026-11-16T12:00:00.000000Z"),
            Some(1_794_830_400)
        );
        assert_eq!(parse_timestamp("2026-13-16T12:00:00.000000Z"), None);
        assert_eq!(parse_timestamp("2026-11-16 12:00:00"), None);
        let t = UNIX_EPOCH + Duration::new(1_794_830_400, 123_456_000);
        assert_eq!(format_timestamp(t), "2026-11-16T12:00:00.123456Z");
        assert_eq!(parse_timestamp(&format_timestamp(t)), Some(1_794_830_400));
    }

    #[test]
    fn a_snapshot_written_is_read_back_and_expires() {
        let dir = scratch("roundtrip");
        let mut entries = BTreeMap::new();
        entries.insert(
            "A_ENABLED".to_string(),
            (2, "ab".repeat(32), vec!["backend".to_string()]),
        );
        let manifest = Manifest {
            revision: 9,
            entries,
            sig: "cd".repeat(32),
        };
        let a = row("A_ENABLED");
        let now = SystemTime::now();
        write_snapshot(&dir, "backend", &[&a], &manifest, now).unwrap();
        let (raw, _) = read_snapshot(&dir, "backend", Some(7.0), now).unwrap();
        assert_eq!(raw.rows, vec![a]);
        assert_eq!(raw.manifest.as_ref(), Some(&manifest));
        assert_eq!(
            read_snapshot(&dir, "auth", Some(7.0), now).unwrap_err().0,
            "missing"
        );
        let later = now + Duration::from_hours(192);
        assert_eq!(
            read_snapshot(&dir, "backend", Some(7.0), later)
                .unwrap_err()
                .0,
            "expired"
        );
        assert!(read_snapshot(&dir, "backend", None, later).is_ok());
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_file_other_users_can_read_is_not_trusted() {
        use std::os::unix::fs::PermissionsExt;
        let dir = scratch("modes");
        let manifest = Manifest {
            revision: 1,
            entries: BTreeMap::new(),
            sig: String::new(),
        };
        write_snapshot(&dir, "backend", &[], &manifest, SystemTime::now()).unwrap();
        let path = snapshot_path(&dir, "backend");
        fs::set_permissions(&path, fs::Permissions::from_mode(0o644)).unwrap();
        assert_eq!(
            read_snapshot(&dir, "backend", None, SystemTime::now())
                .unwrap_err()
                .0,
            "insecure"
        );
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_symlink_in_place_of_the_snapshot_is_not_followed() {
        let dir = scratch("symlink");
        let manifest = Manifest {
            revision: 1,
            entries: BTreeMap::new(),
            sig: String::new(),
        };
        write_snapshot(&dir, "backend", &[], &manifest, SystemTime::now()).unwrap();
        let real = snapshot_path(&dir, "backend");
        let elsewhere = dir.join("elsewhere.json");
        fs::rename(&real, &elsewhere).unwrap();
        std::os::unix::fs::symlink(&elsewhere, &real).unwrap();
        assert_eq!(
            read_snapshot(&dir, "backend", None, SystemTime::now())
                .unwrap_err()
                .0,
            "insecure"
        );
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_garbled_file_is_malformed_and_a_missing_one_is_missing() {
        use std::os::unix::fs::PermissionsExt;
        let dir = scratch("garbled");
        assert_eq!(
            read_snapshot(&dir, "backend", None, SystemTime::now())
                .unwrap_err()
                .0,
            "missing"
        );
        fs::create_dir_all(&dir).unwrap();
        fs::set_permissions(&dir, fs::Permissions::from_mode(0o700)).unwrap();
        let path = snapshot_path(&dir, "backend");
        fs::write(&path, b"{not json").unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).unwrap();
        assert_eq!(
            read_snapshot(&dir, "backend", None, SystemTime::now())
                .unwrap_err()
                .0,
            "malformed"
        );
        let _ = fs::remove_dir_all(&dir);
    }
}
