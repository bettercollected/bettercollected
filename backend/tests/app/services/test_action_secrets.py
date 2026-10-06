"""A form keeps each action's secrets under the action's id: writing or
removing one action's secrets leaves every other action's alone (#769), and
secrets never leave the backend in an API response."""

from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import ActionState, ParameterValue
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.form_actions_dto import FormActionsDto
from backend.app.services.form_service import FormService
from backend.config import settings
from tests.app.controllers.data import testUser

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
