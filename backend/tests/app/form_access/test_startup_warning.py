"""The startup notice for ``FORM_ACCESS_ENABLED`` off while restricted forms,
grants or teams are stored: counts only, no query with the switch on, and never
a reason to stop the start."""

import asyncio

import pytest
from loguru import logger

from backend.app.container import container
from backend.app.schemas.form_access_grant import ROLE_VIEWER
from backend.app.services.form_access import startup as notice
from backend.app.services.form_access.startup import log_if_form_access_data_stored
from tests.app.form_access.helpers import (
    add_member,
    grant,
    restrict,
    set_mode,
    team_with,
)
from tests.app.form_access.test_switch_and_memo import statements


@pytest.fixture()
def logged():
    """Every message the block logs, as (level, text)."""
    seen = []
    handler = logger.add(
        lambda message: seen.append(
            (message.record["level"].name, message.record["message"])
        ),
        level="DEBUG",
    )
    yield seen
    logger.remove(handler)


def warnings_in(seen):
    return [text for level, text in seen if level == "WARNING"]


async def run():
    return await log_if_form_access_data_stored(container.pg_sessionmaker())


async def test_off_with_a_restricted_form_it_warns_with_counts_only(
    switch_off, workspace, workspace_form, logged
):
    await restrict(workspace, workspace_form.form_id)
    member = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, member.id, ROLE_VIEWER)
    await team_with(workspace, member, name="Secret team name")

    counts = await run()

    assert counts == (1, 1, 1)
    (line,) = warnings_in(logged)
    assert "FORM_ACCESS_ENABLED is off" in line
    assert "1 restricted forms, 1 grants, 1 teams" in line
    assert "open to every member's workspace role" in line
    # counts only: no ids, no names
    for private in (
        workspace.id,
        str(workspace_form.form_id),
        member.id,
        "Secret team name",
    ):
        assert str(private) not in line


async def test_off_a_private_form_with_no_mode_counts_as_restricted(
    switch_off, workspace, workspace_form, logged
):
    await set_mode(workspace, workspace_form.form_id, hidden=True)

    assert await run() == (1, 0, 0)
    assert len(warnings_in(logged)) == 1


async def test_off_an_explicit_workspace_mode_is_not_restricted_even_if_private(
    switch_off, workspace, workspace_form, logged
):
    await set_mode(workspace, workspace_form.form_id, "workspace", hidden=True)

    assert await run() is None
    assert warnings_in(logged) == []


async def test_off_a_team_alone_is_enough_to_warn(
    switch_off, workspace, workspace_form, logged
):
    await team_with(workspace, name="Only a team")

    assert await run() == (0, 0, 1)
    assert len(warnings_in(logged)) == 1


async def test_off_with_nothing_stored_it_does_not_warn(
    switch_off, workspace, workspace_form, logged
):
    assert await run() is None
    assert warnings_in(logged) == []


async def test_on_it_does_not_warn_and_runs_no_query(
    switch_on, workspace, workspace_form, logged
):
    await restrict(workspace, workspace_form.form_id)

    with statements() as seen:
        assert await run() is None
    assert seen == []
    assert warnings_in(logged) == []


async def test_a_database_error_does_not_stop_the_start(
    switch_off, workspace, workspace_form, logged, monkeypatch
):
    await restrict(workspace, workspace_form.form_id)
    monkeypatch.setattr(
        notice,
        "_COUNTS",
        notice.text("SELECT count(*) FROM app.no_such_table_here"),
    )

    assert await run() is None
    assert warnings_in(logged) == []
    assert any(
        level == "DEBUG" and "startup count was skipped" in text
        for level, text in logged
    )


async def test_a_slow_database_is_given_up_on(
    switch_off, workspace, workspace_form, logged, monkeypatch
):
    await restrict(workspace, workspace_form.form_id)

    async def never(sessionmaker):
        await asyncio.sleep(30)

    monkeypatch.setattr(notice, "_read_counts", never)

    assert (
        await log_if_form_access_data_stored(
            container.pg_sessionmaker(), overall_timeout_s=0.05
        )
        is None
    )
    assert warnings_in(logged) == []


async def test_a_statement_that_overruns_is_cancelled_by_the_database(
    switch_off, workspace, workspace_form, logged, monkeypatch
):
    """The timeout is set inside the database, not only in Python."""
    monkeypatch.setattr(notice, "STATEMENT_TIMEOUT_MS", 50)
    monkeypatch.setattr(notice, "_COUNTS", notice.text("SELECT pg_sleep(2), 0, 0"))

    assert await run() is None
    assert any("startup count was skipped" in text for _, text in logged)


async def test_no_sessionmaker_is_not_an_error(switch_off):
    assert await log_if_form_access_data_stored(None) is None
