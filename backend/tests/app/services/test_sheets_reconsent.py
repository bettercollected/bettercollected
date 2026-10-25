"""A Google Sheets credential from before ``drive.file`` is held back on its next
use, never kept silently (services/sheets_reconsent.py): the run is skipped and
counted, the action is marked ``needs_reconsent`` and the billing owner is
mailed once. Only while the backend runs the Sheets flow."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
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
    MAILED_AT,
    NEEDS_RECONSENT,
    NOTIFY_PATH,
    SKIPPED_RUNS,
    count_legacy_sheets_actions,
    is_legacy_credential,
    is_legacy_scopes,
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
    """The auth service's mail endpoint, as the reconsent service calls it."""
    http_client = MagicMock()
    http_client.post = AsyncMock(return_value={"message": "Notice queued."})
    monkeypatch.setattr(container.sheets_reconsent_service(), "_http_client", http_client)
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


async def submit(form_id, workspace):
    await container.action_service().start_actions_for_submission(
        form=await draft(form_id), response=MagicMock(), workspace_id=workspace.id
    )


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
