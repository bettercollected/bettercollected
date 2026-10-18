"""Values that start with the ciphertext prefix ("v1:"): a plaintext one is
encrypted like any other (it used to be stored as is), stored ciphertext is
never encrypted twice, and a stored value that does not decrypt is read as
unreadable instead of failing the request."""

import json

import pytest
from common.models.standard_form import RespondentFeedback, StandardForm
from common.services.crypto_service import crypto_service

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from tests.app.controllers.data import testUser, testUser2
from tests.app.services.test_internal_fields import (  # noqa: F401 (fixtures)
    REVIEWER,
    internal_form,
    respondent_response,
)
from tests.app.services.test_respondent_feedback import (
    NAME,
    _cookies,
    _enable,
    _feedback_url,
    _form_payload,
)

pytestmark = pytest.mark.asyncio

PREFIXED = "v1:hello"


@pytest.fixture()
async def prefix_form(workspace):
    form = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**_form_payload()), testUser
    )
    await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, testUser
    )
    return form


async def _submit(workspace, form, text="Ada", user=testUser2):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={NAME: {"field": {"id": NAME}, "type": "text", "text": text}}
        ),
        user,
    )


async def _stored(response_id):
    return await container.form_response_repo().get_response(response_id)


def _open(workspace, form_id, value):
    return crypto_service.decrypt(
        workspace_id=workspace.id, form_id=form_id, data=value
    )


def _submission_url(workspace, response_id):
    return f"/api/v1/workspaces/{workspace.id}/submissions/{response_id}"


# ---------------------------------------------------------------------------
# A prefixed plaintext is encrypted and round-trips
# ---------------------------------------------------------------------------


async def test_a_feedback_message_starting_with_the_prefix_is_encrypted(
    client, workspace, prefix_form
):
    await _enable(client, workspace, prefix_form)
    response = await _submit(workspace, prefix_form)
    result = await client.post(
        _feedback_url(workspace, prefix_form.form_id, response.response_id),
        json={"message": PREFIXED},
        cookies=_cookies(testUser),
    )
    assert result.status_code == 200, result.text

    stored = (await _stored(response.response_id)).respondent_feedback[0].message
    assert isinstance(stored, bytes)
    assert stored != PREFIXED.encode() and b"hello" not in stored
    assert _open(workspace, prefix_form.form_id, stored) == PREFIXED.encode()

    for user in (testUser, testUser2):  # staff view, respondent view
        page = await client.get(
            _submission_url(workspace, response.response_id), cookies=_cookies(user)
        )
        assert page.status_code == 200, page.text
        body = page.json()
        feedback = (
            body["feedback"] if user is testUser else body["response"]["feedback"]
        )
        assert feedback["entries"][0]["message"] == PREFIXED


async def test_an_answer_starting_with_the_prefix_round_trips(
    client, workspace, prefix_form
):
    response = await _submit(workspace, prefix_form, text=PREFIXED)

    stored = await _stored(response.response_id)
    assert isinstance(stored.answers, bytes) and b"hello" not in stored.answers
    page = await client.get(
        _submission_url(workspace, response.response_id), cookies=_cookies(testUser)
    )
    assert page.status_code == 200, page.text
    assert page.json()["response"]["answers"][NAME]["text"] == PREFIXED
    assert page.json()["response"].get("unreadableFields") is None


# ---------------------------------------------------------------------------
# Stored ciphertext is never encrypted again
# ---------------------------------------------------------------------------


async def test_stored_ciphertext_is_kept_as_is_by_later_writes(
    client, workspace, prefix_form
):
    await _enable(client, workspace, prefix_form)
    response = await _submit(workspace, prefix_form)
    url = _feedback_url(workspace, prefix_form.form_id, response.response_id)
    await client.post(url, json={"message": "first"}, cookies=_cookies(testUser))
    before = await _stored(response.response_id)

    # appending an update keeps the stored answers and earlier messages
    result = await client.post(
        url, json={"message": "second"}, cookies=_cookies(testUser)
    )
    assert result.status_code == 200, result.text
    after = await _stored(response.response_id)
    assert after.answers == before.answers
    assert after.respondent_feedback[0].message == (
        before.respondent_feedback[0].message
    )
    # each opens with one decryption, to the plaintext (not to a ciphertext)
    assert _open(workspace, prefix_form.form_id, after.answers).startswith(b"{")
    assert [
        _open(workspace, prefix_form.form_id, entry.message)
        for entry in after.respondent_feedback
    ] == [b"first", b"second"]


async def test_a_respondent_edit_encrypts_the_merged_answers_once(workspace):
    from tests.app.services.test_date_rules import END, START, _day, _published

    form = await _published(workspace, [START, END])
    workspace_form = (
        await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form.form_id)
        )
    )
    workspace_form.settings.require_verified_identity = True
    workspace_form.settings.allow_editing_response = True
    await container.workspace_form_repo().save(workspace_form)
    submitted = await _submit_dates(workspace, form, _day)

    await container.workspace_form_service().patch_response(
        workspace.id,
        form.form_id,
        submitted.response_id,
        None,
        StandardFormResponseCamelModel(answers={"end": _day("2026-03-21")}),
        testUser,
    )

    stored = await _stored(submitted.response_id)
    answers = json.loads(_open(workspace, form.form_id, stored.answers))
    assert answers["start"]["date"] == "2026-03-12"
    assert answers["end"]["date"] == "2026-03-21"

    # an edit of a submission whose answers do not decrypt is refused
    # rather than replacing them with the edit alone
    stored.answers = b"v1:" + b"not a ciphertext"
    await container.form_response_repo().save(stored)
    with pytest.raises(HTTPException) as error:
        await container.workspace_form_service().patch_response(
            workspace.id,
            form.form_id,
            submitted.response_id,
            None,
            StandardFormResponseCamelModel(answers={"end": _day("2026-03-22")}),
            testUser,
        )
    assert error.value.status_code == 409
    assert (await _stored(submitted.response_id)).answers == (b"v1:not a ciphertext")


async def _submit_dates(workspace, form, day):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={"start": day("2026-03-12"), "end": day("2026-03-20")}
        ),
        testUser,
    )


# ---------------------------------------------------------------------------
# Stored values that do not decrypt
# ---------------------------------------------------------------------------


async def test_unreadable_values_are_marked_not_a_500(client, workspace, prefix_form):
    await _enable(client, workspace, prefix_form)
    readable = await _submit(workspace, prefix_form, text="Grace")
    response = await _submit(workspace, prefix_form)
    stored = await _stored(response.response_id)
    # what encrypt used to store for these: the plaintext itself, or damage
    stored.answers = PREFIXED.encode()
    stored.hidden_fields = b"v1:corrupted"
    stored.internal_answers = b"v1:corrupted"
    stored.respondent_feedback = [
        RespondentFeedback(id="f1", status="Under review", message=PREFIXED.encode())
    ]
    await container.form_response_repo().save(stored)

    staff = await client.get(
        _submission_url(workspace, response.response_id), cookies=_cookies(testUser)
    )
    assert staff.status_code == 200, staff.text
    body = staff.json()
    assert body["response"]["answers"] == {}
    assert body["response"]["hiddenFields"] is None
    assert body["response"]["internalAnswers"] is None
    assert body["response"]["unreadableFields"] == [
        "answers",
        "hidden_fields",
        "internal_answers",
    ]
    entry = body["feedback"]["entries"][0]
    assert entry["status"] == "Under review"
    assert entry["message"] is None and entry["messageUnreadable"] is True
    assert "hello" not in staff.text

    respondent = await client.get(
        _submission_url(workspace, response.response_id), cookies=_cookies(testUser2)
    )
    assert respondent.status_code == 200, respondent.text
    assert respondent.json()["response"]["feedback"]["entries"][0]["message"] is None
    assert "hello" not in respondent.text

    base = f"/api/v1/workspaces/{workspace.id}/forms/{prefix_form.form_id}"
    listing = await client.get(f"{base}/submissions", cookies=_cookies(testUser))
    assert listing.status_code == 200, listing.text
    by_id = {i["responseId"]: i for i in listing.json()["items"]}
    assert by_id[response.response_id]["unreadableFields"] == [
        "answers",
        "hidden_fields",
        "internal_answers",
    ]
    assert by_id[readable.response_id]["answers"][NAME]["text"] == "Grace"
    assert by_id[readable.response_id].get("unreadableFields") is None

    for path in ("all-submissions", "submission-paths"):
        result = await client.get(f"{base}/{path}", cookies=_cookies(testUser))
        assert result.status_code == 200, (path, result.text)
        assert "hello" not in result.text


async def test_saving_internal_answers_that_do_not_decrypt_is_refused(
    client, workspace, internal_form, respondent_response  # noqa: F811
):
    stored = await _stored(respondent_response.response_id)
    stored.internal_answers = b"v1:corrupted"
    await container.form_response_repo().save(stored)
    url = (
        f"/api/v1/workspaces/{workspace.id}/forms/{internal_form.form_id}"
        f"/submissions/{respondent_response.response_id}/internal-answers"
    )

    # the save would replace values it cannot read
    result = await client.patch(
        url, json={"answers": {REVIEWER: {"text": "Grace"}}}, cookies=_cookies(testUser)
    )
    assert result.status_code == 409, result.text
    stored = await _stored(respondent_response.response_id)
    assert stored.internal_answers == b"v1:corrupted"
    assert stored.internal_answers_version is None
