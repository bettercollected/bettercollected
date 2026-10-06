"""A form keeps each action's secrets under the action's id: writing or
removing one action's secrets leaves every other action's alone (#769), and
secrets never leave the backend in an API response."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import ActionState, ParameterValue
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.dtos.form_actions_dto import FormActionsDto
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.form_service import FormService
from backend.config import settings
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser2

FIRST = str(PydanticObjectId())
SECOND = str(PydanticObjectId())


async def _form(form_id):
    return await container.form_repo().get_form_document_by_id(form_id)


async def _secrets(form_id):
    return {
        action_id: {s.name: s.value for s in values}
        for action_id, values in ((await _form(form_id)).secrets or {}).items()
    }


async def _add_credentials(form_id, action_id, value):
    await container.integration_action_service().add_credentials_to_form_action(
        form_id=form_id, action_id=action_id, credentials=value
    )


async def _attach_actions(form_id, *action_ids):
    form = await _form(form_id)
    form.actions = {
        "on_submit": [ActionState(id=PydanticObjectId(a)) for a in action_ids]
    }
    await container.form_repo().save_form(form)


class TestAddCredentials:
    async def test_second_action_keeps_the_first_actions_credentials(
        self, workspace_form
    ):
        await _add_credentials(workspace_form.form_id, FIRST, "first-cred")
        await _add_credentials(workspace_form.form_id, SECOND, "second-cred")

        assert await _secrets(workspace_form.form_id) == {
            FIRST: {"Credentials": "first-cred"},
            SECOND: {"Credentials": "second-cred"},
        }

    async def test_updating_replaces_only_that_actions_credentials(
        self, workspace_form
    ):
        await _add_credentials(workspace_form.form_id, FIRST, "first-cred")
        await _add_credentials(workspace_form.form_id, SECOND, "second-cred")

        await _add_credentials(workspace_form.form_id, FIRST, "first-cred-2")

        assert await _secrets(workspace_form.form_id) == {
            FIRST: {"Credentials": "first-cred-2"},
            SECOND: {"Credentials": "second-cred"},
        }
        # one Credentials entry, not one per connection
        assert len((await _form(workspace_form.form_id)).secrets[FIRST]) == 1

    async def test_the_actions_other_secrets_are_kept(self, workspace_form):
        form = await _form(workspace_form.form_id)
        form.secrets = {FIRST: [ParameterValue(name="Token", value="tok")]}
        await container.form_repo().save_form(form)

        await _add_credentials(workspace_form.form_id, FIRST, "first-cred")

        assert await _secrets(workspace_form.form_id) == {
            FIRST: {"Token": "tok", "Credentials": "first-cred"}
        }


class TestRefreshAndRemove:
    async def test_refreshed_credentials_touch_only_that_action(
        self, workspace_form
    ):
        await _attach_actions(workspace_form.form_id, FIRST, SECOND)
        await _add_credentials(workspace_form.form_id, FIRST, "first-cred")
        await _add_credentials(workspace_form.form_id, SECOND, "second-cred")

        await container.form_actions_service().update_form_secrets(
            PydanticObjectId(workspace_form.form_id),
            PydanticObjectId(SECOND),
            FormActionsDto(
                name="Credentials", value="second-refreshed", type="secrets"
            ),
        )

        assert await _secrets(workspace_form.form_id) == {
            FIRST: {"Credentials": "first-cred"},
            SECOND: {"Credentials": "second-refreshed"},
        }

    async def test_removing_an_action_from_a_form_keeps_the_others_secrets(
        self, workspace_form
    ):
        await _attach_actions(workspace_form.form_id, FIRST, SECOND)
        await _add_credentials(workspace_form.form_id, FIRST, "first-cred")
        await _add_credentials(workspace_form.form_id, SECOND, "second-cred")

        await container.form_service().remove_action_from_form(
            form_id=PydanticObjectId(workspace_form.form_id),
            action_id=PydanticObjectId(FIRST),
            trigger="on_submit",
        )

        assert await _secrets(workspace_form.form_id) == {
            SECOND: {"Credentials": "second-cred"}
        }

    async def test_deleting_an_action_drops_only_its_secrets(self, workspace_form):
        await _attach_actions(workspace_form.form_id, FIRST, SECOND)
        await _add_credentials(workspace_form.form_id, FIRST, "first-cred")
        await _add_credentials(workspace_form.form_id, SECOND, "second-cred")

        await container.form_repo().remove_action_from_all_forms(
            action_id=PydanticObjectId(FIRST)
        )

        form = await _form(workspace_form.form_id)
        assert [str(a.id) for a in form.actions["on_submit"]] == [SECOND]
        assert await _secrets(workspace_form.form_id) == {
            SECOND: {"Credentials": "second-cred"}
        }

    async def test_deleting_an_action_drops_credentials_never_attached(
        self, workspace_form
    ):
        # OAuth stores the credentials before the action is added to the form
        await _add_credentials(workspace_form.form_id, FIRST, "first-cred")
        await _add_credentials(workspace_form.form_id, SECOND, "second-cred")

        await container.form_repo().remove_action_from_all_forms(
            action_id=PydanticObjectId(FIRST)
        )

        assert await _secrets(workspace_form.form_id) == {
            SECOND: {"Credentials": "second-cred"}
        }


JOB_KEY = "a-generated-job-key"


@pytest.fixture()
def user_details():
    """User details come from the auth service, outside the test."""
    with patch.object(
        FormService,
        "fetch_user_details",
        AsyncMock(return_value={"users_info": [{"_id": testUser.id}]}),
    ):
        yield


class TestSecretsStayInside:
    async def test_form_responses_carry_no_secrets(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        user_details,
    ):
        await _add_credentials(workspace_form.form_id, FIRST, "first-cred")
        base = f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}"

        fetched = await client.get(base, cookies=test_user_cookies)
        published = await client.post(f"{base}/publish", cookies=test_user_cookies)

        for response in (fetched, published):
            assert response.status_code == 200, response.text
            assert "secrets" not in response.json()
            assert "first-cred" not in response.text

    async def test_temporal_endpoints_do_not_echo_secrets(
        self, client: AsyncClient, monkeypatch, workspace, workspace_form
    ):
        await _attach_actions(workspace_form.form_id, FIRST)
        await _add_credentials(workspace_form.form_id, FIRST, "first-cred")
        monkeypatch.setattr(settings.temporal_settings, "api_key", JOB_KEY)
        key = {"api-key": JOB_KEY}

        refreshed = await client.patch(
            f"/api/v1/temporal/forms/{workspace_form.form_id}/actions/{FIRST}/secrets",
            headers=key,
            json={
                "name": "Credentials",
                "value": "first-refreshed",
                "type": "secrets",
            },
        )
        disabled = await client.patch(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}"
            f"/action/{FIRST}/update",
            headers=key,
        )

        for response in (refreshed, disabled):
            assert response.status_code == 200, response.text
            assert "first-refreshed" not in response.text
            assert "secrets" not in response.text
        assert (await _secrets(workspace_form.form_id))[FIRST] == {
            "Credentials": "first-refreshed"
        }


# ---------------------------------------------------------------------------
# Every way a form or an action leaves the backend
# ---------------------------------------------------------------------------

CRED = "encrypted-cred-value"
HOOK = "https://hooks.example.test/T000/B000/hook-token"
CODE = "send_to_partner()  # action code"


def _cookies(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def _no_action_config(text: str, *, parameters: bool = True):
    assert CRED not in text
    assert '"secrets"' not in text
    if parameters:
        assert HOOK not in text


@pytest.fixture()
async def partner_action():
    """A global action with code and a secret of its own."""
    return await container.action_repository().create_global_action(
        ActionDto(
            name="partner_sync",
            action_code=CODE,
            secrets=[ParameterValue(name="Token", value="global-secret")],
            parameters=[ParameterValue(name="Webhook URL", value="", required=True)],
        ),
        testUser,
    )


@pytest.fixture()
async def configured_form(workspace, workspace_form, partner_action):
    """A published form whose action has credentials and a webhook URL; the
    published version carries both, as publishing copies them."""
    action_id = str(partner_action.id)
    await container.action_repository().create_action_in_workspace_from_action(
        workspace_id=workspace.id, action_id=partner_action.id, credentials=CRED
    )
    await _attach_actions(workspace_form.form_id, action_id)
    await _add_credentials(workspace_form.form_id, action_id, CRED)
    form = await _form(workspace_form.form_id)
    form.parameters = {action_id: [ParameterValue(name="Webhook URL", value=HOOK)]}
    await container.form_repo().save_form(form)
    await container.workspace_form_service().publish_form(
        workspace.id, workspace_form.form_id, testUser
    )
    return workspace_form


async def _submit(workspace, form_id, user):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form_id,
        StandardFormResponseCamelModel(answers={}, anonymize=False),
        user,
    )


@pytest.fixture()
def job_starts(monkeypatch):
    """The action job is out of process: record what it would be given."""
    calls = []

    async def fake_start(action, form, response, workspace):
        calls.append({"action": action, "form": form, "workspace": workspace})

    monkeypatch.setattr(
        container.temporal_service(), "start_action_execution", fake_start
    )
    return calls


class TestRespondentAndPublicResponses:
    async def test_receipt_without_login_has_no_action_config(
        self, client: AsyncClient, workspace, configured_form, job_starts
    ):
        response = await _submit(workspace, configured_form.form_id, testUser2)
        version = await container.form_repo().get_latest_version_of_form(
            PydanticObjectId(configured_form.form_id)
        )
        assert version.secrets and version.parameters  # stored, as before

        receipt = await client.get(
            f"/api/v1/workspaces/{workspace.id}/submissions/by-uuid/"
            f"{response.submission_uuid}"
        )

        assert receipt.status_code == 200, receipt.text
        _no_action_config(receipt.text)

    async def test_view_my_submission_has_no_action_config(
        self, client: AsyncClient, workspace, configured_form, job_starts
    ):
        response = await _submit(workspace, configured_form.form_id, testUser2)

        mine = await client.get(
            f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}",
            cookies=_cookies(testUser2),
        )

        assert mine.status_code == 200, mine.text
        _no_action_config(mine.text)

    async def test_public_form_has_no_action_config(
        self, client: AsyncClient, workspace, configured_form
    ):
        url = f"/api/v1/workspaces/{workspace.id}/forms/{configured_form.form_id}"
        for cookies in (None, _cookies(testUser2)):
            public = await client.get(
                url, params={"published": "true"}, cookies=cookies
            )
            assert public.status_code == 200, public.text
            _no_action_config(public.text)
            version = await client.get(f"{url}/versions/latest", cookies=cookies)
            assert version.status_code == 200, version.text
            _no_action_config(version.text)

    async def test_editors_still_see_parameters_but_not_secrets(
        self,
        client: AsyncClient,
        workspace,
        configured_form,
        test_user_cookies,
        user_details,
    ):
        url = f"/api/v1/workspaces/{workspace.id}/forms/{configured_form.form_id}"
        fetched = await client.get(url, cookies=test_user_cookies)

        assert fetched.status_code == 200, fetched.text
        _no_action_config(fetched.text, parameters=False)
        assert HOOK in fetched.text  # the builder shows the configured URL


class TestAiResponses:
    async def test_ai_chat_returns_no_secrets(
        self,
        client: AsyncClient,
        monkeypatch,
        workspace,
        configured_form,
        test_user_cookies,
    ):
        fake = FakeProvider()
        use_fake_provider(monkeypatch, fake)
        await enable_ai(workspace)
        fake.replies = [json.dumps({"reply": "Nothing to change.", "ops": []})]

        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/"
            f"{configured_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "anything to improve?"},
        )

        assert response.status_code == 200, response.text
        assert "form" in response.json()
        _no_action_config(response.text, parameters=False)
        # nor were they put into the prompt
        assert CRED not in json.dumps(fake.calls, default=str)

    async def test_review_apply_returns_no_secrets(
        self, client: AsyncClient, workspace, configured_form, test_user_cookies
    ):
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/"
            f"{configured_form.form_id}/ai/review/apply",
            cookies=test_user_cookies,
            json={"ops": [{"op": "remove_field", "fieldId": "gone-field"}]},
        )

        assert response.status_code == 200, response.text
        assert "form" in response.json()
        _no_action_config(response.text, parameters=False)


class TestActionResponses:
    async def test_actions_api_returns_no_code_or_secrets(
        self, client: AsyncClient, partner_action, test_user_cookies
    ):
        listed = await client.get("/api/v1/actions", cookies=test_user_cookies)
        one = await client.get(
            f"/api/v1/actions/{partner_action.id}", cookies=test_user_cookies
        )

        for response in (listed, one):
            assert response.status_code == 200, response.text
            assert "global-secret" not in response.text
            assert CODE not in response.text
            assert "secrets" not in response.text
            assert "actionCode" not in response.text
        assert one.json()["parameters"][0]["name"] == "Webhook URL"

    async def test_the_action_job_still_gets_code_and_secrets(
        self, workspace, configured_form, partner_action, job_starts
    ):
        await _submit(workspace, configured_form.form_id, testUser2)

        assert len(job_starts) == 1
        job = job_starts[0]
        action_id = str(partner_action.id)
        form = json.loads(job["form"].json())
        assert form["secrets"][action_id][0]["value"] == CRED
        assert form["parameters"][action_id][0]["value"] == HOOK
        action = json.loads(job["action"].json())
        assert action["action_code"] == CODE
        assert action["secrets"][0]["name"] == "Token"
        assert job["workspace"]["secrets"][action_id][0]["value"] == CRED


class TestActionDeleteCleanup:
    async def test_delete_clears_versions_and_workspace_copies(
        self, workspace, configured_form, partner_action
    ):
        action_id = str(partner_action.id)
        await _add_credentials(configured_form.form_id, SECOND, "second-cred")

        await container.action_service().delete_action_from_workspace(
            action_id=partner_action.id
        )

        form = await _form(configured_form.form_id)
        versions = await container.form_repo().get_versions_of_form(
            PydanticObjectId(configured_form.form_id)
        )
        assert versions  # the published version had the action's secrets too
        for document in (form, *versions):
            assert action_id not in (document.secrets or {})
            assert action_id not in (document.parameters or {})
            triggers = (document.actions or {}).get("on_submit") or []
            assert action_id not in [str(a.id) for a in triggers]
        assert form.secrets[SECOND][0].value == "second-cred"
        actions = container.action_repository()
        copy = await actions.get_workspace_action(workspace.id, partner_action.id)
        assert copy is None
        assert await actions.get_action_by_id(partner_action.id) is None
