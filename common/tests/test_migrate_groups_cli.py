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
from common.db.migrate.cli import (
    build_parser,
    main,
    mongo_primary_groups,
    reconcile_to_mongo_refusal,
    select_collections,
    skipped_groups,
    write_mode_in,
)
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


# -- reconcile postgres->mongo only under postgres_primary_dual ----------------
PPD = {"DB_WRITE_MODE": "postgres_primary_dual", "DB_READ_SOURCE": "postgres"}


def test_reconcile_to_mongo_is_refused_unless_postgres_is_primary(capsys):
    """Under dual, Mongo deletes first and records no tombstone for a document
    that is not there, so a delete racing reconcile's Mongo insert could bring
    the record back: the CLI refuses before connecting to anything."""
    for env in (
        {},
        {"DB_WRITE_MODE": "dual"},
        {"DB_WRITE_MODE": "postgres", "DB_READ_SOURCE": "postgres"},
    ):
        with pytest.raises(SystemExit) as exit_:
            main(
                ["reconcile", "--direction", "postgres->mongo"],
                _target(),
                prog="python -m backend.migrate",
                env=env,
            )
        assert exit_.value.code == 2
        assert "postgres_primary_dual" in capsys.readouterr().err


def test_the_refusal_names_only_the_groups_not_on_postgres_primary_dual():
    env = {**PPD, "DB_WRITE_MODE__forms": "dual"}
    args = _args(
        "--group", "forms,refdata", "reconcile", "--direction", "postgres->mongo"
    )
    refusal = reconcile_to_mongo_refusal(args, _target(), env)
    assert refusal and "forms (dual)" in refusal and "refdata" not in refusal
    args = _args("--group", "refdata", "reconcile", "--direction", "postgres->mongo")
    assert reconcile_to_mongo_refusal(args, _target(), env) is None


def test_other_reconciles_and_dry_runs_are_not_refused():
    target = _target()
    dual = {"DB_WRITE_MODE": "dual"}
    assert reconcile_to_mongo_refusal(_args("reconcile"), target, dual) is None
    assert (
        reconcile_to_mongo_refusal(
            _args("reconcile", "--direction", "postgres->mongo", "--dry-run"),
            target,
            dual,
        )
        is None
    )
    assert (
        reconcile_to_mongo_refusal(
            _args("reconcile", "--direction", "postgres->mongo"), target, PPD
        )
        is None
    )


# -- groups served from Postgres only: never verified or reconciled ------------
def _pg_only_target():
    from dataclasses import replace

    return replace(_target(), postgres_only_groups=("refdata",))


BOTH_STORES = [
    ["verify"],
    ["reconcile"],
    ["reconcile", "--direction", "mongo->postgres"],
    ["reconcile", "--direction", "postgres->mongo"],
]


@pytest.mark.parametrize("command", BOTH_STORES, ids=" ".join)
def test_verify_and_reconcile_skip_postgres_only_groups_by_default(command):
    target = _pg_only_target()
    assert target.migrating_groups() == ["identity", "forms", "responses"]
    assert select_collections(_args(*command), target) == [
        "workspaces",
        "forms",
        "form_responses",
    ]
    assert skipped_groups(_args(*command), target) == ["refdata"]
    # the other commands still cover them: backfill is the import
    for other in (["backfill"], ["preflight"], ["status"]):
        assert select_collections(_args(*other), target) is None
        assert skipped_groups(_args(*other), target) == []


@pytest.mark.parametrize("command", BOTH_STORES, ids=" ".join)
@pytest.mark.parametrize(
    "selection",
    [
        ["--group", "refdata"],
        ["--group", "forms,refdata"],
        ["--collections", "allowed_origins"],
    ],
    ids=["group", "groups", "collection"],
)
def test_verify_and_reconcile_refuse_a_postgres_only_group_by_name(
    command, selection, capsys
):
    """Exit 2 before connecting to anything, naming the group; under
    postgres_primary_dual too, where the effective mode check used to read
    the global write mode for it and let it through."""
    for env in ({}, PPD):
        with pytest.raises(SystemExit) as exit_:
            main(
                selection + command,
                _pg_only_target(),
                prog="python -m backend.migrate",
                env=env,
            )
        assert exit_.value.code == 2
        err = capsys.readouterr().err
        assert "served from Postgres only: refdata" in err
        assert "backfill" in err


def test_a_postgres_only_group_can_still_be_backfilled():
    target = _pg_only_target()
    assert select_collections(_args("--group", "refdata", "backfill"), target) == [
        "allowed_origins"
    ]


def test_write_modes_are_the_4_0_stacks_as_the_operator_states_them():
    """``DB_WRITE_MODE__<group>`` wins over ``DB_WRITE_MODE`` (the group's name
    in any case); a group served from Postgres only is always on postgres,
    whatever the environment says; nothing set is no mode at all."""
    target = _pg_only_target()
    env = {"DB_WRITE_MODE": "dual", "DB_WRITE_MODE__Forms": " Postgres_Primary_Dual "}
    assert write_mode_in(target, env, "forms") == "postgres_primary_dual"
    assert write_mode_in(target, env, "identity") == "dual"
    assert write_mode_in(target, env, "refdata") == "postgres"
    assert write_mode_in(target, {}, "identity") is None
    assert write_mode_in(target, {"DB_WRITE_MODE": ""}, "identity") is None
    assert write_mode_in(target, {"DB_WRITE_MODE__forms": ""}, "forms") is None


def test_the_refusal_skips_postgres_only_groups_by_default():
    args = _args("reconcile", "--direction", "postgres->mongo")
    assert reconcile_to_mongo_refusal(args, _pg_only_target(), PPD) is None


def test_mongo_primary_groups_follow_the_write_mode():
    """reconcile --mongo-wins lets Mongo's copy replace a newer Postgres row
    only where the services write Mongo first by an explicit setting."""
    target = _target()
    assert mongo_primary_groups(target, {"DB_WRITE_MODE": "dual"}) == (
        target.migrating_groups()
    )
    mixed = {
        "DB_WRITE_MODE": "dual",
        "DB_WRITE_MODE__forms": "postgres_primary_dual",
        "DB_READ_SOURCE__forms": "postgres",
    }
    assert "forms" not in mongo_primary_groups(target, mixed)
    assert "identity" in mongo_primary_groups(target, mixed)
    assert mongo_primary_groups(target, {"DB_WRITE_MODE": "nonsense"}) == []


def test_missing_flags_make_no_group_mongo_primary():
    """load_flags defaults an unset DB_WRITE_MODE to mongo; that default must
    not let Mongo overwrite newer Postgres rows."""
    target = _target()
    assert mongo_primary_groups(target, {}) == []
    assert mongo_primary_groups(target, {"DB_WRITE_MODE": ""}) == []
    only = {"DB_WRITE_MODE__identity": "dual"}
    assert mongo_primary_groups(target, only) == ["identity"]
    pinned = {
        "DB_WRITE_MODE": "dual",
        "DB_WRITE_MODE__identity": "postgres_primary_dual",
        "DB_READ_SOURCE__identity": "postgres",
    }
    assert "identity" not in mongo_primary_groups(target, pinned)
    assert "forms" in mongo_primary_groups(target, pinned)


def test_mongo_wins_is_only_for_mongo_to_postgres(capsys):
    with pytest.raises(SystemExit) as exc:
        main(
            ["reconcile", "--direction", "postgres->mongo", "--mongo-wins", "--dry-run"],
            _target(),
            prog="python -m backend.migrate",
            env={"DB_WRITE_MODE": "postgres_primary_dual", "DB_READ_SOURCE": "postgres"},
        )
    assert exc.value.code == 2
    assert "--mongo-wins" in capsys.readouterr().err


def test_mongo_primary_groups_leave_out_the_postgres_only_groups():
    import dataclasses

    target = dataclasses.replace(_target(), postgres_only_groups=("identity",))
    assert "identity" not in mongo_primary_groups(target, {"DB_WRITE_MODE": "dual"})


# ---- commands that do not read MongoDB run without a MONGO_URI ----------------


def _target_without_mongo(**extras) -> Target:
    target = _target()
    return Target(
        schema=target.schema,
        tables=target.tables,
        progress=target.progress,
        mongo_uri="",
        mongo_db="unused",
        database_url="postgresql+asyncpg://unused:unused@127.0.0.1:1/unused",
        service=target.service,
        groups=target.groups,
        extras=extras,
    )


async def test_jobs_sweep_runs_without_a_mongo_uri(capsys):
    from common.db.migrate.cli import run

    async def sweep(backend):
        return {"backend": backend, "scheduled": 3}

    target = _target_without_mongo(jobs_sweep=sweep)
    assert await run(_args("jobs-sweep", "--backend", "postgres"), target) == 0
    assert '"scheduled": 3' in capsys.readouterr().out


@pytest.mark.parametrize("command", ["preflight", "backfill", "verify", "status"])
async def test_a_command_that_reads_mongo_says_so_without_a_mongo_uri(command, capsys):
    from common.db.migrate.cli import run

    target = _target_without_mongo()
    assert await run(_args(command), target) == 2
    err = capsys.readouterr().err
    assert command in err and "MONGO_URI is not set" in err


async def test_the_runner_opens_mongo_only_when_something_reads_it():
    from common.db.migrate.engine import MongoNotConfigured, Runner

    async with Runner(_target_without_mongo()) as runner:
        assert runner._mongo is None  # entering the runner never builds a client
        with pytest.raises(MongoNotConfigured):
            runner.collection("forms")
    async with Runner(
        Target(**{**_target_without_mongo().__dict__, "mongo_uri": "mongodb://127.0.0.1:1"})
    ) as runner:
        assert runner._mongo is None
        runner.collection("forms")  # builds the client; nothing connects until it is used
        assert runner._mongo is not None
