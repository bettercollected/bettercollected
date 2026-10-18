"""The task runner's data role (``bc_tasks_data``) against a real Postgres.

The role is made by ``postgres/ensure-admin-roles.sh`` (the superuser: the
tables belong to other roles, so a migration of the admin chain could not grant
on them). The database here is laid out like production: the init script's
roles and schemas, the backend's real migrations (as ``bc_app``), the Google
credentials table (as ``bc_google``), then the roles script. The tests prove
exactly what the role can read and update, that everything else is denied, and
that the code the tasks run really works with only these grants.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.admin.tasks.impl import keyset_core as core
from backend.admin.tasks.impl.responses_backfill import PostgresStore as BackfillStore
from backend.db.startup import MIGRATIONS as APP_MIGRATIONS
from common.db.canonical import canonical_document, checksum
from common.db.schema_guard import upgrade_schema
from common.services.keyset import (
    CryptoService,
    add_primary_key,
    ciphertext_key_id,
    encode_keyset,
    parse_keyset,
)
from tests.admin.conftest import needs_postgres, roles_sql
from tests.app.db.test_auto_migrate import _execute
from tests.admin.tasks.keyset_support import generated_keyset

pytestmark = needs_postgres

WS = "65e5501d00000000000000a1"
HEX = "0123456789abcdef01234567"
# exactly what the role holds: (schema, table, column, privilege)
EXPECTED = {
    *(
        ("app", "form_responses", c, "SELECT")
        for c in ("id", "form_id", "response_id", "workspace_id", "doc")
    ),
    *(("app", "form_responses", c, "UPDATE") for c in ("doc", "_bc_checksum")),
    *(
        ("app", "responses_deletion_requests", c, "SELECT")
        for c in ("id", "form_id", "response_id", "workspace_id", "doc")
    ),
    *(
        ("app", "responses_deletion_requests", c, "UPDATE")
        for c in ("doc", "_bc_checksum")
    ),
    *(("app", "workspace_forms", c, "SELECT") for c in ("id", "form_id", "workspace_id", "doc")),
    *(("google", "oauth_credentials", c, "SELECT") for c in ("id", "user_id", "doc")),
    *(("google", "oauth_credentials", c, "UPDATE") for c in ("doc", "_bc_checksum")),
}


async def _roles(server, database):
    await _execute(
        server.url(database),
        roles_sql(
            server.suffix,
            server.admin_pw,
            server.mig_pw,
            server.tasks_pw,
            server.data_pw,
        ),
    )


@pytest_asyncio.fixture(loop_scope="session")
async def db(server):
    name = await server.create_database(template=server.template)
    await upgrade_schema(server.url(name, "reader:app"), APP_MIGRATIONS)
    await _execute(
        server.url(name),
        "CREATE TABLE google.oauth_credentials (id text PRIMARY KEY, "
        "doc jsonb NOT NULL, _bc_checksum text NOT NULL, "
        "user_id text GENERATED ALWAYS AS (doc ->> 'user_id') STORED, "
        "created_at timestamptz);"
        f'ALTER TABLE google.oauth_credentials OWNER TO "{server.reader_role("google")}";',
    )
    await _roles(server, name)
    return name


@pytest_asyncio.fixture(loop_scope="session")
async def data(server, db):
    engine = create_async_engine(server.url(db, "data"), poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def superuser(server, db):
    engine = create_async_engine(server.url(db), poolclass=NullPool)
    yield engine
    await engine.dispose()


async def denied(engine, sql, **params):
    """The SQLSTATE of the refusal (42501 = permission denied)."""
    with pytest.raises(DBAPIError) as caught:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    orig = caught.value.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


# ---------------------------------------------------------------- the grants
async def test_the_role_holds_exactly_the_expected_privileges(superuser, server):
    async with superuser.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT table_schema, table_name, column_name, privilege_type "
                "FROM information_schema.column_privileges WHERE grantee = :r "
                "AND table_schema NOT IN ('information_schema', 'pg_catalog')"
            ),
            {"r": server.data_role},
        )
        held = {tuple(r) for r in rows}
        # no table-level privilege of any kind
        tables = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.role_table_grants "
                    "WHERE grantee = :r AND table_schema NOT IN ('information_schema', 'pg_catalog') "
                    "AND privilege_type NOT IN ('SELECT', 'UPDATE')"
                ),
                {"r": server.data_role},
            )
        ).scalar_one()
        attrs = (
            await conn.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolcanlogin, rolreplication, "
                    "rolbypassrls FROM pg_roles WHERE rolname = :r"
                ),
                {"r": server.data_role},
            )
        ).one()
        schemas = {
            s: (
                await conn.execute(
                    text("SELECT has_schema_privilege(:r, :s, 'USAGE'), has_schema_privilege(:r, :s, 'CREATE')"),
                    {"r": server.data_role, "s": s},
                )
            ).one()
            for s in ("app", "google", "auth", "jobs", "admin", "tasks", "settings", "public")
        }
        temp = (
            await conn.execute(
                text("SELECT has_database_privilege(:r, current_database(), 'TEMPORARY')"),
                {"r": server.data_role},
            )
        ).scalar_one()
    assert held == EXPECTED
    assert tables == 0
    assert tuple(attrs) == (False, False, False, True, False, False)
    # `public` keeps its default USAGE (nothing in it; CREATE was revoked)
    assert {s for s, (use, _) in schemas.items() if use} - {"public"} == {"app", "google"}
    assert not any(create for _, create in schemas.values())
    assert temp is False


async def test_the_grants_are_idempotent_and_repair_drift(server, db, superuser):
    async def held():
        async with superuser.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT table_schema, table_name, column_name, privilege_type "
                    "FROM information_schema.column_privileges WHERE grantee = :r "
                    "AND table_schema NOT IN ('information_schema', 'pg_catalog')"
                ),
                {"r": server.data_role},
            )
            return {tuple(r) for r in rows}

    await _roles(server, db)
    assert await held() == EXPECTED
    # drift: someone widened it by hand; the script takes it back
    async with superuser.begin() as conn:
        await conn.execute(
            text(f'GRANT SELECT, INSERT, DELETE ON app.form_responses TO "{server.data_role}"')
        )
        await conn.execute(text(f'GRANT USAGE ON SCHEMA auth TO "{server.data_role}"'))
    assert await held() != EXPECTED
    await _roles(server, db)
    assert await held() == EXPECTED


# ----------------------------------------------------------- what it can do
async def _seed(superuser):
    """One response, one deletion request, one link, one credential: documents
    as the application stores them."""
    keyset = generated_keyset()
    cipher = CryptoService(keyset)
    answers = cipher.encrypt(WS, "f1", '{"q1": "an answer"}')
    response = canonical_document(
        {"_id": uuid_oid(HEX), "form_id": "f1", "workspace_id": None, "answers": answers}
    )
    request = canonical_document({"_id": uuid_oid(HEX), "form_id": "f1", "response_id": "r1"})
    link = canonical_document({"_id": uuid_oid(HEX), "form_id": "f1", "workspace_id": WS})
    credential = canonical_document(
        {
            "_id": uuid_oid(HEX),
            "user_id": "user-1",
            "credentials": cipher.encrypt("personal", "user-1", '{"t": "x"}'),
        }
    )
    async with superuser.begin() as conn:
        for table, doc in (
            ("app.form_responses", response),
            ("app.responses_deletion_requests", request),
            ("app.workspace_forms", link),
            ("google.oauth_credentials", credential),
        ):
            await conn.execute(
                text(
                    f"INSERT INTO {table} (id, doc, _bc_checksum) "
                    "VALUES (:id, CAST(:doc AS jsonb), :c)"
                ),
                {"id": HEX, "doc": json.dumps(doc), "c": checksum(doc)},
            )
    return keyset, answers


def uuid_oid(value: str) -> dict:
    from bson import ObjectId

    return ObjectId(value)


async def test_it_reads_and_updates_what_the_tasks_need(data, superuser):
    await _seed(superuser)
    async with data.begin() as conn:
        for table in (
            "app.form_responses",
            "app.responses_deletion_requests",
            "app.workspace_forms",
            "google.oauth_credentials",
        ):
            assert (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 1
            assert (await conn.execute(text(f"SELECT id, doc FROM {table}"))).first() is not None
        row = (
            await conn.execute(
                text("SELECT id, form_id, response_id, workspace_id, doc FROM app.form_responses")
            )
        ).first()
        assert row.form_id == "f1"
        for table in ("app.form_responses", "app.responses_deletion_requests", "google.oauth_credentials"):
            result = await conn.execute(
                text(f"UPDATE {table} SET doc = doc, _bc_checksum = 'c' WHERE id = :i"),
                {"i": HEX},
            )
            assert result.rowcount == 1
        # the row lock a compare-and-swap takes
        await conn.execute(
            text("SELECT doc FROM app.form_responses WHERE id = :i FOR UPDATE"), {"i": HEX}
        )


async def test_everything_else_is_denied(data, superuser):
    await _seed(superuser)
    sqlstate = "42501"
    statements = [
        # other columns of the granted tables
        "SELECT created_at FROM app.form_responses",
        "SELECT * FROM app.form_responses",
        "SELECT updated_at FROM app.responses_deletion_requests",
        "SELECT created_at FROM google.oauth_credentials",
        "UPDATE app.form_responses SET created_at = now()",
        "UPDATE app.workspace_forms SET doc = doc",
        "UPDATE google.oauth_credentials SET created_at = now()",
        # no insert, delete, truncate
        "INSERT INTO app.form_responses (id, doc, _bc_checksum) VALUES ('a', '{}', 'c')",
        "DELETE FROM app.form_responses",
        "DELETE FROM google.oauth_credentials",
        "TRUNCATE app.form_responses",
        # other tables of the schemas it can see
        "SELECT 1 FROM app.workspaces",
        "SELECT 1 FROM app.sessions",
        "SELECT 1 FROM app.forms",
        "UPDATE app.forms SET doc = doc",
        # other schemas
        "SELECT 1 FROM auth.users",
        "SELECT 1 FROM jobs.procrastinate_jobs",
        "SELECT * FROM admin.audit_log",
        "INSERT INTO admin.audit_log (action) VALUES ('x')",
        "SELECT * FROM admin.sessions",
        "SELECT * FROM tasks.runs",
        "SELECT * FROM tasks.locks",
        "SELECT * FROM settings.entries",
        "SELECT * FROM settings.v_tasks",
        "SELECT * FROM settings.service_state",
        "UPDATE settings.entries SET version = version",
        "SELECT settings.report_state('x', 1, '{}', '{}', false, '')",
        # no objects of its own, no temporary tables
        "CREATE TABLE app.t (a int)",
        "CREATE TABLE public.t (a int)",
        "CREATE TEMP TABLE t (a int)",
        "CREATE SCHEMA s",
    ]
    for sql in statements:
        got = await denied(data, sql)
        assert got == sqlstate, f"{sql!r} -> {got}"


async def test_the_runner_state_role_cannot_touch_the_data_tables(server, db, superuser):
    await _seed(superuser)
    tasks = create_async_engine(server.url(db, "reader:tasks"), poolclass=NullPool)
    try:
        for sql in (
            "SELECT 1 FROM app.form_responses",
            "UPDATE google.oauth_credentials SET doc = doc",
        ):
            assert await denied(tasks, sql) == "42501", sql
    finally:
        await tasks.dispose()


# ------------------------------------------------ the code the tasks run
async def test_the_rotation_walk_works_with_only_these_grants(data, superuser):
    old_keyset, answers = await _seed(superuser)
    rotated = encode_keyset(add_primary_key(parse_keyset(old_keyset)))
    rotation = core.Rotation(rotated)
    store = core.PostgresStore(data, core.RESPONSES)
    google = core.PostgresStore(data, core.GOOGLE_CREDENTIALS)

    counts = await core.scan(store, core.RESPONSES, rotation, 100)
    assert counts["records"] == 1 and counts["values_stale"] == 1
    assert (await core.verify_store(store, core.RESPONSES, rotation, 100))["values_unopenable"] == 0
    done, _ = await core.reencrypt_store(store, core.RESPONSES, rotation, None, 100, readback=True)
    assert done["records_reencrypted"] == 1 and "records_readback_failed" not in done
    done, _ = await core.reencrypt_store(google, core.GOOGLE_CREDENTIALS, rotation, None, 100, readback=True)
    assert done["records_reencrypted"] == 1
    async with superuser.connect() as conn:
        doc = (await conn.execute(text("SELECT doc FROM app.form_responses"))).scalar_one()
        checksum_stored = (await conn.execute(text("SELECT _bc_checksum FROM app.form_responses"))).scalar_one()
    assert checksum_stored == checksum(doc)
    after = await store.batch(None, 10)
    assert ciphertext_key_id(after[0]["answers"]) == rotation.primary
    assert after[0]["answers"] != answers


async def test_the_backfill_and_the_scans_work_with_only_these_grants(data, superuser):
    await _seed(superuser)
    backfill = BackfillStore(data)
    assert await backfill.count_responses() == 1
    unstamped = await backfill.unstamped("form_responses", None, 10)
    assert len(unstamped) == 1
    assert await backfill.stamp("form_responses", unstamped[0]["key"], WS) == 1
    assert await backfill.stamp("responses_deletion_requests", HEX, WS) == 1
    links = await backfill.links()
    assert links == {"f1": [WS]}
