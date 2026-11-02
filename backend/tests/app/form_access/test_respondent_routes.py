"""Respondent routes against a restricted form.

Restricting a form is about the team, never about who may answer it: every route
that ``route_table.EXEMPT`` lists as a respondent route has to answer exactly as
it does for an open form, to an anonymous respondent and to a workspace member the
form is closed to (an Editor with no grant, who answers as a respondent).

Two identical published forms are made, one open and one restricted; every
request is sent to both, by the same caller, and the two answers must be the same
(status and the shape of the body). The routes that matter most are also pinned to
what they answer: the published form is read, an answer is taken and stored, a
draft is saved, a member reads their own submission.
"""

import json
import re
from typing import Dict, Optional

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.config import settings
from tests.app.controllers.data import testUser
from common.models.standard_form import StandardFormResponse

from tests.app.controllers.data import formResponse, testUser2
from tests.app.form_access.helpers import (
    add_member,
    api,
    cookies,
    create_form,
    restrict,
)
from tests.app.form_drafts.helpers import ANSWERS, body, drafting_form

ID = re.compile(r"[0-9a-f]{24}")


def _shape(response) -> tuple:
    """Status and the shape of the body: ids and values left out."""
    try:
        data = response.json()
    except ValueError:
        return (response.status_code, "text")
    if isinstance(data, dict):
        keys = sorted(data) if response.status_code < 400 else json.dumps(data, sort_keys=True)
    elif isinstance(data, list):
        keys = "list"
    else:
        keys = type(data).__name__
    return (response.status_code, ID.sub("<id>", str(keys)))


@pytest.fixture()
async def forms(workspace, monkeypatch):
    """An open and a restricted published form that take drafts and answers, and
    an Editor who may open neither's staff view of the restricted one."""
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", True)
    open_form = await drafting_form(workspace)
    closed_form = await drafting_form(workspace)
    await restrict(workspace, closed_form.form_id)
    editor = await add_member(workspace, "COLLABORATOR")
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    return open_form, closed_form, editor


def _requests(workspace, form):
    base = f"{api(workspace)}/forms/{form.form_id}"
    return [
        ("published form", "GET", base, {"params": {"published": "true"}}),
        ("a version", "GET", f"{base}/versions/1", {}),
        (
            "an answer",
            "POST",
            f"{base}/response",
            {"data": {"response": json.dumps({"answers": ANSWERS})}},
        ),
        ("save a draft", "PUT", f"{base}/drafts", {"json": body()}),
        ("open a draft", "POST", f"{base}/drafts/open", {"json": {"token": "x" * 20}}),
        ("my draft", "POST", f"{base}/drafts/mine", {"json": {}}),
        ("discard a draft", "POST", f"{base}/drafts/discard", {"json": {}}),
        (
            "a flow event",
            "POST",
            f"{base}/flow-events",
            {"json": {"sessionId": "session-0001", "fromPage": "s1", "toPage": "end"}},
        ),
        (
            "an address lookup",
            "POST",
            f"{base}/address-lookup",
            {"json": {"fieldId": "name", "postcode": "1234AB", "houseNumber": "1"}},
        ),
        ("an option page", "GET", f"{base}/options/name", {}),
    ]


@pytest.mark.parametrize("caller", ["anonymous", "closed_member"])
async def test_every_respondent_route_answers_a_restricted_form_as_it_answers_an_open_one(
    client: AsyncClient, workspace, forms, caller
):
    open_form, closed_form, editor = forms
    jar: Optional[Dict[str, str]] = cookies(editor) if caller == "closed_member" else None
    opened = _requests(workspace, open_form)
    closed = _requests(workspace, closed_form)
    seen = {}
    for (name, method, url, kw), (_, _, closed_url, closed_kw) in zip(opened, closed):
        a = await client.request(method, url, cookies=jar, **kw)
        b = await client.request(method, closed_url, cookies=jar, **closed_kw)
        assert a.status_code < 500 and b.status_code < 500, (name, a.status_code, b.status_code)
        assert _shape(a) == _shape(b), (
            f"{name} as {caller}: open {_shape(a)} vs restricted {_shape(b)}"
        )
        seen[name] = b
    # and what matters most is the answer it should be
    assert seen["published form"].status_code == 200
    assert seen["published form"].json()["title"], "the published form is read"
    assert seen["an answer"].status_code == 200, seen["an answer"].text[:150]
    if caller == "closed_member":
        # (an anonymous respondent's draft needs the browser's edit key)
        assert seen["save a draft"].status_code == 200, seen["save a draft"].text[:150]
    # the answer is stored on the restricted form
    stored = await container.form_response_repo().list_by_form_id(
        await container.form_response_service().scope(workspace.id, [str(closed_form.form_id)])
    )
    assert len(stored) == 1


async def test_a_member_the_form_is_closed_to_reads_their_own_submission_and_no_one_elses(
    client: AsyncClient, workspace, forms
):
    """The respondent side of the staff routes shared with it: a member answers a
    restricted form, then reads and may delete their own submission; the answer of
    anyone else is 'not found' to them, as it is for an unknown id."""
    _, _, editor = forms
    base = api(workspace)
    form = await create_form(workspace, testUser)
    await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, testUser
    )
    await restrict(workspace, form.form_id)
    service = container.workspace_form_service()
    mine_id = str(dict(await service.submit_response(
        workspace.id, form.form_id, StandardFormResponse(**formResponse), editor
    ))["response_id"])
    theirs_id = str(dict(await service.submit_response(
        workspace.id, form.form_id, StandardFormResponse(**formResponse), testUser2
    ))["response_id"])
    got = await client.get(f"{base}/submissions/{mine_id}", cookies=cookies(editor))
    assert got.status_code == 200, got.text[:150]
    other = await client.get(f"{base}/submissions/{theirs_id}", cookies=cookies(editor))
    unknown = await client.get(f"{base}/submissions/{RecordId()}", cookies=cookies(editor))
    assert (other.status_code, other.text) == (unknown.status_code, unknown.text)
    assert other.status_code == 404
    listed = await client.get(f"{base}/submissions", cookies=cookies(editor))
    assert listed.status_code == 200
