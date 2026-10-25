"""The task runner's data roles (``bc_tasks_data_app``, ``bc_tasks_data_google``)
against a real Postgres.

One role per owning schema: an UPDATE runs the table owner's triggers and
generated-column helpers with the UPDATER's privileges, so a single role over
both ``bc_app``'s and ``bc_google``'s tables would let either owner plant code
that runs with access to the other's table.

The roles are made by ``postgres/ensure-admin-roles.sh`` (the superuser: the
tables belong to other roles, so a migration of the admin chain could not grant
on them). The database here is laid out like production: the init script's
roles and schemas, the backend's real migrations (as ``bc_app``), the Google
credentials table (as ``bc_google``), then the roles script. The tests prove
exactly what each role can read and update, that everything else is denied
(including the other role's schema and anything the other owner owns), that a
hostile trigger of either owner gets nothing from the other, and that the code
the tasks run works with only these grants.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from bson import ObjectId
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
from tests.admin.engines import fixture_engine
from tests.admin.conftest import needs_postgres, roles_sql
from tests.admin.tasks.keyset_support import generated_keyset
from tests.app.db.test_auto_migrate import _execute

pytestmark = needs_postgres

WS = "65e5501d00000000000000a1"
HEX = "0123456789abcdef01234567"
RESPONSE_COLUMNS = ("id", "form_id", "response_id", "workspace_id", "doc")
# exactly what each role holds: (schema, table, column, privilege)
EXPECTED = {
    "app": {
        *(("app", "form_responses", c, "SELECT") for c in RESPONSE_COLUMNS),
        *(("app", "form_responses", c, "UPDATE") for c in ("doc", "_bc_checksum")),
        *(("app", "responses_deletion_requests", c, "SELECT") for c in RESPONSE_COLUMNS),
        *(("app", "responses_deletion_requests", c, "UPDATE") for c in ("doc", "_bc_checksum")),
        *(("app", "workspace_forms", c, "SELECT") for c in ("id", "form_id", "workspace_id", "doc")),
        *(
            ("app", "migration_progress", c, "SELECT")
            for c in ("collection", "state", "last_id", "skipped")
        ),
    },
    "google": {
        *(("google", "oauth_credentials", c, "SELECT") for c in ("id", "user_id", "doc")),
        *(("google", "oauth_credentials", c, "UPDATE") for c in ("doc", "_bc_checksum")),
    },
}
OTHER = {"app": "google", "google": "app"}


async def _roles(server, database):
    await _execute(
        server.url(database),
        roles_sql(
            server.suffix,
            server.admin_pw,
            server.mig_pw,
            server.tasks_pw,
            server.data_app_pw,
            server.data_google_pw,
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


def role_of(server, which: str) -> str:
    return server.data_app_role if which == "app" else server.data_google_role


@pytest_asyncio.fixture(loop_scope="session")
async def app(server, db):
    engine = fixture_engine(server.url(db, "data_app"))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def google(server, db):
    engine = fixture_engine(server.url(db, "data_google"))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def superuser(server, db):
    engine = fixture_engine(server.url(db))
    yield engine
    await engine.dispose()


async def sqlstate(engine, sql, **params):
    with pytest.raises(DBAPIError) as caught:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    orig = caught.value.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


async def held(superuser, role):
    async with superuser.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT table_schema, table_name, column_name, privilege_type "
                "FROM information_schema.column_privileges WHERE grantee = :r "
                "AND table_schema NOT IN ('information_schema', 'pg_catalog')"
            ),
            {"r": role},
        )
        return {tuple(r) for r in rows}


# ---------------------------------------------------------------- the grants
@pytest.mark.parametrize("which", ["app", "google"])
async def test_each_role_holds_exactly_its_schemas_privileges(superuser, server, which):
    role = role_of(server, which)
    async with superuser.connect() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.role_table_grants "
                    "WHERE grantee = :r AND table_schema NOT IN ('information_schema', 'pg_catalog') "
                    "AND privilege_type NOT IN ('SELECT', 'UPDATE')"
                ),
                {"r": role},
            )
        ).scalar_one()
        attrs = (
            await conn.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolcanlogin, rolreplication, "
                    "rolbypassrls FROM pg_roles WHERE rolname = :r"
                ),
                {"r": role},
            )
        ).one()
        schemas = {
            s: (
                await conn.execute(
                    text("SELECT has_schema_privilege(:r, :s, 'USAGE'), has_schema_privilege(:r, :s, 'CREATE')"),
                    {"r": role, "s": s},
                )
            ).one()
            for s in ("app", "google", "auth", "jobs", "admin", "tasks", "settings", "public")
        }
        temp = (
            await conn.execute(
                text("SELECT has_database_privilege(:r, current_database(), 'TEMPORARY')"),
                {"r": role},
            )
        ).scalar_one()
        config = (
            await conn.execute(
                text(
                    "SELECT setconfig FROM pg_db_role_setting s JOIN pg_roles r ON r.oid = s.setrole "
                    "WHERE r.rolname = :r"
                ),
                {"r": role},
            )
        ).scalar_one()
    assert await held(superuser, role) == EXPECTED[which]
    assert tables == 0
    assert tuple(attrs) == (False, False, False, True, False, False)
    # `public` keeps its default USAGE (nothing in it; CREATE was revoked)
    assert {s for s, (use, _) in schemas.items() if use} - {"public"} == {which}
    assert not any(create for _, create in schemas.values())
    assert temp is False
    assert config == ["search_path=pg_catalog"]


async def test_the_grants_are_idempotent_and_repair_drift(server, db, superuser):
    await _roles(server, db)
    assert await held(superuser, server.data_app_role) == EXPECTED["app"]
    assert await held(superuser, server.data_google_role) == EXPECTED["google"]
    # drift: someone widened them by hand (one role over both schemas, a write
    # on a table, a schema of another service); the script takes it all back
    async with superuser.begin() as conn:
        await conn.execute(
            text(f'GRANT SELECT, INSERT, DELETE ON app.form_responses TO "{server.data_app_role}"')
        )
        await conn.execute(text(f'GRANT USAGE ON SCHEMA google TO "{server.data_app_role}"'))
        await conn.execute(text(f'GRANT USAGE ON SCHEMA app TO "{server.data_google_role}"'))
        await conn.execute(text(f'GRANT SELECT ON google.oauth_credentials TO "{server.data_app_role}"'))
        await conn.execute(text(f'GRANT USAGE ON SCHEMA auth TO "{server.data_google_role}"'))
    assert await held(superuser, server.data_app_role) != EXPECTED["app"]
    await _roles(server, db)
    assert await held(superuser, server.data_app_role) == EXPECTED["app"]
    assert await held(superuser, server.data_google_role) == EXPECTED["google"]
    async with superuser.connect() as conn:
        for which in ("app", "google"):
            use = (
                await conn.execute(
                    text("SELECT has_schema_privilege(:r, :s, 'USAGE')"),
                    {"r": role_of(server, which), "s": OTHER[which]},
                )
            ).scalar_one()
            assert use is False


# ----------------------------------------------------------- what they can do
async def _seed(superuser):
    """One response, one deletion request, one link, one credential: documents
    as the application stores them."""
    keyset = generated_keyset()
    cipher = CryptoService(keyset)
    answers = cipher.encrypt(WS, "f1", '{"q1": "an answer"}')
    docs = {
        "app.form_responses": canonical_document(
            {"_id": ObjectId(HEX), "form_id": "f1", "workspace_id": None, "answers": answers}
        ),
        "app.responses_deletion_requests": canonical_document(
            {"_id": ObjectId(HEX), "form_id": "f1", "response_id": "r1"}
        ),
        "app.workspace_forms": canonical_document(
            {"_id": ObjectId(HEX), "form_id": "f1", "workspace_id": WS}
        ),
        "google.oauth_credentials": canonical_document(
            {
                "_id": ObjectId(HEX),
                "user_id": "user-1",
                "credentials": cipher.encrypt("personal", "user-1", '{"t": "x"}'),
            }
        ),
    }
    async with superuser.begin() as conn:
        for table, doc in docs.items():
            await conn.execute(
                text(
                    f"INSERT INTO {table} (id, doc, _bc_checksum) "
                    "VALUES (:id, CAST(:doc AS jsonb), :c)"
                ),
                {"id": HEX, "doc": json.dumps(doc), "c": checksum(doc)},
            )
    return keyset, answers


async def test_each_role_reads_and_updates_what_the_tasks_need(app, google, superuser):
    await _seed(superuser)
    async with app.begin() as conn:
        for table in ("app.form_responses", "app.responses_deletion_requests", "app.workspace_forms"):
            assert (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 1
            assert (await conn.execute(text(f"SELECT id, doc FROM {table}"))).first() is not None
        row = (
            await conn.execute(
                text("SELECT id, form_id, response_id, workspace_id, doc FROM app.form_responses")
            )
        ).first()
        assert row.form_id == "f1"
        for table in ("app.form_responses", "app.responses_deletion_requests"):
            result = await conn.execute(
                text(f"UPDATE {table} SET doc = doc, _bc_checksum = 'c' WHERE id = :i"), {"i": HEX}
            )
            assert result.rowcount == 1
        # the row lock a compare-and-swap takes
        await conn.execute(text("SELECT doc FROM app.form_responses WHERE id = :i FOR UPDATE"), {"i": HEX})
    # the forms import check before a task writes from the forms' links
    # (backend.db.forms_import): the backfill state, read without a fallback
    from backend.db.forms_import import Backfill, workspace_forms_backfill

    assert await workspace_forms_backfill(app) == Backfill(complete=False)
    async with google.begin() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM google.oauth_credentials"))).scalar_one() == 1
        assert (await conn.execute(text("SELECT id, user_id, doc FROM google.oauth_credentials"))).first()
        result = await conn.execute(
            text("UPDATE google.oauth_credentials SET doc = doc, _bc_checksum = 'c' WHERE id = :i"),
            {"i": HEX},
        )
        assert result.rowcount == 1


COMMON_DENIED = [
    "SELECT 1 FROM app.workspaces",
    "SELECT 1 FROM auth.users",
    "SELECT 1 FROM jobs.procrastinate_jobs",
    "SELECT * FROM admin.audit_log",
    "INSERT INTO admin.audit_log (action) VALUES ('x')",
    "SELECT * FROM admin.sessions",
    "SELECT * FROM admin.notifications",
    "SELECT * FROM tasks.runs",
    "SELECT * FROM tasks.locks",
    "SELECT * FROM settings.entries",
    "SELECT * FROM settings.v_tasks",
    "SELECT * FROM settings.service_state",
    "UPDATE settings.entries SET version = version",
    "SELECT settings.report_state('x', 1, '{}', '{}', false, '')",
    "SELECT settings.task_write_keyset(NULL, 1, 1, 's', ARRAY['a'], 'v2:x', 'u', now(), 'x', 'a', 'b', '{}', 'c', 'promote', 'r', '{}')",
    "SELECT settings.task_notify_reencrypt('x', 1)",
    "CREATE TABLE public.t (a int)",
    "CREATE TEMP TABLE t (a int)",
    "CREATE SCHEMA s",
]
APP_DENIED = [
    "SELECT created_at FROM app.form_responses",
    "SELECT * FROM app.form_responses",
    "SELECT updated_at FROM app.responses_deletion_requests",
    "UPDATE app.form_responses SET created_at = now()",
    "UPDATE app.workspace_forms SET doc = doc",
    "INSERT INTO app.form_responses (id, doc, _bc_checksum) VALUES ('a', '{}', 'c')",
    "DELETE FROM app.form_responses",
    "TRUNCATE app.form_responses",
    "SELECT 1 FROM app.sessions",
    "SELECT 1 FROM app.forms",
    "UPDATE app.forms SET doc = doc",
    "CREATE TABLE app.t (a int)",
    # the other owner's schema: tables and what it owns
    "SELECT * FROM google.oauth_credentials",
    "SELECT id FROM google.oauth_credentials",
    "UPDATE google.oauth_credentials SET doc = doc",
    "SELECT google.bc_text('{}'::jsonb)",
    "CREATE TABLE google.t (a int)",
]
GOOGLE_DENIED = [
    "SELECT created_at FROM google.oauth_credentials",
    "SELECT * FROM google.oauth_credentials",
    "UPDATE google.oauth_credentials SET created_at = now()",
    "INSERT INTO google.oauth_credentials (id, doc, _bc_checksum) VALUES ('a', '{}', 'c')",
    "DELETE FROM google.oauth_credentials",
    "TRUNCATE google.oauth_credentials",
    "CREATE TABLE google.t (a int)",
    # the other owner's schema: tables and what it owns
    "SELECT id FROM app.form_responses",
    "SELECT * FROM app.workspace_forms",
    "UPDATE app.form_responses SET doc = doc",
    "SELECT app.bc_text('{}'::jsonb)",
    "CREATE TABLE app.t (a int)",
]


@pytest.mark.parametrize(
    "which, statements",
    [("app", APP_DENIED), ("google", GOOGLE_DENIED)],
)
async def test_everything_else_is_denied(app, google, superuser, which, statements):
    await _seed(superuser)
    engine = app if which == "app" else google
    for sql in [*COMMON_DENIED, *statements]:
        got = await sqlstate(engine, sql)
        assert got == "42501", f"{which}: {sql!r} -> {got}"


async def test_neither_role_can_use_anything_the_other_owner_owns(superuser, server):
    """No schema USAGE, so no table, function or type of the other owner is
    reachable, whatever PUBLIC may execute."""
    async with superuser.connect() as conn:
        for which in ("app", "google"):
            other = OTHER[which]
            assert not (
                await conn.execute(
                    text("SELECT has_schema_privilege(:r, :s, 'USAGE')"),
                    {"r": role_of(server, which), "s": other},
                )
            ).scalar_one()
            # and the owner of that schema really is the other service's role
            owner = (
                await conn.execute(
                    text("SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = :s"),
                    {"s": other},
                )
            ).scalar_one()
            assert owner.strip('"') in (server.reader_role("app"), server.reader_role("google"))


async def _hostile_trigger(superuser, server, schema, table, owner, body):
    """A trigger function of the table's owner, firing on UPDATE, that runs ``body``."""
    function = f"{schema}.hostile_{schema}"
    async with superuser.begin() as conn:
        await conn.execute(
            text(
                f"CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                f"BEGIN {body}; RETURN NEW; END $$"
            )
        )
        await conn.execute(text(f'ALTER FUNCTION {function}() OWNER TO "{owner}"'))
        await conn.execute(
            text(
                f"CREATE TRIGGER hostile BEFORE UPDATE ON {schema}.{table} "
                f"FOR EACH ROW EXECUTE FUNCTION {function}()"
            )
        )


async def test_a_hostile_trigger_of_either_owner_gets_nothing_from_the_other(
    app, google, superuser, server
):
    """The trigger runs with the updater's privileges. With one role over both
    owners' tables, bc_app's trigger could read or rewrite the Google
    credentials during a re-encryption; with one role per schema it is denied."""
    await _seed(superuser)
    await _hostile_trigger(
        superuser, server, "app", "form_responses", server.reader_role("app"),
        "PERFORM count(*) FROM google.oauth_credentials",
    )
    await _hostile_trigger(
        superuser, server, "google", "oauth_credentials", server.reader_role("google"),
        "PERFORM count(*) FROM app.form_responses",
    )
    update_app = "UPDATE app.form_responses SET doc = doc, _bc_checksum = 'x' WHERE id = :i"
    update_google = "UPDATE google.oauth_credentials SET doc = doc, _bc_checksum = 'x' WHERE id = :i"
    assert await sqlstate(app, update_app, i=HEX) == "42501"
    assert await sqlstate(google, update_google, i=HEX) == "42501"
    # the rows are untouched
    async with superuser.connect() as conn:
        for table in ("app.form_responses", "google.oauth_credentials"):
            assert (await conn.execute(text(f"SELECT _bc_checksum FROM {table}"))).scalar_one() != "x"


async def test_the_runner_state_role_cannot_touch_the_data_tables(server, db, superuser):
    await _seed(superuser)
    tasks = create_async_engine(server.url(db, "reader:tasks"), poolclass=NullPool)
    try:
        for sql in (
            "SELECT 1 FROM app.form_responses",
            "UPDATE google.oauth_credentials SET doc = doc",
        ):
            assert await sqlstate(tasks, sql) == "42501", sql
    finally:
        await tasks.dispose()


# ------------------------------------------------ the code the tasks run
async def test_the_rotation_walk_works_with_only_these_grants(app, google, superuser):
    old_keyset, answers = await _seed(superuser)
    rotated = encode_keyset(add_primary_key(parse_keyset(old_keyset)))
    rotation = core.Rotation(rotated)
    store = core.PostgresStore(app, core.RESPONSES)
    credentials = core.PostgresStore(google, core.GOOGLE_CREDENTIALS)

    counts = await core.scan(store, core.RESPONSES, rotation, 100)
    assert counts["records"] == 1 and counts["values_stale"] == 1
    assert (await core.verify_store(store, core.RESPONSES, rotation, 100))["values_unopenable"] == 0
    done, _ = await core.reencrypt_store(store, core.RESPONSES, rotation, None, 100, readback=True)
    assert done["records_reencrypted"] == 1 and "records_readback_failed" not in done
    done, _ = await core.reencrypt_store(
        credentials, core.GOOGLE_CREDENTIALS, rotation, None, 100, readback=True
    )
    assert done["records_reencrypted"] == 1
    async with superuser.connect() as conn:
        doc = (await conn.execute(text("SELECT doc FROM app.form_responses"))).scalar_one()
        stored = (await conn.execute(text("SELECT _bc_checksum FROM app.form_responses"))).scalar_one()
    assert stored == checksum(doc)
    after = await store.batch(None, 10)
    assert ciphertext_key_id(after[0]["answers"]) == rotation.primary
    assert after[0]["answers"] != answers


async def test_the_backfill_and_the_scans_work_with_only_these_grants(app, superuser):
    await _seed(superuser)
    backfill = BackfillStore(app)
    assert await backfill.count_responses() == 1
    unstamped = await backfill.unstamped("form_responses", None, 10)
    assert len(unstamped) == 1
    assert await backfill.stamp("form_responses", unstamped[0]["key"], WS) == 1
    assert await backfill.stamp("responses_deletion_requests", HEX, WS) == 1
    assert await backfill.links() == {"f1": [WS]}


async def test_the_first_run_of_an_upgrade_precedes_the_workspace_id_column(server):
    """deploy.sh runs the script before the application's migrations. A stack
    upgraded from a release that predates the response tables' ``workspace_id``
    (app revision 0015) must not fail on it: the columns that exist are granted,
    the run after the migrations grants the rest."""
    name = await server.create_database(template=server.template)
    await upgrade_schema(server.url(name, "reader:app"), APP_MIGRATIONS)
    # the schema as the previous release left it
    await _execute(
        server.url(name, "reader:app"),
        "ALTER TABLE app.form_responses DROP COLUMN workspace_id;"
        "ALTER TABLE app.responses_deletion_requests DROP COLUMN workspace_id;",
    )
    await _roles(server, name)  # raised "column workspace_id does not exist" before
    engine = create_async_engine(server.url(name), poolclass=NullPool)
    try:
        before = await held(engine, server.data_app_role)
        assert ("app", "form_responses", "response_id", "SELECT") in before
        assert ("app", "form_responses", "doc", "UPDATE") in before
        assert not any(
            column == "workspace_id" and table != "workspace_forms"
            for _, table, column, _ in before
        )
        # the migration arrives, then the second run completes the grants
        for table in ("form_responses", "responses_deletion_requests"):
            await _execute(
                server.url(name, "reader:app"),
                f"ALTER TABLE app.{table} ADD COLUMN workspace_id TEXT "
                "GENERATED ALWAYS AS (app.bc_text(doc -> 'workspace_id')) STORED",
            )
        await _roles(server, name)
        assert await held(engine, server.data_app_role) == EXPECTED["app"]
    finally:
        await engine.dispose()
