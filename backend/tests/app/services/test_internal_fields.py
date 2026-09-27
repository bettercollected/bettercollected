"""Internal ("for office use only") fields: hidden from respondents, filled in
by workspace members on each submission afterwards."""

import json

import pytest
from common.models.standard_form import StandardForm
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.internal_fields import internal_field_ids
from tests.app.controllers.data import invited_user, testUser, testUser1, testUser2

pytestmark = pytest.mark.asyncio

NAME = "field-name"
REFERENCE = "field-reference"
STATUS = "field-status"
REVIEWER = "field-reviewer"


def _field(field_id, index, title, field_type="short_text", internal=None, **extra):
    field = {
        "id": field_id,
        "index": index,
        "title": title,
        "type": field_type,
        "properties": {},
        "validations": {},
    }
    if internal is not None:
        field["internal"] = internal
    field.update(extra)
    return field


def _form_payload():
    return {
        "title": "Intake",
        "builder_version": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {
                    "fields": [
                        _field(NAME, 0, "Your name"),
                        _field(
                            REFERENCE,
                            1,
                            "Reference number",
                            internal=True,
                            validations={"required": True},
                        ),
                    ]
                },
            },
            {
                # A page holding nothing but internal fields: respondents
                # must not even see an empty page for it.
                "id": "page-2",
                "index": 1,
                "type": "slide",
                "properties": {
                    "fields": [
                        _field(
                            STATUS,
                            0,
                            "Status",
                            "multiple_choice",
                            internal=True,
                        ),
                        _field(REVIEWER, 1, "Reviewer", internal=True),
                    ]
                },
            },
        ],
    }


@pytest.fixture()
async def internal_form(workspace):
    form = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**_form_payload()), testUser
    )
    await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, testUser
    )
    return form


@pytest.fixture()
async def respondent_response(workspace, internal_form):
    """A submission by testUser2 — a pure respondent, not a workspace member."""
    return await container.workspace_form_service().submit_response(
        workspace.id,
        internal_form.form_id,
        StandardFormResponseCamelModel(
            answers={NAME: {"field": {"id": NAME}, "type": "text", "text": "Ada"}},
            anonymize=False,
        ),
        testUser2,
    )


def _cookies(user):
    token = container.jwt_service().encode(user)
    return {"Authorization": token, "RefreshToken": token}


def _all_field_ids(form_json):
    ids = []
    for slide in form_json.get("fields") or []:
        ids.append(slide.get("id"))
        for field in (slide.get("properties") or {}).get("fields") or []:
            ids.append(field.get("id"))
    return ids


# ---------------------------------------------------------------------------
# Form definitions never reach respondents
# ---------------------------------------------------------------------------


async def test_public_form_payload_has_no_internal_fields(
    client, workspace, internal_form
):
    url = f"/api/v1/workspaces/{workspace.id}/forms/{internal_form.form_id}"
    public = await client.get(url, params={"published": "true"})
    assert public.status_code == 200
    body = public.json()
    assert _all_field_ids(body) == ["page-1", NAME]
    assert '"internal": true' not in json.dumps(body)
    assert "Reference number" not in json.dumps(body)

    # A signed-in respondent (not a member) gets the same stripped form.
    as_respondent = await client.get(
        url, params={"published": "true"}, cookies=_cookies(testUser2)
    )
    assert _all_field_ids(as_respondent.json()) == ["page-1", NAME]


async def test_members_get_the_internal_fields(workspace, internal_form):
    form = await container.form_service().get_form_by_id(
        workspace_id=workspace.id,
        form_id=internal_form.form_id,
        user=testUser,
        published=True,
    )
    fields = form["fields"] if isinstance(form, dict) else form.fields
    assert len(fields) == 2


async def test_public_form_listing_and_search_strip_internal_fields(
    client, workspace, internal_form
):
    listing = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms", params={"published": "true"}
    )
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert items and all(_all_field_ids(i) == ["page-1", NAME] for i in items)

    search = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/search",
        params={"query": "Intake", "published": "true"},
        cookies=_cookies(testUser2),
    )
    assert search.status_code == 200
    assert search.json() and all(
        _all_field_ids(i) == ["page-1", NAME] for i in search.json()
    )


async def test_versioned_form_for_respondents_is_stripped(workspace, internal_form):
    form = await container.form_service().get_form_by_version(
        workspace_id=workspace.id,
        form_id=internal_form.form_id,
        version=1,
        user=testUser2,
    )
    assert internal_field_ids(form) == set()
    member_view = await container.form_service().get_form_by_version(
        workspace_id=workspace.id,
        form_id=internal_form.form_id,
        version=1,
        user=testUser,
    )
    assert internal_field_ids(member_view) == {REFERENCE, STATUS, REVIEWER}


# ---------------------------------------------------------------------------
# Logic may not depend on internal fields
# ---------------------------------------------------------------------------


async def test_saving_logic_that_depends_on_an_internal_field_is_refused(
    client, workspace, internal_form
):
    payload = _form_payload()
    payload["fields"][0]["properties"]["fields"][0]["properties"]["logic"] = {
        "action": "SHOW",
        "operator": "AND",
        "conditions": [{"fieldId": REFERENCE, "comparison": "is_not_empty"}],
    }
    with pytest.raises(HTTPException) as refused:
        await container.workspace_form_service().update_form(
            workspace.id, internal_form.form_id, StandardForm(**payload), testUser
        )
    assert refused.value.status_code == 400

    with pytest.raises(HTTPException):
        await container.workspace_form_service().create_form(
            workspace.id, StandardForm(**payload), testUser
        )

    http = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{internal_form.form_id}",
        data={"form_body": json.dumps(payload)},
        cookies=_cookies(testUser),
    )
    assert http.status_code == 400


async def test_the_builder_save_round_trips_the_internal_flag(
    client, workspace, internal_form
):
    response = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{internal_form.form_id}",
        data={"form_body": json.dumps(_form_payload())},
        cookies=_cookies(testUser),
    )
    assert response.status_code == 200
    stored = await container.form_repo().get_form_document_by_id(internal_form.form_id)
    assert internal_field_ids(stored) == {REFERENCE, STATUS, REVIEWER}


# ---------------------------------------------------------------------------
# Respondents cannot submit internal values
# ---------------------------------------------------------------------------


async def test_respondent_submission_with_internal_answers_is_rejected(
    client, workspace, internal_form
):
    url = f"/api/v1/workspaces/{workspace.id}/forms/{internal_form.form_id}/response"
    disguised = {
        "answers": {
            REFERENCE: {"field": {"id": REFERENCE}, "type": "text", "text": "X-1"}
        }
    }
    response = await client.post(url, data={"response": json.dumps(disguised)})
    assert response.status_code == 400

    smuggled = {
        "answers": {},
        "internalAnswers": {REFERENCE: {"text": "X-1"}},
    }
    response = await client.post(url, data={"response": json.dumps(smuggled)})
    assert response.status_code == 400

    ok = await client.post(
        url,
        data={
            "response": json.dumps(
                {"answers": {NAME: {"field": {"id": NAME}, "text": "Ada"}}}
            )
        },
    )
    assert ok.status_code == 200


# ---------------------------------------------------------------------------
# Staff fill in internal answers
# ---------------------------------------------------------------------------


def _internal_url(workspace, form_id, response_id):
    return (
        f"/api/v1/workspaces/{workspace.id}/forms/{form_id}"
        f"/submissions/{response_id}/internal-answers"
    )


async def test_member_fills_in_internal_answers_with_audit_trail(
    client, workspace, internal_form, respondent_response
):
    url = _internal_url(
        workspace, internal_form.form_id, respondent_response.response_id
    )
    result = await client.patch(
        url,
        json={
            "answers": {
                REFERENCE: {"type": "text", "text": "REF-001"},
                STATUS: {"type": "choice", "choice": {"value": "Verified"}},
            }
        },
        cookies=_cookies(testUser),
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["internalAnswers"][REFERENCE]["text"] == "REF-001"
    assert body["internalAnswers"][REFERENCE]["field"] == {"id": REFERENCE}
    meta = body["internalAnswersMeta"][REFERENCE]
    assert meta["updated_by"] == testUser.id
    assert meta["updated_by_email"] == testUser.sub
    assert meta["updated_at"]

    # Encrypted at rest, like respondent answers.
    stored = await container.form_response_repo().get_response(
        respondent_response.response_id
    )
    assert isinstance(stored.internal_answers, (bytes, str))
    assert b"REF-001" not in (
        stored.internal_answers
        if isinstance(stored.internal_answers, bytes)
        else stored.internal_answers.encode()
    )
    # The respondent's own answers are untouched.
    decrypted = container.form_response_service().decrypt_form_response(
        workspace_id=workspace.id, response=stored
    )
    assert decrypted.answers[NAME]["text"] == "Ada"

    # A collaborator (write access to the form) edits and clears; each change
    # records its author.
    result = await client.patch(
        url,
        json={"answers": {REFERENCE: None, REVIEWER: {"text": "Grace"}}},
        cookies=_cookies(invited_user),
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert REFERENCE not in body["internalAnswers"]
    assert body["internalAnswers"][STATUS]["choice"]["value"] == "Verified"
    assert body["internalAnswers"][REVIEWER]["text"] == "Grace"
    assert body["internalAnswersMeta"][REFERENCE]["updated_by"] == invited_user.id
    assert body["internalAnswersMeta"][STATUS]["updated_by"] == testUser.id

    # The dashboard listing shows them to members.
    listing = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{internal_form.form_id}/submissions",
        cookies=_cookies(testUser),
    )
    assert listing.status_code == 200
    item = listing.json()["items"][0]
    assert item["internalAnswers"][REVIEWER]["text"] == "Grace"

    all_submissions = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{internal_form.form_id}/all-submissions",
        cookies=_cookies(testUser),
    )
    assert all_submissions.json()[0]["internalAnswers"][STATUS]["choice"] == {
        "value": "Verified"
    }


async def test_internal_answers_endpoint_authorization(
    client, workspace, workspace_1, internal_form, respondent_response
):
    url = _internal_url(
        workspace, internal_form.form_id, respondent_response.response_id
    )
    payload = {"answers": {REFERENCE: {"text": "nope"}}}

    unauthenticated = await client.patch(url, json=payload)
    assert unauthenticated.status_code == 401

    # The respondent who submitted it is not a member: no write access.
    respondent = await client.patch(url, json=payload, cookies=_cookies(testUser2))
    assert respondent.status_code == 403

    # A member of a different workspace naming their own workspace.

    other = await client.patch(
        _internal_url(
            workspace_1, internal_form.form_id, respondent_response.response_id
        ),
        json=payload,
        cookies=_cookies(testUser1),
    )
    assert other.status_code == 404

    # Only internal fields of this form can be written.
    not_internal = await client.patch(
        url, json={"answers": {NAME: {"text": "overwrite"}}}, cookies=_cookies(testUser)
    )
    assert not_internal.status_code == 400
    unknown = await client.patch(
        url, json={"answers": {"nope": {"text": "x"}}}, cookies=_cookies(testUser)
    )
    assert unknown.status_code == 400
    too_long = await client.patch(
        url,
        json={"answers": {REFERENCE: {"text": "x" * 20_000}}},
        cookies=_cookies(testUser),
    )
    assert too_long.status_code == 400

    stored = await container.form_response_repo().get_response(
        respondent_response.response_id
    )
    assert stored.internal_answers is None


async def test_respondents_never_see_internal_values(
    client, workspace, internal_form, respondent_response
):
    await container.form_response_service().update_internal_answers(
        workspace.id,
        internal_form.form_id,
        respondent_response.response_id,
        {REFERENCE: {"text": "REF-SECRET"}},
        testUser,
    )

    # "View my submission" as the respondent.
    mine = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/{respondent_response.response_id}",
        cookies=_cookies(testUser2),
    )
    assert mine.status_code == 200
    text = mine.text
    assert "REF-SECRET" not in text
    assert mine.json()["response"].get("internalAnswers") is None
    assert mine.json()["response"].get("internalAnswersMeta") is None
    assert _all_field_ids(mine.json()["form"]) == ["page-1", NAME]
    assert mine.json().get("internalFields") is None

    # The public submission-number receipt.
    receipt = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/by-uuid/"
        f"{respondent_response.submission_uuid}"
    )
    assert receipt.status_code == 200
    assert "REF-SECRET" not in receipt.text
    assert "Reference number" not in receipt.text

    # The respondent's own submissions listing.
    set_page(Page[StandardFormResponseCamelModel])
    set_params(Params(page=1, size=50))
    page = await container.form_response_service().get_user_submissions(
        workspace.id, testUser2
    )
    assert page.items
    for item in page.items:
        dumped = json.dumps(
            item if isinstance(item, dict) else item.model_dump(mode="json"),
            default=str,
        )
        assert "REF-SECRET" not in dumped

    # Members see the values and the current internal field definitions.
    staff = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/{respondent_response.response_id}",
        cookies=_cookies(testUser),
    )
    assert staff.status_code == 200
    body = staff.json()
    assert body["response"]["internalAnswers"][REFERENCE]["text"] == "REF-SECRET"
    assert [f["id"] for f in body["internalFields"]] == [REFERENCE, STATUS, REVIEWER]
    assert body["internalFields"][0]["validations"]["required"] is True


async def test_mcp_exposes_internal_fields_and_answers_to_staff_keys(
    client, workspace, internal_form, respondent_response
):
    from tests.app.controllers.test_mcp_server import _call_tool, _make_key, _tool_text

    await container.form_response_service().update_internal_answers(
        workspace.id,
        internal_form.form_id,
        respondent_response.response_id,
        {REFERENCE: {"text": "REF-9"}},
        testUser,
    )
    token = await _make_key(workspace.id, ["forms:read", "responses:read"])
    response = _tool_text(
        await _call_tool(
            client,
            token,
            "get_response",
            {"response_id": respondent_response.response_id},
        )
    )
    assert response["internalAnswers"][REFERENCE]["text"] == "REF-9"
    assert response["answers"][NAME]["text"] == "Ada"

    form = _tool_text(
        await _call_tool(client, token, "get_form", {"form_id": internal_form.form_id})
    )
    internal = [
        f["id"]
        for slide in form["fields"]
        for f in slide["properties"]["fields"]
        if f.get("internal")
    ]
    assert internal == [REFERENCE, STATUS, REVIEWER]
