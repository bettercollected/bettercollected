"""The Health page's schema revisions and mirror outbox counts.

The admin role reads the ``app``, ``auth`` and ``google`` schemas through narrow
definer functions only (postgres/ensure-admin-roles.sh): the revision(s) in
``alembic_version`` and the unresolved/total rows of ``mirror_write_failures``.
These tests check the privileges (the portal's role may execute them and still
cannot read a table; no other role may execute them; a hostile schema owner
gets nothing from planting code), the numbers and the page.
"""

from __future__ import annotations

import re
import textwrap

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.admin.repositories import views
from backend.admin.schema_heads import VERSIONS, code_revisions, parse_versions
from backend.admin.services import pages as pg
from tests.admin.conftest import _execute, needs_postgres, roles_sql
from tests.admin.engines import fixture_engine
from tests.admin.test_portal_pages import signed_in, superuser  # noqa: F401 - fixture

SCHEMAS = ("app", "auth", "google")
FUNCTIONS = [f"admin.schema_revision_{s}()" for s in SCHEMAS] + [
    f"admin.outbox_counts_{s}()" for s in SCHEMAS
]


# -- the code's side (no database) ---------------------------------------------------
@pytest.mark.parametrize("schema", SCHEMAS)
def test_parsed_heads_match_alembic(schema):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    directory = VERSIONS[schema]
    config = Config()
    config.set_main_option("script_location", str(directory.parent))
    config.set_main_option("path_separator", "os")
    script = ScriptDirectory.from_config(config)
    parsed = code_revisions(schema)
    assert parsed is not None
    assert parsed.heads == tuple(sorted(script.get_heads()))
    assert parsed.known == frozenset(s.revision for s in script.walk_revisions())


def _revision(directory, name, revision, down, annotated=True):
    down_src = repr(down)
    body = (
        f"revision: str = {revision!r}\ndown_revision = {down_src}\n"
        if annotated
        else f"revision = {revision!r}\ndown_revision = {down_src}\n"
    )
    (directory / f"{name}.py").write_text(
        textwrap.dedent('"""doc"""\nimport os\nos.environ["PARSED"] = "executed"\n') + body
    )


def test_parsing_follows_branches_and_merges_and_never_executes(tmp_path, monkeypatch):
    monkeypatch.delenv("PARSED", raising=False)
    _revision(tmp_path, "a", "a", None)
    _revision(tmp_path, "b", "b", "a", annotated=False)
    _revision(tmp_path, "c", "c", "a")
    assert parse_versions(tmp_path).heads == ("b", "c")
    _revision(tmp_path, "m", "m", ("b", "c"))
    parsed = parse_versions(tmp_path)
    assert parsed.heads == ("m",) and parsed.known == {"a", "b", "c", "m"}
    assert "PARSED" not in __import__("os").environ
    assert parse_versions(tmp_path / "absent") is None


def test_the_backend_image_carries_the_other_services_revision_files():
    root = VERSIONS["app"].parents[3]
    dockerfile = (root / "backend" / "Dockerfile").read_text()
    for schema in ("auth", "google"):
        relative = VERSIONS[schema].relative_to(root).as_posix()
        assert f"COPY ./{relative} ./{relative}" in dockerfile


# -- the database's side ----------------------------------------------------------------
OUTBOX_DDL = (
    "CREATE TABLE {s}.mirror_write_failures (id bigserial PRIMARY KEY, table_name text NOT NULL, "
    "row_id text NOT NULL, op text NOT NULL, error text NOT NULL, attempts integer NOT NULL DEFAULT 0, "
    "created_at timestamptz NOT NULL DEFAULT now(), resolved_at timestamptz)"
)


async def lay_out(server, database, schema, revisions, unresolved=0, resolved=0, column="varchar(32)"):
    """The schema's version table and outbox, created by the schema's own role, as
    its migrations would; then the roles script runs again, as on every deploy."""
    engine = fixture_engine(server.url(database, f"reader:{schema}"))
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                f"CREATE TABLE {schema}.alembic_version (version_num {column} PRIMARY KEY)"))
            for revision in revisions:
                await conn.execute(text(f"INSERT INTO {schema}.alembic_version VALUES (:r)"), {"r": revision})
            await conn.execute(text(OUTBOX_DDL.format(s=schema)))
            for n in range(unresolved + resolved):
                await conn.execute(
                    text(f"INSERT INTO {schema}.mirror_write_failures (table_name, row_id, op, error, resolved_at) "
                         "VALUES ('t', :i, 'update', 'secret detail', CASE WHEN :r THEN now() END)"),
                    {"i": str(n), "r": n >= unresolved},
                )
    finally:
        await engine.dispose()


async def rerun_roles(server, database):
    await _execute(
        server.url(database),
        roles_sql(server.suffix, server.admin_pw, server.mig_pw, server.tasks_pw,
                  server.data_app_pw, server.data_google_pw),
    )


async def refused(engine, sql):
    with pytest.raises(DBAPIError) as caught:
        async with engine.begin() as conn:
            await conn.execute(text(sql))
    return str(caught.value.orig)


@needs_postgres
async def test_before_the_migrations_the_functions_answer_null(server, migrated):
    engine = fixture_engine(server.url(migrated, "runtime"))
    try:
        async with engine.connect() as conn:
            for schema in SCHEMAS:
                assert await views.schema_revisions(conn, schema) is None
                assert await views.outbox_counts(conn, schema) is None
    finally:
        await engine.dispose()


@needs_postgres
async def test_the_portal_role_executes_the_functions_and_still_reads_no_table(server, migrated, superuser):  # noqa: F811
    await lay_out(server, migrated, "app", ["0021"], unresolved=2, resolved=1)
    await lay_out(server, migrated, "auth", ["0004"])
    await lay_out(server, migrated, "google", ["0003"], resolved=4)
    await rerun_roles(server, migrated)
    engine = fixture_engine(server.url(migrated, "runtime"))
    try:
        async with engine.connect() as conn:
            assert await views.schema_revisions(conn, "app") == ("0021",)
            assert await views.schema_revisions(conn, "auth") == ("0004",)
            assert await views.schema_revisions(conn, "google") == ("0003",)
            assert await views.outbox_counts(conn, "app") == (2, 3)
            assert await views.outbox_counts(conn, "auth") == (0, 0)
            assert await views.outbox_counts(conn, "google") == (0, 4)
        for schema in SCHEMAS:
            for table in ("alembic_version", "mirror_write_failures"):
                assert "permission denied" in await refused(engine, f"SELECT count(*) FROM {schema}.{table}")
            # not even a function of the schema itself: no USAGE on it
            assert "permission denied for schema" in await refused(engine, f"SELECT {schema}.anything()")
    finally:
        await engine.dispose()
    async with superuser.connect() as conn:
        for schema in SCHEMAS:
            usage = (await conn.execute(text("SELECT has_schema_privilege(:r, :s, 'USAGE')"),
                                        {"r": server.runtime_role, "s": schema})).scalar_one()
            assert usage is False


@needs_postgres
@pytest.mark.parametrize("role", ["reader:app", "reader:auth", "reader:google", "reader:tasks", "owner"])
async def test_no_other_role_may_execute_the_functions(server, migrated, role):
    engine = fixture_engine(server.url(migrated, role))
    try:
        for function in FUNCTIONS:
            assert "permission denied" in await refused(engine, f"SELECT * FROM {function}")
    finally:
        await engine.dispose()


@needs_postgres
async def test_each_function_is_a_narrow_definer_owned_by_its_schemas_count_role(server, migrated, superuser):  # noqa: F811
    for schema in SCHEMAS:
        await lay_out(server, migrated, schema, ["x"])
    await rerun_roles(server, migrated)
    async with superuser.connect() as conn:
        for schema in SCHEMAS:
            owner_role = f"bc_count_{schema}_{server.suffix}"
            role = (await conn.execute(text(
                "SELECT rolsuper, rolcanlogin, rolcreaterole, rolcreatedb, rolbypassrls "
                "FROM pg_roles WHERE rolname = :r"), {"r": owner_role})).one()
            assert not any(role)
            for name in (f"schema_revision_{schema}", f"outbox_counts_{schema}"):
                fn = (await conn.execute(text(
                    "SELECT r.rolname, p.prosecdef, p.proconfig, p.pronargs, p.proacl::text AS acl, "
                    "pg_get_functiondef(p.oid) AS definition "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "JOIN pg_roles r ON r.oid = p.proowner WHERE n.nspname = 'admin' AND p.proname = :f"),
                    {"f": name})).one()
                assert fn.rolname == owner_role and fn.prosecdef and fn.pronargs == 0
                assert "search_path=pg_catalog, pg_temp" in fn.proconfig
                # EXECUTE for the portal's role and the owner, nobody else (not PUBLIC)
                grantees = {g.split("=")[0] for g in re.findall(r"[^{},]+=[A-Za-z]*/[^,}]+", fn.acl)}
                assert grantees == {server.runtime_role, owner_role}, fn.acl
                body = fn.definition.split("$function$")[1]
                assert not re.search(r"[A-Za-z_]+\.[A-Za-z_]+\s*\(", body), body
                others = set(SCHEMAS) - {schema}
                assert not any(f"{o}." in body for o in others) and "admin." not in body
                assert re.search(r"\b(INSERT|UPDATE|DELETE|EXECUTE)\b", body, re.I) is None
            # column-level SELECT on exactly version_num and resolved_at of its own schema
            columns = (await conn.execute(text(
                "SELECT table_schema, table_name, column_name FROM information_schema.column_privileges "
                "WHERE grantee = :r AND table_name IN ('alembic_version', 'mirror_write_failures') "
                "ORDER BY 1, 2, 3"), {"r": owner_role})).all()
            assert [tuple(c) for c in columns] == [
                (schema, "alembic_version", "version_num"),
                (schema, "mirror_write_failures", "resolved_at"),
            ]
            tables = (await conn.execute(text(
                "SELECT count(*) FROM information_schema.table_privileges WHERE grantee = :r"),
                {"r": owner_role})).scalar_one()
            assert tables == 0


EVIL = """
CREATE FUNCTION {schema}.evil(x text) RETURNS boolean LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO {schema}.loot VALUES (jsonb_build_object('ran_as', current_user));
    BEGIN
        INSERT INTO {schema}.loot SELECT to_jsonb(v) FROM {other}.alembic_version v;
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('stole', 'other schema'));
    EXCEPTION WHEN others THEN
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('denied', SQLERRM));
    END;
    BEGIN
        INSERT INTO {schema}.loot SELECT to_jsonb(a) FROM admin.audit_log a;
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('stole', 'audit'));
    EXCEPTION WHEN others THEN
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('denied', SQLERRM));
    END;
    BEGIN
        INSERT INTO {schema}.loot SELECT to_jsonb(s) FROM admin.sessions s;
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('stole', 'sessions'));
    EXCEPTION WHEN others THEN
        INSERT INTO {schema}.loot VALUES (jsonb_build_object('denied', SQLERRM));
    END;
    RETURN true;
END $$
"""


@needs_postgres
@pytest.mark.parametrize("schema,other", [("app", "auth"), ("google", "app")])
async def test_a_hostile_schema_owner_gets_nothing_from_planting_code(server, migrated, schema, other):
    """The owner swaps its version table for a view that calls its own function and
    then tries to redefine or take over the admin function itself."""
    for s in SCHEMAS:
        await lay_out(server, migrated, s, ["0001"], unresolved=1)
    await rerun_roles(server, migrated)
    count_role = f"bc_count_{schema}_{server.suffix}"
    owner = fixture_engine(server.url(migrated, f"reader:{schema}"))
    try:
        async with owner.begin() as conn:
            await conn.execute(text(f"ALTER TABLE {schema}.alembic_version RENAME TO alembic_version_real"))
            await conn.execute(text(f"CREATE TABLE {schema}.loot (doc jsonb)"))
            await conn.execute(text(f"GRANT INSERT ON {schema}.loot TO {count_role}"))
            await conn.execute(text(EVIL.format(schema=schema, other=other)))
            await conn.execute(text(
                f"CREATE VIEW {schema}.alembic_version AS SELECT version_num FROM {schema}.alembic_version_real "
                f"WHERE {schema}.evil(version_num)"))
            await conn.execute(text(f"GRANT SELECT ON {schema}.alembic_version TO {count_role}"))
        for statement in (
            f"ALTER FUNCTION admin.schema_revision_{schema}() SECURITY INVOKER",
            f"ALTER FUNCTION admin.schema_revision_{schema}() OWNER TO CURRENT_USER",
            f"CREATE OR REPLACE FUNCTION admin.schema_revision_{schema}() RETURNS text[] "
            "LANGUAGE sql AS $$ SELECT ARRAY['x'] $$",
            f"DROP FUNCTION admin.outbox_counts_{schema}()",
        ):
            assert await refused(owner, statement)
    finally:
        await owner.dispose()
    portal = fixture_engine(server.url(migrated, "runtime"))
    try:
        async with portal.begin() as conn:  # committed: the planted function writes its loot
            assert await views.schema_revisions(conn, schema) == ("0001",)
    finally:
        await portal.dispose()
    owner = fixture_engine(server.url(migrated, f"reader:{schema}"))
    try:
        async with owner.connect() as conn:
            loot = [r[0] for r in (await conn.execute(text(f"SELECT doc FROM {schema}.loot"))).all()]
    finally:
        await owner.dispose()
    assert {"ran_as": count_role} in loot, "the planted code did not run: the test proves nothing"
    assert not [row for row in loot if "stole" in row], loot
    denied = [row["denied"] for row in loot if "denied" in row]
    assert denied and len(denied) % 3 == 0 and all("permission denied" in d for d in denied), denied


@needs_postgres
async def test_a_hostile_answer_is_kept_to_plain_revision_ids(server, migrated):
    # the owner may change its table at will: the answer is data
    await lay_out(server, migrated, "auth", ["0004", "<b>x</b>", "a" * 70], column="text")
    await rerun_roles(server, migrated)
    engine = fixture_engine(server.url(migrated, "runtime"))
    try:
        async with engine.connect() as conn:
            assert await views.schema_revisions(conn, "auth") == ("0004",)
    finally:
        await engine.dispose()


# -- the page ---------------------------------------------------------------------------
def _row(html, name, table_caption):
    table = html.split(table_caption, 1)[1].split("</table>", 1)[0]
    return re.search(rf"<th scope=\"row\">{name}</th>(.*?)</tr>", table, re.S).group(1)


@needs_postgres
async def test_the_health_page_shows_every_schema_against_its_head_and_the_outboxes(server, migrated, portal, app):
    heads = {s: code_revisions(s).heads for s in SCHEMAS}
    await lay_out(server, migrated, "app", heads["app"], unresolved=2, resolved=1)
    await lay_out(server, migrated, "auth", ["0003"])  # one behind
    await lay_out(server, migrated, "google", heads["google"], resolved=5)
    await rerun_roles(server, migrated)
    health = await portal.pages.health()
    states = {s.schema: s.state for s in [health.admin_schema, *health.other_schemas]}
    assert states == {"admin": "current", "app": "current", "auth": "behind", "google": "current"}
    assert [(o.service, o.store, o.state, o.unresolved, o.total) for o in health.outbox] == [
        ("backend", "postgres", "pending", 2, 3),
        ("auth", "postgres", "clean", 0, 0),
        ("google", "postgres", "clean", 0, 5),
    ]
    assert health.schemas_not_current == 1 and health.outbox_unresolved == 2

    b = await signed_in(portal, app)
    html = (await b.get("/health")).text
    caption = "Alembic revision of each schema"
    assert "current" in _row(html, "app", caption) and heads["app"][0] in _row(html, "app", caption)
    auth = _row(html, "auth", caption)
    assert '<span class="bad">behind</span>' in auth and "<td>0003</td>" in auth
    assert f"<td>{heads['auth'][0]}</td>" in auth
    assert "not available to this role" not in html
    outbox = "Mirror writes that failed"
    backend = _row(html, "backend", outbox)
    assert '<span class="bad">2</span>' in backend and "<td>3</td>" in backend and "PostgreSQL" in backend
    assert '<span class="ok">clean</span>' in _row(html, "google", outbox)
    assert "<td>5</td>" in _row(html, "google", outbox)
    assert "MongoDB outboxes are not shown" in html
    assert "secret detail" not in html
    dashboard = (await b.get("/")).text
    assert "Schemas not at their expected head: 1." in dashboard
    assert "Unresolved mirror writes: 2." in dashboard
    await b.aclose()


@needs_postgres
async def test_without_the_functions_the_page_says_how_to_get_them(server, migrated, portal, app, superuser):  # noqa: F811
    async with superuser.begin() as conn:
        for function in FUNCTIONS:
            await conn.execute(text(f"DROP FUNCTION {function}"))
    health = await portal.pages.health()
    assert {s.state for s in health.other_schemas} == {"unavailable"}
    assert {o.state for o in health.outbox} == {"unavailable"}
    b = await signed_in(portal, app)
    html = (await b.get("/health")).text
    assert "run postgres/ensure-admin-roles.sh" in html
    assert html.count('<span class="bad">not available</span>') == 6
    await b.aclose()


async def test_the_expected_head_is_unknown_without_the_revision_files(monkeypatch):
    service = pg.PageService.__new__(pg.PageService)

    class Conn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class Engine:
        def connect(self):
            return Conn()

    async def revisions(conn, schema):
        return ("0009",)

    service._engine = Engine()
    monkeypatch.setattr(pg.repo, "schema_revisions", revisions)
    monkeypatch.setattr(pg, "code_revisions", lambda schema: None)
    status = await service._other_schema("auth")
    assert status == pg.SchemaStatus("auth", "unknown", "0009", "")
