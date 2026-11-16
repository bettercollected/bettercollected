#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::print_stderr,
    clippy::too_many_lines
)]
//! `settings.report_state` against a real, migrated database (the admin chain makes
//! schema `settings`). Needs `BC_TEST_DATABASE_URL`, a throw-away database whose name
//! contains "test" and which a superuser URL names (for example
//! `postgresql://postgres:postgres@127.0.0.1:5433/bc_rs60_limits_test` after
//! `uv run --project backend python rust/contract/seed.py migrate`); without it the
//! test says so and passes.
//!
//! The database function trusts `session_user`: the report belongs to the service whose
//! database role (`settings.reader_roles`) logs in. The test makes a login role of its own,
//! maps it to the service `backend` and grants it exactly what `bc_app` holds in production
//! (EXECUTE on both signatures, SELECT on the backend's views), then reports as that role. The last
//! step replaces the two database functions to prove the fallback for an older store, and puts their
//! definitions back afterwards (their grants to other roles are not restored: use a scratch database).

use bc_config::store::pg::PgSource;
use bc_config::store::report::ServiceState;
use bc_config::store::runtime::SnapshotSource;
use sqlx::{Connection, PgConnection, Row};

const ROLE: &str = "bc_rs60_report_test_role";
const SEVEN: &str = "(text, bigint, text[], text[], boolean, text, text)";
const NO_PERMISSION: &str =
    "no permission to report (not a settings reader, or no EXECUTE on settings.report_state)";
const SIX: &str = "(text, bigint, text[], text[], boolean, text)";

fn url_as(url: &str, user: &str, password: &str) -> String {
    let (scheme, rest) = url.split_once("://").unwrap();
    let host = rest.rsplit_once('@').map_or(rest, |(_, h)| h);
    format!("{scheme}://{user}:{password}@{host}")
}

fn state(revision: u64, pending: bool) -> ServiceState {
    ServiceState {
        revision_applied: revision,
        env_overrides: vec!["AUTH_JWT_SECRET".into(), "FIELD_RULES_ENABLED".into()],
        rejected_keys: vec![],
        restart_pending: pending,
        keyset_fp: "ks-0123456789ab".into(),
        write_stores: "postgres".into(),
    }
}

async fn row(admin: &mut PgConnection, instance: &str) -> sqlx::postgres::PgRow {
    sqlx::query(
        "SELECT service, revision_applied, restart_pending, keyset_fp, write_stores, env_overrides \
         FROM settings.service_state WHERE instance = $1",
    )
    .bind(instance)
    .fetch_one(admin)
    .await
    .unwrap()
}

#[tokio::test]
async fn the_report_reaches_the_store_as_the_backend_role_does() {
    let Some(url) = std::env::var("BC_TEST_DATABASE_URL")
        .ok()
        .filter(|u| !u.is_empty())
    else {
        eprintln!("BC_TEST_DATABASE_URL is not set: skipped");
        return;
    };
    assert!(
        url.rsplit('/').next().is_some_and(|n| n.contains("test")),
        "BC_TEST_DATABASE_URL must name a throw-away database with 'test' in its name"
    );
    let mut admin = PgConnection::connect(&url).await.unwrap();
    // a role of the test's own (roles are shared by the whole server)
    for sql in [
        format!("DROP OWNED BY {ROLE}"),
        format!("DROP ROLE IF EXISTS {ROLE}"),
    ] {
        let _ = sqlx::query(&sql).execute(&mut admin).await;
    }
    for sql in [
        format!("CREATE ROLE {ROLE} LOGIN PASSWORD 'pw-of-the-test'"),
        format!("GRANT USAGE ON SCHEMA settings TO {ROLE}"),
        format!("GRANT SELECT ON settings.v_backend, settings.v_backend_manifest TO {ROLE}"),
        format!("GRANT EXECUTE ON FUNCTION settings.report_state{SEVEN} TO {ROLE}"),
        format!("GRANT EXECUTE ON FUNCTION settings.report_state{SIX} TO {ROLE}"),
        format!("UPDATE settings.reader_roles SET role = '{ROLE}' WHERE service = 'backend'"),
        "DELETE FROM settings.service_state WHERE instance LIKE 'backend.edge:test-%'".to_string(),
    ] {
        sqlx::query(&sql).execute(&mut admin).await.unwrap();
    }

    let as_backend = url_as(&url, ROLE, "pw-of-the-test");
    let source = PgSource::new(&as_backend, "backend").unwrap();

    // 1. the seven-argument function
    let instance = "backend.edge:test-one";
    source
        .report_state(instance, &state(9, false))
        .await
        .unwrap();
    let r = row(&mut admin, instance).await;
    assert_eq!(r.get::<String, _>("service"), "backend");
    assert_eq!(r.get::<i64, _>("revision_applied"), 9);
    assert!(!r.get::<bool, _>("restart_pending"));
    assert_eq!(r.get::<String, _>("keyset_fp"), "ks-0123456789ab.r1");
    assert_eq!(r.get::<String, _>("write_stores"), "postgres");
    assert_eq!(
        r.get::<Vec<String>, _>("env_overrides"),
        ["AUTH_JWT_SECRET", "FIELD_RULES_ENABLED"]
    );
    // a second report replaces the row of the instance (one row per instance)
    source
        .report_state(instance, &state(10, true))
        .await
        .unwrap();
    let r = row(&mut admin, instance).await;
    assert_eq!(r.get::<i64, _>("revision_applied"), 10);
    assert!(r.get::<bool, _>("restart_pending"));
    let count: i64 =
        sqlx::query_scalar("SELECT count(*) FROM settings.service_state WHERE instance = $1")
            .bind(instance)
            .fetch_one(&mut admin)
            .await
            .unwrap();
    assert_eq!(count, 1);

    // 2. what the function itself refuses is a failure of the report, with a reason of ours
    let refused = source
        .report_state("not valid!", &state(1, false))
        .await
        .unwrap_err();
    assert_eq!(refused.0, "the store refused the report");

    // 3. a role that is not a settings reader is refused by the function (insufficient_privilege)
    sqlx::query("UPDATE settings.reader_roles SET role = 'someone_else' WHERE service = 'backend'")
        .execute(&mut admin)
        .await
        .unwrap();
    let denied = source
        .report_state("backend.edge:test-two", &state(1, false))
        .await
        .unwrap_err();
    assert_eq!(denied.0, NO_PERMISSION);
    sqlx::query(&format!(
        "UPDATE settings.reader_roles SET role = '{ROLE}' WHERE service = 'backend'"
    ))
    .execute(&mut admin)
    .await
    .unwrap();

    // 4. without EXECUTE, the same reason
    sqlx::query(&format!(
        "REVOKE EXECUTE ON FUNCTION settings.report_state{SEVEN} FROM {ROLE}"
    ))
    .execute(&mut admin)
    .await
    .unwrap();
    let no_grant = source
        .report_state("backend.edge:test-three", &state(1, false))
        .await
        .unwrap_err();
    assert_eq!(no_grant.0, NO_PERMISSION);
    sqlx::query(&format!(
        "GRANT EXECUTE ON FUNCTION settings.report_state{SEVEN} TO {ROLE}"
    ))
    .execute(&mut admin)
    .await
    .unwrap();

    // 5. (the last step: it replaces the functions, and puts the originals back) a store from before the write stores existed (rolling deploy): only the six-argument
    //    function is there, and the report falls back to it
    let originals: Vec<String> = sqlx::query_scalar(
        "SELECT pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace \
         WHERE n.nspname = 'settings' AND p.proname = 'report_state' ORDER BY p.pronargs DESC",
    )
    .fetch_all(&mut admin)
    .await
    .unwrap();
    assert_eq!(
        originals.len(),
        2,
        "the seven- and the six-argument function"
    );
    let mut tx = admin.begin().await.unwrap();
    sqlx::query(&format!("DROP FUNCTION settings.report_state{SIX}"))
        .execute(&mut *tx)
        .await
        .unwrap();
    sqlx::query(&format!("DROP FUNCTION settings.report_state{SEVEN}"))
        .execute(&mut *tx)
        .await
        .unwrap();
    sqlx::query(
        "CREATE FUNCTION settings.report_state(p_instance text, p_revision_applied bigint, \
         p_env_overrides text[], p_rejected_keys text[], p_restart_pending boolean, p_keyset_fp text) \
         RETURNS void LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, settings, pg_temp AS $$ \
         INSERT INTO settings.service_state (service, instance, reported_at, revision_applied, \
             env_overrides, rejected_keys, restart_pending, keyset_fp) \
         VALUES ('backend', p_instance, now(), p_revision_applied, p_env_overrides, p_rejected_keys, \
             p_restart_pending, p_keyset_fp) \
         ON CONFLICT (service, instance) DO UPDATE SET revision_applied = excluded.revision_applied, \
             keyset_fp = excluded.keyset_fp $$",
    )
    .execute(&mut *tx)
    .await
    .unwrap();
    sqlx::query(&format!(
        "GRANT EXECUTE ON FUNCTION settings.report_state{SIX} TO {ROLE}"
    ))
    .execute(&mut *tx)
    .await
    .unwrap();
    tx.commit().await.unwrap();
    source
        .report_state("backend.edge:test-old", &state(4, false))
        .await
        .unwrap();
    let r = row(&mut admin, "backend.edge:test-old").await;
    assert_eq!(r.get::<i64, _>("revision_applied"), 4);
    assert_eq!(r.get::<String, _>("keyset_fp"), "ks-0123456789ab.r1");
    assert_eq!(r.get::<String, _>("write_stores"), "");

    // put the functions back as they were (the seven-argument one first: the other calls it)
    sqlx::query(&format!("DROP FUNCTION settings.report_state{SIX}"))
        .execute(&mut admin)
        .await
        .unwrap();
    for definition in &originals {
        sqlx::query(definition).execute(&mut admin).await.unwrap();
    }
    for signature in [SEVEN, SIX] {
        sqlx::query(&format!(
            "REVOKE ALL ON FUNCTION settings.report_state{signature} FROM PUBLIC"
        ))
        .execute(&mut admin)
        .await
        .unwrap();
    }
    // leave the database as the test found it
    let _ =
        sqlx::query("DELETE FROM settings.service_state WHERE instance LIKE 'backend.edge:test-%'")
            .execute(&mut admin)
            .await;
}
