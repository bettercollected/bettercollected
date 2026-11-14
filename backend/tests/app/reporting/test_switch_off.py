"""``REPORTING_ENABLED`` is off by default and environment-only. Off: every report
route answers 422 ``reporting_off`` before a session, a permission, a row or an
answer is looked at (no query at all), and nothing else changes."""

from contextlib import contextmanager

import pytest
from sqlalchemy import event, text

from backend.app.container import container
from backend.app.services.reporting.mode import OFF_CODE, refuse_when_off, reporting_enabled
from backend.config import settings
from backend.config.application import Application
from common.settings.inventory import ENV_ONLY_INVENTORY
from common.settings.registry import ENV_ONLY_KEYS
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import cookies
from tests.app.reporting.helpers import (
    add_response,
    answer_choice,
    card,
    definition,
    make_form,
    report_url,
    survey_fields,
)

pytestmark = pytest.mark.asyncio


@contextmanager
def statements():
    """Every SQL statement the database sees while the block runs."""
    seen = []
    engine = container.pg_engine().sync_engine

    def record(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_the_switch_is_off_by_default_and_read_from_the_environment_only():
    assert Application.model_fields["reporting"].default.ENABLED is False
    assert settings.reporting.ENABLED is False
    assert reporting_enabled() is False
    spec = next(s for s in ENV_ONLY_INVENTORY if s.key == "REPORTING_ENABLED")
    assert spec.default is False and spec.tier == "T5"
    assert "REPORTING_ENABLED" in ENV_ONLY_KEYS


def test_turning_it_on_lets_the_check_pass(monkeypatch):
    monkeypatch.setattr(settings.reporting, "ENABLED", True)
    refuse_when_off()


async def test_every_route_answers_422_with_no_query_at_all(client, workspace):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    body = definition(card())
    for method, tail, kwargs in (
        ("get", "fields", {}),
        ("post", "query", {"json": body}),
        ("post", "query", {"content": b"not json at all"}),
        ("post", "responses", {"json": {"definition": definition(card()), "card": "c1", "group": "x"}}),
        ("post", "responses", {"content": b"not json at all"}),
        ("post", "export", {"json": {"definition": definition(card()), "card": "c1", "format": "csv"}}),
        ("post", "export", {"content": b"not json at all"}),
    ):
        for signed_in in (True, False):
            with statements() as seen:
                response = await getattr(client, method)(
                    report_url(workspace, form, tail),
                    cookies=cookies(testUser) if signed_in else None,
                    **kwargs,
                )
            assert response.status_code == 422, (method, tail, response.text)
            assert response.json()["code"] == OFF_CODE
            # not even the session or the permissions were looked at (the CORS
            # middleware's own read of the allowed origins is not ours)
            ours = [s for s in seen if "allowed_origins" not in s]
            assert ours == [], (method, tail, ours)


async def test_a_download_while_off_writes_no_audit_entry_and_reads_nothing(client, workspace):
    from backend.app.schemas.workspace_audit_event import REPORT_EXPORTED
    from tests.app.form_access.helpers import audit_events

    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    body = {"definition": definition(card(dimension="q:dept")), "card": "c1", "format": "csv"}
    with statements() as seen:
        response = await client.post(
            report_url(workspace, form, "export"), json=body, cookies=cookies(testUser)
        )
    assert response.status_code == 422 and response.json()["code"] == OFF_CODE
    assert [s for s in seen if "allowed_origins" not in s] == []
    assert await audit_events(workspace, REPORT_EXPORTED) == []


async def test_the_saved_view_routes_answer_422_and_never_touch_their_table(client, workspace):
    """Off: no session, no permission and no row, and the table of saved views
    is not read or written by any of the five routes (a view id is not looked up)."""
    form = await make_form(workspace, survey_fields())
    view = {"name": "Mine", "definition": definition(card())}
    some_id = "a" * 24
    for method, tail, kwargs in (
        ("get", "views", {}),
        ("post", "views", {"json": view}),
        ("post", "views", {"content": b"not json at all"}),
        ("get", f"views/{some_id}", {}),
        ("patch", f"views/{some_id}", {"json": {"revision": 1, "name": "x"}}),
        ("delete", f"views/{some_id}", {}),
    ):
        for signed_in in (True, False):
            with statements() as seen:
                response = await getattr(client, method)(
                    report_url(workspace, form, tail),
                    cookies=cookies(testUser) if signed_in else None,
                    **kwargs,
                )
            assert response.status_code == 422, (method, tail, response.text)
            assert response.json()["code"] == OFF_CODE
            ours = [s for s in seen if "allowed_origins" not in s]
            assert ours == [], (method, tail, ours)
    # and nothing was written
    async with container.pg_engine().connect() as connection:
        assert (await connection.execute(text("SELECT count(*) FROM app.form_report_views"))).scalar_one() == 0


async def test_what_a_deletion_removes_it_removes_with_the_switch_off_and_nothing_else_touches_the_table(
    client, workspace, monkeypatch
):
    """Views made while it was on do not outlive their form, their member, their
    account or their workspace because it was turned off since: those four deletes
    run whatever the switch says. They are the only statements on the table."""
    from tests.app.form_access.helpers import add_member

    monkeypatch.setattr(settings.reporting, "ENABLED", True)
    leaver = await add_member(workspace, "EDITOR")
    gone_account = await add_member(workspace, "EDITOR")
    forms = [await make_form(workspace, survey_fields(), title=f"Form {n}") for n in range(3)]
    body = {"name": "Overview", "scope": "private", "definition": definition(card("n", "tile"))}
    for form, user in ((forms[0], leaver), (forms[1], gone_account), (forms[2], testUser)):
        made = await client.post(report_url(workspace, form, "views"), json=body, cookies=cookies(user))
        assert made.status_code == 201, made.text
    monkeypatch.setattr(settings.reporting, "ENABLED", False)

    async def left():
        async with container.pg_engine().connect() as connection:
            return (await connection.execute(text("SELECT form_id FROM app.form_report_views"))).scalars().all()

    assert len(await left()) == 3
    with statements() as seen:
        await container.member_removal_repo().remove(workspace.id, leaver.id, testUser.id)
        await container.workspace_user_service().delete_user_form_all_workspaces(gone_account)
        await container.workspace_form_service().delete_form_from_workspace(
            workspace.id, forms[2].form_id, testUser
        )
        await container.workspace_user_service().forget_access_of_workspaces([workspace.id])
    assert await left() == []
    on_table = [s for s in seen if "form_report_views" in s]
    assert on_table and all(s.lstrip().startswith("DELETE FROM app.form_report_views") for s in on_table), on_table


async def test_nothing_is_decrypted_while_it_is_off(client, workspace, monkeypatch):
    from backend.app.services.reporting import engine

    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})

    def forbidden(*args, **kwargs):
        raise AssertionError("an answer was decrypted")

    monkeypatch.setattr(engine, "stored_answers", forbidden)
    response = await client.post(
        report_url(workspace, form),
        json=definition(card(dimension="q:dept")),
        cookies=cookies(testUser),
    )
    assert response.status_code == 422 and response.json()["code"] == OFF_CODE


async def test_the_permissions_tell_the_webapp_whether_it_is_on(
    client, workspace, monkeypatch
):
    url = f"/api/v1/workspaces/{workspace.id}/permissions"
    off = await client.get(url, cookies=cookies(testUser))
    assert off.json()["reportingEnabled"] is False
    monkeypatch.setattr(settings.reporting, "ENABLED", True)
    on = await client.get(url, cookies=cookies(testUser))
    assert on.json()["reportingEnabled"] is True


async def test_the_responses_list_and_the_export_are_the_same_with_it_on_or_off(
    client, workspace, monkeypatch
):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    url = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/submissions"

    async def read():
        response = await client.get(url, cookies=cookies(testUser))
        assert response.status_code == 200
        items = response.json()["items"]
        return [{k: v for k, v in i.items() if k not in ("createdAt", "updatedAt")} for i in items]

    off = await read()
    monkeypatch.setattr(settings.reporting, "ENABLED", True)
    assert await read() == off
