"""A closed form takes no new responses: the server refuses them with 409
``form_closed`` (services/form_availability.py), judged at the time the
request arrived. Respondents may still edit what they already sent, a form
never published takes no responses, and the respondent's read, the public
listing and the search agree with the gate."""

import datetime as dt
import json
from typing import Any, Coroutine
from unittest.mock import AsyncMock, patch

import pytest
from common.models.standard_form import StandardFormResponse
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.actions_service import ActionService
from backend.app.services.workspace_form_service import (
    WorkspaceFormService,
    _question_ids,
)
from tests.app.controllers.data import formResponse, testUser

UTC = dt.timezone.utc
SECOND = dt.timedelta(seconds=1)
CLOSED_BODY = {
    "code": "form_closed",
    "message": "This form is closed and no longer accepts responses.",
}


def _url(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}"


def _close_at() -> dt.datetime:
    """A close instant a little ahead of the real time, whole seconds."""
    return (dt.datetime.now(UTC) + dt.timedelta(minutes=10)).replace(microsecond=0)


def _freeze(monkeypatch, at: dt.datetime) -> None:
    """The server's clock as the gate reads it (common.clock.utcnow)."""
    monkeypatch.setattr("common.clock.utcnow", lambda: at)


async def _store_close_date(workspace, form_id, value) -> None:
    """Store a close date as it is, the way values written before the
    settings were validated look (any offset, any spelling)."""
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(form_id)
    )
    link.settings.form_close_date = value
    await repo.update(link.id, link)


async def _post(client, workspace, form_id, cookies=None, **extra):
    return await client.post(
        f"{_url(workspace)}/forms/{form_id}/response",
        data={"response": json.dumps({"answers": {}}), **extra.pop("data", {})},
        cookies=cookies,
        **extra,
    )


async def _stored_count(client, workspace, form_id, cookies) -> int:
    listed = await client.get(
        f"{_url(workspace)}/forms/{form_id}/submissions", cookies=cookies
    )
    assert listed.status_code == 200, listed.text
    return listed.json()["total"]


def _assert_closed(refused, closes_at: dt.datetime) -> None:
    assert refused.status_code == 409, refused.text
    assert refused.json() == {**CLOSED_BODY, "closesAt": closes_at.isoformat()}


class TestSubmitGate:
    @pytest.mark.parametrize("signed_in", [False, True])
    async def test_on_the_close_instant_a_submission_is_refused_and_nothing_stored(
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
        close = _close_at()
        await _store_close_date(workspace, form_id, close.isoformat())
        respondent = test_user_cookies_1 if signed_in else None

        _freeze(monkeypatch, close - SECOND)
        accepted = await _post(client, workspace, form_id, respondent)
        assert accepted.status_code == 200, accepted.text
        assert await _stored_count(client, workspace, form_id, test_user_cookies) == 1

        for at in (close, close + SECOND, close + dt.timedelta(days=30)):
            _freeze(monkeypatch, at)
            _assert_closed(await _post(client, workspace, form_id, respondent), close)
        assert await _stored_count(client, workspace, form_id, test_user_cookies) == 1

    @pytest.mark.parametrize(
        "spelling",
        [
            lambda close: close.astimezone(dt.timezone(dt.timedelta(hours=2))).isoformat(),
            lambda close: close.astimezone(dt.timezone(-dt.timedelta(hours=5))).isoformat(),
            lambda close: close.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            lambda close: close.replace(tzinfo=None).isoformat(),
            lambda close: close,
        ],
        ids=["+02:00", "-05:00", "Z-ms", "naive", "datetime"],
    )
    async def test_every_stored_spelling_closes_on_the_same_instant(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        monkeypatch,
        spelling,
    ):
        form_id = published_form.form_id
        close = _close_at()
        await _store_close_date(workspace, form_id, spelling(close))
        _freeze(monkeypatch, close - SECOND)
        assert (await _post(client, workspace, form_id)).status_code == 200
        _freeze(monkeypatch, close)
        _assert_closed(await _post(client, workspace, form_id), close)

    @pytest.mark.parametrize("value", ["", None, "banana"])
    async def test_no_or_an_unreadable_close_date_leaves_the_form_open(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        value,
    ):
        await _store_close_date(workspace, published_form.form_id, value)
        posted = await _post(client, workspace, published_form.form_id)
        assert posted.status_code == 200, posted.text

    async def test_the_time_the_request_arrived_decides(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        monkeypatch,
    ):
        """A submission that arrived before the close is on time even when
        it is handled after it (a slow upload)."""
        form_id = published_form.form_id
        close = _close_at()
        await _store_close_date(workspace, form_id, close.isoformat())
        # the request is stamped on arrival (middleware), before the close;
        # the clock has passed it by the time the service runs
        monkeypatch.setattr(
            "backend.app.services.form_availability.now", lambda: close - SECOND
        )
        _freeze(monkeypatch, close + SECOND)
        posted = await _post(client, workspace, form_id)
        assert posted.status_code == 200, posted.text

    async def test_a_refusal_uploads_nothing_and_starts_no_action(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
    ):
        from backend.app.exceptions import HTTPException

        form_id = published_form.form_id
        close = _close_at()
        await _store_close_date(workspace, form_id, close.isoformat())
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
                container.form_response_service().__class__,
                "submit_form_response",
                new=AsyncMock(),
            ) as stored,
        ):
            with pytest.raises(HTTPException) as refused:
                await container.workspace_form_service().submit_response(
                    workspace.id,
                    form_id,
                    StandardFormResponse(**formResponse),
                    testUser,
                    form_files=[object()],
                    received_at=close,
                )
        assert refused.value.status_code == 409
        assert refused.value.content["code"] == "form_closed"
        upload.assert_not_called()
        actions.assert_not_called()
        stored.assert_not_called()

    async def test_a_closed_private_or_hidden_form_keeps_its_own_answers(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        """Who may answer is decided first: a stranger still gets 404 for a
        private form, closed or not."""
        form_id = published_form.form_id
        patched = await client.patch(
            f"{_url(workspace)}/forms/{form_id}/settings",
            json={"private": True},
            cookies=test_user_cookies,
        )
        assert patched.status_code == 200, patched.text
        await _store_close_date(workspace, form_id, "2020-01-01T00:00:00Z")
        refused = await _post(client, workspace, form_id)
        assert refused.status_code == 404, refused.text


class TestEditsAfterClose:
    async def test_a_respondent_edits_their_response_after_the_close(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
        test_user_cookies: dict[str, str],
    ):
        form_id = published_form.form_id
        allowed = await client.patch(
            f"{_url(workspace)}/forms/{form_id}/settings",
            json={
                "requireVerifiedIdentity": True,
                "allowEditingResponse": True,
                "formCloseDate": "2020-01-01T00:00:00Z",
            },
            cookies=test_user_cookies,
        )
        assert allowed.status_code == 200, allowed.text
        _assert_closed(
            await _post(client, workspace, form_id, test_user_cookies),
            dt.datetime(2020, 1, 1, tzinfo=UTC),
        )
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

    async def test_a_deletion_request_after_the_close_is_taken(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
        test_user_cookies: dict[str, str],
    ):
        await _store_close_date(
            workspace, published_form.form_id, "2020-01-01T00:00:00Z"
        )
        requested = await client.delete(
            f"{_url(workspace)}/submissions/{workspace_form_response['response_id']}",
            cookies=test_user_cookies,
        )
        assert requested.status_code == 200, requested.text


class TestUnpublishedForm:
    async def test_a_form_never_published_takes_no_response(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        form_id = workspace_form.form_id
        refused = await _post(client, workspace, form_id)
        assert refused.status_code == 404, refused.text
        assert refused.json() == "Form not found"
        assert await _stored_count(client, workspace, form_id, test_user_cookies) == 0


class TestSettingsPatch:
    async def _patch(self, client, workspace, form_id, cookies, value):
        return await client.patch(
            f"{_url(workspace)}/forms/{form_id}/settings",
            json={"formCloseDate": value},
            cookies=cookies,
        )

    async def test_a_close_date_is_stored_as_a_utc_instant_and_cleared_with_empty(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        form_id = workspace_form.form_id
        for sent, stored in (
            ("2026-10-30T14:00:00+02:00", "2026-10-30T12:00:00+00:00"),
            ("2026-10-30T12:00:00.000Z", "2026-10-30T12:00:00+00:00"),
            ("2026-10-30T12:00:00", "2026-10-30T12:00:00+00:00"),
            ("", ""),
        ):
            patched = await self._patch(
                client, workspace, form_id, test_user_cookies, sent
            )
            assert patched.status_code == 200, patched.text
            assert patched.json()["settings"]["formCloseDate"] == stored

    @pytest.mark.parametrize("value", ["banana", "2026-13-45T00:00:00", 1730289600])
    async def test_what_is_not_a_date_is_refused_and_nothing_changes(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        value,
    ):
        form_id = workspace_form.form_id
        kept = await self._patch(
            client, workspace, form_id, test_user_cookies, "2030-01-01T00:00:00Z"
        )
        assert kept.status_code == 200, kept.text
        refused = await self._patch(client, workspace, form_id, test_user_cookies, value)
        assert refused.status_code == 422, refused.text
        link = await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form_id)
        )
        assert link.settings.form_close_date == "2030-01-01T00:00:00+00:00"

    async def test_only_form_editors_set_it(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies_1: dict[str, str],
    ):
        refused = await self._patch(
            client,
            workspace,
            workspace_form.form_id,
            test_user_cookies_1,
            "2020-01-01T00:00:00Z",
        )
        assert refused.status_code == 403, refused.text


class TestReadsAgreeWithTheGate:
    async def _read(self, client, workspace, form_id, cookies=None):
        page = await client.get(
            f"{_url(workspace)}/forms/{form_id}",
            params={"published": "true"},
            cookies=cookies,
        )
        assert page.status_code == 200, page.text
        return page.json()

    async def _listed(self, client, workspace, cookies=None):
        listed = await client.get(
            f"{_url(workspace)}/forms", params={"published": "true"}, cookies=cookies
        )
        assert listed.status_code == 200, listed.text
        return {form["formId"] for form in listed.json()["items"]}

    async def _searched(self, client, workspace, title, cookies=None):
        found = await client.post(
            f"{_url(workspace)}/forms/search",
            params={"query": title, "published": "true"},
            cookies=cookies,
        )
        assert found.status_code == 200, found.text
        return {form["formId"] for form in found.json()}

    async def test_a_closed_form_reaches_respondents_as_a_stub_and_staff_in_full(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        test_user_cookies_1: dict[str, str],
        monkeypatch,
    ):
        form_id = published_form.form_id
        close = _close_at()
        await _store_close_date(
            workspace,
            form_id,
            close.astimezone(dt.timezone(dt.timedelta(hours=2))).isoformat(),
        )
        title = published_form.title

        _freeze(monkeypatch, close - SECOND)
        for cookies in (None, test_user_cookies_1):
            page = await self._read(client, workspace, form_id, cookies)
            assert page.get("unavailable") is None
            assert page["fields"]
            assert form_id in await self._listed(client, workspace, cookies)
            assert form_id in await self._searched(client, workspace, title, cookies)

        _freeze(monkeypatch, close)
        for cookies in (None, test_user_cookies_1):
            page = await self._read(client, workspace, form_id, cookies)
            assert page["unavailable"] == "closed"
            assert page["formId"] == form_id
            assert page["builderVersion"] == published_form.builder_version
            assert page["title"] == title
            assert page.get("fields") is None
            assert page.get("aiNoticeToken") is None
            assert form_id not in await self._listed(client, workspace, cookies)
            assert form_id not in await self._searched(
                client, workspace, title, cookies
            )
        # staff keep the whole form (preview, dashboard)
        staff = await self._read(client, workspace, form_id, test_user_cookies)
        assert staff.get("unavailable") is None
        assert staff["fields"]
        assert form_id in await self._searched(
            client, workspace, title, test_user_cookies
        )


class TestArrivalWindow:
    async def _submit(self, workspace, form_id, received_at):
        return await container.workspace_form_service().submit_response(
            workspace.id,
            form_id,
            StandardFormResponse(**formResponse),
            testUser,
            received_at=received_at,
        )

    async def test_arrival_counts_for_at_most_the_window(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        monkeypatch,
    ):
        """Arrived before the close: judged at the arrival while it is within
        MAX_ARRIVAL_WINDOW of now, at now after that."""
        from backend.app.exceptions import HTTPException
        from backend.app.services.form_availability import MAX_ARRIVAL_WINDOW

        form_id = published_form.form_id
        close = _close_at()
        await _store_close_date(workspace, form_id, close.isoformat())
        _freeze(monkeypatch, close + SECOND)
        arrived = close + SECOND - MAX_ARRIVAL_WINDOW
        assert (await self._submit(workspace, form_id, arrived)).response_id
        with pytest.raises(HTTPException) as refused:
            await self._submit(workspace, form_id, arrived - SECOND)
        assert refused.value.status_code == 409


class TestReceivedAtMiddleware:
    async def _scope_after(self, method, path):
        from backend.app.middlewares.received_at import ReceivedAtMiddleware

        seen = {}

        async def app(scope, receive, send):
            seen.update(scope)

        await ReceivedAtMiddleware(app)(
            {"type": "http", "method": method, "path": path}, None, None
        )
        return seen

    async def test_only_a_submission_is_stamped(self, monkeypatch):
        at = dt.datetime(2026, 10, 30, 12, tzinfo=UTC)
        _freeze(monkeypatch, at)
        submit = "/api/v1/workspaces/w1/forms/f1/response"
        assert (await self._scope_after("POST", submit))["state"]["received_at"] == at
        for method, path in (
            ("PATCH", f"{submit}/r1"),
            ("GET", "/api/v1/workspaces/w1/forms/f1"),
            ("POST", "/api/v1/workspaces/w1/forms/f1/publish"),
        ):
            assert "state" not in await self._scope_after(method, path)


class TestStubsCarryNoExtras:
    async def test_a_closed_stub_has_no_ai_token_and_keeps_the_look(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        monkeypatch,
    ):
        from backend.app.services.form_service import FormService
        monkeypatch.setattr(
            FormService, "ai_notice_token", AsyncMock(return_value="v1.token.sig")
        )
        form_id = published_form.form_id
        url = f"{_url(workspace)}/forms/{form_id}"
        page = (await client.get(url, params={"published": "true"})).json()
        # the patch is live: an open form carries the token
        assert page["aiNoticeToken"] == "v1.token.sig"

        await _store_close_date(workspace, form_id, "2020-01-01T00:00:00Z")
        stub = (await client.get(url, params={"published": "true"})).json()
        assert stub["unavailable"] == "closed"
        assert stub.get("aiNoticeToken") is None
        assert stub.get("fields") is None
        for key in ("title", "description", "welcomePage", "theme"):
            assert stub[key] == page[key], key
        assert "coverImage" in stub and "logo" in stub


class TestVersionReads:
    @pytest.mark.parametrize("version", ["latest", "1"])
    async def test_a_closed_form_version_reaches_respondents_as_a_stub(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        test_user_cookies_1: dict[str, str],
        version: str,
    ):
        form_id = published_form.form_id
        url = f"{_url(workspace)}/forms/{form_id}/versions/{version}"
        for cookies in (None, test_user_cookies_1):
            opened = await client.get(url, cookies=cookies)
            assert opened.status_code == 200, opened.text
            assert opened.json()["fields"]
            assert opened.json().get("unavailable") is None

        await _store_close_date(workspace, form_id, "2020-01-01T00:00:00Z")
        for cookies in (None, test_user_cookies_1):
            closed = await client.get(url, cookies=cookies)
            assert closed.status_code == 200, closed.text
            body = closed.json()
            assert body["unavailable"] == "closed"
            assert body["formId"] == form_id
            assert body.get("fields") is None
        staff = await client.get(url, cookies=test_user_cookies)
        assert staff.status_code == 200, staff.text
        assert staff.json()["fields"]
        assert staff.json().get("unavailable") is None
