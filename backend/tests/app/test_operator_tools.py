"""The operator commands read through the container's repositories, so they
follow the services' read source and write mode before, during and after the
move to Postgres: ``python -m backend.migrate jobs-sweep``, ``python -m
backend.custom_domain export-reference-map`` and ``python -m
backend.membership_duplicates``.

The read methods they use behave the same on both stores (parity), and a
routed repository reads them from the store its flags name, whatever the suite's
own mode (mongo, dual or postgres in CI). The identity group (workspaces,
memberships) is served from Postgres only since 4.1."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.cli_store import needs_mongo
from common.db import load_flags
from common.db.routing import RoutingRepository

WRITE_MODES = ("mongo", "dual", "postgres_primary_dual", "postgres")


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def response(response_id, **extra):
    return FormResponseDocument(
        id=PydanticObjectId(), form_id="f1", response_id=response_id, **extra
    )


def expiring():
    return [
        response(
            "r-date", expiration="2031-01-02T03:04:05.000Z", expiration_type="date"
        ),
        response(
            "r-days", expiration="2030-06-01T00:00:00.000Z", expiration_type="days"
        ),
        response(
            "r-forever",
            expiration="2030-06-01T00:00:00.000Z",
            expiration_type="forever",
        ),
        response("r-unset", expiration_type="days"),  # no expiration stored: skipped
        response("r-plain"),
    ]


SCHEDULES = [
    ("r-date", "2031-01-02T03:04:05.000Z"),
    ("r-days", "2030-06-01T00:00:00.000Z"),
]


def workspace(name, **extra):
    return WorkspaceDocument(
        id=PydanticObjectId(), title=name, workspace_name=name, owner_id="o", **extra
    )


def workspaces():
    return [
        workspace("a", custom_domain="Forms.Example.org."),
        workspace("b", custom_domain="b.example", custom_domain_disabled=False),
        workspace("c", custom_domain="c.example", custom_domain_disabled=True),
        workspace("d", custom_domain=""),
        workspace("e"),
    ]


def routed(group, mongo, postgres, read):
    return RoutingRepository(
        group=group,
        flags=load_flags({"DB_READ_SOURCE": read, "DB_WRITE_MODE": "dual"}),
        mongo=mongo,
        postgres=postgres,
    )


# ------------------------------------------------------------- parity and routing
async def test_expiration_schedules_are_the_same_on_both_stores(sessions):
    mongo = FormResponseRepository(container.crypto(), None, None)
    postgres = PostgresFormResponseRepository(sessions, None, None)
    for document in expiring():
        await document.save()
        await postgres.upsert(document)
    assert await mongo.list_expiration_schedules() == SCHEDULES
    assert await postgres.list_expiration_schedules() == SCHEDULES


@pytest.mark.parametrize("read", ["mongo", "postgres"])
async def test_jobs_sweep_reads_the_responses_from_the_read_source(sessions, read):
    """Each store holds a response the other lacks: the sweep schedules the
    one in the store the flags read from (DB_READ_SOURCE__responses)."""
    from backend.migrate.__main__ import schedule_expirations

    mongo = FormResponseRepository(container.crypto(), None, None)
    postgres = PostgresFormResponseRepository(sessions, None, None)
    await response(
        "only-mongo", expiration="2031-01-01T00:00:00.000Z", expiration_type="date"
    ).save()
    await postgres.upsert(
        response(
            "only-postgres",
            expiration="2031-01-01T00:00:00.000Z",
            expiration_type="date",
        )
    )
    scheduled = []

    async def schedule(item):
        scheduled.append(item.response_id)

    count = await schedule_expirations(
        routed("responses", mongo, postgres, read), schedule
    )
    assert count == 1 and scheduled == [f"only-{read}"]


async def test_jobs_sweep_schedules_through_the_jobs_backend(sessions, monkeypatch):
    """The whole command on the suite's own flags (mongo, dual or postgres in CI),
    with the jobs backend's in-memory connector: every expiring response the
    services can read gets one deletion job, and a second sweep adds none."""
    from procrastinate.testing import InMemoryConnector

    from backend import cli_store
    from backend.jobs.app import app as jobs_app
    from backend.migrate import __main__ as migrate

    for document in expiring():
        await container.form_response_repo().save(document)

    @asynccontextmanager
    async def booted(*groups):  # the suite's container is booted already
        assert groups == ("responses",)
        yield container

    monkeypatch.setattr(cli_store, "routed_repositories", booted)
    connector = InMemoryConnector()
    with jobs_app.replace_connector(connector):
        first = await migrate.jobs_sweep("postgres")
        again = await migrate.jobs_sweep("postgres")
    assert first["scheduled"] == again["scheduled"] == len(SCHEDULES)
    assert first["read_from"] == container.flags().read_source("responses").value
    jobs = list(connector.jobs.values())
    assert sorted(j["args"]["response_id"] for j in jobs) == ["r-date", "r-days"]


async def test_custom_domain_references(sessions):
    postgres = PostgresWorkspaceRepository(
        sessions, PostgresActionRepository(sessions, None)
    )
    rows = workspaces()
    for document in rows:
        await postgres.save(document)
    expected = sorted(
        [("Forms.Example.org.", str(rows[0].id)), ("b.example", str(rows[1].id))],
        key=lambda row: row[1],
    )
    assert await postgres.list_custom_domain_references() == expected


async def test_export_reference_map_reads_the_workspaces_from_postgres(
    sessions, monkeypatch, tmp_path
):
    from backend.custom_domain import __main__ as command

    postgres = PostgresWorkspaceRepository(
        sessions, PostgresActionRepository(sessions, None)
    )
    stored = workspace("p", custom_domain="P.Example.")
    await postgres.save(stored)

    class Container:
        def workspace_repo(self):
            return postgres

    @asynccontextmanager
    async def booted(*groups):
        assert groups == ("identity", "refdata")
        yield

    monkeypatch.setattr(command, "routed_repositories", booted)
    monkeypatch.setattr(command, "container", Container())
    out = tmp_path / "map.json"
    assert await command.export_reference_map(str(out)) == 0
    assert json.loads(out.read_text()) == {"p.example": str(stored.id)}


# ----------------------------------------------------------- which stores to open
@pytest.mark.parametrize("write", WRITE_MODES)
@pytest.mark.parametrize("read", ["mongo", "postgres"])
def test_mongo_is_opened_only_while_a_group_still_uses_it(read, write):
    try:
        flags = load_flags(
            {"DB_READ_SOURCE__responses": read, "DB_WRITE_MODE__responses": write}
        )
    except ValueError:
        pytest.skip("not a valid combination: the services refuse it too")
    expected = read == "mongo" or write != "postgres"
    assert needs_mongo(flags, ["responses"]) is expected
    # another group still on Mongo keeps it open for a command that uses both
    assert needs_mongo(flags, ["responses", "forms"]) is True


def test_mongo_is_not_opened_once_every_group_is_on_postgres():
    flags = load_flags({"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"})
    assert needs_mongo(flags, ["responses", "identity", "refdata"]) is False


# -------------------------------------------------------- membership duplicates
@pytest.mark.parametrize(
    "env",
    [
        {},
        {"DB_WRITE_MODE": "dual"},
        {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"},
    ],
)
def test_membership_duplicates_reads_postgres_only(monkeypatch, capsys, env):
    """The identity group has no Mongo store since 4.1: Mongo is never
    contacted, whatever the flags, and listed under ``skipped``."""
    from backend import membership_duplicates as command

    for name in ("DB_READ_SOURCE", "DB_WRITE_MODE"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert command.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {"skipped": ["mongo", "postgres"]}


async def test_membership_duplicates_reads_the_postgres_store(sessions):
    from sqlalchemy import text

    from backend import membership_duplicates as command
    from tests.conftest import TEST_DATABASE_URL

    """Postgres keeps one membership per workspace and user (revision 0011's
    unique index), so the report of a migrated store is empty."""
    assert await command.postgres_duplicates(TEST_DATABASE_URL) == []
    async with sessions() as session:
        index = (
            await session.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = 'app' "
                    "AND tablename = 'workspace_users' AND indexdef LIKE '%UNIQUE%'"
                    " AND indexdef LIKE '%user_id%'"
                )
            )
        ).scalar_one()
    assert index == "uq_workspace_users_workspace_user"
