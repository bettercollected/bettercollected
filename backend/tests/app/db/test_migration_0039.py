"""Revision 0039 (directory groups feeding teams): the link table, the
``scim_users.user_id`` column and its index on top of 0038, the constraint that
holds in the table itself, existing directory users getting the column filled,
and a downgrade that removes exactly this. Throw-away database, as
``test_migrations``."""

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

TABLE = "scim_group_team_links"
G1, G2 = "6ad000000000000000000001", "6ad000000000000000000002"
T1 = "6ad000000000000000000011"
WS = "6ad000000000000000000021"
U1 = "6ad000000000000000000031"


def _run(url, statement):
    return asyncio.run(_execute(url, statement))


def _link(oid, group, team):
    return (
        f"INSERT INTO app.{TABLE} (id, doc, _bc_checksum) VALUES ('{oid}', "
        f"jsonb_build_object('_id', jsonb_build_object('$oid', '{oid}'), "
        f"'group_id', jsonb_build_object('$oid', '{group}'), "
        f"'team_id', jsonb_build_object('$oid', '{team}'), "
        f"'workspace_id', jsonb_build_object('$oid', '{WS}')), 'x') RETURNING id"
    )


def test_0039_is_on_the_one_chain():
    scripts = ScriptDirectory.from_config(_config("postgresql://unused"))
    assert scripts.get_revision("0039") is not None
    assert len(scripts.get_heads()) == 1


def test_upgrade_adds_the_table_and_column_and_downgrade_removes_only_them(scratch_url):
    config = _config(scratch_url)
    command.upgrade(config, "0038")
    before = asyncio.run(_tables(scratch_url))
    assert TABLE not in before
    # a directory user from before: the column is filled by the upgrade
    _run(
        scratch_url,
        "INSERT INTO app.scim_users (id, doc, _bc_checksum) VALUES ("
        f"'{U1}', jsonb_build_object('_id', jsonb_build_object('$oid', '{U1}'), "
        f"'user_id', 'account-1', 'workspace_id', jsonb_build_object('$oid', '{WS}')), 'x') "
        "RETURNING id",
    )

    command.upgrade(config, "0039")
    assert sorted(set(asyncio.run(_tables(scratch_url))) - set(before)) == [TABLE]
    # exactly what the models declare, but for what 0040 and 0041 add (the saved report views, the spam check's counts)
    assert [
        d
        for d in asyncio.run(_diff(scratch_url))
        if "form_report_views" not in repr(d) and "captcha_daily_counts" not in repr(d)
    ] == []
    assert _run(scratch_url, "SELECT user_id FROM app.scim_users") == [("account-1",)]

    # one link per group; several groups may feed one team
    _run(scratch_url, _link("6ad0000000000000000000a1", G1, T1))
    _run(scratch_url, _link("6ad0000000000000000000a2", G2, T1))
    with pytest.raises(Exception, match="uq_scim_group_team_links_group_id"):
        _run(scratch_url, _link("6ad0000000000000000000a3", G1, T1))

    command.downgrade(config, "0038")
    assert asyncio.run(_tables(scratch_url)) == before
    assert _run(scratch_url, "SELECT count(*) FROM app.scim_users") == [(1,)]
    columns = _run(
        scratch_url,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'app' AND table_name = 'scim_users' AND column_name = 'user_id'",
    )
    assert columns == []

    command.upgrade(config, "head")
    assert asyncio.run(_diff(scratch_url)) == []
    assert _run(scratch_url, f"SELECT count(*) FROM app.{TABLE}") == [(0,)]
