"""Workspace-scoped endpoints refuse users outside the workspace (and data
outside the workspace named in the URL), and still work for its members."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.form_integration import FormIntegrationType
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from tests.app.controllers.data import formData, testUser, testUser1


def _url(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}"


async def _workspace_form_settings(workspace, form_id):
    return (
        await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=form_id
        )
    ).settings


class TestFormSettingsPatch:
    async def test_non_member_cannot_change_a_public_form(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        test_user_cookies_1,
    ):
        url = f"{_url(workspace)}/forms/{workspace_form.form_id}/settings"
        made_public = await client.patch(
            url, cookies=test_user_cookies, json={"private": False}
        )
        assert made_public.status_code == 200

        response = await client.patch(
            url,
            cookies=test_user_cookies_1,
            json={"hidden": True, "pinned": True, "customUrl": "taken-over"},
        )

        assert response.status_code == 403
        form_settings = await _workspace_form_settings(
            workspace, workspace_form.form_id
        )
        assert not form_settings.hidden
        assert not form_settings.pinned
        assert form_settings.custom_url != "taken-over"

    async def test_member_can_change_settings(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies
    ):
        url = f"{_url(workspace)}/forms/{workspace_form.form_id}/settings"

        response = await client.patch(
            url, cookies=test_user_cookies, json={"pinned": True}
        )

        assert response.status_code == 200
        assert response.json()["settings"]["pinned"] is True

    async def test_disable_branding_is_refused_on_a_free_workspace(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies
    ):
        url = f"{_url(workspace)}/forms/{workspace_form.form_id}/settings"

        response = await client.patch(
            url, cookies=test_user_cookies, json={"disableBranding": True}
        )

        assert response.status_code == 403
        form_settings = await _workspace_form_settings(
            workspace, workspace_form.form_id
        )
        assert not form_settings.disable_branding


@pytest.fixture()
def no_s3():
    aws = container.aws_service()
    with patch.object(
        aws, "upload_file_to_s3", AsyncMock(return_value="https://s3/media_library/x")
    ) as upload, patch.object(aws, "delete_file_from_s3", MagicMock()) as remove:
        yield upload, remove


async def _add_media(workspace):
    return await container.media_library_repo().add_media_in_workspace_library(
        workspace_id=str(workspace.id),
        media_url="https://s3/media_library/abc",
        media_type="IMAGE",
        media_name="logo.png",
        s3_key="abc",
    )


class TestMediaLibrary:
    async def test_non_member_cannot_list_upload_or_delete(
        self, client: AsyncClient, workspace, test_user_cookies_1, no_s3
    ):
        media = await _add_media(workspace)
        url = f"{_url(workspace)}/media"

        listed = await client.get(url, cookies=test_user_cookies_1)
        uploaded = await client.post(
            url,
            cookies=test_user_cookies_1,
            files={"file": ("x.png", b"\x89PNG", "image/png")},
        )
        deleted = await client.delete(
            f"{url}/{media.media_id}", cookies=test_user_cookies_1
        )

        assert (listed.status_code, uploaded.status_code, deleted.status_code) == (
            403,
            403,
            403,
        )
        upload, remove = no_s3
        upload.assert_not_called()
        remove.assert_not_called()
        assert await container.media_library_repo().get_single_media_from_workspace_library(
            workspace_id=str(workspace.id), media_id=media.media_id
        )

    async def test_member_can_list_upload_and_delete(
        self, client: AsyncClient, workspace, test_user_cookies, no_s3
    ):
        media = await _add_media(workspace)
        url = f"{_url(workspace)}/media"

        listed = await client.get(url, cookies=test_user_cookies)
        uploaded = await client.post(
            url,
            cookies=test_user_cookies,
            files={"file": ("x.png", b"\x89PNG", "image/png")},
        )
        deleted = await client.delete(
            f"{url}/{media.media_id}", cookies=test_user_cookies
        )

        assert listed.status_code == 200
        assert [m["mediaId"] for m in listed.json()] == [str(media.media_id)]
        assert uploaded.status_code == 200
        assert deleted.status_code == 200


class TestFlowAnalytics:
    async def test_non_member_is_refused(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies_1
    ):
        response = await client.get(
            f"{_url(workspace)}/forms/{workspace_form.form_id}/flow-analytics",
            cookies=test_user_cookies_1,
        )
        assert response.status_code == 403

    async def test_form_of_another_workspace_is_not_found(
        self,
        client: AsyncClient,
        workspace,
        workspace_1,
        workspace_form,
        test_user_cookies_1,
    ):
        """testUser1 owns workspace_1 but the form is in testUser's workspace."""
        response = await client.get(
            f"{_url(workspace_1)}/forms/{workspace_form.form_id}/flow-analytics",
            cookies=test_user_cookies_1,
        )
        assert response.status_code == 404

    async def test_member_gets_the_analytics(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies
    ):
        response = await client.get(
            f"{_url(workspace)}/forms/{workspace_form.form_id}/flow-analytics",
            cookies=test_user_cookies,
        )
        assert response.status_code == 200


@pytest.fixture()
async def sheets_action():
    return await container.action_repository().create_global_action(
        ActionDto(
            name=FormIntegrationType.GOOGLE_SHEET.value,
            action_code="",
            type="external",
        ),
        testUser,
    )


@pytest.fixture()
def google_provider():
    """The Google provider service is out of process: stub its two calls."""
    provider = (
        container.integration_service().integration__provider_factory.google_integration_provider
    )
    http_client = MagicMock()
    http_client.get = AsyncMock(return_value={"oauth_url": "https://google/oauth"})
    http_client.post = AsyncMock(return_value="encrypted-credentials")
    form_provider_service = MagicMock()
    form_provider_service.get_provider_url = AsyncMock(return_value="http://google")
    with patch.object(provider, "http_client", http_client), patch.object(
        provider, "form_provider_service", form_provider_service
    ):
        yield http_client


def _state_for(user) -> str:
    return container.crypto().encrypt(
        json.dumps({"client_referer_uri": None, "user_id": user.id})
    )


CALLBACK_URL = f"/api/v1/integration/{FormIntegrationType.GOOGLE_SHEET.value}/oauth"


async def _secrets(form_id):
    return (await container.form_repo().get_form_document_by_id(form_id)).secrets


class TestIntegrationOAuth:
    async def test_oauth_state_is_bound_to_the_user(
        self, client: AsyncClient, test_user_cookies, google_provider
    ):
        response = await client.get(CALLBACK_URL, cookies=test_user_cookies)

        assert response.status_code == 200
        state = google_provider.get.call_args.kwargs["params"]["state"]
        assert json.loads(container.crypto().decrypt(state))["user_id"] == testUser.id

    async def test_non_member_cannot_attach_credentials_to_a_form(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies_1,
        google_provider,
    ):
        response = await client.post(
            f"{CALLBACK_URL}/callback",
            cookies=test_user_cookies_1,
            json={
                "state": _state_for(testUser1),
                "code": "attacker-code",
                "form_id": workspace_form.form_id,
                "action_id": str(sheets_action.id),
            },
        )

        assert response.status_code == 403
        google_provider.post.assert_not_called()
        assert not await _secrets(workspace_form.form_id)

    async def test_state_of_another_user_is_refused(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_provider,
    ):
        response = await client.post(
            f"{CALLBACK_URL}/callback",
            cookies=test_user_cookies,
            json={
                "state": _state_for(testUser1),
                "code": "code",
                "form_id": workspace_form.form_id,
                "action_id": str(sheets_action.id),
            },
        )

        assert response.status_code == 403
        google_provider.post.assert_not_called()

    @pytest.mark.parametrize("action", ["other", "unknown", "not-an-id"])
    async def test_action_must_be_a_sheets_action(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        google_provider,
        action,
    ):
        if action == "other":
            other = await container.action_repository().create_global_action(
                ActionDto(name="creator_copy_mail", action_code=""), testUser
            )
            action_id = str(other.id)
        elif action == "unknown":
            action_id = str(PydanticObjectId())
        else:
            action_id = "not-an-id"

        response = await client.post(
            f"{CALLBACK_URL}/callback",
            cookies=test_user_cookies,
            json={
                "state": _state_for(testUser),
                "code": "code",
                "form_id": workspace_form.form_id,
                "action_id": action_id,
            },
        )

        assert response.status_code == 404
        google_provider.post.assert_not_called()

    async def test_member_attaches_credentials(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_provider,
    ):
        response = await client.post(
            f"{CALLBACK_URL}/callback",
            cookies=test_user_cookies,
            json={
                "state": _state_for(testUser),
                "code": "code",
                "form_id": workspace_form.form_id,
                "action_id": str(sheets_action.id),
            },
        )

        assert response.status_code == 200, response.text
        secrets = await _secrets(workspace_form.form_id)
        assert secrets[str(sheets_action.id)][0].value == "encrypted-credentials"


async def _deletion_requests(form_id):
    return await container.form_response_repo().list_deletion_requests_for_form_ids(
        [form_id]
    )


class TestResponsesAcrossWorkspaces:
    async def test_member_of_another_workspace_cannot_request_deletion(
        self,
        client: AsyncClient,
        workspace_1,
        workspace_form_response: dict[str, Any],
        test_user_cookies_1,
    ):
        """testUser1 is a member (owner) of workspace_1 only; the response
        belongs to testUser's workspace."""
        response = await client.delete(
            f"{_url(workspace_1)}/submissions/{workspace_form_response['response_id']}",
            cookies=test_user_cookies_1,
        )

        assert response.status_code == 404
        assert not await _deletion_requests(workspace_form_response["form_id"])

    async def test_member_requests_deletion(
        self,
        client: AsyncClient,
        workspace,
        workspace_form_response: dict[str, Any],
        test_user_cookies,
    ):
        response = await client.delete(
            f"{_url(workspace)}/submissions/{workspace_form_response['response_id']}",
            cookies=test_user_cookies,
        )

        assert response.status_code == 200
        assert len(await _deletion_requests(workspace_form_response["form_id"])) == 1

    async def test_respondent_requests_deletion_of_their_response(
        self,
        client: AsyncClient,
        workspace,
        workspace_form_response_1: dict[str, Any],
        test_user_cookies_1,
    ):
        """testUser1 is not a member of the workspace but submitted the response."""
        response = await client.delete(
            f"{_url(workspace)}/submissions/{workspace_form_response_1['response_id']}",
            cookies=test_user_cookies_1,
        )

        assert response.status_code == 200
        assert len(await _deletion_requests(workspace_form_response_1["form_id"])) == 1

    async def test_member_of_another_workspace_cannot_delete_a_response(
        self,
        client: AsyncClient,
        monkeypatch,
        workspace_1,
        workspace_form_response: dict[str, Any],
        test_user_cookies_1,
    ):
        monkeypatch.setattr(settings.api_settings, "ENABLE_FORM_CREATION", True)
        form_id = workspace_form_response["form_id"]
        response_id = workspace_form_response["response_id"]

        response = await client.delete(
            f"{_url(workspace_1)}/forms/{form_id}/response/{response_id}",
            cookies=test_user_cookies_1,
        )

        assert response.status_code == 404
        assert await container.form_response_repo().get_response(response_id)

    async def test_member_deletes_a_response(
        self,
        client: AsyncClient,
        monkeypatch,
        workspace,
        workspace_form_response: dict[str, Any],
        test_user_cookies,
    ):
        monkeypatch.setattr(settings.api_settings, "ENABLE_FORM_CREATION", True)
        form_id = workspace_form_response["form_id"]
        response_id = workspace_form_response["response_id"]

        with patch.object(container.aws_service(), "delete_folder_from_s3"):
            response = await client.delete(
                f"{_url(workspace)}/forms/{form_id}/response/{response_id}",
                cookies=test_user_cookies,
            )

        assert response.status_code == 200
        assert not await container.form_response_repo().get_response(response_id)


class TestWorkspacePatch:
    async def test_admin_who_is_not_the_owner_is_refused(
        self, client: AsyncClient, workspace, test_user_cookies_1
    ):
        await container.workspace_user_repo().save(
            WorkspaceUserDocument(
                workspace_id=workspace.id,
                user_id=testUser1.id,
                roles=[WorkspaceRoles.ADMIN],
            )
        )

        response = await client.patch(
            _url(workspace), cookies=test_user_cookies_1, data={"title": "Renamed"}
        )

        assert response.status_code == 403
        saved = await container.workspace_repo().get_or_404(workspace.id)
        assert saved.title != "Renamed"

    async def test_owner_can_patch(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        response = await client.patch(
            _url(workspace), cookies=test_user_cookies, data={"title": "Renamed"}
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Renamed"


class TestInvitationMail:
    async def test_backend_sends_the_internal_key(
        self, client: AsyncClient, workspace, test_user_cookies, monkeypatch
    ):
        monkeypatch.setattr(
            settings.auth_settings, "INTERNAL_NOTIFY_KEY", "backend-internal-key"
        )
        sent = AsyncMock(return_value="Mail sent successfully!!")
        with patch("common.services.http_client.HttpClient.get", sent):
            response = await client.post(
                f"{_url(workspace)}/members/invitations",
                cookies=test_user_cookies,
                json={"email": "new@example.com", "role": "COLLABORATOR"},
            )

        assert response.status_code == 200, response.text
        (url,), kwargs = sent.call_args
        assert url.endswith("/users/invite/send/mail")
        assert kwargs["headers"] == {"X-Internal-Key": "backend-internal-key"}


async def _refused(call) -> int:
    with pytest.raises(HTTPException) as refused:
        await call
    return refused.value.status_code


class TestFormsAcrossWorkspaces:
    """testUser1 owns workspace_1; the form is in testUser's workspace."""

    async def test_member_of_another_workspace_cannot_delete_the_form(
        self,
        client: AsyncClient,
        workspace_1,
        workspace_form_response: dict[str, Any],
        test_user_cookies_1,
    ):
        form_id = workspace_form_response["form_id"]

        response = await client.delete(
            f"{_url(workspace_1)}/forms/{form_id}", cookies=test_user_cookies_1
        )

        assert response.status_code == 404
        assert await container.form_repo().get_form_document_by_id(form_id)
        assert await container.form_response_repo().get_response(
            workspace_form_response["response_id"]
        )

    async def test_member_deletes_the_form(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies
    ):
        response = await client.delete(
            f"{_url(workspace)}/forms/{workspace_form.form_id}",
            cookies=test_user_cookies,
        )

        assert response.status_code == 200
        assert not await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )

    async def test_member_of_another_workspace_cannot_update_or_publish(
        self, workspace_1, workspace_form
    ):
        service = container.workspace_form_service()
        form = StandardForm(**{**formData, "title": "Taken over"})

        updating = service.update_form(
            workspace_1.id, workspace_form.form_id, form, testUser1
        )
        assert await _refused(updating) == 404
        publishing = service.publish_form(
            workspace_1.id, workspace_form.form_id, testUser1
        )
        assert await _refused(publishing) == 404
        saved = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        assert saved.title != "Taken over"
        assert not await container.form_repo().get_latest_version_of_form(
            workspace_form.form_id
        )

    async def test_member_updates_and_publishes(self, workspace, workspace_form):
        service = container.workspace_form_service()
        form = StandardForm(**{**formData, "title": "Updated"})

        await service.update_form(workspace.id, workspace_form.form_id, form, testUser)
        published = await service.publish_form(
            workspace.id, workspace_form.form_id, testUser
        )

        assert published.title == "Updated"


async def _group_emails(group_id):
    group = await container.responder_groups_service().responder_groups_repo.get_emails_in_group(
        group_id
    )
    return sorted(group["emails"]) if group else None


class TestResponderGroupsAcrossWorkspaces:
    """testUser1 is the admin (owner) of workspace_1; the group belongs to
    testUser's workspace."""

    async def test_admin_of_another_workspace_cannot_touch_a_group(
        self, workspace_1, workspace_group
    ):
        service = container.responder_groups_service()
        before = await _group_emails(workspace_group.id)

        adding = service.add_emails_to_group(
            workspace_1.id, workspace_group.id, [testUser1.sub], testUser1
        )
        assert await _refused(adding) == 404
        reading = service.get_users_in_group(
            workspace_1.id, workspace_group.id, testUser1
        )
        assert await _refused(reading) == 404
        removing = service.remove_responder_group(
            workspace_1.id, workspace_group.id, testUser1
        )
        assert await _refused(removing) == 404
        assert await _group_emails(workspace_group.id) == before

    async def test_group_cannot_be_attached_to_a_form_of_another_workspace(
        self, workspace_1, workspace_form
    ):
        creating = container.responder_groups_service().create_group(
            workspace_1.id,
            "Mine",
            [testUser1.sub],
            testUser1,
            workspace_form.form_id,
            None,
            None,
        )
        assert await _refused(creating) == 404
        attaching = container.workspace_form_service().add_groups_to_form(
            workspace_1.id, workspace_form.form_id, [], testUser1
        )
        assert await _refused(attaching) == 404
        groups = await container.responder_groups_service().responder_groups_repo.get_groups_in_workspace(
            workspace_1.id
        )
        assert not groups

    async def test_admin_manages_their_group(self, workspace, workspace_group):
        service = container.responder_groups_service()

        await service.remove_responder_group(workspace.id, workspace_group.id, testUser)
        assert await _group_emails(workspace_group.id) is None


@pytest.fixture()
async def private_template(workspace):
    template = FormTemplateDocument(title="Private", settings={"is_public": False})
    template.workspace_id = workspace.id
    return await container.form_template_repo().save(template)


class TestPrivateTemplates:
    async def test_other_workspace_cannot_copy_a_private_template(
        self, workspace_1, private_template
    ):
        copying = container.form_template_service().create_form_from_template(
            workspace_1.id, private_template.id, testUser1
        )
        assert await _refused(copying) == 403

    async def test_member_creates_a_form_from_their_private_template(
        self, workspace, private_template
    ):
        form = await container.form_template_service().create_form_from_template(
            workspace.id, private_template.id, testUser
        )
        assert form.title == "Private"
