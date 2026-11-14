"""Revision 0041 (the spam check's daily counts): the table, the constraints that
hold in the table itself, the spine columns filled from ``doc``, and a downgrade
that removes exactly it. Throw-away database, as ``test_migrations``."""

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

TABLE = "captcha_daily_counts"
WS = "6af000000000000000000021"
C1 = "6af0000000000000000000a1"


def _run(url, statement):
    return asyncio.run(_execute(url, statement))


def _count(oid, day="2026-11-14", form="f1"):
    return (
        f"INSERT INTO app.{TABLE} (id, doc, _bc_checksum) VALUES ('{oid}', "
        f"jsonb_build_object('_id', jsonb_build_object('$oid', '{oid}'), "
        f"'day', '{day}', 'workspace_id', '{WS}', 'form_id', '{form}', "
        f"'purpose', 'submit', 'outcome', 'verified', 'count', 3), 'x') RETURNING id"
    )


def test_0041_is_on_the_one_chain():
    scripts = ScriptDirectory.from_config(_config("postgresql://unused"))
    assert scripts.get_revision("0041") is not None
    assert len(scripts.get_heads()) == 1


def test_upgrade_adds_the_table_and_downgrade_removes_only_it(scratch_url):
    config = _config(scratch_url)
    command.upgrade(config, "0040")
    before = asyncio.run(_tables(scratch_url))
    assert TABLE not in before

    command.upgrade(config, "0041")
    assert sorted(set(asyncio.run(_tables(scratch_url))) - set(before)) == [TABLE]
    assert asyncio.run(_diff(scratch_url)) == []  # exactly what the models declare

    # the spine columns are read from the document
    _run(scratch_url, _count(C1))
    assert _run(
        scratch_url, f"SELECT day, workspace_id, form_id FROM app.{TABLE}"
    ) == [("2026-11-14", WS, "f1")]
    # the id is the document's, and an object id
    with pytest.raises(Exception, match="ck_captcha_daily_counts_id_matches_doc"):
        _run(
            scratch_url,
            f"INSERT INTO app.{TABLE} (id, doc, _bc_checksum) VALUES "
            f"('6af0000000000000000000a2', jsonb_build_object('_id', "
            f"jsonb_build_object('$oid', '{C1}')), 'x')",
        )
    with pytest.raises(Exception, match="ck_captcha_daily_counts_id_is_object_id"):
        _run(
            scratch_url,
            f"INSERT INTO app.{TABLE} (id, doc, _bc_checksum) VALUES "
            "('not-an-id', jsonb_build_object('_id', jsonb_build_object('$oid', 'not-an-id')), 'x')",
        )

    command.downgrade(config, "0040")
    assert asyncio.run(_tables(scratch_url)) == before

    command.upgrade(config, "head")
    assert asyncio.run(_diff(scratch_url)) == []
    assert _run(scratch_url, f"SELECT count(*) FROM app.{TABLE}") == [(0,)]
