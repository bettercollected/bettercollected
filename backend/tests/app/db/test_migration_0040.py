"""Revision 0040 (saved report views): the table on top of 0039, the constraints
that hold in the table itself, the spine columns filled from ``doc``, and a
downgrade that removes exactly it. Throw-away database, as ``test_migrations``."""

import asyncio

import pytest
from alembic import command
from alembic.script import ScriptDirectory

from tests.app.db.test_migrations import (  # noqa: F401 (scratch_url is a fixture)
    _config,
    _diff,
    _execute,
    _tables,
    scratch_url,
)

TABLE = "form_report_views"
WS = "6ae000000000000000000021"
V1 = "6ae0000000000000000000a1"


def _run(url, statement):
    return asyncio.run(_execute(url, statement))


def _view(oid, scope="private", owner="u1"):
    return (
        f"INSERT INTO app.{TABLE} (id, doc, _bc_checksum) VALUES ('{oid}', "
        f"jsonb_build_object('_id', jsonb_build_object('$oid', '{oid}'), "
        f"'workspace_id', jsonb_build_object('$oid', '{WS}'), 'form_id', 'f1', "
        f"'owner_id', '{owner}', 'scope', '{scope}', 'name', 'x'), 'x') RETURNING id"
    )


def test_0040_is_on_the_one_chain():
    scripts = ScriptDirectory.from_config(_config("postgresql://unused"))
    assert scripts.get_revision("0040") is not None
    assert scripts.get_revision("0040").down_revision == "0039"
    assert len(scripts.get_heads()) == 1


def test_upgrade_adds_the_table_and_downgrade_removes_only_it(scratch_url):
    config = _config(scratch_url)
    command.upgrade(config, "0039")
    before = asyncio.run(_tables(scratch_url))
    assert TABLE not in before

    command.upgrade(config, "0040")
    assert sorted(set(asyncio.run(_tables(scratch_url))) - set(before)) == [TABLE]
    assert asyncio.run(_diff(scratch_url)) == []  # exactly what the models declare

    # the spine columns are read from the document
    _run(scratch_url, _view(V1, scope="form", owner="u9"))
    assert _run(
        scratch_url,
        f"SELECT workspace_id, form_id, owner_id, scope FROM app.{TABLE}",
    ) == [(WS, "f1", "u9", "form")]
    # the id is the document's, and an object id
    with pytest.raises(Exception, match="ck_form_report_views_id_matches_doc"):
        _run(
            scratch_url,
            f"INSERT INTO app.{TABLE} (id, doc, _bc_checksum) VALUES "
            f"('6ae0000000000000000000a2', jsonb_build_object('_id', "
            f"jsonb_build_object('$oid', '{V1}')), 'x')",
        )
    with pytest.raises(Exception, match="ck_form_report_views_id_is_object_id"):
        _run(
            scratch_url,
            f"INSERT INTO app.{TABLE} (id, doc, _bc_checksum) VALUES "
            "('not-an-id', jsonb_build_object('_id', jsonb_build_object('$oid', 'not-an-id')), 'x')",
        )

    command.downgrade(config, "0039")
    assert asyncio.run(_tables(scratch_url)) == before

    command.upgrade(config, "head")
    assert asyncio.run(_diff(scratch_url)) == []
    assert _run(scratch_url, f"SELECT count(*) FROM app.{TABLE}") == [(0,)]
