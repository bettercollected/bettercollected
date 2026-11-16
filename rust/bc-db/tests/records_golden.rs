#![allow(clippy::unwrap_used, clippy::expect_used)]
//! Rust against the rows and documents the Python backend writes: no database.
//!
//! * a record written by Rust has the document, checksum and timestamp columns
//!   Python wrote for the same input, byte for byte once canonicalised;
//! * Rust reads every document Python wrote, and writes it back unchanged;
//! * Rust reads the stored documents Python reads (old, lax, unknown keys) and
//!   writes back what Python writes back, and refuses what Python refuses;
//! * the ids and lock keys Python derives.

mod common;

use bc_db::canonical::{canonical_json, checksum};
use bc_db::codec::{decode, encode};
use bc_db::records::{Form, FormResponse, Workspace, WorkspaceAuditEvent, WorkspaceUser};
use bc_db::repo::{advisory_key, to_ms};
use bc_db::{Record, RecordId};
use chrono::{DateTime, Utc};
use serde_json::Value;

use common::{instant, now, rust_row, vectors};

fn check_written<T: Record>(name: &str, input: &Value, row: &Value, now: DateTime<Utc>) {
    let written = rust_row::<T>(input, now);
    assert_eq!(written.doc, row["doc"], "{name}: doc");
    assert_eq!(
        canonical_json(&written.doc).unwrap(),
        canonical_json(&row["doc"]).unwrap(),
        "{name}: canonical bytes"
    );
    assert_eq!(written.checksum, row["_bc_checksum"], "{name}: checksum");
    assert_eq!(written.source, row["_bc_source"], "{name}: source");
    assert_eq!(written.id, row["id"], "{name}: id");
    assert_eq!(
        written.created_at,
        instant(&row["created_at"]),
        "{name}: created_at"
    );
    assert_eq!(
        written.updated_at,
        instant(&row["updated_at"]),
        "{name}: updated_at"
    );
}

#[test]
fn a_record_written_by_rust_is_the_one_python_wrote() {
    let v = vectors();
    let now = now(&v);
    let cases = v["cases"].as_array().unwrap();
    assert!(cases.len() >= 10);
    for case in cases {
        let name = format!("{} / {}", case["table"], case["name"]);
        let table = case["table"].as_str().unwrap();
        with_record!(
            table,
            check_written(&name, &case["input"], &case["row"], now)
        );
    }
}

fn check_read<T: Record>(name: &str, input: &Value, row: &Value, now: DateTime<Utc>) {
    let read: T = decode(row["doc"].clone(), now).unwrap_or_else(|e| panic!("{name}: {e}"));
    // a record without timestamps is stamped on read, as Python stamps it
    let from_input: T = decode(input.clone(), now).unwrap();
    // (a BSON date keeps milliseconds, so compare what each writes, not the structs)
    assert_eq!(
        encode(&read).unwrap(),
        encode(&from_input).unwrap(),
        "{name}: the stored document reads as the input"
    );
    assert_eq!(
        encode(&read).unwrap(),
        row["doc"],
        "{name}: written back unchanged"
    );
    assert_eq!(
        checksum(&encode(&read).unwrap()).unwrap(),
        row["_bc_checksum"],
        "{name}: checksum"
    );
    assert_eq!(read.id().unwrap().to_string(), row["id"].as_str().unwrap());
    // the column keeps microseconds a BSON date in `doc` does not
    assert_eq!(
        read.created_at().map(to_ms),
        Some(to_ms(instant(&row["created_at"]))),
        "{name}"
    );
}

#[test]
fn rust_reads_every_row_python_wrote() {
    let v = vectors();
    let now = now(&v);
    for case in v["cases"].as_array().unwrap() {
        let name = format!("{} / {}", case["table"], case["name"]);
        let table = case["table"].as_str().unwrap();
        with_record!(table, check_read(&name, &case["input"], &case["row"], now));
    }
}

fn check_stored<T: Record>(entry: &Value, now: DateTime<Utc>) {
    let name = format!("{} / {}", entry["table"], entry["name"]);
    let result = decode::<T>(entry["stored"].clone(), now);
    if let Some(why) = entry.get("refused") {
        assert!(
            result.is_err(),
            "{name}: Python refuses this ({why}); Rust read it"
        );
    } else {
        let read =
            result.unwrap_or_else(|e| panic!("{name}: Python reads this, Rust did not: {e}"));
        assert_eq!(
            encode(&read).unwrap(),
            entry["rewritten"],
            "{name}: what is written back"
        );
    }
}

#[test]
fn rust_is_tolerant_exactly_where_python_is() {
    let v = vectors();
    let now = now(&v);
    let cases = v["read_cases"].as_array().unwrap();
    assert!(cases.iter().any(|c| c.get("refused").is_some()));
    assert!(cases.iter().any(|c| c.get("rewritten").is_some()));
    for entry in cases {
        with_record!(entry["table"].as_str().unwrap(), check_stored(entry, now));
    }
}

fn keys_of<T: Record>(sample: &Value, now: DateTime<Utc>) -> Vec<String> {
    let read: T = decode(sample.clone(), now).unwrap();
    let mut keys: Vec<String> = encode(&read)
        .unwrap()
        .as_object()
        .unwrap()
        .keys()
        .cloned()
        .collect();
    keys.sort();
    keys
}

#[test]
fn a_record_has_exactly_the_keys_of_its_python_model() {
    let v = vectors();
    let now = now(&v);
    for (table, want) in v["python_model_keys"].as_object().unwrap() {
        let sample = v["cases"]
            .as_array()
            .unwrap()
            .iter()
            .find(|c| c["table"] == table.as_str())
            .unwrap();
        let want: Vec<String> = want
            .as_array()
            .unwrap()
            .iter()
            .map(|k| k.as_str().unwrap().to_string())
            .collect();
        let got = with_record!(table.as_str(), keys_of(&sample["row"]["doc"], now));
        assert_eq!(got, want, "{table}");
    }
}

#[test]
fn derived_ids_and_lock_keys_are_pythons() {
    let v = vectors();
    for case in v["derived_ids"].as_array().unwrap() {
        let parts: Vec<&str> = case["parts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| p.as_str().unwrap())
            .collect();
        assert_eq!(
            RecordId::derived(&parts).to_string(),
            case["id"].as_str().unwrap(),
            "{parts:?}"
        );
    }
    for case in v["advisory_keys"].as_array().unwrap() {
        let parts: Vec<&str> = case["parts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| p.as_str().unwrap())
            .collect();
        assert_eq!(
            advisory_key(&parts),
            case["key"].as_i64().unwrap(),
            "{parts:?}"
        );
    }
}
