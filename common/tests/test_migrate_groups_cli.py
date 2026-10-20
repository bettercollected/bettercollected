"""Group selection, the status summary and the id ranges of the migration CLI
(no database: the store-driven parts run in the backend suite)."""

import pytest
from sqlalchemy import Column, MetaData, Table, Text, select
from sqlalchemy.dialects import postgresql

from common.db.groups import (
    SERVICE_GROUPS,
    UnknownGroup,
    collections_of,
    parse_groups,
    validate_groups,
)
from common.db.migrate.cli import build_parser, main, select_collections
from common.db.migrate.cli import format_status
from common.db.migrate.engine import Target, id_range


def _table(name: str) -> Table:
    return Table(name, MetaData(), Column("id", Text, primary_key=True))


def _target(service="backend", groups=None) -> Target:
    names = ["workspaces", "forms", "form_responses", "allowed_origins"]
    return Target(
        schema="app",
        tables={n: _table(n) for n in names},
        progress=_table("migration_progress"),
        mongo_uri="mongodb://unused",
        mongo_db="unused",
        database_url="postgresql+asyncpg://unused/unused",
        service=service,
        groups=(
            groups
            if groups is not None
            else {
                "workspaces": "identity",
                "forms": "forms",
                "form_responses": "responses",
                "allowed_origins": "refdata",
            }
        ),
    )


def _args(*argv):
    return build_parser("python -m backend.migrate").parse_args(list(argv))


def test_group_values_are_split_lowered_and_deduplicated():
    assert parse_groups(["Forms,responses", "forms", " ai "]) == [
        "forms",
        "responses",
        "ai",
    ]
    assert parse_groups(None) == []


def test_an_unknown_group_names_the_valid_ones():
    with pytest.raises(UnknownGroup) as err:
        validate_groups(["forms", "nope"], SERVICE_GROUPS["backend"])
    message = str(err.value)
    assert "nope" in message
    for group in SERVICE_GROUPS["backend"]:
        assert group in message


def test_collections_of_keeps_the_map_order():
    groups = {"a": "x", "b": "y", "c": "x"}
    assert collections_of(groups, ["x"]) == ["a", "c"]


def test_group_selects_its_collections():
    target = _target()
    assert select_collections(_args("--group", "forms", "verify"), target) == ["forms"]
    assert select_collections(
        _args("--group", "responses,identity", "backfill"), target
    ) == ["workspaces", "form_responses"]
    assert select_collections(_args("verify"), target) is None
    assert select_collections(_args("--collections", "forms", "verify"), target) == [
        "forms"
    ]


def test_a_known_group_without_collections_is_refused():
    # "ai" is a backend group, but this target has no ai collection
    with pytest.raises(UnknownGroup, match="no collections"):
        select_collections(_args("--group", "ai", "verify"), _target())


def test_services_with_one_group_accept_only_it():
    target = _target(service="auth", groups={})
    assert target.group_names() == ["auth"]
    assert select_collections(_args("--group", "auth", "verify"), target) == list(
        target.tables
    )
    with pytest.raises(UnknownGroup, match="valid groups: auth"):
        select_collections(_args("--group", "forms", "verify"), target)


def test_cli_exits_2_on_an_unknown_group(capsys):
    with pytest.raises(SystemExit) as exit_:
        main(["--group", "nope", "verify"], _target(), prog="python -m backend.migrate")
    assert exit_.value.code == 2
    assert "valid groups: refdata, identity" in capsys.readouterr().err


def test_group_and_collections_are_exclusive(capsys):
    with pytest.raises(SystemExit):
        _args("--group", "forms", "--collections", "forms", "verify")


def test_status_json_flag():
    assert _args("status", "--json").json is True
    assert _args("status").json is False


def test_id_range_covers_the_gap_after_the_previous_batch():
    table = _table("t")

    def sql(clause) -> str:
        return str(
            select(table.c.id)
            .where(clause)
            .compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )

    assert "t.id <= 'b'" in sql(id_range(table, None, "b"))
    assert "t.id > 'a' AND t.id <= 'b'" in sql(id_range(table, "a", "b"))


def test_status_summary_names_counts_states_and_the_marker():
    report = {
        "service": "backend",
        "schema": "app",
        "marker": None,
        "outbox": {"mongo": 0, "postgres": 2},
        "groups": {
            "forms": {
                "collections": ["forms"],
                "last_verify": {
                    "verified_at": "2026-10-19T10:00:00+00:00",
                    "run_id": "r1",
                },
            },
        },
        "collections": {
            "forms": {
                "group": "forms",
                "mongo": 3,
                "postgres": 3,
                "backfill": {"state": "running", "stalled": True},
            }
        },
    }
    text = format_status(report)
    assert "marker: none" in text and "outbox: mongo=0 postgres=2" in text
    assert "group forms: last clean verify 2026-10-19T10:00:00+00:00 (run r1)" in text
    assert "forms: mongo=3 postgres=3 backfill=running (stalled)" in text
    report["marker"] = {
        "verified_at": "2026-10-19T11:00:00+00:00",
        "combined": True,
        "run_id": "r2",
        "code_version": "0.1.0+schema.0017",
    }
    assert "combined from group verifies" in format_status(report)
