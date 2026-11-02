"""How long a workspace's audit entries are kept: the owner's setting, its
audit entry, the daily purge applying each workspace's own figure and never
going inside the minimum, the reader stating the right figure, and the renamed
purge job still answering to its old name. Everything here is synthetic."""

import datetime as dt

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas import workspace_audit_event as E
from backend.app.schemas.workspace_audit_event import (
    NO_WORKSPACE,
    WorkspaceAuditEventDocument,
)
from backend.app.services.audit_log import catalog
from backend.app.services.audit_log import retention as R
from backend.app.services.audit_log.mode import OFF_CODE
from backend.config import settings
from backend.jobs import tasks
from tests.app.controllers.data import testUser, testUser1
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    fail_audit,
)

pytestmark = pytest.mark.asyncio

NOW = dt.datetime(2026, 11, 2, 4, 0, tzinfo=dt.timezone.utc)


@pytest.fixture(autouse=True)
def switched_on(monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_LOG_UI_ENABLED", True)


def url(workspace) -> str:
    return api(workspace) + "/audit-log/retention"


async def put(client, workspace, months, user=testUser):
    return await client.put(
        url(workspace), json={"months": months}, cookies=cookies(user)
    )


async def seed_aged(workspace_id, days, event=E.ACCESS_MODE_CHANGED):
    document = WorkspaceAuditEventDocument(
        id=RecordId(),
        workspace_id=workspace_id,
        user_id="u",
        event=event,
        created_at=NOW - dt.timedelta(days=days),
    )
    await container.workspace_audit_repo().record(document)
    return str(document.id)


async def remaining(workspace_id):
    rows = await container.workspace_audit_repo().page(workspace_id, 200)
    return {str(r.id) for r in rows}


async def choose(workspace, months):
    await container.workspace_repo().set_fields(
        workspace, {"audit_retention_months": months}
    )


# -- the choices -------------------------------------------------------------------------
def test_the_choices_the_minimum_and_the_default():
    assert R.CHOICES == (6, 12, 24, 60)
    assert R.MINIMUM_MONTHS == 6 and R.DEFAULT_MONTHS == 12
    assert R.days_of(12) == 365
    # a stored value that is not a choice is read as the default, never shorter
    for stored in (None, "", "x", 0, 1, 3, 5, 7, -12, 13, 1000):
        assert R.months_of(stored) == 12, stored
    for choice in R.CHOICES:
        assert R.months_of(choice) == choice
        assert R.months_of(str(choice)) == choice
    # whatever is asked, the period is never under the minimum
    assert R.days_of(1) >= R.MINIMUM_DAYS and R.days_of(None) >= R.MINIMUM_DAYS


def test_the_catalogue_lists_the_new_kind_once_in_the_security_area():
    assert E.AUDIT_RETENTION_CHANGED in E.SETTINGS_EVENTS
    assert catalog.area_of(E.AUDIT_RETENTION_CHANGED) == catalog.AREA_SECURITY


# -- the setting -------------------------------------------------------------------------
async def test_the_default_is_twelve_months_and_the_reader_states_the_workspace_figure(
    client: AsyncClient, workspace
):
    page = await client.get(api(workspace) + "/audit-log", cookies=cookies(testUser))
    assert page.json()["retentionDays"] == 365
    overview = (await client.get(url(workspace), cookies=cookies(testUser))).json()
    assert overview["months"] == 12 and overview["days"] == 365
    assert overview["options"] == [6, 12, 24, 60]
    assert overview["minimumMonths"] == 6 and overview["canChange"] is True

    changed = await put(client, workspace, 24)
    assert changed.status_code == 200, changed.text
    assert changed.json()["months"] == 24 and changed.json()["days"] == 730
    assert changed.json()["appliesAtNextPurge"] is False
    page = await client.get(api(workspace) + "/audit-log", cookies=cookies(testUser))
    assert page.json()["retentionDays"] == 730
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert stored.audit_retention_months == 24


async def test_shortening_says_it_applies_at_the_next_purge_and_deletes_nothing_now(
    client: AsyncClient, workspace
):
    old = await seed_aged(workspace.id, 300)
    shortened = await put(client, workspace, 6)
    assert shortened.status_code == 200, shortened.text
    assert shortened.json()["months"] == 6 and shortened.json()["appliesAtNextPurge"] is True
    assert old in await remaining(workspace.id)


@pytest.mark.parametrize("months", [0, 1, 3, 5, -6])
async def test_nothing_under_the_minimum_is_accepted(
    client: AsyncClient, workspace, months
):
    response = await put(client, workspace, months)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == R.BELOW_MINIMUM_CODE
    assert (await audit_events(workspace, E.AUDIT_RETENTION_CHANGED)) == []


@pytest.mark.parametrize("months", [7, 13, 36, 61, 1200])
async def test_only_the_four_choices_are_accepted(
    client: AsyncClient, workspace, months
):
    response = await put(client, workspace, months)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == R.INVALID_CODE
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert stored.audit_retention_months is None


async def test_a_wrong_type_is_refused(client: AsyncClient, workspace):
    for body in ({"months": "soon"}, {"months": 12.5}, {}):
        response = await client.put(url(workspace), json=body, cookies=cookies(testUser))
        assert response.status_code == 422, body


async def test_the_change_is_audited_with_the_months_before_and_after(
    client: AsyncClient, workspace
):
    assert (await put(client, workspace, 60)).status_code == 200
    assert (await put(client, workspace, 6)).status_code == 200
    # the same value again changes nothing and records nothing
    assert (await put(client, workspace, 6)).status_code == 200
    rows = await audit_events(workspace, E.AUDIT_RETENTION_CHANGED)
    assert [(r.previous_retention_months, r.retention_months) for r in rows] == [
        (12, 60),
        (60, 6),
    ]
    assert all(r.user_id == testUser.id for r in rows)

    # and the entry is on the page, as enum-like numbers only
    page = await client.get(
        api(workspace) + "/audit-log",
        cookies=cookies(testUser),
        params={"event": E.AUDIT_RETENTION_CHANGED},
    )
    entry = page.json()["entries"][0]
    assert entry["event"] == E.AUDIT_RETENTION_CHANGED and entry["area"] == "security"
    assert (entry["previousRetentionMonths"], entry["retentionMonths"]) == (60, 6)


async def test_a_change_that_cannot_be_recorded_is_not_made(
    client: AsyncClient, workspace, monkeypatch
):
    fail_audit(monkeypatch)
    response = await put(client, workspace, 6)
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "audit_unavailable"
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert stored.audit_retention_months is None


@pytest.mark.parametrize(
    "roles,status",
    [
        (["OWNER"], 200),
        (["ADMIN"], 403),
        (["PRIVACY_OFFICER"], 403),
        (["EDITOR"], 403),
        (["VIEWER"], 403),
        ([], 403),
    ],
)
async def test_only_an_owner_changes_it(client: AsyncClient, workspace, roles, status):
    member = await add_member(workspace, *roles)
    response = await put(client, workspace, 24, user=member)
    assert response.status_code == status, response.text
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert stored.audit_retention_months == (24 if status == 200 else None)


async def test_strangers_and_the_signed_out_cannot_change_or_read_it(
    client: AsyncClient, workspace
):
    assert (await put(client, workspace, 24, user=testUser1)).status_code == 403
    assert (
        await client.put(url(workspace), json={"months": 24})
    ).status_code == 401
    assert (await client.get(url(workspace))).status_code == 401
    assert (
        await client.get(url(workspace), cookies=cookies(testUser1))
    ).status_code == 403


@pytest.mark.parametrize(
    "roles,can_change",
    [(["OWNER"], True), (["ADMIN"], False), (["PRIVACY_OFFICER"], False)],
)
async def test_staff_who_read_the_log_see_the_figure_but_only_an_owner_can_change_it(
    client: AsyncClient, workspace, roles, can_change
):
    member = await add_member(workspace, *roles)
    response = await client.get(url(workspace), cookies=cookies(member))
    assert response.status_code == 200, response.text
    assert response.json()["canChange"] is can_change
    # another workspace's figure is not this one's
    await choose(workspace, 60)
    assert (await client.get(url(workspace), cookies=cookies(member))).json()["months"] == 60


async def test_the_setting_and_its_route_are_behind_the_switch(
    client: AsyncClient, workspace, monkeypatch
):
    monkeypatch.setattr(settings, "AUDIT_LOG_UI_ENABLED", False)
    for response in (
        await client.get(url(workspace), cookies=cookies(testUser)),
        await put(client, workspace, 24),
    ):
        assert response.status_code == 422, response.text
        assert response.json()["code"] == OFF_CODE
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert stored.audit_retention_months is None


# -- the purge ----------------------------------------------------------------------------
async def test_the_purge_applies_each_workspaces_own_period(
    client: AsyncClient, workspace, workspace_1
):
    await choose(workspace, 24)
    await choose(workspace_1, 6)
    # workspace: kept 24 months (730 days); workspace_1: kept 6 months (183 days)
    mine = {days: await seed_aged(workspace.id, days) for days in (100, 400, 700, 800)}
    theirs = {days: await seed_aged(workspace_1.id, days) for days in (100, 170, 200, 400)}

    deleted = await container.audit_retention().purge(NOW)
    assert deleted == 1 + 2

    assert await remaining(workspace.id) == {mine[100], mine[400], mine[700]}
    assert await remaining(workspace_1.id) == {theirs[100], theirs[170]}


async def test_a_workspace_that_never_chose_keeps_twelve_months_and_so_do_unowned_entries(
    client: AsyncClient, workspace, workspace_1
):
    await choose(workspace_1, 60)
    ids = {
        "default_young": await seed_aged(workspace.id, 360),
        "default_old": await seed_aged(workspace.id, 370),
        "long_old": await seed_aged(workspace_1.id, 1000),
        "long_older": await seed_aged(workspace_1.id, 1900),
    }
    # an entry that belongs to no workspace (a second-factor event of an account)
    unowned_old = await seed_aged(RecordId(NO_WORKSPACE), 400, E.TOTP_ENROLLED)
    unowned_young = await seed_aged(RecordId(NO_WORKSPACE), 30, E.TOTP_ENROLLED)

    await container.audit_retention().purge(NOW)

    assert await remaining(workspace.id) == {ids["default_young"]}
    assert await remaining(workspace_1.id) == {ids["long_old"]}
    assert await remaining(RecordId(NO_WORKSPACE)) == {unowned_young}
    assert unowned_old not in await remaining(RecordId(NO_WORKSPACE))


async def test_the_purge_never_deletes_inside_the_minimum_whatever_is_stored(
    client: AsyncClient, workspace
):
    young = await seed_aged(workspace.id, 100)
    just_inside = await seed_aged(workspace.id, 182)
    outside = await seed_aged(workspace.id, 184)
    # values no route would store: shorter than the minimum, zero, negative, a
    # number that is not a choice. Each reads as the default (a year).
    for stored in (1, 3, 5, 0, -6, 7):
        await choose(workspace, stored)
        await container.audit_retention().purge(NOW)
        assert {young, just_inside, outside} <= await remaining(workspace.id), stored
    # the shortest choice deletes only what is past six months
    await choose(workspace, 6)
    assert await container.audit_retention().purge(NOW) == 1
    assert await remaining(workspace.id) == {young, just_inside}


async def test_the_purge_changes_nothing_inside_the_period_and_counts_only(
    client: AsyncClient, workspace
):
    kept = [await seed_aged(workspace.id, d) for d in (0, 1, 200, 364)]
    assert await container.audit_retention().purge(NOW) == 0
    assert await remaining(workspace.id) == set(kept)


async def test_the_purge_without_an_audit_store_deletes_nothing():
    retention = R.AuditRetention(None, container.workspace_repo(), None)
    assert await retention.purge(NOW) == 0


# -- the job -------------------------------------------------------------------------------
async def test_the_job_runs_the_purge_and_reports_counts_only(
    client: AsyncClient, workspace
):
    await choose(workspace, 6)
    await seed_aged(workspace.id, 400)
    # the job body deletes by the real clock: an entry two years old is gone
    document = WorkspaceAuditEventDocument(
        id=RecordId(), workspace_id=workspace.id, user_id="u", event=E.ACCESS_MODE_CHANGED
    )
    document.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=800)
    await container.workspace_audit_repo().record(document)
    result = await tasks.audit_log_purge.func(0)
    assert result.endswith("deleted") and result.split()[0].isdigit()
    assert str(document.id) not in await remaining(workspace.id)


def test_the_renamed_job_keeps_its_schedule_and_still_answers_to_its_old_name():
    """A job queued under the old name before an upgrade is found by the worker
    (the old name resolves to the same task), and the daily schedule is the one
    task, not two."""
    from backend.jobs.app import app

    task = app.tasks["audit_log_purge"]
    assert "sso_audit_purge" in task.aliases
    assert app.tasks["sso_audit_purge"] is task
    scheduled = [
        key for key, p in app.periodic_registry.periodic_tasks.items() if p.task is task
    ]
    assert len(scheduled) == 1
    assert scheduled[0][1] == "audit_log_purge"
    assert all(
        p.task.name != "sso_audit_purge"
        for p in app.periodic_registry.periodic_tasks.values()
    )
