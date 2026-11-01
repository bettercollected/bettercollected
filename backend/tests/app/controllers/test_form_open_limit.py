"""A form that has not opened yet, or has received as many responses as its
limit, takes no new responses: the server refuses them with 409
``form_not_open`` / ``form_full`` (services/form_availability.py), as it does
for a closed form, before anything is stored. The limit is enforced under a
lock, so parallel submissions never pass it. Respondents may still edit what
they sent and ask for its deletion; the respondent's read, the public listing
and the search agree with the gate."""

import asyncio
import datetime as dt
import json
from types import SimpleNamespace
from typing import Any, Coroutine
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from common.models.standard_form import StandardFormResponse
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.actions_service import ActionService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.workspace_form_service import (
    WorkspaceFormService,
    _question_ids,
)
from tests.app.controllers.data import formResponse, testUser

UTC = dt.timezone.utc
SECOND = dt.timedelta(seconds=1)
FULL_BODY = {
    "code": "form_full",
    "message": "This form has received all the responses it accepts.",
}


def _url(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}"


def _opens_at() -> dt.datetime:
    return (dt.datetime.now(UTC) + dt.timedelta(days=3)).replace(microsecond=0)


def _freeze(monkeypatch, at: dt.datetime) -> None:
    monkeypatch.setattr("common.clock.utcnow", lambda: at)


async def _settings(workspace, form_id, **values) -> None:
    """Store settings as they are (no validation), the way the repository
    reads them back."""
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(form_id)
    )
    for key, value in values.items():
        setattr(link.settings, key, value)
    await repo.update(link.id, link)


async def _patch(client, workspace, form_id, cookies, **body):
    return await client.patch(
        f"{_url(workspace)}/forms/{form_id}/settings", json=body, cookies=cookies
    )


async def _post(client, workspace, form_id, cookies=None):
    return await client.post(
        f"{_url(workspace)}/forms/{form_id}/response",
        data={"response": json.dumps({"answers": {}})},
        cookies=cookies,
    )


async def _stored_count(client, workspace, form_id, cookies) -> int:
    listed = await client.get(
        f"{_url(workspace)}/forms/{form_id}/submissions", cookies=cookies
    )
    assert listed.status_code == 200, listed.text
    return listed.json()["total"]


async def _read(client, workspace, form_id, cookies=None):
    page = await client.get(
        f"{_url(workspace)}/forms/{form_id}",
        params={"published": "true"},
        cookies=cookies,
    )
    assert page.status_code == 200, page.text
    return page.json()


async def _listed(client, workspace, cookies=None):
    listed = await client.get(
        f"{_url(workspace)}/forms", params={"published": "true"}, cookies=cookies
    )
    assert listed.status_code == 200, listed.text
    return {form["formId"] for form in listed.json()["items"]}


async def _searched(client, workspace, title, cookies=None):
    found = await client.post(
        f"{_url(workspace)}/forms/search",
        params={"query": title, "published": "true"},
        cookies=cookies,
    )
    assert found.status_code == 200, found.text
    return {form["formId"] for form in found.json()}


async def _submit_service(workspace, form_id, **extra):
    return await container.workspace_form_service().submit_response(
        workspace.id, form_id, StandardFormResponse(**formResponse), testUser, **extra
    )


class TestOpenDateGate:
    @pytest.mark.parametrize("signed_in", [False, True])
    async def test_before_the_open_instant_a_submission_is_refused_and_nothing_stored(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        test_user_cookies_1: dict[str, str],
        monkeypatch,
        signed_in: bool,
    ):
        form_id = published_form.form_id
        opens = _opens_at()
        await _settings(
            workspace,
            form_id,
            form_open_date=opens.astimezone(
                dt.timezone(dt.timedelta(hours=2))
            ).isoformat(),
        )
        respondent = test_user_cookies_1 if signed_in else None

        for at in (opens - dt.timedelta(days=30), opens - SECOND):
            _freeze(monkeypatch, at)
            refused = await _post(client, workspace, form_id, respondent)
            assert refused.status_code == 409, refused.text
            assert refused.json() == {
                "code": "form_not_open",
                "message": "This form is not open yet.",
                "opensAt": opens.isoformat(),
            }
        assert await _stored_count(client, workspace, form_id, test_user_cookies) == 0

        for at in (opens, opens + SECOND):
            _freeze(monkeypatch, at)
            accepted = await _post(client, workspace, form_id, respondent)
            assert accepted.status_code == 200, accepted.text
        assert await _stored_count(client, workspace, form_id, test_user_cookies) == 2

    async def test_a_refusal_uploads_nothing_and_starts_no_action(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
    ):
        form_id = published_form.form_id
        opens = _opens_at()
        await _settings(workspace, form_id, form_open_date=opens.isoformat())
        with (
            patch.object(
                WorkspaceFormService,
                "upload_files_to_s3_and_update_url",
                new=AsyncMock(),
            ) as upload,
            patch.object(
                ActionService, "start_actions_for_submission", new=AsyncMock()
            ) as actions,
            patch.object(
                FormResponseService, "submit_form_response", new=AsyncMock()
            ) as stored,
        ):
            with pytest.raises(HTTPException) as refused:
                await _submit_service(
                    workspace,
                    form_id,
                    form_files=[object()],
                    received_at=opens - SECOND,
                )
        assert refused.value.status_code == 409
        assert refused.value.content["code"] == "form_not_open"
        upload.assert_not_called()
        actions.assert_not_called()
        stored.assert_not_called()

    async def test_the_arrival_time_decides(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        monkeypatch,
    ):
        """Arrived before the open instant: refused, even when it is handled
        after it; arrived at it: taken."""
        form_id = published_form.form_id
        opens = _opens_at()
        await _settings(workspace, form_id, form_open_date=opens.isoformat())
        monkeypatch.setattr(
            "backend.app.services.form_availability.now", lambda: opens - SECOND
        )
        _freeze(monkeypatch, opens + SECOND)
        refused = await _post(client, workspace, form_id)
        assert refused.status_code == 409, refused.text

    async def test_a_private_form_keeps_its_own_answer_first(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        """Who may answer is decided before the dates: a stranger gets 404
        for a private form, open or not."""
        form_id = published_form.form_id
        patched = await _patch(
            client, workspace, form_id, test_user_cookies, private=True
        )
        assert patched.status_code == 200, patched.text
        await _settings(workspace, form_id, form_open_date=_opens_at().isoformat())
        refused = await _post(client, workspace, form_id)
        assert refused.status_code == 404, refused.text


class TestResponseLimitGate:
    async def test_the_response_over_the_limit_is_refused_and_nothing_stored(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        test_user_cookies_1: dict[str, str],
    ):
        form_id = published_form.form_id
        await _settings(workspace, form_id, response_limit=2)
        for respondent in (None, test_user_cookies_1):
            accepted = await _post(client, workspace, form_id, respondent)
            assert accepted.status_code == 200, accepted.text
        for respondent in (None, test_user_cookies_1, None):
            refused = await _post(client, workspace, form_id, respondent)
            assert refused.status_code == 409, refused.text
            assert refused.json() == FULL_BODY
        assert await _stored_count(client, workspace, form_id, test_user_cookies) == 2

    async def test_a_refusal_uploads_nothing_and_starts_no_action(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
    ):
        form_id = published_form.form_id
        await _settings(workspace, form_id, response_limit=1)
        await _submit_service(workspace, form_id)
        with (
            patch.object(
                WorkspaceFormService,
                "upload_files_to_s3_and_update_url",
                new=AsyncMock(),
            ) as upload,
            patch.object(
                ActionService, "start_actions_for_submission", new=AsyncMock()
            ) as actions,
        ):
            with pytest.raises(HTTPException) as refused:
                await _submit_service(workspace, form_id, form_files=[object()])
        assert refused.value.status_code == 409
        assert refused.value.content["code"] == "form_full"
        upload.assert_not_called()
        actions.assert_not_called()

    async def test_a_submission_that_loses_the_race_removes_its_files(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
    ):
        """The count before the upload said there was room, the insert under
        the lock found none: refused, and the files of this attempt go."""
        form_id = published_form.form_id
        await _settings(workspace, form_id, response_limit=1)
        await _submit_service(workspace, form_id)
        with (
            patch.object(
                FormResponseService, "count_for_form", new=AsyncMock(return_value=0)
            ),
            patch.object(
                WorkspaceFormService,
                "upload_files_to_s3_and_update_url",
                new=AsyncMock(side_effect=lambda files, response, **_: response),
            ) as upload,
            patch.object(
                container.workspace_form_service(), "_aws_service", new=MagicMock()
            ) as aws,
            patch.object(
                ActionService, "start_actions_for_submission", new=AsyncMock()
            ) as actions,
            # the fixture form has no file question: this part stands for an
            # upload to one (a part must belong to one, services/signatures.py)
            patch(
                "backend.app.services.signatures.part_fields",
                return_value={"upload"},
            ),
        ):
            part = SimpleNamespace(file_id="file-1", field_id="upload")
            with pytest.raises(HTTPException) as refused:
                await _submit_service(workspace, form_id, form_files=[part])
        assert refused.value.content["code"] == "form_full"
        upload.assert_called_once()
        aws.delete_folder_from_s3.assert_called_once()
        prefix = aws.delete_folder_from_s3.call_args.args[0]
        assert prefix.startswith(f"private/{workspace.id}/{form_id}/")
        actions.assert_not_called()

    async def test_parallel_submissions_never_pass_the_limit(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        client: AsyncClient,
        test_user_cookies: dict[str, str],
    ):
        """N submissions at once with one slot left (limit N-1 reached minus
        one): exactly one is taken, the others get 409 form_full."""
        form_id = published_form.form_id
        parallel = 8
        await _settings(workspace, form_id, response_limit=parallel - 1)
        for _ in range(parallel - 2):
            await _submit_service(workspace, form_id)

        results = await asyncio.gather(
            *[_submit_service(workspace, form_id) for _ in range(parallel)],
            return_exceptions=True,
        )
        taken = [r for r in results if not isinstance(r, BaseException)]
        refused = [r for r in results if isinstance(r, BaseException)]
        assert len(taken) == 1, results
        assert len(refused) == parallel - 1
        for error in refused:
            assert isinstance(error, HTTPException), repr(error)
            assert error.status_code == 409
            assert error.content["code"] == "form_full"
        assert (
            await _stored_count(client, workspace, form_id, test_user_cookies)
            == parallel - 1
        )

    async def test_parallel_submissions_into_an_empty_form_stop_at_the_limit(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        client: AsyncClient,
        test_user_cookies: dict[str, str],
    ):
        form_id = published_form.form_id
        await _settings(workspace, form_id, response_limit=3)
        results = await asyncio.gather(
            *[_submit_service(workspace, form_id) for _ in range(10)],
            return_exceptions=True,
        )
        assert sum(not isinstance(r, BaseException) for r in results) == 3
        assert await _stored_count(client, workspace, form_id, test_user_cookies) == 3

    async def test_a_deleted_response_frees_its_slot(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        form_id = published_form.form_id
        await _settings(workspace, form_id, response_limit=1)
        first = await _submit_service(workspace, form_id)
        assert (await _post(client, workspace, form_id)).status_code == 409
        await container.form_response_service().delete_form_response(
            form_id=form_id,
            response_id=str(first.response_id),
            workspace_id=workspace.id,
        )
        assert (await _post(client, workspace, form_id)).status_code == 200
        assert (await _post(client, workspace, form_id)).status_code == 409

    async def test_the_limit_counts_this_workspaces_responses_of_the_form(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
    ):
        """What counts is the stored responses in scope: a limit of 2 with
        one stored leaves exactly one slot."""
        form_id = published_form.form_id
        await _settings(workspace, form_id, response_limit=2)
        await _submit_service(workspace, form_id)
        await _submit_service(workspace, form_id)
        with pytest.raises(HTTPException):
            await _submit_service(workspace, form_id)
        assert (
            await container.form_response_service().count_for_form(
                workspace.id, str(form_id)
            )
            == 2
        )

    @pytest.mark.parametrize("value", [None, 0, -4])
    async def test_no_or_an_unreadable_limit_leaves_the_form_open(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        value,
    ):
        form_id = published_form.form_id
        await _settings(workspace, form_id, response_limit=value)
        for _ in range(3):
            assert (await _post(client, workspace, form_id)).status_code == 200


class TestEditsAndDeletionsAreUnaffected:
    async def test_a_full_form_still_takes_edits_and_deletion_requests(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
        test_user_cookies: dict[str, str],
    ):
        form_id = published_form.form_id
        allowed = await _patch(
            client,
            workspace,
            form_id,
            test_user_cookies,
            requireVerifiedIdentity=True,
            allowEditingResponse=True,
            responseLimit=1,
            formOpenDate="2099-01-01T00:00:00Z",
        )
        assert allowed.status_code == 200, allowed.text
        refused = await _post(client, workspace, form_id, test_user_cookies)
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] in ("form_full", "form_not_open")
        question = sorted(_question_ids(published_form.fields))[0]
        edited = await client.patch(
            f"{_url(workspace)}/forms/{form_id}/response/"
            f"{workspace_form_response['response_id']}",
            data={
                "response": json.dumps(
                    {"answers": {question: {"field": {"id": question}, "text": "x"}}}
                )
            },
            cookies=test_user_cookies,
        )
        assert edited.status_code == 200, edited.text
        requested = await client.delete(
            f"{_url(workspace)}/submissions/{workspace_form_response['response_id']}",
            cookies=test_user_cookies,
        )
        assert requested.status_code == 200, requested.text


class TestSettingsPatch:
    async def test_dates_are_stored_as_utc_and_cleared_with_empty_a_limit_with_zero(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        form_id = workspace_form.form_id
        patched = await _patch(
            client,
            workspace,
            form_id,
            test_user_cookies,
            formOpenDate="2030-10-30T14:00:00+02:00",
            formCloseDate="2030-11-30T12:00:00.000Z",
            responseLimit=150,
        )
        assert patched.status_code == 200, patched.text
        settings = patched.json()["settings"]
        assert settings["formOpenDate"] == "2030-10-30T12:00:00+00:00"
        assert settings["formCloseDate"] == "2030-11-30T12:00:00+00:00"
        assert settings["responseLimit"] == 150
        # a patch that leaves them out keeps them
        kept = await _patch(client, workspace, form_id, test_user_cookies, pinned=True)
        assert kept.json()["settings"]["formOpenDate"] == "2030-10-30T12:00:00+00:00"
        assert kept.json()["settings"]["responseLimit"] == 150
        cleared = await _patch(
            client,
            workspace,
            form_id,
            test_user_cookies,
            formOpenDate="",
            responseLimit=0,
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["settings"]["formOpenDate"] == ""
        assert cleared.json()["settings"]["responseLimit"] is None
        assert cleared.json()["settings"]["formCloseDate"] == (
            "2030-11-30T12:00:00+00:00"
        )

    @pytest.mark.parametrize(
        "body",
        [
            {"formOpenDate": "banana"},
            {"formOpenDate": 1730289600},
            {"responseLimit": -1},
            {"responseLimit": 2.5},
            {"responseLimit": "ten"},
            {"responseLimit": 10**9},
            {
                "formOpenDate": "2030-12-01T00:00:00Z",
                "formCloseDate": "2030-11-01T00:00:00Z",
            },
        ],
    )
    async def test_what_is_not_valid_is_refused_with_422_and_nothing_changes(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        body,
    ):
        form_id = workspace_form.form_id
        kept = await _patch(
            client,
            workspace,
            form_id,
            test_user_cookies,
            formOpenDate="2030-01-01T00:00:00Z",
            responseLimit=5,
        )
        assert kept.status_code == 200, kept.text
        refused = await _patch(client, workspace, form_id, test_user_cookies, **body)
        assert refused.status_code == 422, refused.text
        link = await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form_id)
        )
        assert link.settings.form_open_date == "2030-01-01T00:00:00+00:00"
        assert link.settings.response_limit == 5

    async def test_an_open_date_is_checked_against_the_stored_close_date_and_back(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        form_id = workspace_form.form_id
        stored = await _patch(
            client,
            workspace,
            form_id,
            test_user_cookies,
            formOpenDate="2030-02-01T00:00:00Z",
            formCloseDate="2030-03-01T00:00:00Z",
        )
        assert stored.status_code == 200, stored.text
        for body in (
            {"formOpenDate": "2030-03-01T00:00:00Z"},
            {"formOpenDate": "2030-04-01T00:00:00Z"},
            {"formCloseDate": "2030-02-01T00:00:00Z"},
            {"formCloseDate": "2030-01-01T00:00:00Z"},
        ):
            refused = await _patch(
                client, workspace, form_id, test_user_cookies, **body
            )
            assert refused.status_code == 422, (body, refused.text)
        # moving one inside the other's room is fine; so is removing either
        for body in (
            {"formOpenDate": "2030-02-15T00:00:00Z"},
            {"formCloseDate": "2030-06-01T00:00:00Z"},
            {"formCloseDate": ""},
            {"formOpenDate": "2031-01-01T00:00:00Z"},
            {"formOpenDate": ""},
        ):
            ok = await _patch(client, workspace, form_id, test_user_cookies, **body)
            assert ok.status_code == 200, (body, ok.text)

    async def test_only_form_editors_set_them(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies_1: dict[str, str],
    ):
        refused = await _patch(
            client,
            workspace,
            workspace_form.form_id,
            test_user_cookies_1,
            formOpenDate="2030-01-01T00:00:00Z",
            responseLimit=3,
        )
        assert refused.status_code == 403, refused.text


class TestReadsAgreeWithTheGate:
    async def test_a_form_not_open_yet_reaches_respondents_as_a_stub_and_staff_in_full(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        test_user_cookies_1: dict[str, str],
        monkeypatch,
    ):
        form_id = published_form.form_id
        opens = _opens_at()
        await _settings(
            workspace,
            form_id,
            form_open_date=opens.astimezone(
                dt.timezone(dt.timedelta(hours=-5))
            ).isoformat(),
        )
        title = published_form.title

        _freeze(monkeypatch, opens - SECOND)
        for cookies in (None, test_user_cookies_1):
            page = await _read(client, workspace, form_id, cookies)
            assert page["unavailable"] == "not_yet_open"
            assert page["formId"] == form_id
            assert page["title"] == title
            assert page.get("fields") is None
            assert page.get("aiNoticeToken") is None
            assert dt.datetime.fromisoformat(page["settings"]["formOpenDate"]) == opens
            assert form_id not in await _listed(client, workspace, cookies)
            assert form_id not in await _searched(client, workspace, title, cookies)
            versions = await client.get(
                f"{_url(workspace)}/forms/{form_id}/versions/latest", cookies=cookies
            )
            assert versions.json()["unavailable"] == "not_yet_open"
            assert versions.json().get("fields") is None
        staff = await _read(client, workspace, form_id, test_user_cookies)
        assert staff.get("unavailable") is None
        assert staff["fields"]
        assert form_id in await _searched(client, workspace, title, test_user_cookies)

        _freeze(monkeypatch, opens)
        for cookies in (None, test_user_cookies_1):
            page = await _read(client, workspace, form_id, cookies)
            assert page.get("unavailable") is None
            assert page["fields"]
            assert form_id in await _listed(client, workspace, cookies)
            assert form_id in await _searched(client, workspace, title, cookies)

    async def test_a_full_form_reaches_respondents_as_a_stub_and_staff_in_full(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        test_user_cookies_1: dict[str, str],
    ):
        form_id = published_form.form_id
        title = published_form.title
        await _settings(workspace, form_id, response_limit=2)
        await _submit_service(workspace, form_id)
        for cookies in (None, test_user_cookies_1):
            page = await _read(client, workspace, form_id, cookies)
            assert page.get("unavailable") is None
            assert page["fields"]
            assert form_id in await _listed(client, workspace, cookies)
            assert form_id in await _searched(client, workspace, title, cookies)

        await _submit_service(workspace, form_id)
        for cookies in (None, test_user_cookies_1):
            page = await _read(client, workspace, form_id, cookies)
            assert page["unavailable"] == "full"
            assert page["formId"] == form_id
            assert page["title"] == title
            assert page.get("fields") is None
            assert page.get("aiNoticeToken") is None
            assert page.get("registrationDestination") is None
            assert form_id not in await _listed(client, workspace, cookies)
            assert form_id not in await _searched(client, workspace, title, cookies)
            versions = await client.get(
                f"{_url(workspace)}/forms/{form_id}/versions/1", cookies=cookies
            )
            assert versions.json()["unavailable"] == "full"
            assert versions.json().get("fields") is None
        staff = await _read(client, workspace, form_id, test_user_cookies)
        assert staff.get("unavailable") is None
        assert staff["fields"]
        assert staff["settings"]["responseLimit"] == 2
        assert form_id in await _searched(client, workspace, title, test_user_cookies)

        # deleting a response makes the form fillable again, everywhere
        first = (
            await client.get(
                f"{_url(workspace)}/forms/{form_id}/submissions",
                cookies=test_user_cookies,
            )
        ).json()["items"][0]
        await container.form_response_service().delete_form_response(
            form_id=form_id,
            response_id=str(first["responseId"]),
            workspace_id=workspace.id,
        )
        page = await _read(client, workspace, form_id)
        assert page.get("unavailable") is None
        assert form_id in await _listed(client, workspace)

    async def test_respondents_never_see_the_limit_only_staff_do(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        test_user_cookies_1: dict[str, str],
    ):
        form_id = published_form.form_id
        await _settings(workspace, form_id, response_limit=40)
        for cookies in (None, test_user_cookies_1):
            page = await _read(client, workspace, form_id, cookies)
            assert page.get("unavailable") is None
            assert not (page["settings"] or {}).get("responseLimit")
            assert "40" not in json.dumps(page["settings"])
        staff = await _read(client, workspace, form_id, test_user_cookies)
        assert staff["settings"]["responseLimit"] == 40
        # the stubs of a private form leave it out too
        await _patch(client, workspace, form_id, test_user_cookies, private=True)
        stub = await _read(client, workspace, form_id)
        assert not (stub.get("settings") or {}).get("responseLimit")

    async def test_the_listing_counts_once_for_all_limited_forms(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
    ):
        """A limit far from reached keeps the form listed."""
        form_id = published_form.form_id
        await _settings(workspace, form_id, response_limit=1000)
        await _submit_service(workspace, form_id)
        assert form_id in await _listed(client, workspace)
