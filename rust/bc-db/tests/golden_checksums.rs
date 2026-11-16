#![allow(clippy::unwrap_used, clippy::expect_used)]
//! The canonical bytes and the checksum, against the Python backend's own
//! pinned vectors: for every document class mirrored to Postgres, the `doc` the
//! Python codec writes and its `_bc_checksum` (`backend/tests/fixtures/
//! codec_golden/backend.json`, 180 cases: full, minimal, nulls and naive
//! variants; unicode, control characters, floats, integers past 2^53,
//! binaries, decimals). The checksum is recomputed here from the `doc` and
//! must be the pinned one, byte for byte.

use std::path::PathBuf;

use bc_db::canonical::{canonical_json, checksum};
use serde_json::Value;

fn golden() -> serde_json::Map<String, Value> {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../backend/tests/fixtures/codec_golden/backend.json");
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("cannot read the golden file {}: {e}", path.display()));
    match serde_json::from_str(&text).expect("the golden file is JSON") {
        Value::Object(map) => map,
        _ => panic!("the golden file is an object"),
    }
}

#[test]
fn every_pinned_checksum_is_reproduced() {
    let cases = golden();
    assert!(cases.len() >= 150, "the golden file went missing or shrank");
    let mut wrong = Vec::new();
    for (name, case) in &cases {
        let want = case["checksum"].as_str().expect("a checksum");
        let got = checksum(&case["doc"]).expect("a canonical form");
        if got != want {
            wrong.push(name.clone());
        }
    }
    assert!(wrong.is_empty(), "checksums differ for: {wrong:?}");
}

#[test]
fn the_canonical_text_survives_a_parse() {
    // text -> value -> text is stable: no float or key moves
    for (name, case) in &golden() {
        let text = canonical_json(&case["doc"]).expect("a canonical form");
        let again: Value = serde_json::from_str(&text).expect("canonical JSON parses");
        assert_eq!(canonical_json(&again).unwrap(), text, "{name}");
    }
}
