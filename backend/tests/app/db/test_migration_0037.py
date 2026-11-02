"""Revision 0037 (form-level access): three new tables on top of 0035, constraints
that hold in the table itself, a downgrade that removes exactly them, and an
upgrade again afterwards. Throw-away database, as ``test_migrations``."""

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

NEW = ["form_access_grants", "member_group_members", "member_groups"]
WS_A, WS_B = "6ac000000000000000000001", "6ac000000000000000000002"


def _row(table: str, oid: str, **doc) -> str:
    keys = ", ".join(
        f"'{k}', " + (f"jsonb_build_object('$oid', '{v}')" if k == "workspace_id" or k == "group_id" else f"'{v}'")
        for k, v in doc.items()
    )
    return (
        f"INSERT INTO app.{table} (id, doc, _bc_checksum) VALUES ('{oid}', "
        f"jsonb_build_object('_id', jsonb_build_object('$oid', '{oid}'), {keys}), 'x') "
        "RETURNING id"
    )


def _grant(oid, workspace, form="form-1", subject="u1", subject_type="user"):
    return _row(
        "form_access_grants",
        oid,
        workspace_id=workspace,
        form_id=form,
        subject_type=subject_type,
        subject_id=subject,
        role="VIEWER",
    )


def _team(oid, workspace, key):
    return _row("member_groups", oid, workspace_id=workspace, name_key=key)


def _member(oid, group, workspace, user):
    return _row(
        "member_group_members", oid, group_id=group, workspace_id=workspace, user_id=user
    )


def _run(url, statement):
    return asyncio.run(_execute(url, statement))


def test_0037_is_on_the_one_chain():
    scripts = ScriptDirectory.from_config(_config("postgresql://unused"))
    assert scripts.get_revision("0037") is not None
    # a single head: no second branch beside it
    assert len(scripts.get_heads()) == 1


def test_upgrade_creates_the_three_tables_and_downgrade_removes_only_them(scratch_url):
    config = _config(scratch_url)
    command.upgrade(config, "0035")
    before = asyncio.run(_tables(scratch_url))
    assert not set(NEW) & set(before)

    command.upgrade(config, "0037")
    assert sorted(set(asyncio.run(_tables(scratch_url))) - set(before)) == NEW
    # exactly what the models declare, but for what a later revision adds (0038:
    # the audit log reader's columns and indexes)
    assert [
        d for d in asyncio.run(_diff(scratch_url)) if "workspace_audit_events" not in repr(d)
    ] == []

    command.downgrade(config, "0035")
    assert asyncio.run(_tables(scratch_url)) == before
    version = _run(scratch_url, "SELECT version_num FROM app.alembic_version")
    assert version == [("0035",)]

    # and it goes up again, with the tables empty
    command.upgrade(config, "head")
    assert asyncio.run(_diff(scratch_url)) == []
    assert _run(scratch_url, "SELECT count(*) FROM app.form_access_grants") == [(0,)]


def test_a_downgrade_with_rows_in_the_tables_drops_them_without_touching_anything_else(
    scratch_url,
):
    config = _config(scratch_url)
    command.upgrade(config, "0037")
    _run(scratch_url, _grant("a" * 24, WS_A))
    _run(scratch_url, _team("b" * 24, WS_A, "hr"))
    command.downgrade(config, "0035")
    assert not set(NEW) & set(asyncio.run(_tables(scratch_url)))
    assert "workspace_forms" in asyncio.run(_tables(scratch_url))


def test_the_grant_is_unique_per_workspace_form_and_subject(scratch_url):
    command.upgrade(_config(scratch_url), "0037")
    _run(scratch_url, _grant("a" * 24, WS_A))
    with pytest.raises(Exception, match="uq_form_access_grants_subject"):
        _run(scratch_url, _grant("b" * 24, WS_A))
    # another subject, another subject type, another form, another workspace: all fine
    _run(scratch_url, _grant("c" * 24, WS_A, subject="u2"))
    _run(scratch_url, _grant("d" * 24, WS_A, subject_type="key"))  # free text, on purpose
    _run(scratch_url, _grant("e" * 24, WS_A, form="form-2"))
    _run(scratch_url, _grant("f" * 24, WS_B))
    assert _run(scratch_url, "SELECT count(*) FROM app.form_access_grants") == [(5,)]


def test_team_names_are_unique_per_workspace(scratch_url):
    command.upgrade(_config(scratch_url), "0037")
    _run(scratch_url, _team("a" * 24, WS_A, "hr"))
    with pytest.raises(Exception, match="uq_member_groups_workspace_id_name_key"):
        _run(scratch_url, _team("b" * 24, WS_A, "hr"))
    _run(scratch_url, _team("c" * 24, WS_B, "hr"))


def test_a_member_is_in_a_team_once(scratch_url):
    command.upgrade(_config(scratch_url), "0037")
    team = "a" * 24
    _run(scratch_url, _member("1" * 24, team, WS_A, "u1"))
    with pytest.raises(Exception, match="uq_member_group_members_group_id_user_id"):
        _run(scratch_url, _member("2" * 24, team, WS_A, "u1"))
    _run(scratch_url, _member("3" * 24, team, WS_A, "u2"))


def test_the_spine_columns_are_computed_from_the_document(scratch_url):
    command.upgrade(_config(scratch_url), "0037")
    _run(scratch_url, _grant("a" * 24, WS_A, form="form-9", subject="u9", subject_type="group"))
    row = _run(
        scratch_url,
        "SELECT workspace_id, form_id, subject_type, subject_id FROM app.form_access_grants",
    )
    assert row == [(WS_A, "form-9", "group", "u9")]


def test_the_row_checks_refuse_a_bad_id(scratch_url):
    command.upgrade(_config(scratch_url), "0037")
    with pytest.raises(Exception, match="id_is_object_id"):
        _run(scratch_url, _grant("not-an-object-id", WS_A))
