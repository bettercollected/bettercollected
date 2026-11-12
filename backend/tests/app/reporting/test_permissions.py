"""Who may run a report: ``response.read`` and ``analytics.read`` on the form.

The Privacy officer holds ``analytics.read`` but never ``response.read``, so
nothing derived from answers is theirs. A restricted form is the 404 of an
unknown form for a member it is closed to; a grant opens it."""

import pytest

from backend.app.schemas.form_access_grant import ROLE_REVIEWER, ROLE_VIEWER
from backend.app.container import container
from tests.app.controllers.data import testUser1
from tests.app.form_access.helpers import add_member, grant, restrict, team_with
from tests.app.reporting.helpers import (
    add_response,
    answer_choice,
    card,
    definition,
    make_form,
    query,
    survey_fields,
)

pytestmark = pytest.mark.asyncio

BODY = definition(card(dimension="q:dept"))


async def setup_form(workspace):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    return form


@pytest.mark.parametrize(
    "role,allowed",
    [
        ("OWNER", True),
        ("ADMIN", True),
        ("EDITOR", True),
        ("COLLABORATOR", True),
        ("REVIEWER", True),
        ("VIEWER", True),
        # analytics.read without response.read: never answers
        ("PRIVACY_OFFICER", False),
    ],
)
@pytest.mark.parametrize("tail,method", [("query", "post"), ("fields", "get")])
async def test_the_role_decides(client, workspace, reporting_on, role, allowed, tail, method):
    form = await setup_form(workspace)
    member = await add_member(workspace, role)
    response = await query(client, workspace, form, BODY, user=member, tail=tail, method=method)
    assert response.status_code == (200 if allowed else 403), response.text


async def test_a_privacy_officer_is_refused_before_anything_is_read(
    client, workspace, reporting_on, monkeypatch
):
    from backend.app.services.reporting import engine

    form = await setup_form(workspace)
    officer = await add_member(workspace, "PRIVACY_OFFICER")

    def forbidden(*args, **kwargs):
        raise AssertionError("an answer was decrypted")

    monkeypatch.setattr(engine, "stored_answers", forbidden)
    response = await query(client, workspace, form, BODY, user=officer)
    assert response.status_code == 403


async def test_a_privacy_officer_keeps_the_refusal_with_another_role_beside_it(
    client, workspace, reporting_on
):
    form = await setup_form(workspace)
    both = await add_member(workspace, "PRIVACY_OFFICER", "VIEWER")
    response = await query(client, workspace, form, BODY, user=both)
    assert response.status_code == 403


async def test_a_stranger_and_a_signed_out_caller_are_refused(
    client, workspace, reporting_on
):
    form = await setup_form(workspace)
    assert (await query(client, workspace, form, BODY, user=testUser1)).status_code in (403, 404)
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/report/query", json=BODY
    )
    assert response.status_code in (401, 403)


async def test_a_form_of_another_workspace_is_a_404(client, workspace, workspace_1, reporting_on):
    other = await make_form(workspace_1, survey_fields(), user=testUser1)
    response = await query(client, workspace, other, BODY)
    assert response.status_code == 404


async def test_an_unknown_form_is_a_404(client, workspace, reporting_on):
    ghost = type("F", (), {"form_id": "f" * 24})()
    response = await query(client, workspace, ghost, BODY)
    assert response.status_code == 404


async def test_a_restricted_form_is_a_404_to_a_member_it_is_closed_to(
    client, workspace, reporting_on, form_access_on
):
    form = await setup_form(workspace)
    await restrict(workspace, form.form_id)
    viewer = await add_member(workspace, "VIEWER")
    editor = await add_member(workspace, "EDITOR")
    ghost = type("F", (), {"form_id": "f" * 24})()
    unknown = await query(client, workspace, ghost, BODY, user=viewer)
    for member in (viewer, editor):
        for tail, method in (("query", "post"), ("fields", "get")):
            closed = await query(client, workspace, form, BODY, user=member, tail=tail, method=method)
            assert closed.status_code == 404
            assert closed.json() == unknown.json()


async def test_an_owner_and_an_admin_still_open_a_restricted_form(
    client, workspace, reporting_on, form_access_on
):
    form = await setup_form(workspace)
    await restrict(workspace, form.form_id)
    admin = await add_member(workspace, "ADMIN")
    assert (await query(client, workspace, form, BODY)).status_code == 200
    assert (await query(client, workspace, form, BODY, user=admin)).status_code == 200


async def test_a_grant_opens_a_restricted_form_and_only_that_one(
    client, workspace, reporting_on, form_access_on
):
    form = await setup_form(workspace)
    other = await setup_form(workspace)
    await restrict(workspace, form.form_id)
    await restrict(workspace, other.form_id)
    viewer = await add_member(workspace, "VIEWER")
    await grant(workspace, form.form_id, viewer.id, ROLE_VIEWER)
    assert (await query(client, workspace, form, BODY, user=viewer)).status_code == 200
    assert (await query(client, workspace, other, BODY, user=viewer)).status_code == 404


async def test_a_team_grant_opens_it_too(client, workspace, reporting_on, form_access_on):
    form = await setup_form(workspace)
    await restrict(workspace, form.form_id)
    viewer = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, viewer)
    await grant(workspace, form.form_id, team.id, ROLE_REVIEWER, subject_type="group")
    assert (await query(client, workspace, form, BODY, user=viewer)).status_code == 200


async def test_a_privacy_officer_with_a_grant_still_reads_no_answers(
    client, workspace, reporting_on, form_access_on
):
    form = await setup_form(workspace)
    await restrict(workspace, form.form_id)
    officer = await add_member(workspace, "PRIVACY_OFFICER")
    await grant(workspace, form.form_id, officer.id, ROLE_VIEWER)
    response = await query(client, workspace, form, BODY, user=officer)
    assert response.status_code in (403, 404)
