"""Respondent feedback: workspace admins post a status and/or message on a
submission; its respondent sees it (without staff identity) and may get an
email notice that never carries the update itself."""

import json
from unittest.mock import patch

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from tests.app.auth_helpers import access_token
from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from tests.app.controllers.data import invited_user, testUser, testUser1, testUser2

pytestmark = pytest.mark.asyncio

NAME = "field-name"
ORGANISATION = "Acme Hiring"
SECRET = "Please bring your passport on Monday"

workspace_admin = User(id=str(PydanticObjectId()), sub="workspace-admin@example.com")


def _form_payload():
    return {
        "title": "Job application",
        "builder_version": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": NAME,
                            "index": 0,
                            "title": "Your name",
                            "type": "short_text",
                            "properties": {},
                            "validations": {},
                        }
                    ]
                },
            }
        ],
    }


def _cookies(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def _settings_url(workspace, form_id):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/settings"


def _feedback_url(workspace, form_id, response_id):
    return (
        f"/api/v1/workspaces/{workspace.id}/forms/{form_id}"
        f"/submissions/{response_id}/feedback"
    )


@pytest.fixture()
async def form(workspace):
    workspace.title = ORGANISATION
    await container.workspace_repo().save(workspace)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=workspace_admin.id,
            roles=[WorkspaceRoles.ADMIN],
        )
    )
    form = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**_form_payload()), testUser
    )
    await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, testUser
    )
    return form


async def _enable(client, workspace, form, **extra):
    result = await client.patch(
        _settings_url(workspace, form.form_id),
        json={"respondentFeedbackEnabled": True, **extra},
        cookies=_cookies(testUser),
    )
    assert result.status_code == 200, result.text
    return result.json()


async def _submit(workspace, form, user=testUser2, anonymize=False):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={NAME: {"field": {"id": NAME}, "type": "text", "text": "Ada"}},
            anonymize=anonymize,
        ),
        user,
    )


class _Mailer:
    """Stands in for the auth service's notification endpoint."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def post(self, url, *args, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self.fail:
            raise RuntimeError("smtp down")
        return {"message": "queued"}


def _mailer(fail=False):
    mailer = _Mailer(fail)
    return mailer, patch.object(
        type(container.http_client()), "post", side_effect=mailer.post
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


async def test_settings_default_and_validation(client, workspace, form):
    body = await _enable(
        client, workspace, form, feedbackStatuses=["  Shortlisted ", "Hired"]
    )
    assert body["settings"]["respondentFeedbackEnabled"] is True
    assert body["settings"]["feedbackStatuses"] == ["Shortlisted", "Hired"]

    for statuses in (
        ["A"] * 2,
        ["Hired", "hired"],
        [""],
        ["x" * 41],
        [f"s{i}" for i in range(11)],
    ):
        result = await client.patch(
            _settings_url(workspace, form.form_id),
            json={"feedbackStatuses": statuses},
            cookies=_cookies(testUser),
        )
        assert result.status_code == 422, statuses

    stored = await container.workspace_form_repo().get_workspace_form_in_workspace(
        workspace.id, form.form_id
    )
    assert stored.settings.feedback_statuses == ["Shortlisted", "Hired"]


async def test_a_new_form_has_default_statuses_and_feedback_off(
    client, workspace, form
):
    stored = await container.workspace_form_repo().get_workspace_form_in_workspace(
        workspace.id, form.form_id
    )
    assert not stored.settings.respondent_feedback_enabled
    assert stored.settings.feedback_statuses == ["Under review", "Selected", "Rejected"]


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------


async def test_only_admins_switch_it_or_its_statuses(
    client, workspace, workspace_1, form
):
    """Turning feedback on decides whether respondents get emailed: like
    posting, it is for workspace admins and the owner."""
    url = _settings_url(workspace, form.form_id)
    for body in (
        {"respondentFeedbackEnabled": True},
        {"respondentFeedbackEnabled": False},
        {"feedbackStatuses": ["Shortlisted"]},
    ):
        collaborator = await client.patch(
            url, json=body, cookies=_cookies(invited_user)
        )
        assert collaborator.status_code == 403, body
        assert "admins" in collaborator.text
    # other settings stay open to members, as before
    pinned = await client.patch(
        url, json={"pinned": True}, cookies=_cookies(invited_user)
    )
    assert pinned.status_code == 200, pinned.text
    # the owner may
    settings = await _enable(client, workspace, form, feedbackStatuses=["Shortlisted"])
    assert settings["settings"]["respondentFeedbackEnabled"] is True
    assert settings["settings"]["feedbackStatuses"] == ["Shortlisted"]


async def test_who_may_post(client, workspace, workspace_1, form):
    await _enable(client, workspace, form)
    response = await _submit(workspace, form)
    url = _feedback_url(workspace, form.form_id, response.response_id)
    payload = {"status": "Selected"}

    assert (await client.post(url, json=payload)).status_code == 401
    # a collaborator sees feedback but may not post
    collaborator = await client.post(url, json=payload, cookies=_cookies(invited_user))
    assert collaborator.status_code == 403
    assert "admins" in collaborator.text
    # the respondent is not a member
    respondent = await client.post(url, json=payload, cookies=_cookies(testUser2))
    assert respondent.status_code == 403
    # an owner of another workspace naming their own workspace
    other = await client.post(
        _feedback_url(workspace_1, form.form_id, response.response_id),
        json=payload,
        cookies=_cookies(testUser1),
    )
    assert other.status_code in (403, 404)

    owner = await client.post(url, json=payload, cookies=_cookies(testUser))
    assert owner.status_code == 200, owner.text
    admin = await client.post(
        url, json={"message": "Welcome aboard"}, cookies=_cookies(workspace_admin)
    )
    assert admin.status_code == 200, admin.text
    body = admin.json()
    assert [e.get("status") for e in body["entries"]] == ["Selected", None]
    assert [e.get("message") for e in body["entries"]] == [None, "Welcome aboard"]
    assert body["entries"][0]["createdBy"] == testUser.id
    assert body["entries"][1]["createdByEmail"] == workspace_admin.sub
    assert body["entries"][1]["createdAt"]
    # a message-only update keeps the status
    assert body["currentStatus"] == "Selected"
    assert body["canPost"] is True


async def test_refused_payloads(client, workspace, form):
    response = await _submit(workspace, form)
    url = _feedback_url(workspace, form.form_id, response.response_id)
    cookies = _cookies(testUser)

    off = await client.post(url, json={"status": "Selected"}, cookies=cookies)
    assert off.status_code == 400
    assert "turned off" in off.text

    await _enable(client, workspace, form)
    for payload in ({}, {"status": "  ", "message": ""}):
        result = await client.post(url, json=payload, cookies=cookies)
        assert result.status_code == 422, payload
    unknown = await client.post(url, json={"status": "Hired"}, cookies=cookies)
    assert unknown.status_code == 422
    too_long = await client.post(url, json={"message": "x" * 5001}, cookies=cookies)
    assert too_long.status_code == 422
    missing = await client.post(
        _feedback_url(workspace, form.form_id, str(PydanticObjectId())),
        json={"status": "Selected"},
        cookies=cookies,
    )
    assert missing.status_code == 404

    # matched ignoring case, stored in the form's spelling
    ok = await client.post(url, json={"status": "selected"}, cookies=cookies)
    assert ok.status_code == 200
    assert ok.json()["entries"][0]["status"] == "Selected"

    # a status removed from the list can no longer be given
    await _enable(client, workspace, form, feedbackStatuses=["Hired"])
    removed = await client.post(url, json={"status": "Selected"}, cookies=cookies)
    assert removed.status_code == 422

    stored = await container.form_response_repo().get_response(response.response_id)
    assert len(stored.respondent_feedback) == 1


async def test_message_is_encrypted_at_rest(client, workspace, form):
    await _enable(client, workspace, form)
    response = await _submit(workspace, form)
    result = await client.post(
        _feedback_url(workspace, form.form_id, response.response_id),
        json={"status": "Under review", "message": SECRET},
        cookies=_cookies(testUser),
    )
    assert result.status_code == 200, result.text

    stored = await container.form_response_repo().get_response(response.response_id)
    entry = stored.respondent_feedback[0]
    assert isinstance(entry.message, bytes)
    assert SECRET.encode() not in entry.message
    assert SECRET not in json.dumps(stored.model_dump(mode="python"), default=repr)
    # the respondent's answers are untouched
    decrypted = container.form_response_service().decrypt_form_response(
        workspace_id=workspace.id, response=stored
    )
    assert decrypted.answers[NAME]["text"] == "Ada"
    assert decrypted.respondent_feedback[0].message == SECRET


async def test_a_submission_cannot_carry_feedback(workspace, form):
    forged = StandardFormResponseCamelModel(
        answers={NAME: {"field": {"id": NAME}, "type": "text", "text": "Eve"}},
        respondentFeedback=[{"status": "Selected", "message": "forged"}],
    )
    response = await container.workspace_form_service().submit_response(
        workspace.id, form.form_id, forged, testUser2
    )
    stored = await container.form_response_repo().get_response(response.response_id)
    assert not stored.respondent_feedback


# ---------------------------------------------------------------------------
# What the respondent sees
# ---------------------------------------------------------------------------


async def test_respondent_views_have_feedback_without_staff_identity(
    client, workspace, form
):
    await _enable(client, workspace, form)
    response = await _submit(workspace, form)
    url = _feedback_url(workspace, form.form_id, response.response_id)
    await client.post(
        url,
        json={"status": "Under review", "message": SECRET},
        cookies=_cookies(testUser),
    )
    await client.post(
        url, json={"status": "Selected"}, cookies=_cookies(workspace_admin)
    )

    def check(feedback, text):
        # the organisation, never the staff member
        assert feedback["author"] == ORGANISATION
        assert feedback["currentStatus"] == "Selected"
        assert [e["status"] for e in feedback["entries"]] == [
            "Under review",
            "Selected",
        ]
        assert feedback["entries"][0]["message"] == SECRET
        assert feedback["entries"][0]["createdAt"]
        for staff in (
            testUser.id,
            testUser.sub,
            workspace_admin.id,
            workspace_admin.sub,
        ):
            assert staff not in text
        assert "createdBy" not in text and "created_by" not in text
        assert '"respondentFeedback":' not in text

    mine = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}",
        cookies=_cookies(testUser2),
    )
    assert mine.status_code == 200, mine.text
    check(mine.json()["response"]["feedback"], mine.text)
    assert mine.json().get("feedback") is None

    receipt = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/by-uuid/"
        f"{response.submission_uuid}"
    )
    assert receipt.status_code == 200, receipt.text
    check(receipt.json()["response"]["feedback"], receipt.text)

    set_page(Page[StandardFormResponseCamelModel])
    set_params(Params(page=1, size=50))
    page = await container.form_response_service().get_user_submissions(
        workspace.id, testUser2
    )
    assert len(page.items) == 1
    item = page.items[0]
    dumped = json.dumps(
        item if isinstance(item, dict) else item.model_dump(mode="json", by_alias=True),
        default=str,
    )
    assert "Selected" in dumped
    assert SECRET not in dumped
    assert testUser.sub not in dumped and workspace_admin.sub not in dumped
    feedback = item["feedback"] if isinstance(item, dict) else item.feedback
    current = (
        feedback["currentStatus"]
        if isinstance(feedback, dict)
        else feedback.current_status
    )
    assert current == "Selected"

    # members get the staff view, with who posted each update
    staff = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}",
        cookies=_cookies(invited_user),
    )
    assert staff.status_code == 200
    body = staff.json()
    assert body["feedback"]["currentStatus"] == "Selected"
    assert body["feedback"]["entries"][1]["createdByEmail"] == workspace_admin.sub
    assert body["feedback"]["entries"][0]["message"] == SECRET
    assert body["feedback"]["canPost"] is False  # a collaborator
    assert body["response"].get("respondentFeedback") is None

    owner = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}",
        cookies=_cookies(testUser),
    )
    assert owner.json()["feedback"]["canPost"] is True
    # the panel's composer reads the form's statuses from the same payload
    settings_json = owner.json()["form"]["settings"]
    assert settings_json["respondentFeedbackEnabled"] is True
    assert settings_json["feedbackStatuses"] == ["Under review", "Selected", "Rejected"]


async def test_no_feedback_section_while_off_and_empty(client, workspace, form):
    response = await _submit(workspace, form)
    receipt = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/by-uuid/"
        f"{response.submission_uuid}"
    )
    assert receipt.json()["response"].get("feedback") is None

    await _enable(client, workspace, form)
    receipt = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/by-uuid/"
        f"{response.submission_uuid}"
    )
    feedback = receipt.json()["response"]["feedback"]
    assert feedback.get("entries") == [] and feedback.get("currentStatus") is None

    # turned off again after an update: what was said stays visible
    await client.post(
        _feedback_url(workspace, form.form_id, response.response_id),
        json={"status": "Rejected"},
        cookies=_cookies(testUser),
    )
    await client.patch(
        _settings_url(workspace, form.form_id),
        json={"respondentFeedbackEnabled": False},
        cookies=_cookies(testUser),
    )
    receipt = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/by-uuid/"
        f"{response.submission_uuid}"
    )
    assert receipt.json()["response"]["feedback"]["currentStatus"] == "Rejected"


async def test_anonymous_submission_feedback_is_read_with_the_number(
    client, workspace, form
):
    await _enable(client, workspace, form)
    response = await _submit(workspace, form, user=None, anonymize=True)
    mailer, patched = _mailer()
    with patched:
        result = await client.post(
            _feedback_url(workspace, form.form_id, response.response_id),
            json={"message": SECRET},
            cookies=_cookies(testUser),
        )
    assert result.status_code == 200
    assert result.json()["notifiesRespondent"] is False
    assert mailer.calls == []
    receipt = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/by-uuid/"
        f"{response.submission_uuid}"
    )
    assert receipt.json()["response"]["feedback"]["entries"][0]["message"] == SECRET


# ---------------------------------------------------------------------------
# Email notice
# ---------------------------------------------------------------------------


async def test_email_only_for_identified_submitters_of_identity_forms(
    client, workspace, form, monkeypatch
):
    monkeypatch.setattr(
        settings.auth_settings, "INTERNAL_NOTIFY_KEY", "backend-internal-key"
    )
    await _enable(client, workspace, form)
    identified = await _submit(workspace, form)
    anonymised = await _submit(workspace, form, anonymize=True)

    async def post(response, payload):
        mailer, patched = _mailer()
        with patched:
            result = await client.post(
                _feedback_url(workspace, form.form_id, response.response_id),
                json=payload,
                cookies=_cookies(testUser),
            )
        assert result.status_code == 200, result.text
        return result.json(), mailer.calls

    # identity not required: no mail
    body, calls = await post(identified, {"status": "Under review"})
    assert calls == [] and body["notifiesRespondent"] is False

    await _enable(client, workspace, form, requireVerifiedIdentity=True)
    body, calls = await post(identified, {"status": "Selected", "message": SECRET})
    assert body["notifiesRespondent"] is True
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == settings.auth_settings.BASE_URL + (
        "/notifications/submission-update"
    )
    assert call["headers"]["Authorization"].startswith("Bearer ")
    # only the backend may trigger notices: it proves itself with the shared key
    assert call["headers"]["X-Internal-Key"] == "backend-internal-key"
    assert call["json"] == {
        "recipient": testUser2.sub,
        "form_title": "Job application",
        "workspace_title": ORGANISATION,
        "link": settings.api_settings.CLIENT_URL.rstrip("/")
        + f"/{workspace.workspace_name}/submissions/{identified.response_id}",
    }
    sent = json.dumps(call)
    assert "Selected" not in sent and SECRET not in sent

    # each new update sends one notice
    _, calls = await post(identified, {"message": "Second"})
    assert len(calls) == 1 and "Second" not in json.dumps(calls[0])

    # anonymised: nobody to write to
    body, calls = await post(anonymised, {"status": "Rejected"})
    assert calls == [] and body["notifiesRespondent"] is False


async def test_mail_failure_never_fails_the_update(client, workspace, form):
    await _enable(client, workspace, form, requireVerifiedIdentity=True)
    response = await _submit(workspace, form)
    mailer, patched = _mailer(fail=True)
    with patched:
        result = await client.post(
            _feedback_url(workspace, form.form_id, response.response_id),
            json={"status": "Selected"},
            cookies=_cookies(testUser),
        )
    assert result.status_code == 200, result.text
    assert len(mailer.calls) == 1
    stored = await container.form_response_repo().get_response(response.response_id)
    assert [e.status for e in stored.respondent_feedback] == ["Selected"]


async def test_staff_member_who_is_also_respondent_sees_staff_view(
    client, workspace, form
):
    """A member's own submission is shown with the staff view."""
    await _enable(client, workspace, form)
    response = await _submit(workspace, form, user=invited_user)
    await client.post(
        _feedback_url(workspace, form.form_id, response.response_id),
        json={"status": "Selected"},
        cookies=_cookies(testUser),
    )
    result = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}",
        cookies=_cookies(invited_user),
    )
    assert result.json()["feedback"]["entries"][0]["createdBy"] == testUser.id
