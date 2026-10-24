"""The Alembic revisions must create exactly the tables the models declare, and roll back clean.

Runs against a throw-away database created for the test (so the local
app-postgres roles and the CI service database are never touched), skipped
when DATABASE_URL is unset. Synchronous on purpose: Alembic's env.py drives its
own event loop.
"""

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import backend.db.models  # noqa: F401
from backend.db.base import SCHEMA, Base
from common.db.alembic_support import metadata_diff
from common.db.engine import normalise_url

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)
SERVICE_DIR = Path(__file__).resolve().parents[3]  # .../backend


def _with_database(url: str, database: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{database}"


async def _admin(url: str, statement: str) -> None:
    engine = create_async_engine(
        _with_database(url, "postgres"),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text(statement))
    finally:
        await engine.dispose()


async def _diff(url: str) -> list:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(metadata_diff, Base.metadata, SCHEMA)
    finally:
        await engine.dispose()


async def _tables(url: str) -> list[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = :s ORDER BY 1"
                ),
                {"s": SCHEMA},
            )
            return [r[0] for r in rows]
    finally:
        await engine.dispose()


@pytest.fixture
def scratch_url():
    base_url = normalise_url(os.environ["DATABASE_URL"])
    name = f"bc_migtest_{uuid.uuid4().hex[:10]}"
    asyncio.run(_admin(base_url, f'CREATE DATABASE "{name}"'))
    try:
        yield _with_database(base_url, name)
    finally:
        asyncio.run(_admin(base_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


def _config(url: str) -> Config:
    config = Config(str(SERVICE_DIR / "alembic.ini"))
    config.set_main_option(
        "script_location", str(SERVICE_DIR / "backend" / "migrations")
    )
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_upgrade_head_matches_the_models_and_downgrade_base_is_clean(scratch_url):
    config = _config(scratch_url)

    command.upgrade(config, "head")
    diffs = asyncio.run(_diff(scratch_url))
    assert diffs == [], f"models and migrations have drifted: {diffs}"
    created = asyncio.run(_tables(scratch_url))
    expected = sorted(t.name for t in Base.metadata.sorted_tables) + ["alembic_version"]
    assert created == sorted(expected)

    command.downgrade(config, "base")
    assert asyncio.run(_tables(scratch_url)) == ["alembic_version"]


def test_upgrade_is_idempotent(scratch_url):
    config = _config(scratch_url)
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # nothing to do, must not fail
    assert asyncio.run(_diff(scratch_url)) == []


async def _execute(url: str, statement: str):
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            return (await conn.execute(text(statement))).all()
    finally:
        await engine.dispose()


def _membership(oid: str) -> str:
    def ref(value):
        return f"jsonb_build_object('$oid', '{value}')"

    return (
        "INSERT INTO app.workspace_users (id, doc, _bc_checksum) VALUES "
        f"('{oid}', jsonb_build_object('_id', {ref(oid)}, 'workspace_id', "
        f"{ref('6ac000000000000000000001')}, 'user_id', "
        f"{ref('6ac000000000000000000002')}), 'x') RETURNING id"
    )


def test_duplicate_memberships_stop_0011_before_it_changes_anything(scratch_url):
    """Revision 0011's unique membership index refuses, loudly and before
    any change, while duplicates exist; nothing is deleted."""
    config = _config(scratch_url)
    command.upgrade(config, "0010")
    for oid in ("a" * 24, "b" * 24):
        asyncio.run(_execute(scratch_url, _membership(oid)))

    with pytest.raises(RuntimeError, match="membership_duplicates"):
        command.upgrade(config, "head")

    rows = asyncio.run(_execute(scratch_url, "SELECT id FROM app.workspace_users"))
    assert len(rows) == 2
    version = asyncio.run(
        _execute(scratch_url, "SELECT version_num FROM app.alembic_version")
    )
    assert version == [("0010",)]
    # resolved by hand: it goes through
    asyncio.run(
        _execute(
            scratch_url,
            f"DELETE FROM app.workspace_users WHERE id = '{'b' * 24}' RETURNING id",
        )
    )
    command.upgrade(config, "head")


def _memory(oid: str, user_id: str) -> str:
    return (
        "INSERT INTO app.ai_preference_memories (id, doc, _bc_checksum) VALUES "
        f"('{oid}', jsonb_build_object('_id', jsonb_build_object('$oid', '{oid}'), "
        "'workspace_id', jsonb_build_object('$oid', '6ac000000000000000000001'), "
        f"'user_id', '{user_id}'), 'x') RETURNING id"
    )


def test_duplicate_ai_memories_stop_0018_before_it_changes_anything(scratch_url):
    """Revision 0018's unique (workspace_id, user_id) index refuses, with counts
    only and before any change, while duplicates exist; nothing is deleted."""
    config = _config(scratch_url)
    command.upgrade(config, "0017")
    for oid in ("a" * 24, "b" * 24):
        asyncio.run(_execute(scratch_url, _memory(oid, "user-1")))
    asyncio.run(_execute(scratch_url, _memory("c" * 24, "user-2")))

    with pytest.raises(RuntimeError) as refused:
        command.upgrade(config, "head")
    message = str(refused.value)
    assert "1 (workspace_id, user_id) pairs held by 2 rows" in message
    assert "user-1" not in message and "a" * 24 not in message

    rows = asyncio.run(
        _execute(scratch_url, "SELECT id FROM app.ai_preference_memories")
    )
    assert len(rows) == 3
    version = asyncio.run(
        _execute(scratch_url, "SELECT version_num FROM app.alembic_version")
    )
    assert version == [("0017",)]
    # resolved by hand: it goes through, and the index holds from then on
    asyncio.run(
        _execute(
            scratch_url,
            f"DELETE FROM app.ai_preference_memories WHERE id = '{'b' * 24}' "
            "RETURNING id",
        )
    )
    command.upgrade(config, "head")
    with pytest.raises(Exception, match="uq_ai_preference_memories_workspace_user"):
        asyncio.run(_execute(scratch_url, _memory("d" * 24, "user-1")))


def _link(
    oid: str, form_id: str, workspace_id: str = "6ac000000000000000000001"
) -> str:
    return (
        "INSERT INTO app.workspace_forms (id, doc, _bc_checksum) VALUES "
        f"('{oid}', jsonb_build_object('_id', jsonb_build_object('$oid', '{oid}'), "
        f"'workspace_id', jsonb_build_object('$oid', '{workspace_id}'), "
        f"'form_id', '{form_id}', 'user_id', 'user-1'), 'x') RETURNING id"
    )


def test_duplicate_workspace_links_stop_0019_before_it_changes_anything(scratch_url):
    """Revision 0019's unique (workspace_id, form_id) index refuses, with counts
    only and before any change, while a form is linked twice to a workspace;
    nothing is deleted."""
    config = _config(scratch_url)
    command.upgrade(config, "0018")
    for oid in ("a" * 24, "b" * 24):
        asyncio.run(_execute(scratch_url, _link(oid, "form-1")))
    asyncio.run(_execute(scratch_url, _link("c" * 24, "form-2")))

    with pytest.raises(RuntimeError) as refused:
        command.upgrade(config, "head")
    message = str(refused.value)
    assert "1 (workspace_id, form_id) pairs linked by 2 rows" in message
    assert "HAVING count(*) > 1" in message  # the read-only query to find them
    assert "form-1" not in message and "a" * 24 not in message

    rows = asyncio.run(_execute(scratch_url, "SELECT id FROM app.workspace_forms"))
    assert len(rows) == 3
    version = asyncio.run(
        _execute(scratch_url, "SELECT version_num FROM app.alembic_version")
    )
    assert version == [("0018",)]
    # resolved by hand: it goes through, and the index holds from then on
    asyncio.run(
        _execute(
            scratch_url,
            f"DELETE FROM app.workspace_forms WHERE id = '{'b' * 24}' RETURNING id",
        )
    )
    command.upgrade(config, "head")
    with pytest.raises(Exception, match="uq_workspace_forms_workspace_form"):
        asyncio.run(_execute(scratch_url, _link("d" * 24, "form-1")))
    # another workspace may link the same form
    asyncio.run(
        _execute(scratch_url, _link("e" * 24, "form-1", "6ac000000000000000000009"))
    )
