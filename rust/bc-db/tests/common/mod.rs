#![allow(dead_code, clippy::unwrap_used, clippy::expect_used)]
//! The Python-written vectors (`golden/records.json`, from
//! `rust/contract/golden_records.py`) and a dispatch from a table name to its
//! record type.

use bc_db::Record;
use bc_db::codec::{self, RowValues};
use bc_db::stamp::Stamp;
use chrono::{DateTime, Utc};
use serde_json::Value;

pub fn vectors() -> Value {
    serde_json::from_str(include_str!("../golden/records.json")).expect("golden/records.json")
}

pub fn now(v: &Value) -> DateTime<Utc> {
    Stamp::from_value(&v["now"]).expect("now").to_utc()
}

pub fn instant(v: &Value) -> DateTime<Utc> {
    Stamp::from_value(v).expect("a timestamp").to_utc()
}

/// Calls `$body::<T>` with the record type of `$table`.
#[macro_export]
macro_rules! with_record {
    ($table:expr, $f:ident ( $($arg:expr),* )) => {
        match $table {
            "workspaces" => $f::<Workspace>($($arg),*),
            "workspace_users" => $f::<WorkspaceUser>($($arg),*),
            "forms" => $f::<Form>($($arg),*),
            "form_responses" => $f::<FormResponse>($($arg),*),
            "workspace_audit_events" => $f::<WorkspaceAuditEvent>($($arg),*),
            other => panic!("no record type for {other}"),
        }
    };
}

/// The row Rust writes for `input`, with the clock at `now`.
pub fn rust_row<T: Record>(input: &Value, now: DateTime<Utc>) -> RowValues {
    let mut record: T =
        serde_json::from_value(input.clone()).expect("the input reads as the record");
    codec::row_values(&mut record, now).expect("a row")
}
