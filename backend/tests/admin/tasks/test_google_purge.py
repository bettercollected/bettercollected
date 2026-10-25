"""``google.purge_unencrypted_credentials`` end to end, through the real runner.

The runner's database is the admin test server's (``world``); the Google
credentials table is created there as the Google service's role and the roles
script runs again, exactly as on a deploy, so the Postgres side runs as the
runner's real data role (``bc_tasks_data_google``: no DELETE) and deletes only
through the definer function. Mongo is the test Mongo (its own database).

The tests prove: a dry run counts and deletes nothing; the apply deletes exactly
the runbook's rows in each store, Mongo first, and leaves an encrypted row with
a user id alone; a second run deletes nothing; results, events and audit rows
hold counts only; and the definer role can delete nothing else while the data
role still cannot delete at all.
"""

from __future__ import annotations

import json
import os

import pytest
import pytest_asyncio
from bson import Binary, ObjectId
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.admin.tasks import catalog
from backend.admin.tasks.catalog import google_purge as meta
from backend.admin.tasks.impl import google_purge as impl
from backend.admin.tasks.registry import check_meta
from common.db.ddl import helper_function_ddl
from tests.admin.conftest import needs_postgres, roles_sql
from tests.admin.engines import fixture_engine
from tests.app.db.test_auto_migrate import _execute
from tests.conftest import TEST_MONGO_DB, TEST_MONGO_URI

pytestmark = needs_postgres

TASK = meta.META.name
COLLECTION = "Oauth2CredentialDocument"
GOOGLE_MONGO_DB = f"{TEST_MONGO_DB}_gpurge"[:60]
SECRET = "plain-refresh-token-0123"
EMAIL = "owner@example.org"
CIPHER = {"$binary": {"base64": "AAEC", "subType": "00"}}


def _hex(n: int) -> str:
    return f"{n:024x}"


# id -> doc; what the purge must delete in Postgres, and what it keeps
PG_DELETE = {
    _hex(1): {"email": EMAIL, "credentials": CIPHER},  # no user id
    _hex(2): {"user_id": "", "email": EMAIL, "credentials": CIPHER},  # empty user id
    _hex(3): {"user_id": None, "email": EMAIL, "credentials": CIPHER},  # null user id
    _hex(4): {"user_id": "u2", "email": EMAIL, "credentials": {"token": SECRET}},  # readable
    _hex(5): {"user_id": "u3", "email": EMAIL, "credentials": {"refresh_token": SECRET}},
}
PG_KEEP = {
    _hex(10): {"user_id": "u1", "email": EMAIL, "credentials": CIPHER},  # encrypted, user id
    _hex(11): {"user_id": "u4", "email": EMAIL},  # no stored credential at all
}


def _mongo_documents():
    keep = [
        {"_id": ObjectId(_hex(20)), "user_id": "u1", "email": EMAIL,
         "credentials": Binary(b"\x00\x01ciphertext")},
        {"_id": ObjectId(_hex(21)), "user_id": "u5", "email": EMAIL},
    ]
    delete = [
        {"_id": ObjectId(_hex(30)), "email": EMAIL, "credentials": Binary(b"x")},  # missing
        {"_id": ObjectId(_hex(31)), "user_id": None, "email": EMAIL, "credentials": Binary(b"x")},
        {"_id": ObjectId(_hex(32)), "user_id": "", "email": EMAIL, "credentials": Binary(b"x")},
        {"_id": ObjectId(_hex(33)), "user_id": "u2", "email": EMAIL,
         "credentials": {"token": SECRET}},
        {"_id": ObjectId(_hex(34)), "user_id": "u3", "email": EMAIL,
         "credentials": {"refresh_token": SECRET, "client_id": "c"}},
    ]
    return keep, delete


# ---------------------------------------------------------------- fixtures
@pytest_asyncio.fixture(loop_scope="session")
async def superuser(server, migrated):
    engine = fixture_engine(server.url(migrated))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def google_table(server, migrated):
    """google.oauth_credentials as the Google service's role owns it, then the
    roles script again (as deploy.sh runs it after the migrations)."""
    google = server.reader_role("google")
    await _execute(
        server.url(migrated),
        # the spine helper and columns as the integration's migration 0001 makes
        # them (common/db/ddl.py; googleform/db/models.py OAuthCredentialRow)
        helper_function_ddl("google")[0] + ";"
        f'ALTER FUNCTION google.bc_text(jsonb) OWNER TO "{google}";'
        "CREATE TABLE google.oauth_credentials (id text PRIMARY KEY, "
        "doc jsonb NOT NULL, _bc_checksum text NOT NULL, "
        "user_id text GENERATED ALWAYS AS (google.bc_text(doc -> 'user_id')) STORED, "
        "email text GENERATED ALWAYS AS (google.bc_text(doc -> 'email')) STORED, "
        "created_at timestamptz);"
        f'ALTER TABLE google.oauth_credentials OWNER TO "{server.reader_role("google")}";'
        # another table of the same owner: the definer role must not reach it
        "CREATE TABLE google.other_rows (id text PRIMARY KEY);"
        f'ALTER TABLE google.other_rows OWNER TO "{server.reader_role("google")}";'
        "INSERT INTO google.other_rows VALUES ('a');",
    )
    await _execute(
        server.url(migrated),
        roles_sql(
            server.suffix,
            server.admin_pw,
            server.mig_pw,
            server.tasks_pw,
            server.data_app_pw,
            server.data_google_pw,
        ),
    )
    return migrated


@pytest.fixture
def pg_env(server, google_table, monkeypatch):
    """Postgres alone: the runner's Google data role; no Mongo configured."""
    monkeypatch.setenv("GOOGLE_DATABASE_URL", server.url(google_table, "data_google"))
    monkeypatch.delenv("MONGO_URI", raising=False)
    for name in list(os.environ):
        if name.upper().startswith("DB_WRITE_MODE"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("DB_WRITE_MODE", "postgres")


@pytest_asyncio.fixture(loop_scope="session")
async def mongo(pg_env, monkeypatch):
    """Both stores: Mongo (its own database) next to Postgres."""
    from pymongo import AsyncMongoClient

    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("GOOGLE_MONGO_DB", GOOGLE_MONGO_DB)
    monkeypatch.setenv("DB_WRITE_MODE", "dual")
    client = AsyncMongoClient(TEST_MONGO_URI, serverSelectionTimeoutMS=5000)
    await client.drop_database(GOOGLE_MONGO_DB)
    yield client[GOOGLE_MONGO_DB][COLLECTION]
    await client.drop_database(GOOGLE_MONGO_DB)
    await client.close()


async def _seed_postgres(superuser, rows=None):
    rows = {**PG_DELETE, **PG_KEEP} if rows is None else rows
    async with superuser.begin() as conn:
        await conn.execute(text("DELETE FROM google.oauth_credentials"))
        for row_id, doc in rows.items():
            await conn.execute(
                text(
                    "INSERT INTO google.oauth_credentials (id, doc, _bc_checksum) "
                    "VALUES (:i, CAST(:d AS jsonb), 'c')"
                ),
                {"i": row_id, "d": json.dumps(doc)},
            )


async def _pg_ids(superuser) -> set:
    async with superuser.connect() as conn:
        return set((await conn.execute(text("SELECT id FROM google.oauth_credentials"))).scalars())


async def _mongo_ids(collection) -> set:
    return {str(d["_id"]) async for d in collection.find({}, {"_id": 1})}


async def _run(world, params=None, *, dry_run=False):
    world.clock.advance(1)
    run_id = await world.enqueue(
        TASK, params or {}, dry_run=dry_run, requested_at=world.clock.now()
    )
    await world.drain()
    return run_id, await world.run(run_id)


async def _both(world, params=None):
    _, dry = await _run(world, params, dry_run=True)
    assert dry["state"] == "succeeded", dry
    return await _run(world, params)


def _no_personal_data(*things):
    dumped = json.dumps(things, default=str)
    for needle in (SECRET, EMAIL, "u1", "u2", "u3", "u4", "u5", "ciphertext", *PG_DELETE, *PG_KEEP):
        assert needle not in dumped, needle
    for n in (20, 21, 30, 31, 32, 33, 34):
        assert _hex(n) not in dumped


# ----------------------------------------------------------------- catalog
def test_the_task_is_in_the_catalog_and_needs_a_dry_run_and_a_confirmation():
    check_meta(meta.META)
    assert meta.META in catalog.all_meta({})
    assert meta.META.mutating and meta.META.requires_prior_dry_run and meta.META.idempotent
    assert meta.PurgeParams().stores.value == "auto"
    # the filters are the runbook's, word for word
    assert impl.MONGO_FILTER == {
        "$or": [
            {"user_id": {"$in": [None, ""]}},
            {"credentials.token": {"$exists": True}},
            {"credentials.refresh_token": {"$exists": True}},
        ]
    }
    assert impl._ordered(["postgres", "mongo"]) == ["mongo", "postgres"]


# --------------------------------------------------------------- Postgres
async def test_postgres_dry_run_counts_and_deletes_nothing(world, pg_env, superuser):
    await _seed_postgres(superuser)
    before = await _pg_ids(superuser)
    run_id, run = await _run(world, dry_run=True)
    assert run["state"] == "succeeded", run
    assert run["result"]["postgres"] == {"matched": len(PG_DELETE), "deleted": 0}
    assert run["result"]["mongo"] is None
    assert await _pg_ids(superuser) == before
    assert await world.audit_rows(impl.AUDIT_ACTION) == []
    events = [e for e in await world.events(run_id) if e["code"] == "counted"]
    assert [e["counts"] for e in events] == [{"matched": len(PG_DELETE), "deleted": 0}]


async def test_postgres_apply_deletes_exactly_the_runbooks_rows_then_nothing(
    world, pg_env, superuser
):
    await _seed_postgres(superuser)
    run_id, run = await _both(world)
    assert run["state"] == "succeeded", run
    assert run["result"]["postgres"] == {"matched": len(PG_DELETE), "deleted": len(PG_DELETE)}
    assert run["result"]["deleted"] == len(PG_DELETE)
    assert await _pg_ids(superuser) == set(PG_KEEP)
    rows = await world.audit_rows(impl.AUDIT_ACTION)
    assert len(rows) == 1
    assert rows[0]["request_id"] == str(run_id)
    assert rows[0]["target_type"] == "google_oauth" and rows[0]["target_id"] == "postgres"
    detail = rows[0]["detail"]
    assert {k: detail[k] for k in ("store", "matched", "deleted")} == {
        "store": "postgres", "matched": len(PG_DELETE), "deleted": len(PG_DELETE)
    }
    assert set(detail) == {"run_id", "task", "requested_by", "store", "matched", "deleted"}
    assert rows[0]["before"] is None and rows[0]["after"] is None
    _no_personal_data(rows, run["result"], await world.events(run_id))

    # idempotent: a second dry run and apply find and delete nothing
    _, again = await _both(world)
    assert again["state"] == "succeeded", again
    assert again["result"]["postgres"] == {"matched": 0, "deleted": 0}
    assert await _pg_ids(superuser) == set(PG_KEEP)


async def test_apply_needs_a_prior_dry_run(world, pg_env, superuser):
    await _seed_postgres(superuser)
    _, run = await _run(world)
    assert run["state"] == "refused" and run["refusal_code"] == "dry_run_required", run
    assert await _pg_ids(superuser) == {*PG_DELETE, *PG_KEEP}


async def test_refusals(world, server, pg_env, superuser, monkeypatch):
    # auto without the services' write mode
    monkeypatch.delenv("DB_WRITE_MODE")
    _, run = await _run(world, dry_run=True)
    assert run["refusal_code"] == "write_mode_unknown", run
    monkeypatch.setenv("DB_WRITE_MODE", "postgres")
    # a named store that is not configured
    _, run = await _run(world, {"stores": "mongo"}, dry_run=True)
    assert run["refusal_code"] == "store_not_configured", run
    # the services write Mongo too, but the runner has no Mongo connection
    monkeypatch.setenv("DB_WRITE_MODE", "dual")
    _, run = await _run(world, dry_run=True)
    assert run["refusal_code"] == "store_not_configured", run
    monkeypatch.setenv("DB_WRITE_MODE", "postgres")
    # EXECUTE taken away from the runner's role, then the function missing (the
    # roles script has not run since the upgrade)
    async with superuser.begin() as conn:
        await conn.execute(
            text(f'REVOKE EXECUTE ON FUNCTION {impl.FUNCTION} FROM "{server.data_google_role}"')
        )
    _, run = await _run(world, dry_run=True)
    assert run["refusal_code"] == "purge_function_missing", run
    async with superuser.begin() as conn:
        await conn.execute(text(f"DROP FUNCTION {impl.FUNCTION}"))
    _, run = await _run(world, dry_run=True)
    assert run["refusal_code"] == "purge_function_missing", run
    # an unreachable store
    monkeypatch.setenv(
        "GOOGLE_DATABASE_URL", "postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none_test"
    )
    _, run = await _run(world, dry_run=True)
    assert run["refusal_code"] == "store_unreachable", run


# ------------------------------------------------------------ both stores
async def test_dry_run_on_both_stores_counts_per_store_and_deletes_nothing(
    world, mongo, superuser
):
    await _seed_postgres(superuser)
    keep, delete = _mongo_documents()
    await mongo.insert_many([*keep, *delete])
    _, run = await _run(world, dry_run=True)
    assert run["state"] == "succeeded", run
    assert run["result"]["mongo"] == {"matched": len(delete), "deleted": 0}
    assert run["result"]["postgres"] == {"matched": len(PG_DELETE), "deleted": 0}
    assert len(await _mongo_ids(mongo)) == len(keep) + len(delete)
    assert await _pg_ids(superuser) == {*PG_DELETE, *PG_KEEP}
    assert await world.audit_rows(impl.AUDIT_ACTION) == []


async def test_apply_on_both_stores_runs_mongo_first_and_is_idempotent(
    world, mongo, superuser, monkeypatch
):
    # Postgres is the services' primary here; the purge still starts with Mongo
    monkeypatch.setenv("DB_WRITE_MODE", "postgres_primary_dual")
    await _seed_postgres(superuser)
    keep, delete = _mongo_documents()
    await mongo.insert_many([*keep, *delete])
    run_id, run = await _both(world)
    assert run["state"] == "succeeded", run
    assert run["result"]["mongo"] == {"matched": len(delete), "deleted": len(delete)}
    assert run["result"]["postgres"] == {"matched": len(PG_DELETE), "deleted": len(PG_DELETE)}
    assert run["result"]["deleted"] == len(delete) + len(PG_DELETE)
    assert await _mongo_ids(mongo) == {str(d["_id"]) for d in keep}
    assert await _pg_ids(superuser) == set(PG_KEEP)

    events = [e for e in await world.events(run_id) if e["code"] == "purged"]
    assert [e["ids"][-1] for e in events] == ["mongo", "postgres"]
    rows = await world.audit_rows(impl.AUDIT_ACTION)
    assert [r["target_id"] for r in rows] == ["mongo", "postgres"]
    assert [(r["detail"]["matched"], r["detail"]["deleted"]) for r in rows] == [
        (len(delete), len(delete)),
        (len(PG_DELETE), len(PG_DELETE)),
    ]
    _no_personal_data(rows, run["result"], await world.events(run_id))

    _, again = await _both(world)
    assert again["state"] == "succeeded", again
    assert again["result"]["mongo"] == {"matched": 0, "deleted": 0}
    assert again["result"]["postgres"] == {"matched": 0, "deleted": 0}
    assert await _mongo_ids(mongo) == {str(d["_id"]) for d in keep}


async def test_a_dry_run_cannot_write_to_mongo(world, mongo, superuser, monkeypatch):
    """The dry run's Mongo handle is read-only: even a purge that tried to
    delete would fail instead."""
    await _seed_postgres(superuser, {})
    keep, delete = _mongo_documents()
    await mongo.insert_many([*keep, *delete])

    async def deleting(store, apply):
        await store.db[COLLECTION].delete_many({})
        return {"matched": 0, "deleted": 0}

    monkeypatch.setattr(impl, "_purge_mongo", deleting)
    _, run = await _run(world, dry_run=True)
    assert run["state"] == "failed", run
    assert len(await _mongo_ids(mongo)) == len(keep) + len(delete)


# ------------------------------------------------- the filter's edges
# Postgres: (doc, deleted?) -- the runbook's filter, word for word
PG_EDGES = {
    _hex(40): ({"user_id": "u6", "credentials": "gAAAAAB-a-fernet-string"}, False),
    _hex(41): ({"user_id": "u6", "credentials": None}, False),  # JSON null
    _hex(42): ({"user_id": "u6", "credentials": CIPHER}, False),
    _hex(43): ({"user_id": "u6", "credentials": {}}, True),  # an object without $binary
    _hex(44): ({"user_id": {"$oid": _hex(99)}, "credentials": CIPHER}, False),
    _hex(45): ({"user_id": {"$oid": _hex(99)}, "credentials": {"token": SECRET}}, True),
    _hex(46): ({"user_id": [], "credentials": CIPHER}, True),  # no text user id
}


async def test_postgres_filter_edges(world, pg_env, superuser):
    await _seed_postgres(superuser, {k: doc for k, (doc, _) in PG_EDGES.items()})
    async with superuser.connect() as conn:
        # the generated column unwraps an ObjectId the way the real table does
        assert (
            await conn.execute(
                text("SELECT user_id FROM google.oauth_credentials WHERE id = :i"), {"i": _hex(44)}
            )
        ).scalar_one() == _hex(99)
    gone = {k for k, (_, deleted) in PG_EDGES.items() if deleted}
    _, run = await _both(world)
    assert run["state"] == "succeeded", run
    assert run["result"]["postgres"] == {"matched": len(gone), "deleted": len(gone)}
    assert await _pg_ids(superuser) == set(PG_EDGES) - gone


async def test_mongo_filter_edges(world, mongo, superuser):
    await _seed_postgres(superuser, {})
    edges = [
        ({"_id": ObjectId(_hex(50)), "user_id": "u6", "credentials": "gAAAAAB-fernet"}, False),
        ({"_id": ObjectId(_hex(51)), "user_id": "u6", "credentials": None}, False),
        ({"_id": ObjectId(_hex(52)), "user_id": "u6", "credentials": Binary(b"x")}, False),
        # the Mongo filter looks for the token fields only (the runbook's):
        # an empty object holds no token and stays
        ({"_id": ObjectId(_hex(53)), "user_id": "u6", "credentials": {}}, False),
        ({"_id": ObjectId(_hex(54)), "user_id": ObjectId(_hex(99)),
          "credentials": Binary(b"x")}, False),
        ({"_id": ObjectId(_hex(55)), "user_id": ObjectId(_hex(99)),
          "credentials": {"token": SECRET}}, True),
    ]
    await mongo.insert_many([doc for doc, _ in edges])
    _, run = await _both(world)
    assert run["state"] == "succeeded", run
    assert run["result"]["mongo"] == {"matched": 1, "deleted": 1}
    assert await _mongo_ids(mongo) == {str(doc["_id"]) for doc, deleted in edges if not deleted}


async def test_an_apply_must_cover_every_store_the_services_write(world, pg_env, superuser, monkeypatch):
    """Postgres alone while the services still write Mongo: a later backfill
    would copy the readable rows back, so the apply refuses. The dry run may
    still count the one store."""
    await _seed_postgres(superuser)
    monkeypatch.setenv("DB_WRITE_MODE", "dual")
    _, dry = await _run(world, {"stores": "postgres"}, dry_run=True)
    assert dry["state"] == "succeeded", dry
    assert dry["result"]["postgres"] == {"matched": len(PG_DELETE), "deleted": 0}
    _, run = await _run(world, {"stores": "postgres"})
    assert run["state"] == "refused" and run["refusal_code"] == "stores_incomplete", run
    assert await _pg_ids(superuser) == {*PG_DELETE, *PG_KEEP}
    # a named store needs no write mode to count, but an apply must know it
    monkeypatch.delenv("DB_WRITE_MODE")
    _, dry = await _run(world, {"stores": "postgres"}, dry_run=True)
    assert dry["state"] == "succeeded", dry
    _, run = await _run(world, {"stores": "postgres"})
    assert run["refusal_code"] == "write_mode_unknown", run
    assert await _pg_ids(superuser) == {*PG_DELETE, *PG_KEEP}
    # the services write Postgres alone: Postgres alone is complete
    monkeypatch.setenv("DB_WRITE_MODE", "postgres")
    _, run = await _both(world, {"stores": "postgres"})
    assert run["state"] == "succeeded", run
    assert await _pg_ids(superuser) == set(PG_KEEP)


# -------------------------------------------------------- least privilege
async def _sqlstate(engine, sql, *, role=None, **params):
    with pytest.raises(DBAPIError) as caught:
        async with engine.begin() as conn:
            if role:
                await conn.execute(text(f'SET LOCAL ROLE "{role}"'))
            await conn.execute(text(sql), params)
    orig = caught.value.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


async def test_the_definer_role_holds_delete_on_the_credentials_and_nothing_else(
    server, google_table, superuser
):
    role = server.purge_google_role
    async with superuser.connect() as conn:
        attrs = (
            await conn.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolcanlogin, rolreplication, "
                    "rolbypassrls FROM pg_roles WHERE rolname = :r"
                ),
                {"r": role},
            )
        ).one()
        tables = set(
            (
                await conn.execute(
                    text(
                        "SELECT table_schema, table_name, privilege_type "
                        "FROM information_schema.role_table_grants WHERE grantee = :r"
                    ),
                    {"r": role},
                )
            ).all()
        )
        columns = set(
            (
                await conn.execute(
                    text(
                        "SELECT table_name, column_name, privilege_type "
                        "FROM information_schema.column_privileges WHERE grantee = :r"
                    ),
                    {"r": role},
                )
            ).all()
        )
        usage = {
            s
            for s in ("app", "google", "auth", "jobs", "admin", "tasks", "settings")
            if (
                await conn.execute(
                    text("SELECT has_schema_privilege(:r, :s, 'USAGE') OR has_schema_privilege(:r, :s, 'CREATE')"),
                    {"r": role, "s": s},
                )
            ).scalar_one()
        }
        fn = (
            await conn.execute(
                text(
                    "SELECT p.proowner::regrole::text, p.prosecdef, p.proconfig, "
                    "coalesce(p.proacl::text[], '{}') FROM pg_proc p "
                    "WHERE p.oid = CAST(:f AS regprocedure)"
                ),
                {"f": impl.FUNCTION},
            )
        ).one()
        executes = {
            name: (
                await conn.execute(
                    text("SELECT has_function_privilege(:r, CAST(:f AS regprocedure), 'EXECUTE')"),
                    {"r": name, "f": impl.FUNCTION},
                )
            ).scalar_one()
            for name in (
                server.data_google_role,
                server.data_app_role,
                server.tasks_role,
                server.runtime_role,
                server.owner_role,
                server.reader_role("google"),
                server.reader_role("app"),
            )
        }
    assert tuple(attrs) == (False, False, False, False, False, False)
    assert tables == {("google", "oauth_credentials", "DELETE")}
    assert columns == {
        ("oauth_credentials", "user_id", "SELECT"),
        ("oauth_credentials", "doc", "SELECT"),
    }
    assert usage == {"google"}
    owner, secdef, config, acl = fn
    assert owner.strip('"') == role and secdef is True
    assert config == ["search_path=pg_catalog, pg_temp"]
    assert not any(entry.startswith("=") for entry in acl)  # nothing for PUBLIC
    assert executes == {
        server.data_google_role: True,
        server.data_app_role: False,
        server.tasks_role: False,
        server.runtime_role: False,
        server.owner_role: False,
        server.reader_role("google"): False,
        server.reader_role("app"): False,
    }


async def test_the_definer_role_cannot_delete_or_change_anything_else(
    server, google_table, superuser
):
    role = server.purge_google_role
    for statement in (
        "DELETE FROM google.other_rows",
        "UPDATE google.oauth_credentials SET doc = doc",
        "INSERT INTO google.oauth_credentials (id, doc, _bc_checksum) VALUES ('z', '{}', 'c')",
        "TRUNCATE google.oauth_credentials",
        "SELECT created_at FROM google.oauth_credentials",
        "DELETE FROM admin.audit_log",
        "DELETE FROM tasks.runs",
        "CREATE TABLE google.t (a int)",
    ):
        got = await _sqlstate(superuser, statement, role=role)
        assert got == "42501", f"{statement!r} -> {got}"
    async with superuser.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM google.other_rows"))).scalar_one() == 1


async def test_the_data_role_still_cannot_delete_and_cannot_widen_the_filter(
    server, google_table, superuser
):
    await _seed_postgres(superuser)
    engine = fixture_engine(server.url(google_table, "data_google"))
    try:
        for statement in (
            "DELETE FROM google.oauth_credentials",
            f"DELETE FROM google.oauth_credentials WHERE id = '{_hex(10)}'",
            "TRUNCATE google.oauth_credentials",
            "DELETE FROM google.other_rows",
            # the definer function is not a way to run other SQL or other filters
            f"ALTER FUNCTION {impl.FUNCTION} OWNER TO CURRENT_USER",
            f"CREATE OR REPLACE FUNCTION google.purge_unencrypted_credentials(p boolean) "
            "RETURNS bigint LANGUAGE sql AS 'SELECT 0::bigint'",
        ):
            got = await _sqlstate(engine, statement)
            assert got == "42501", f"{statement!r} -> {got}"
        async with engine.begin() as conn:
            counted = (
                await conn.execute(text("SELECT google.purge_unencrypted_credentials(false)"))
            ).scalar_one()
        assert counted == len(PG_DELETE)
        assert await _pg_ids(superuser) == {*PG_DELETE, *PG_KEEP}
        assert await _sqlstate(
            engine, "SELECT google.purge_unencrypted_credentials(NULL)"
        ) == "22023"
    finally:
        await engine.dispose()
