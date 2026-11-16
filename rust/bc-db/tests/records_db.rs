#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::print_stderr,
    clippy::semicolon_if_nothing_returned
)]
//! The repository against a real, migrated database.
//!
//! Set `BC_TEST_DATABASE_URL` to a throw-away database (its name must contain
//! "test") that the Python backend's Alembic chain migrated, for example
//! `postgresql://postgres:postgres@127.0.0.1:5433/bc_rs60db_test`
//! (`uv run --project backend python rust/contract/golden_records.py migrate`
//! does it). Without it these tests say so and pass: the proofs that need no
//! database are in `records_golden.rs`.
//!
//! What they prove beyond the golden tests: the row Rust writes is the row
//! Python wrote in the database itself (document, checksum, timestamps and the
//! generated spine columns), Rust reads rows inserted as Python wrote them, and
//! the repository's behaviour (keyset pages, locks, tombstones, timeouts).

mod common;

use std::sync::Arc;

use bc_db::records::{Form, FormResponse, Workspace, WorkspaceAuditEvent, WorkspaceUser};
use bc_db::repo::to_ms;
use bc_db::{Db, DbError, DbSettings, Filter, FixedClock, Keyset, Page, Record, connect_with};
use chrono::{Duration, Utc};
use serde_json::{Value, json};
use sqlx::{AssertSqlSafe, PgConnection};

use common::{instant, now, vectors};

struct Env {
    db: Db,
    clock: Arc<FixedClock>,
    url: String,
}

async fn env() -> Option<Env> {
    let Some(url) = std::env::var("BC_TEST_DATABASE_URL")
        .ok()
        .filter(|u| !u.is_empty())
    else {
        eprintln!("BC_TEST_DATABASE_URL is not set: database tests skipped");
        return None;
    };
    assert!(
        url.rsplit('/').next().is_some_and(|n| n.contains("test")),
        "BC_TEST_DATABASE_URL must name a throw-away database with 'test' in its name"
    );
    let pool = connect_with(&url, &DbSettings::new("bc-db-tests"))
        .await
        .expect("connect");
    let clock = Arc::new(FixedClock::new(now(&vectors())));
    Some(Env {
        db: Db::new(pool, clock.clone()),
        clock,
        url,
    })
}

async fn row_json(conn: &mut PgConnection, table: &str, id: &str) -> Value {
    sqlx::query("SET LOCAL TIME ZONE 'UTC'")
        .execute(&mut *conn)
        .await
        .unwrap();
    sqlx::query_scalar(AssertSqlSafe(format!(
        "SELECT to_jsonb(t.*) FROM app.{table} t WHERE id = $1"
    )))
    .bind(id)
    .fetch_one(conn)
    .await
    .unwrap()
}

async fn clear(conn: &mut PgConnection, table: &str, id: &str) {
    sqlx::query(AssertSqlSafe(format!(
        "DELETE FROM app.{table} WHERE id = $1"
    )))
    .bind(id)
    .execute(conn)
    .await
    .unwrap();
}

async fn write_and_compare<T: Record>(env: &Env, table: &str, case: &Value) {
    let name = format!("{table} / {}", case["name"]);
    let mut tx = env.db.pool().begin().await.unwrap();
    let id = case["input"]["_id"].as_str().unwrap();
    clear(&mut tx, table, id).await;
    let mut record: T = serde_json::from_value(case["input"].clone()).unwrap();
    env.db.upsert_in(&mut tx, &mut record).await.unwrap();
    let stored = row_json(&mut tx, table, id).await;
    // the whole row: doc, timestamps, source, checksum and every spine column
    assert_eq!(stored, case["row"], "{name}");
    tx.rollback().await.unwrap();
}

#[tokio::test]
async fn the_row_rust_writes_is_the_row_python_wrote() {
    let Some(env) = env().await else { return };
    let v = vectors();
    for case in v["cases"].as_array().unwrap() {
        let table = case["table"].as_str().unwrap();
        match table {
            "workspaces" => write_and_compare::<Workspace>(&env, table, case).await,
            "workspace_users" => write_and_compare::<WorkspaceUser>(&env, table, case).await,
            "forms" => write_and_compare::<Form>(&env, table, case).await,
            "form_responses" => write_and_compare::<FormResponse>(&env, table, case).await,
            "workspace_audit_events" => {
                write_and_compare::<WorkspaceAuditEvent>(&env, table, case).await
            }
            other => panic!("{other}"),
        }
    }
}

async fn insert_python_row_and_read<T: Record>(env: &Env, table: &str, case: &Value) {
    let name = format!("{table} / {}", case["name"]);
    let row = &case["row"];
    let id = row["id"].as_str().unwrap();
    let mut tx = env.db.pool().begin().await.unwrap();
    clear(&mut tx, table, id).await;
    // the columns exactly as Python stored them
    sqlx::query(AssertSqlSafe(format!(
        "INSERT INTO app.{table} (id, doc, created_at, updated_at, _bc_source, _bc_checksum) VALUES ($1, $2, $3, $4, $5, $6)"
    )))
    .bind(id)
    .bind(&row["doc"])
    .bind(instant(&row["created_at"]))
    .bind(instant(&row["updated_at"]))
    .bind(row["_bc_source"].as_str().unwrap())
    .bind(row["_bc_checksum"].as_str().unwrap())
    .execute(&mut *tx)
    .await
    .unwrap();
    let read: T = env
        .db
        .get_in(&mut tx, id)
        .await
        .unwrap()
        .unwrap_or_else(|| panic!("{name}: not found"));
    assert_eq!(bc_db::codec::encode(&read).unwrap(), row["doc"], "{name}");
    // writing the record back changes nothing the row holds
    let mut again = read;
    env.db.upsert_in(&mut tx, &mut again).await.unwrap();
    // (a table that stores BSON dates keeps milliseconds in `doc`, so the
    // timestamp columns of a rewrite are those milliseconds, as in Python)
    let mut rewritten = row_json(&mut tx, table, id).await;
    let mut expected = row.clone();
    for key in ["created_at", "updated_at"] {
        let cut = |v: &Value| json!(to_ms(instant(v)).to_rfc3339());
        rewritten[key] = cut(&rewritten[key]);
        expected[key] = cut(&expected[key]);
    }
    assert_eq!(rewritten, expected, "{name}: rewritten row");
    tx.rollback().await.unwrap();
}

#[tokio::test]
async fn rust_reads_the_rows_python_wrote_from_the_database() {
    let Some(env) = env().await else { return };
    let v = vectors();
    for case in v["cases"].as_array().unwrap() {
        let table = case["table"].as_str().unwrap();
        match table {
            "workspaces" => insert_python_row_and_read::<Workspace>(&env, table, case).await,
            "workspace_users" => {
                insert_python_row_and_read::<WorkspaceUser>(&env, table, case).await
            }
            "forms" => insert_python_row_and_read::<Form>(&env, table, case).await,
            "form_responses" => insert_python_row_and_read::<FormResponse>(&env, table, case).await,
            "workspace_audit_events" => {
                insert_python_row_and_read::<WorkspaceAuditEvent>(&env, table, case).await
            }
            other => panic!("{other}"),
        }
    }
}

fn member(id: &str, user: &str, at: &str) -> WorkspaceUser {
    member_of("6b0000000000000000000001", id, user, at)
}

fn member_of(workspace: &str, id: &str, user: &str, at: &str) -> WorkspaceUser {
    serde_json::from_value(json!({
        "_id": id, "workspace_id": workspace, "user_id": user,
        "roles": ["ADMIN"], "created_at": at, "updated_at": at
    }))
    .unwrap()
}

#[tokio::test]
async fn pages_run_on_a_keyset_in_insertion_order() {
    let Some(env) = env().await else { return };
    let mut tx = env.db.pool().begin().await.unwrap();
    // two members share a created_at: the id breaks the tie
    let times = [
        "2026-01-01T00:00:01+00:00",
        "2026-01-01T00:00:02+00:00",
        "2026-01-01T00:00:02+00:00",
        "2026-01-01T00:00:03+00:00",
        "2026-01-01T00:00:04+00:00",
    ];
    for (i, at) in times.iter().enumerate() {
        let mut m = member_of(
            "6c0000000000000000000001",
            &format!("6c00000000000000000b{i:04}"),
            &format!("6c0000000000000000{i:06}"),
            at,
        );
        env.db.upsert_in(&mut tx, &mut m).await.unwrap();
    }
    let ws = Filter::new().eq("workspace_id", "6c0000000000000000000001");
    assert_eq!(
        env.db
            .count_in::<WorkspaceUser>(&mut tx, &ws)
            .await
            .unwrap(),
        5
    );

    let first: Vec<WorkspaceUser> = env.db.list_in(&mut tx, &ws, &Page::first(2)).await.unwrap();
    assert_eq!(first.len(), 2);
    let mut seen: Vec<String> = first.iter().map(|m| m.id().unwrap().to_string()).collect();
    let mut after = Keyset::of(first.last().unwrap()).unwrap();
    loop {
        let page: Vec<WorkspaceUser> = env
            .db
            .list_in(&mut tx, &ws, &Page::first(2).after(after.clone()))
            .await
            .unwrap();
        let Some(last) = page.last() else { break };
        after = Keyset::of(last).unwrap();
        seen.extend(page.iter().map(|m| m.id().unwrap().to_string()));
    }
    let want: Vec<String> = (0..5)
        .map(|i| format!("6c00000000000000000b{i:04}"))
        .collect();
    assert_eq!(seen, want, "no row twice, none missed, ties by id");

    let newest: Vec<WorkspaceUser> = env
        .db
        .list_in(&mut tx, &ws, &Page::newest_first(2))
        .await
        .unwrap();
    assert_eq!(newest[0].id().unwrap().to_string(), want[4]);
    let older: Vec<WorkspaceUser> = env
        .db
        .list_in(
            &mut tx,
            &ws,
            &Page::newest_first(10).after(Keyset::of(&newest[1]).unwrap()),
        )
        .await
        .unwrap();
    assert_eq!(
        older
            .iter()
            .map(|m| m.id().unwrap().to_string())
            .collect::<Vec<_>>(),
        want[..3].iter().rev().cloned().collect::<Vec<_>>()
    );

    let one: Option<WorkspaceUser> = env
        .db
        .find_in(
            &mut tx,
            &ws.clone().eq("user_id", "6c0000000000000000000002"),
            false,
        )
        .await
        .unwrap();
    assert_eq!(one.unwrap().id().unwrap().to_string(), want[2]);
    let any: Vec<WorkspaceUser> = env
        .db
        .list_in(
            &mut tx,
            &Filter::new().any_of(
                "user_id",
                vec![
                    "6c0000000000000000000001".into(),
                    "6c0000000000000000000003".into(),
                ],
            ),
            &Page::default(),
        )
        .await
        .unwrap();
    assert_eq!(any.len(), 2);
    tx.rollback().await.unwrap();
}

#[tokio::test]
async fn set_fields_update_and_save_follow_the_python_rules() {
    let Some(env) = env().await else { return };
    let v = vectors();
    let form_case = v["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|c| c["table"] == "forms" && c["name"] == "full")
        .unwrap();
    let id = form_case["input"]["_id"].as_str().unwrap();
    let mut tx = env.db.pool().begin().await.unwrap();
    clear(&mut tx, "forms", id).await;
    let mut form: Form = serde_json::from_value(form_case["input"].clone()).unwrap();
    env.db.upsert_in(&mut tx, &mut form).await.unwrap();

    // set_fields: a dotted path, the row locked, updated_at left alone, the checksum follows
    env.clock.advance(Duration::minutes(5));
    let changed = env
        .db
        .set_fields_in::<Form>(
            &mut tx,
            id,
            &[
                ("settings.custom_url", json!("renamed")),
                ("title", json!("New")),
            ],
        )
        .await
        .unwrap()
        .unwrap();
    assert_eq!(changed.title.as_deref(), Some("New"));
    let row = row_json(&mut tx, "forms", id).await;
    assert_eq!(
        row["custom_url"], "renamed",
        "the generated column follows doc"
    );
    assert_eq!(row["title"], "New");
    assert_eq!(
        row["updated_at"], form_case["row"]["updated_at"],
        "set_fields does not touch updated_at"
    );
    assert_eq!(
        row["_bc_checksum"],
        json!(bc_db::canonical::checksum(&row["doc"]).unwrap())
    );
    assert!(
        env.db
            .set_fields_in::<Form>(
                &mut tx,
                "6a00000000000000000fffff",
                &[("title", json!("x"))]
            )
            .await
            .unwrap()
            .is_none()
    );

    // update: the closure sees the stored record
    let (stored, seen) = env
        .db
        .update_in::<Form, _>(&mut tx, id, |f| {
            let seen = f.title.clone();
            f.title = Some("Again".into());
            Ok(seen)
        })
        .await
        .unwrap()
        .unwrap();
    assert_eq!(seen.as_deref(), Some("New"));
    assert_eq!(stored.title.as_deref(), Some("Again"));

    // save moves updated_at to the clock
    let mut again: Form = env.db.get_in(&mut tx, id).await.unwrap().unwrap();
    env.db.save_in(&mut tx, &mut again).await.unwrap();
    let row = row_json(&mut tx, "forms", id).await;
    assert_eq!(instant(&row["updated_at"]), env.clock.now_utc());
    assert_eq!(
        row["created_at"], form_case["row"]["created_at"],
        "created_at never moves"
    );
    tx.rollback().await.unwrap();
}

#[tokio::test]
async fn a_delete_leaves_a_tombstone_in_the_same_transaction() {
    let Some(env) = env().await else { return };
    let mut tx = env.db.pool().begin().await.unwrap();
    let mut m = member(
        "6b00000000000000000c0001",
        "6b0000000000000000000009",
        "2026-01-01T00:00:01+00:00",
    );
    env.db.upsert_in(&mut tx, &mut m).await.unwrap();
    env.clock.set(now(&vectors()) + Duration::microseconds(789));
    assert_eq!(
        env.db
            .delete_by_id_in::<WorkspaceUser>(&mut tx, "6b00000000000000000c0001")
            .await
            .unwrap(),
        1
    );
    assert!(
        env.db
            .get_in::<WorkspaceUser>(&mut tx, "6b00000000000000000c0001")
            .await
            .unwrap()
            .is_none()
    );
    let (collection, at): (String, chrono::DateTime<Utc>) = sqlx::query_as(
        "SELECT collection, deleted_at FROM app.deletion_tombstones WHERE row_id = $1",
    )
    .bind("6b00000000000000000c0001")
    .fetch_one(&mut *tx)
    .await
    .unwrap();
    assert_eq!(collection, "workspace_users");
    assert_eq!(
        at,
        to_ms(env.clock.now_utc()),
        "milliseconds, as Python records them"
    );
    assert_eq!(
        env.db
            .delete_by_id_in::<WorkspaceUser>(&mut tx, "6b00000000000000000c0001")
            .await
            .unwrap(),
        0
    );
    tx.rollback().await.unwrap();
    env.clock.set(now(&vectors()));
}

#[tokio::test]
async fn a_second_writer_waits_for_the_lock_and_then_reports_busy() {
    let Some(env) = env().await else { return };
    let id = "6b00000000000000000d0001";
    let mut m = member(id, "6b0000000000000000000010", "2026-01-01T00:00:01+00:00");
    env.db.upsert(&mut m).await.unwrap();

    let mut holder = env.db.pool().begin().await.unwrap();
    assert!(
        env.db
            .get_locked_in::<WorkspaceUser>(&mut holder, id)
            .await
            .unwrap()
            .is_some()
    );

    let mut waiter = env.db.pool().begin().await.unwrap();
    env.db
        .set_local_lock_timeout_in(&mut waiter, 150)
        .await
        .unwrap();
    let outcome = env.db.get_locked_in::<WorkspaceUser>(&mut waiter, id).await;
    assert!(matches!(outcome, Err(DbError::Busy)), "{outcome:?}");
    drop(waiter);

    holder.rollback().await.unwrap();
    // advisory locks: held to the end of the transaction, named by parts
    let mut a = env.db.pool().begin().await.unwrap();
    env.db
        .advisory_lock_in(&mut a, &["response-limit", "ws", "form"])
        .await
        .unwrap();
    let mut b = env.db.pool().begin().await.unwrap();
    env.db.set_local_lock_timeout_in(&mut b, 150).await.unwrap();
    let blocked = env
        .db
        .advisory_lock_in(&mut b, &["response-limit", "ws", "form"])
        .await;
    assert!(matches!(blocked, Err(DbError::Busy)), "{blocked:?}");
    drop(b);
    let mut c = env.db.pool().begin().await.unwrap();
    env.db
        .advisory_lock_in(&mut c, &["response-limit", "ws", "other"])
        .await
        .unwrap();
    env.db
        .advisory_lock_text_in(&mut c, "form_imports:ws")
        .await
        .unwrap();
    a.rollback().await.unwrap();
    c.rollback().await.unwrap();

    env.db.delete_by_id::<WorkspaceUser>(id).await.unwrap();
}

#[tokio::test]
async fn a_duplicate_is_a_conflict_and_the_python_timeouts_apply() {
    let Some(env) = env().await else { return };
    let mut tx = env.db.pool().begin().await.unwrap();
    let mut a = member(
        "6b00000000000000000e0001",
        "6b0000000000000000000020",
        "2026-01-01T00:00:01+00:00",
    );
    env.db.insert_in(&mut tx, &mut a).await.unwrap();
    // the same membership under another id: the unique index (workspace_id, user_id)
    let mut b = member(
        "6b00000000000000000e0002",
        "6b0000000000000000000020",
        "2026-01-01T00:00:02+00:00",
    );
    let outcome = env.db.insert_in(&mut tx, &mut b).await;
    assert!(matches!(outcome, Err(DbError::Conflict)), "{outcome:?}");
    drop(tx);

    // every connection carries the Python engine's timeouts
    let mut conn = env.db.pool().acquire().await.unwrap();
    for (name, want) in [
        ("statement_timeout", "30s"),
        ("lock_timeout", "5s"),
        ("idle_in_transaction_session_timeout", "1min"),
    ] {
        let got: String = sqlx::query_scalar(AssertSqlSafe(format!("SHOW {name}")))
            .fetch_one(&mut *conn)
            .await
            .unwrap();
        assert_eq!(got, want, "{name}");
    }
    drop(conn);
    let mut quick = DbSettings::new("bc-db-tests");
    quick.statement_timeout_ms = 200;
    let pool = connect_with(&env.url, &quick).await.unwrap();
    let slept = sqlx::query("SELECT pg_sleep(2)")
        .execute(&pool)
        .await
        .map(|_| ())
        .map_err(DbError::from);
    assert!(matches!(slept, Err(DbError::Timeout)), "{slept:?}");
}
