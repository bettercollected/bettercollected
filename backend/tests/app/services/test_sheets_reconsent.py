"""A Google Sheets credential from before ``drive.file`` is held back on its next
use, never kept silently (services/sheets_reconsent.py): the run is skipped and
counted, the action is marked ``needs_reconsent`` and the billing owner is
mailed once. Only while the backend runs the Sheets flow."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from common.exceptions.http import HTTPException as UpstreamHTTPException
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.form_integration import (
    FormActionType,
    FormIntegrationType,
)
from backend.app.repositories.form_repository import merge_action_parameters
from backend.app.services.google_sheets_oauth import DRIVE_FILE_SCOPE
from backend.app.services.sheets_reconsent import (
    LOCALE_MAX_LENGTH,
    MAILED_AT,
    NEEDS_RECONSENT,
    NOTIFY_PATH,
    RECONSENT_REQUIRED_CODE,
    SKIPPED_RUNS,
    TITLE_MAX_LENGTH,
    SheetsReconsentService,
    clip,
    count_legacy_sheets_actions,
    is_legacy_credential,
    is_legacy_scopes,
    notice_failure,
)
from backend.config import settings
from common.models.standard_form import ActionState, ParameterValue, Trigger
from tests.app.controllers.data import testUser

LEGACY_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets "
    "https://www.googleapis.com/auth/drive"
)


def encrypted_credential(scopes) -> str:
    return container.crypto().encrypt(
        json.dumps(
            {
                "token": "t",
                "refresh_token": "r",
                "token_uri": "https://oauth2.example.test/token",
                "client_id": "c",
                "client_secret": "s",
                "scopes": scopes,
            }
        )
    )


# --------------------------------------------------------------------- detection
class TestDetection:
    @pytest.mark.parametrize(
        "scopes, legacy",
        [
            (DRIVE_FILE_SCOPE, False),
            (f" {DRIVE_FILE_SCOPE} ", False),
            ([DRIVE_FILE_SCOPE], False),
            (LEGACY_SCOPES, True),
            (f"{DRIVE_FILE_SCOPE} https://www.googleapis.com/auth/drive", True),
            (f"{DRIVE_FILE_SCOPE} {DRIVE_FILE_SCOPE}", True),
            ("https://www.googleapis.com/auth/drive", True),
            ("", True),
            (None, True),
        ],
    )
    def test_only_exactly_drive_file_is_current(self, scopes, legacy):
        assert is_legacy_scopes({"scopes": scopes}) is legacy

    def test_a_credential_without_scopes_is_legacy(self):
        assert is_legacy_scopes({"token": "t"}) is True

    def test_no_credential_is_nothing_to_hold_back(self):
        assert is_legacy_credential(None, container.crypto()) is None
        assert is_legacy_credential("", container.crypto()) is None

    def test_an_unreadable_credential_counts_as_legacy(self):
        crypto = container.crypto()
        assert is_legacy_credential("not-a-fernet-token", crypto) is True
        assert is_legacy_credential(crypto.encrypt("not json"), crypto) is True

    def test_stored_credentials(self):
        crypto = container.crypto()
        assert is_legacy_credential(encrypted_credential(LEGACY_SCOPES), crypto)
        assert not is_legacy_credential(encrypted_credential(DRIVE_FILE_SCOPE), crypto)


class TestMergeActionParameters:
    def test_sets_appends_and_keeps_the_rest(self):
        current = [{"name": "Title", "value": "Sheet", "required": True}]
        merged = merge_action_parameters(current, {NEEDS_RECONSENT: "true"})
        assert merged == [
            {"name": "Title", "value": "Sheet", "required": True},
            {"name": NEEDS_RECONSENT, "value": "true", "required": False},
        ]
        assert current == [{"name": "Title", "value": "Sheet", "required": True}]

    def test_no_change_is_none(self):
        current = [{"name": NEEDS_RECONSENT, "value": "true", "required": False}]
        assert merge_action_parameters(current, {NEEDS_RECONSENT: "true"}) is None
        assert merge_action_parameters(current, remove=["absent"]) is None

    def test_counts_from_zero_and_up(self):
        first = merge_action_parameters(None, increment=SKIPPED_RUNS)
        assert first == [{"name": SKIPPED_RUNS, "value": "1", "required": False}]
        assert merge_action_parameters(first, increment=SKIPPED_RUNS)[0]["value"] == "2"
        broken = [{"name": SKIPPED_RUNS, "value": "x"}]
        assert merge_action_parameters(broken, increment=SKIPPED_RUNS)[0]["value"] == "1"

    def test_a_marker_is_claimed_once(self):
        claimed = merge_action_parameters([], {MAILED_AT: "t1"}, only_if_absent=MAILED_AT)
        assert claimed == [{"name": MAILED_AT, "value": "t1", "required": False}]
        assert (
            merge_action_parameters(claimed, {MAILED_AT: "t2"}, only_if_absent=MAILED_AT)
            is None
        )

    def test_remove(self):
        current = [{"name": MAILED_AT, "value": "t"}, {"name": "Title", "value": "x"}]
        assert merge_action_parameters(current, remove=[MAILED_AT]) == [
            {"name": "Title", "value": "x"}
        ]


# --------------------------------------------------------------------- fixtures
@pytest.fixture()
async def sheets_action():
    return await container.action_repository().create_global_action(
        ActionDto(
            name=FormIntegrationType.GOOGLE_SHEET.value,
            action_code="",
            type=FormActionType.EXTERNAL.value,
        ),
        testUser,
    )


@pytest.fixture()
async def other_action():
    return await container.action_repository().create_global_action(
        ActionDto(name="send_mail", action_code="", type=FormActionType.INTERNAL.value),
        testUser,
    )


@pytest.fixture()
def enforced(monkeypatch):
    monkeypatch.setattr(settings.google_sheets, "SHEETS_OAUTH", "backend")


@pytest.fixture()
def auth_mail(monkeypatch):
    """The auth service's mail endpoint, as the reconsent service calls it
    (retries of a transient failure without the waits)."""
    http_client = MagicMock()
    http_client.post = AsyncMock(return_value={"message": "Notice queued."})
    service = container.sheets_reconsent_service()
    monkeypatch.setattr(service, "_http_client", http_client)
    monkeypatch.setattr(service, "retry_delays_s", (0, 0, 0))
    monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", "internal-key")
    return http_client.post


@pytest.fixture()
def dispatched(monkeypatch):
    """Runs handed to the job runner (the workspace's copy of the action is
    looked up for each, stubbed here)."""
    service = container.action_service()
    start = AsyncMock()
    monkeypatch.setattr(service.temporal_service, "start_action_execution", start)
    workspace_repo = MagicMock()
    workspace_repo.get_workspace_with_action_by_id = AsyncMock(return_value=None)
    monkeypatch.setattr(service, "workspace_repo", workspace_repo)
    return start


async def attach(form_id, *actions, scopes=LEGACY_SCOPES, title="Sheet"):
    """Attach ``actions`` on submit; the Sheets one holds a credential with
    ``scopes`` (None: not connected)."""
    form_repo = container.form_repo()
    form = await form_repo.get_form_document_by_id(form_id)
    form.actions = {
        Trigger.on_submit: [ActionState(id=a.id, enabled=True) for a in actions]
    }
    form.parameters = {
        str(a.id): [ParameterValue(name="Title", value=title)] for a in actions
    }
    if scopes is not None:
        form.secrets = {
            str(actions[0].id): [
                ParameterValue(name="Credentials", value=encrypted_credential(scopes))
            ]
        }
    await form_repo.save_form(form)
    return await form_repo.get_form_document_by_id(form_id)


async def draft(form_id):
    return await container.form_repo().get_form_document_by_id(form_id)


def params(form, action) -> dict:
    return {p.name: p.value for p in (form.parameters or {}).get(str(action.id)) or []}


async def submit(form_id, workspace, settle=True):
    """A submission; ``settle``: then wait for the reconnect mail, which
    runs in the background."""
    await container.action_service().start_actions_for_submission(
        form=await draft(form_id), response=MagicMock(), workspace_id=workspace.id
    )
    if settle:
        await settled()


async def settled():
    await container.sheets_reconsent_service().drain()


# --------------------------------------------------------------------- submissions
class TestSubmission:
    async def test_a_legacy_grant_is_held_back_marked_counted_and_mailed_once(
        self, workspace, workspace_form, sheets_action, enforced, auth_mail, dispatched
    ):
        form_id = workspace_form.form_id
        before = await attach(form_id, sheets_action)

        await submit(form_id, workspace)

        dispatched.assert_not_called()
        stored = await draft(form_id)
        marks = params(stored, sheets_action)
        assert marks["Title"] == "Sheet"
        assert marks[NEEDS_RECONSENT] == "true"
        assert marks[SKIPPED_RUNS] == "1"
        assert marks[MAILED_AT]
        # the builder's conflict check is not disturbed by a submission
        assert stored.updated_at == before.updated_at
        auth_mail.assert_awaited_once()
        url = auth_mail.call_args.args[0]
        assert url == settings.auth_settings.BASE_URL + NOTIFY_PATH
        body = auth_mail.call_args.kwargs["json"]
        assert body == {
            "user_id": str(workspace.owner_id),
            "workspace_name": workspace.workspace_name,
            "workspace_title": workspace.title or None,
            "form_id": form_id,
            "form_title": stored.title or None,
            **(
                {"locale": stored.settings.language}
                if stored.settings and stored.settings.language
                else {}
            ),
        }
        assert auth_mail.call_args.kwargs["headers"]["X-Internal-Key"] == "internal-key"

        await submit(form_id, workspace)

        dispatched.assert_not_called()
        marks = params(await draft(form_id), sheets_action)
        assert marks[SKIPPED_RUNS] == "2"
        auth_mail.assert_awaited_once()

    async def test_other_actions_still_run(
        self,
        workspace,
        workspace_form,
        sheets_action,
        other_action,
        enforced,
        auth_mail,
        dispatched,
    ):
        await attach(workspace_form.form_id, sheets_action, other_action)

        await submit(workspace_form.form_id, workspace)

        [call] = dispatched.call_args_list
        assert call.kwargs["action"].id == other_action.id

    async def test_a_drive_file_grant_runs(
        self, workspace, workspace_form, sheets_action, enforced, auth_mail, dispatched
    ):
        await attach(workspace_form.form_id, sheets_action, scopes=DRIVE_FILE_SCOPE)

        await submit(workspace_form.form_id, workspace)

        dispatched.assert_awaited_once()
        assert NEEDS_RECONSENT not in params(
            await draft(workspace_form.form_id), sheets_action
        )
        auth_mail.assert_not_called()

    async def test_nothing_is_held_back_under_the_google_service(
        self, workspace, workspace_form, sheets_action, auth_mail, dispatched
    ):
        """Reconnecting there grants the broad scopes again: holding the run
        back would stop the action for good."""
        assert settings.google_sheets.SHEETS_OAUTH == "google_service"
        await attach(workspace_form.form_id, sheets_action)

        await submit(workspace_form.form_id, workspace)

        dispatched.assert_awaited_once()
        assert params(await draft(workspace_form.form_id), sheets_action) == {
            "Title": "Sheet"
        }
        auth_mail.assert_not_called()

    async def test_a_mail_that_was_not_handed_over_is_retried_on_the_next_use(
        self, workspace, workspace_form, sheets_action, enforced, auth_mail, dispatched
    ):
        await attach(workspace_form.form_id, sheets_action)
        auth_mail.side_effect = RuntimeError("auth down")

        await submit(workspace_form.form_id, workspace)

        marks = params(await draft(workspace_form.form_id), sheets_action)
        assert MAILED_AT not in marks
        assert marks[NEEDS_RECONSENT] == "true"
        dispatched.assert_not_called()

        auth_mail.side_effect = None
        await submit(workspace_form.form_id, workspace)

        assert auth_mail.await_count == 2
        marks = params(await draft(workspace_form.form_id), sheets_action)
        assert marks[MAILED_AT]
        assert marks[SKIPPED_RUNS] == "2"

    async def test_a_store_failure_still_skips_the_run_and_never_fails_it(
        self,
        workspace,
        workspace_form,
        sheets_action,
        enforced,
        auth_mail,
        dispatched,
        monkeypatch,
    ):
        await attach(workspace_form.form_id, sheets_action)
        monkeypatch.setattr(
            container.sheets_reconsent_service()._form_repo,
            "update_action_parameters",
            AsyncMock(side_effect=RuntimeError("store down")),
        )

        await submit(workspace_form.form_id, workspace)

        dispatched.assert_not_called()
        auth_mail.assert_not_called()

    async def test_logs_hold_ids_and_counts_only(
        self, workspace, workspace_form, sheets_action, enforced, auth_mail, dispatched
    ):
        from loguru import logger

        lines = []
        sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
        try:
            await attach(workspace_form.form_id, sheets_action, title="Secret sheet")
            await submit(workspace_form.form_id, workspace)
        finally:
            logger.remove(sink)
        text = "\n".join(lines)
        assert "sheets reconsent" in text
        assert str(sheets_action.id) in text
        form = await draft(workspace_form.form_id)
        for private in ("Secret sheet", testUser.sub, form.title or "\0", "refresh"):
            assert private not in text


    async def test_the_submission_does_not_wait_for_auth(
        self, workspace, workspace_form, sheets_action, enforced, auth_mail, dispatched
    ):
        """The mail runs in a task of its own: a slow or unreachable auth
        service never holds the respondent's request."""
        await attach(workspace_form.form_id, sheets_action)
        release = asyncio.Event()

        async def slow_auth(*args, **kwargs):
            await release.wait()
            return {"message": "Notice queued."}

        auth_mail.side_effect = slow_auth

        await asyncio.wait_for(submit(workspace_form.form_id, workspace, settle=False), 5)

        dispatched.assert_not_called()
        assert params(await draft(workspace_form.form_id), sheets_action)[SKIPPED_RUNS] == "1"
        release.set()
        await settled()
        auth_mail.assert_awaited_once()
        assert params(await draft(workspace_form.form_id), sheets_action)[MAILED_AT]

    async def test_a_422_is_final_kept_and_logged_once(
        self, workspace, workspace_form, sheets_action, enforced, auth_mail, dispatched
    ):
        """Auth refuses the notice for good (a handle it cannot link to, an
        unset CLIENT_ADMIN_URL): never retried, the marker stays."""
        from loguru import logger

        await attach(workspace_form.form_id, sheets_action)
        auth_mail.side_effect = UpstreamHTTPException(422, {"detail": "x"})
        lines = []
        sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
        try:
            for _ in range(3):
                await submit(workspace_form.form_id, workspace)
        finally:
            logger.remove(sink)

        auth_mail.assert_awaited_once()
        marks = params(await draft(workspace_form.form_id), sheets_action)
        assert marks[MAILED_AT]
        assert marks[SKIPPED_RUNS] == "3"
        refused = [line for line in lines if "refused by auth" in line]
        assert len(refused) == 1
        assert str(sheets_action.id) in refused[0]

    @pytest.mark.parametrize(
        "failure",
        [
            UpstreamHTTPException(503, "unavailable"),
            UpstreamHTTPException(500, "error"),
            httpx.ConnectTimeout("slow"),
            httpx.ReadTimeout("slow"),
        ],
        ids=["503", "500", "connect-timeout", "read-timeout"],
    )
    async def test_a_transient_failure_is_retried(
        self,
        workspace,
        workspace_form,
        sheets_action,
        enforced,
        auth_mail,
        dispatched,
        failure,
    ):
        await attach(workspace_form.form_id, sheets_action)
        auth_mail.side_effect = [failure, failure, {"message": "Notice queued."}]

        await submit(workspace_form.form_id, workspace)

        assert auth_mail.await_count == 3
        assert params(await draft(workspace_form.form_id), sheets_action)[MAILED_AT]

    async def test_a_lasting_transient_failure_releases_the_marker(
        self, workspace, workspace_form, sheets_action, enforced, auth_mail, dispatched
    ):
        await attach(workspace_form.form_id, sheets_action)
        auth_mail.side_effect = UpstreamHTTPException(503, "unavailable")

        await submit(workspace_form.form_id, workspace)

        assert auth_mail.await_count == 4  # the first try and three retries
        assert MAILED_AT not in params(await draft(workspace_form.form_id), sheets_action)

        auth_mail.side_effect = None
        await submit(workspace_form.form_id, workspace)

        assert auth_mail.await_count == 5
        assert params(await draft(workspace_form.form_id), sheets_action)[MAILED_AT]

    async def test_a_mailed_action_does_not_claim_again(
        self,
        workspace,
        workspace_form,
        sheets_action,
        enforced,
        auth_mail,
        dispatched,
        monkeypatch,
    ):
        """Once the form carries the marker, a submission writes only the
        skip count: no claim, no task."""
        await attach(workspace_form.form_id, sheets_action)
        await submit(workspace_form.form_id, workspace)
        service = container.sheets_reconsent_service()
        writes = AsyncMock(wraps=service._form_repo.update_action_parameters)
        monkeypatch.setattr(service._form_repo, "update_action_parameters", writes)

        await submit(workspace_form.form_id, workspace)

        [call] = writes.call_args_list
        assert call.kwargs.get("increment") == SKIPPED_RUNS
        auth_mail.assert_awaited_once()


# --------------------------------------------------------------------- the notice
class TestNotice:
    """``_mail_once`` against stand-ins: what is sent to auth and when."""

    def service(self, post, workspace_title="Acme"):
        form_repo = MagicMock()
        form_repo.update_action_parameters = AsyncMock(return_value=True)
        workspace_repo = MagicMock()
        workspace_repo.get_workspace_by_id = AsyncMock(
            return_value=SimpleNamespace(
                owner_id="owner-1", workspace_name="acme", title=workspace_title
            )
        )
        http_client = MagicMock()
        http_client.post = post
        service = SheetsReconsentService(
            form_repo, workspace_repo, container.crypto(), http_client
        )
        service.retry_delays_s = (0, 0)
        return service

    async def mail(self, service, form_title="Form", language=None):
        return await service._mail_once(
            form_id="f1",
            form_title=form_title,
            language=language,
            action_id="a1",
            workspace_id="w1",
        )

    async def test_titles_are_clipped_to_auths_limit(self):
        post = AsyncMock(return_value={})
        service = self.service(post, workspace_title="w" * 5000)

        assert await self.mail(service, form_title="f" * 5000) == "sent"

        body = post.call_args.kwargs["json"]
        for key in ("form_title", "workspace_title"):
            assert len(body[key]) == TITLE_MAX_LENGTH
            assert body[key].endswith("\u2026")

    async def test_short_titles_and_locale_are_sent_as_they_are(self):
        post = AsyncMock(return_value={})
        await self.mail(self.service(post), form_title="Form", language="nl")
        body = post.call_args.kwargs["json"]
        assert body["form_title"] == "Form"
        assert body["workspace_title"] == "Acme"
        assert body["locale"] == "nl"

    async def test_an_over_long_locale_is_left_out(self):
        post = AsyncMock(return_value={})
        await self.mail(self.service(post), language="x" * (LOCALE_MAX_LENGTH + 1))
        assert "locale" not in post.call_args.kwargs["json"]

    async def test_422_keeps_the_marker(self):
        post = AsyncMock(side_effect=UpstreamHTTPException(422, {}))
        service = self.service(post)
        assert await self.mail(service) == "final"
        post.assert_awaited_once()
        for call in service._form_repo.update_action_parameters.call_args_list:
            assert "remove" not in call.kwargs

    async def test_other_refusals_release_without_retrying(self):
        post = AsyncMock(side_effect=UpstreamHTTPException(403, {}))
        service = self.service(post)
        assert await self.mail(service) == "released"
        post.assert_awaited_once()
        last = service._form_repo.update_action_parameters.call_args_list[-1]
        assert last.kwargs["remove"] == [MAILED_AT]

    async def test_auths_hourly_cap_releases_without_retrying(self):
        post = AsyncMock(side_effect=UpstreamHTTPException(429, {}))
        service = self.service(post)
        assert await self.mail(service) == "released"
        post.assert_awaited_once()
        last = service._form_repo.update_action_parameters.call_args_list[-1]
        assert last.kwargs["remove"] == [MAILED_AT]

    async def test_a_cancelled_mail_releases_the_marker(self):
        """Cancelled mid-way (shutdown during a retry wait): the marker is
        freed, so a later use sends the mail."""
        post = AsyncMock(side_effect=UpstreamHTTPException(503, "unavailable"))
        service = self.service(post)
        service.retry_delays_s = (3600,)
        task = asyncio.create_task(self.mail(service))
        while not post.await_count:
            await asyncio.sleep(0)
        await asyncio.sleep(0)

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        last = service._form_repo.update_action_parameters.call_args_list[-1]
        assert last.kwargs["remove"] == [MAILED_AT]

    async def test_shutdown_waits_then_cancels_and_releases(self):
        release = asyncio.Event()

        async def slow(*args, **kwargs):
            await release.wait()
            return {}

        service = self.service(AsyncMock(side_effect=slow))
        form = SimpleNamespace(
            form_id="f1", title="Form", settings=None, parameters={}
        )
        service._notify_in_background(form, "a1", "w1")
        await asyncio.sleep(0)

        await service.shutdown(timeout=0.05)

        assert not service._pending
        last = service._form_repo.update_action_parameters.call_args_list[-1]
        assert last.kwargs["remove"] == [MAILED_AT]

    async def test_shutdown_lets_a_quick_mail_finish(self):
        post = AsyncMock(return_value={})
        service = self.service(post)
        form = SimpleNamespace(
            form_id="f1", title="Form", settings=None, parameters={}
        )
        service._notify_in_background(form, "a1", "w1")

        await service.shutdown(timeout=5)

        post.assert_awaited_once()
        for call in service._form_repo.update_action_parameters.call_args_list:
            assert "remove" not in call.kwargs

    async def test_shutdown_without_mails_returns_at_once(self):
        service = self.service(AsyncMock())
        await asyncio.wait_for(service.shutdown(timeout=60), 1)

    async def test_no_billing_owner_is_final(self):
        post = AsyncMock(return_value={})
        service = self.service(post)
        service._workspace_repo.get_workspace_by_id = AsyncMock(return_value=None)
        assert await self.mail(service) == "final"
        post.assert_not_called()

    async def test_someone_else_holds_the_marker(self):
        post = AsyncMock(return_value={})
        service = self.service(post)
        service._form_repo.update_action_parameters = AsyncMock(return_value=False)
        assert await self.mail(service) == "claimed"
        post.assert_not_called()


@pytest.mark.parametrize(
    "exc, kind",
    [
        (UpstreamHTTPException(422, {}), "final"),
        # auth's hourly cap per owner: retries within minutes cannot pass it
        (UpstreamHTTPException(429, {}), "other"),
        (UpstreamHTTPException(502, {}), "transient"),
        (UpstreamHTTPException(503, {}), "transient"),
        (httpx.ConnectError("x"), "transient"),
        (TimeoutError(), "transient"),
        (UpstreamHTTPException(401, {}), "other"),
        (UpstreamHTTPException(404, {}), "other"),
        (ValueError("x"), "other"),
    ],
)
def test_notice_failures(exc, kind):
    assert notice_failure(exc) == kind


def test_clip():
    assert clip(None) is None
    assert clip("") is None
    assert clip("abc", 3) == "abc"
    assert clip("abcd", 3) == "ab\u2026"


# --------------------------------------------------------------------- builder
def reconsent_url(workspace, form_id, action_id):
    return (
        f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/actions/"
        f"{action_id}/reconsent"
    )


class TestBuilder:
    async def test_opening_a_legacy_action_marks_it_and_mails_once(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        enforced,
        auth_mail,
    ):
        await attach(workspace_form.form_id, sheets_action)
        url = reconsent_url(workspace, workspace_form.form_id, sheets_action.id)

        for _ in range(2):
            response = await client.get(url, cookies=test_user_cookies)
            assert response.status_code == 200, response.text
            assert response.json() == {"needs_reconsent": True}
            await settled()

        marks = params(await draft(workspace_form.form_id), sheets_action)
        assert marks[NEEDS_RECONSENT] == "true"
        assert SKIPPED_RUNS not in marks  # nothing ran
        auth_mail.assert_awaited_once()

    async def test_a_drive_file_action_needs_nothing(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        enforced,
        auth_mail,
    ):
        await attach(workspace_form.form_id, sheets_action, scopes=DRIVE_FILE_SCOPE)
        response = await client.get(
            reconsent_url(workspace, workspace_form.form_id, sheets_action.id),
            cookies=test_user_cookies,
        )
        assert response.json() == {"needs_reconsent": False}
        auth_mail.assert_not_called()

    async def test_not_enforced_under_the_google_service(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        auth_mail,
    ):
        await attach(workspace_form.form_id, sheets_action)
        response = await client.get(
            reconsent_url(workspace, workspace_form.form_id, sheets_action.id),
            cookies=test_user_cookies,
        )
        assert response.json() == {"needs_reconsent": False}
        auth_mail.assert_not_called()

    async def test_an_action_not_on_the_form_is_not_found(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        enforced,
        auth_mail,
    ):
        response = await client.get(
            reconsent_url(workspace, workspace_form.form_id, sheets_action.id),
            cookies=test_user_cookies,
        )
        assert response.status_code == 404
        auth_mail.assert_not_called()

    async def test_someone_outside_the_workspace_is_refused(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies_1,
        enforced,
        auth_mail,
    ):
        await attach(workspace_form.form_id, sheets_action)
        response = await client.get(
            reconsent_url(workspace, workspace_form.form_id, sheets_action.id),
            cookies=test_user_cookies_1,
        )
        assert response.status_code in (403, 404)
        assert NEEDS_RECONSENT not in params(
            await draft(workspace_form.form_id), sheets_action
        )
        auth_mail.assert_not_called()


# --------------------------------------------------------------------- operator count
class TestOperatorCount:
    async def test_counts_only(
        self,
        workspace,
        workspace_form,
        workspace_form_1,
        sheets_action,
        other_action,
        enforced,
        auth_mail,
        dispatched,
    ):
        await attach(workspace_form.form_id, sheets_action)
        await attach(workspace_form_1.form_id, sheets_action, scopes=DRIVE_FILE_SCOPE)
        await submit(workspace_form.form_id, workspace)

        counts = await count_legacy_sheets_actions(
            container.form_repo(), container.action_repository(), container.crypto()
        )

        assert counts == {
            "sheets_actions_with_credential": 2,
            "legacy": 1,
            "drive_file": 1,
            "unreadable": 0,
            "needs_reconsent_marked": 1,
            "owners_mailed": 1,
            "skipped_runs": 1,
            "forms": 2,
        }
        assert all(isinstance(value, int) for value in counts.values())

    async def test_the_command_refuses_arguments(self, capsys):
        from backend.sheets_legacy import main

        assert await main(["--apply"]) == 2
        assert "usage" in capsys.readouterr().out


# --------------------------------------------------------------------- builder save
def actions_url(workspace, form_id):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/actions"


@pytest.fixture()
def create_spreadsheet(monkeypatch):
    provider = container.integration_provider().google_integration_provider
    create = AsyncMock(return_value="sheet-id")
    monkeypatch.setattr(provider.sheets_oauth, "create_spreadsheet", create)
    return create


class TestBuilderSave:
    """Saving a Sheets action creates its spreadsheet with the stored grant:
    a grant from before drive.file is never refreshed or used for it."""

    async def save(self, client, workspace, form_id, action, cookies):
        return await client.post(
            actions_url(workspace, form_id),
            json={
                "action_id": str(action.id),
                "parameters": [{"name": "Title", "value": "New sheet"}],
            },
            cookies=cookies,
        )

    async def test_a_legacy_grant_is_refused_and_the_markers_stay(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        enforced,
        auth_mail,
        create_spreadsheet,
    ):
        form_id = workspace_form.form_id
        await attach(form_id, sheets_action)
        await container.form_repo().update_action_parameters(
            form_id,
            str(sheets_action.id),
            values={NEEDS_RECONSENT: "true", MAILED_AT: "2026-10-25T00:00:00+00:00"},
        )
        before = params(await draft(form_id), sheets_action)

        response = await self.save(
            client, workspace, form_id, sheets_action, test_user_cookies
        )

        assert response.status_code == 409, response.text
        assert response.json()["code"] == RECONSENT_REQUIRED_CODE
        create_spreadsheet.assert_not_called()
        assert params(await draft(form_id), sheets_action) == before

    async def test_a_drive_file_grant_creates_the_sheet(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        enforced,
        auth_mail,
        create_spreadsheet,
    ):
        form_id = workspace_form.form_id
        await attach(form_id, sheets_action, scopes=DRIVE_FILE_SCOPE)

        response = await self.save(
            client, workspace, form_id, sheets_action, test_user_cookies
        )

        assert response.status_code == 200, response.text
        create_spreadsheet.assert_awaited_once()
        assert params(await draft(form_id), sheets_action)["Google Sheet Id"] == "sheet-id"

    async def test_unchanged_under_the_google_service(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        auth_mail,
        create_spreadsheet,
        monkeypatch,
    ):
        """There the Google Forms service creates the sheet, legacy grant
        or not (reconnecting grants the same scopes again)."""
        form_id = workspace_form.form_id
        await attach(form_id, sheets_action)
        provider = container.integration_provider().google_integration_provider
        monkeypatch.setattr(
            provider.form_provider_service,
            "get_provider_url",
            AsyncMock(return_value="http://google.test"),
        )
        service_post = AsyncMock(return_value="service-sheet-id")
        monkeypatch.setattr(provider.http_client, "post", service_post)

        response = await self.save(
            client, workspace, form_id, sheets_action, test_user_cookies
        )

        assert response.status_code == 200, response.text
        service_post.assert_awaited_once()
        create_spreadsheet.assert_not_called()
        assert (
            params(await draft(form_id), sheets_action)["Google Sheet Id"]
            == "service-sheet-id"
        )
