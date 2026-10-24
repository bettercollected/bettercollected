"""Staff close deletion requests by hand, without the form's provider.

A response imported from Google Forms could only leave the pending state by
being deleted at the source and synced again; with the import read-only (or
the provider gone) such a request could never complete. ``privacy.manage``
now closes it here: completed (the workspace's stored copy is deleted) or
declined (one of the fixed reasons), with who and when kept on the request.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form_response import (
    DeclineReason,
    DeletionRequestStatus,
)
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.workspace_form_service import WorkspaceFormService
from tests.app.controllers.data import testUser

ROOT = "/api/v1"
GOOGLE_FORM_ID = "google-form-dr-1"
KEPT, ASKED = "google-response-kept", "google-response-asked"


def _imported():
    def response(response_id):
        return {
            "response_id": response_id,
            "form_id": GOOGLE_FORM_ID,
            "provider": "google",
            "respondent_email": "respondent@example.com",
            "answers": {},
            "created_at": "2026-01-02T03:04:05Z",
            "updated_at": "2026-01-02T03:04:05Z",
        }

    return {
        "form": {
            "form_id": GOOGLE_FORM_ID,
            "title": "Imported from Google Forms",
            "fields": [],
            "settings": {"provider": "google", "is_public": True},
        },
        "responses": [response(KEPT), response(ASKED)],
    }


@pytest.fixture()
def google_source():
    """The Google Forms service, faked: it still has both responses."""
    with patch.object(
        WorkspaceFormService,
        "convert_form",
        AsyncMock(side_effect=lambda **kwargs: _imported()),
    ) as convert:
        yield convert


async def _import(client, workspace, cookies):
    response = await client.post(
        f"{ROOT}/workspaces/{workspace.id}/forms/import/google",
        cookies=cookies,
        json={"form": {"formId": GOOGLE_FORM_ID}, "response_data_owner": "x"},
    )
    assert response.status_code == 200, response.text
    return response.json()["formId"]


@pytest.fixture()
async def imported(client, workspace, test_user_cookies, google_source):
    """An imported Google Forms form whose respondent asked for deletion."""
    form_id = await _import(client, workspace, test_user_cookies)
    stored = await container.form_response_service().workspace_response(
        workspace.id, ASKED
    )
    assert stored is not None and stored.provider == "google"
    await container.form_response_repo().add_deletion_request(stored, ASKED)
    return form_id


def _close_url(workspace, form_id, response_id=ASKED):
    return (
        f"{ROOT}/workspaces/{workspace.id}/forms/{form_id}/submissions/"
        f"{response_id}/deletion-request/close"
    )


async def _request(workspace, form_id, response_id=ASKED):
    scope = await container.form_response_service().scope(workspace.id, [form_id])
    requests = await container.form_response_repo().list_deletion_requests_for_form_ids(
        scope
    )
    return next(r for r in requests if r.response_id == response_id)


class TestCompleted:
    async def test_deletes_the_stored_copy_without_the_provider(
        self, client: AsyncClient, workspace, test_user_cookies, imported, google_source
    ):
        calls = google_source.await_count
        response = await client.post(
            _close_url(workspace, imported),
            cookies=test_user_cookies,
            json={"outcome": "completed"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "success"
        assert body["closedBy"] == testUser.id
        assert body["closedAt"]
        assert body.get("declineReason") is None
        assert google_source.await_count == calls  # the provider is never asked
        service = container.form_response_service()
        assert await service.workspace_response(workspace.id, ASKED) is None
        assert await service.workspace_response(workspace.id, KEPT) is not None
        request = await _request(workspace, imported)
        assert request.status == DeletionRequestStatus.SUCCESS
        assert request.closed_by == testUser.id and request.closed_at is not None

    async def test_a_later_sync_does_not_bring_the_response_back(
        self, client: AsyncClient, workspace, test_user_cookies, imported, google_source
    ):
        await client.post(
            _close_url(workspace, imported),
            cookies=test_user_cookies,
            json={"outcome": "completed"},
        )
        # the source still has it: the sync must not restore it
        await _import(client, workspace, test_user_cookies)

        service = container.form_response_service()
        assert await service.workspace_response(workspace.id, ASKED) is None
        assert await service.workspace_response(workspace.id, KEPT) is not None
        request = await _request(workspace, imported)
        assert request.status == DeletionRequestStatus.SUCCESS
        assert request.closed_by == testUser.id

    async def test_works_when_the_copy_is_already_gone(
        self, client: AsyncClient, workspace, test_user_cookies, imported
    ):
        stored = await container.form_response_service().workspace_response(
            workspace.id, ASKED
        )
        await container.form_response_repo().delete_response(stored.response_id)

        response = await client.post(
            _close_url(workspace, imported),
            cookies=test_user_cookies,
            json={"outcome": "completed"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


class TestDeclined:
    async def test_keeps_the_response_and_records_the_reason(
        self, client: AsyncClient, workspace, test_user_cookies, imported
    ):
        response = await client.post(
            _close_url(workspace, imported),
            cookies=test_user_cookies,
            json={"outcome": "declined", "reason": "legal_obligation"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "declined"
        assert response.json()["declineReason"] == "legal_obligation"
        service = container.form_response_service()
        assert await service.workspace_response(workspace.id, ASKED) is not None
        request = await _request(workspace, imported)
        assert request.status == DeletionRequestStatus.DECLINED
        assert request.decline_reason == DeclineReason.LEGAL_OBLIGATION
        assert request.closed_by == testUser.id

    @pytest.mark.parametrize(
        "body",
        [
            {"outcome": "declined"},
            {"outcome": "completed", "reason": "other"},
            {"outcome": "declined", "reason": "because I said so"},
            {"outcome": "ignored"},
        ],
    )
    async def test_needs_exactly_a_known_reason(
        self, client: AsyncClient, workspace, test_user_cookies, imported, body
    ):
        response = await client.post(
            _close_url(workspace, imported), cookies=test_user_cookies, json=body
        )
        assert response.status_code == 422
        request = await _request(workspace, imported)
        assert request.status == DeletionRequestStatus.PENDING


class TestRefusals:
    async def test_a_closed_request_cannot_be_closed_again(
        self, client: AsyncClient, workspace, test_user_cookies, imported
    ):
        url = _close_url(workspace, imported)
        first = await client.post(
            url,
            cookies=test_user_cookies,
            json={"outcome": "declined", "reason": "other"},
        )
        again = await client.post(
            url, cookies=test_user_cookies, json={"outcome": "completed"}
        )

        assert first.status_code == 200
        assert again.status_code == 409
        assert again.json()["code"] == "deletion_request_closed"
        service = container.form_response_service()
        assert await service.workspace_response(workspace.id, ASKED) is not None

    async def test_a_response_without_a_request_is_not_found(
        self, client: AsyncClient, workspace, test_user_cookies, imported
    ):
        response = await client.post(
            _close_url(workspace, imported, KEPT),
            cookies=test_user_cookies,
            json={"outcome": "completed"},
        )
        assert response.status_code == 404
        service = container.form_response_service()
        assert await service.workspace_response(workspace.id, KEPT) is not None

    async def test_a_non_member_is_refused(
        self, client: AsyncClient, workspace, test_user_cookies_1, imported
    ):
        response = await client.post(
            _close_url(workspace, imported),
            cookies=test_user_cookies_1,
            json={"outcome": "completed"},
        )
        assert response.status_code == 403
        request = await _request(workspace, imported)
        assert request.status == DeletionRequestStatus.PENDING


class TestNativeForms:
    async def test_a_native_response_closes_the_same_way(
        self,
        client: AsyncClient,
        workspace,
        published_form,
        workspace_form_response,
        test_user_cookies,
    ):
        response_id = workspace_form_response["response_id"]
        service = container.form_response_service()
        stored = await service.workspace_response(workspace.id, response_id)
        await container.form_response_repo().add_deletion_request(stored, response_id)

        response = await client.post(
            _close_url(workspace, published_form.form_id, response_id),
            cookies=test_user_cookies,
            json={"outcome": "completed"},
        )

        assert response.status_code == 200, response.text
        assert await service.workspace_response(workspace.id, response_id) is None


class TestReviewFollowUps:
    async def test_closing_from_another_workspace_is_refused(
        self, client: AsyncClient, workspace, workspace_1, test_user_cookies_1, imported
    ):
        # testUser1 owns workspace_1 (privacy.manage there), not this form's
        response = await client.post(
            _close_url(workspace_1, imported),
            cookies=test_user_cookies_1,
            json={"outcome": "completed"},
        )
        assert response.status_code in (403, 404)
        request = await _request(workspace, imported)
        assert request.status == DeletionRequestStatus.PENDING
        service = container.form_response_service()
        assert await service.workspace_response(workspace.id, ASKED) is not None

    async def test_completed_is_refused_while_an_unattributed_copy_remains(
        self, client: AsyncClient, workspace, test_user_cookies, imported
    ):
        # the workspace's copy can't be resolved (e.g. a legacy copy without a
        # workspace on a form linked to several): the data would stay
        with patch.object(
            FormResponseService, "workspace_response", AsyncMock(return_value=None)
        ):
            response = await client.post(
                _close_url(workspace, imported),
                cookies=test_user_cookies,
                json={"outcome": "completed"},
            )

        assert response.status_code == 409
        assert response.json()["code"] == "deletion_request_copy_unresolved"
        request = await _request(workspace, imported)
        assert request.status == DeletionRequestStatus.PENDING

    async def test_a_sync_after_a_decline_records_a_new_close(
        self, client: AsyncClient, workspace, test_user_cookies, imported, google_source
    ):
        await client.post(
            _close_url(workspace, imported),
            cookies=test_user_cookies,
            json={"outcome": "declined", "reason": "legal_claims"},
        )
        # the source drops the declined response
        only_kept = _imported()
        only_kept["responses"] = only_kept["responses"][:1]
        google_source.side_effect = lambda **kwargs: only_kept
        await _import(client, workspace, test_user_cookies)

        request = await _request(workspace, imported)
        assert request.status == DeletionRequestStatus.SUCCESS
        assert [(c.status, c.source) for c in request.closures] == [
            ("declined", "staff"),
            ("success", "import"),
        ]
        # the decline itself is kept, not overwritten
        assert request.closures[0].by == testUser.id
        assert request.closures[0].reason == "legal_claims"
        assert request.decline_reason == DeclineReason.LEGAL_CLAIMS

    async def test_the_respondent_sees_a_declined_request_as_not_deleted(
        self,
        client: AsyncClient,
        workspace,
        published_form,
        workspace_form_response,
        test_user_cookies,
    ):
        response_id = workspace_form_response["response_id"]
        service = container.form_response_service()
        stored = await service.workspace_response(workspace.id, response_id)
        await container.form_response_repo().add_deletion_request(stored, response_id)
        await client.post(
            _close_url(workspace, published_form.form_id, response_id),
            cookies=test_user_cookies,
            json={"outcome": "declined", "reason": "legal_obligation"},
        )

        # the respondent's own deletion requests (testUser submitted it)
        listed = await client.get(
            f"{ROOT}/workspaces/{workspace.id}/submissions",
            params={"request_for_deletion": True},
            cookies=test_user_cookies,
        )

        assert listed.status_code == 200, listed.text
        items = [i for i in listed.json()["items"] if i["responseId"] == response_id]
        assert len(items) == 1
        assert items[0]["status"] == "declined"
        assert items[0]["declineReason"] == "legal_obligation"
        # who declined it is never sent to the respondent
        assert "closedBy" not in items[0] and "closures" not in items[0]
        assert await service.workspace_response(workspace.id, response_id) is not None
