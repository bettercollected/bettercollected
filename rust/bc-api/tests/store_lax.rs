#![allow(clippy::unwrap_used, clippy::expect_used, clippy::print_stderr)]
//! The membership and workspace reads of the permissions group, against stored
//! documents spelled the way the Python models accept them. Needs
//! `BC_TEST_DATABASE_URL` (a migrated throw-away database, see
//! `bc-db/tests/records_db.rs`); without it the test says so and passes.

use bc_api::store::workspaces::{StoreError, find_by_id, find_membership};
use serde_json::{Value, json};
use sqlx::{AssertSqlSafe, PgPool};

const USER: &str = "6d0000000000000000000002";

async fn put(pool: &PgPool, table: &str, id: &str, doc: &Value) {
    sqlx::query(AssertSqlSafe(format!(
        "DELETE FROM app.{table} WHERE id = $1"
    )))
    .bind(id)
    .execute(pool)
    .await
    .unwrap();
    sqlx::query(AssertSqlSafe(format!(
        "INSERT INTO app.{table} (id, doc, created_at, updated_at, _bc_source, _bc_checksum) \
         VALUES ($1, $2, now(), now(), 'app', 'sha256:test')"
    )))
    .bind(id)
    .bind(doc)
    .execute(pool)
    .await
    .unwrap();
}

fn workspace(id: &str, name: &str, extra: &Value) -> Value {
    let mut doc = json!({
        "_id": {"$oid": id}, "workspace_name": name, "owner_id": USER,
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"
    });
    for (k, v) in extra.as_object().unwrap() {
        doc[k] = v.clone();
    }
    doc
}

#[tokio::test]
async fn policy_flags_are_read_as_pydantic_reads_them() {
    let Some(url) = std::env::var("BC_TEST_DATABASE_URL")
        .ok()
        .filter(|u| !u.is_empty())
    else {
        eprintln!("BC_TEST_DATABASE_URL is not set: skipped");
        return;
    };
    let pool = bc_db::connect(&url, 2).await.unwrap();

    let on = [
        json!("true"),
        json!("Yes"),
        json!("on"),
        json!("1"),
        json!(1),
        json!(1.0),
    ];
    let off = [
        json!("false"),
        json!("0"),
        json!(0),
        json!(0.0),
        json!(null),
    ];
    for (n, flag) in ["disabled", "sso_required", "require_totp"]
        .into_iter()
        .enumerate()
    {
        for (i, value) in on.iter().chain(off.iter()).enumerate() {
            let id = format!("6d00000000000000{n:02}{i:04}00");
            let doc = workspace(&id, &format!("lax-{flag}-{i}"), &json!({ flag: value }));
            put(&pool, "workspaces", &id, &doc).await;
            let facts = find_by_id(&pool, &id).await.unwrap().unwrap();
            let got = match flag {
                "disabled" => facts.disabled,
                "sso_required" => facts.sso_required,
                _ => facts.require_totp,
            };
            assert_eq!(got, i < on.len(), "{flag} = {value}");
        }
        // a value pydantic refuses: not read as "off" but handed to Python
        for (i, value) in [json!("maybe"), json!(2), json!("")].iter().enumerate() {
            let id = format!("6d00000000000000{n:02}{:04}ff", i + 100);
            put(
                &pool,
                "workspaces",
                &id,
                &workspace(&id, &format!("bad-{flag}-{i}"), &json!({ flag: value })),
            )
            .await;
            assert!(
                matches!(find_by_id(&pool, &id).await, Err(StoreError::Unreadable)),
                "{flag} = {value}"
            );
        }
    }

    // the membership
    for (i, value) in on.iter().chain(off.iter()).enumerate() {
        if value.is_null() {
            continue; // a plain bool: null is refused (below)
        }
        let id = format!("6d00000000000000aa{i:04}00");
        let workspace_id = format!("6d00000000000000bb{i:04}00");
        let doc = json!({"_id": {"$oid": id}, "workspace_id": {"$oid": workspace_id}, "user_id": {"$oid": USER},
            "roles": ["ADMIN"], "disabled": value,
            "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"});
        put(&pool, "workspace_users", &id, &doc).await;
        let member = find_membership(&pool, &workspace_id, USER)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(member.disabled, i < on.len(), "disabled = {value}");
        assert_eq!(member.roles, vec![json!("ADMIN")]);
    }
    for (i, value) in [json!(null), json!("maybe"), json!(2)].iter().enumerate() {
        let id = format!("6d00000000000000cc{i:04}00");
        let workspace_id = format!("6d00000000000000dd{i:04}00");
        let doc = json!({"_id": {"$oid": id}, "workspace_id": {"$oid": workspace_id}, "user_id": {"$oid": USER},
            "disabled": value, "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"});
        put(&pool, "workspace_users", &id, &doc).await;
        assert!(
            matches!(
                find_membership(&pool, &workspace_id, USER).await,
                Err(StoreError::Unreadable)
            ),
            "disabled = {value}"
        );
    }
}
