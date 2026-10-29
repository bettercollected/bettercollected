"""The "send me a copy" action (``creator_copy_mail``) may only mail a current
member of the form's workspace (the form's creator only while they are one):
refused with a 422 when
it is attached (``copy_recipient_not_allowed``) and answered yes or no to the
actions executor right before it sends."""

from unittest.mock import AsyncMock, patch

import pytest
from common.models.standard_form import ParameterValue
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.copy_recipient import (
    COPY_RECIPIENT_NOT_ALLOWED,
    normalize_address,
)
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import invited_user, testUser, testUser1

RECIPIENT = "Receiving Mail Address"
JOB_KEY = "a-generated-job-key"
# who the (faked) auth service knows, by account id
EMAILS = {
    testUser.id: "owner@acme.example",
    invited_user.id: "Editor@Acme.example",
    testUser1.id: "outsider@elsewhere.example",
}


@pytest.fixture(autouse=True)
def auth_users():
    """User details come from the auth service, outside the test."""

    async def users(url, params=None, **kwargs):
        return {
            "users_info": [
                {"_id": user_id, "email": EMAILS[user_id]}
                for user_id in params["user_ids"]
                if user_id in EMAILS
            ]
        }

    with patch.object(
        container.copy_recipient_service()._http_client,
        "get",
        AsyncMock(side_effect=users),
    ) as get:
        yield get


@pytest.fixture()
async def mail_action():
    return await container.action_repository().create_global_action(
        ActionDto(
            name="creator_copy_mail",
            action_code="",
            predefined=True,
            parameters=[ParameterValue(name=RECIPIENT, value="", required=True)],
        ),
        testUser,
    )


def _cookies(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def _remove_member(workspace, user):
    membership = await container.workspace_user_repo().find_workspace_user(
        workspace.id, user.id
    )
    await container.workspace_user_repo().delete_by_id(membership.id)


async def _disable_member(workspace, user):
    membership = await container.workspace_user_repo().find_workspace_user(
        workspace.id, user.id
    )
    membership.disabled = True
    await container.workspace_user_repo().save(membership)


def _attach(client, workspace, form, action, address, user=testUser):
    return client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/actions",
        json={
            "action_id": str(action.id),
            "parameters": [{"name": RECIPIENT, "value": address}],
        },
        cookies=_cookies(user),
    )


async def _form_actions(form):
    stored = await container.form_repo().get_form_document_by_id(form.form_id)
    return (stored.actions or {}).get("on_submit") or [], stored.parameters or {}


async def _refused(response, form):
    assert response.status_code == 422, response.text
    assert response.json()["code"] == COPY_RECIPIENT_NOT_ALLOWED
    # the rule is named; nobody is
    assert "acme.example" not in response.text
    assert "elsewhere.example" not in response.text
    actions, parameters = await _form_actions(form)
    assert not actions and not parameters


class TestAtSave:
    @pytest.mark.parametrize(
        "address",
        [
            "owner@acme.example",
            "editor@acme.example",
            # case and surrounding space do not matter
            "  OWNER@Acme.Example ",
            "EDITOR@ACME.EXAMPLE\t",
        ],
    )
    async def test_a_member_is_allowed(
        self, client: AsyncClient, workspace, workspace_form, mail_action, address
    ):
        response = await _attach(
            client, workspace, workspace_form, mail_action, address
        )

        assert response.status_code == 200, response.text
        actions, parameters = await _form_actions(workspace_form)
        assert [str(a.id) for a in actions] == [str(mail_action.id)]
        assert parameters[str(mail_action.id)][0].value == address

    async def test_a_creator_who_left_the_workspace_is_refused(
        self, client: AsyncClient, workspace, workspace_form, mail_action
    ):
        # the creator's membership is gone: their address is no longer allowed,
        # although the form still names them as its creator
        await _remove_member(workspace, testUser)
        # another member (who may attach actions) saves the action
        response = await _attach(
            client,
            workspace,
            workspace_form,
            mail_action,
            "owner@acme.example",
            user=invited_user,
        )

        await _refused(response, workspace_form)

    async def test_a_disabled_creator_is_refused(
        self, client: AsyncClient, workspace, workspace_form, mail_action
    ):
        await _disable_member(workspace, testUser)
        response = await _attach(
            client,
            workspace,
            workspace_form,
            mail_action,
            "owner@acme.example",
            user=invited_user,
        )

        await _refused(response, workspace_form)

    async def test_a_non_member_is_refused(
        self, client: AsyncClient, workspace, workspace_form, mail_action
    ):
        response = await _attach(
            client, workspace, workspace_form, mail_action, "outsider@elsewhere.example"
        )

        await _refused(response, workspace_form)

    async def test_an_address_nobody_has_is_refused(
        self, client: AsyncClient, workspace, workspace_form, mail_action
    ):
        response = await _attach(
            client, workspace, workspace_form, mail_action, "attacker@evil.example"
        )

        await _refused(response, workspace_form)

    @pytest.mark.parametrize(
        "address",
        [
            "owner+news@acme.example",  # a plus tag of a member
            "own.er@acme.example",  # a dotted variant of a member
            "owner@acme.example\r\nBcc: attacker@evil.example",
            "owner@acme.example\nBcc: attacker@evil.example",
            "owner@acme.example,attacker@evil.example",
            "owner@acme.example; attacker@evil.example",
            "owner@acme.example attacker@evil.example",
            "Owner <owner@acme.example>",
            "owner@acme.example@evil.example",
            "owner",
            "@acme.example",
        ],
    )
    async def test_variants_and_injection_are_refused(
        self, client: AsyncClient, workspace, workspace_form, mail_action, address
    ):
        response = await _attach(
            client, workspace, workspace_form, mail_action, address
        )

        await _refused(response, workspace_form)

    async def test_a_disabled_member_is_refused(
        self, client: AsyncClient, workspace, workspace_form, mail_action
    ):
        membership = await container.workspace_user_repo().find_workspace_user(
            workspace.id, invited_user.id
        )
        membership.disabled = True
        await container.workspace_user_repo().save(membership)

        response = await _attach(
            client, workspace, workspace_form, mail_action, "editor@acme.example"
        )

        await _refused(response, workspace_form)

    async def test_a_member_of_another_workspace_is_refused(
        self, client: AsyncClient, workspace, workspace_form, workspace_1, mail_action
    ):
        # testUser1 owns workspace_1; this form lives in `workspace`
        response = await _attach(
            client, workspace, workspace_form, mail_action, "outsider@elsewhere.example"
        )

        await _refused(response, workspace_form)

    async def test_no_recipient_is_nothing_to_check(
        self, client: AsyncClient, workspace, workspace_form, mail_action
    ):
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/actions",
            json={"action_id": str(mail_action.id)},
            cookies=_cookies(testUser),
        )

        assert response.status_code == 200, response.text

    async def test_other_actions_are_not_held_to_the_rule(
        self, client: AsyncClient, workspace, workspace_form
    ):
        other = await container.action_repository().create_global_action(
            ActionDto(name="send_webhook", action_code="", predefined=True), testUser
        )
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/actions",
            json={
                "action_id": str(other.id),
                "parameters": [{"name": RECIPIENT, "value": "anyone@evil.example"}],
            },
            cookies=_cookies(testUser),
        )

        assert response.status_code == 200, response.text


class TestGlobalAction:
    async def test_a_default_recipient_is_refused(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/actions",
            json={
                "name": "creator_copy_mail",
                "actionCode": "",
                "parameters": [{"name": RECIPIENT, "value": "anyone@evil.example"}],
            },
            cookies=_cookies(testUser),
        )

        assert response.status_code == 422, response.text
        assert response.json()["code"] == COPY_RECIPIENT_NOT_ALLOWED

    async def test_an_empty_recipient_field_is_fine(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/actions",
            json={
                "name": "creator_copy_mail",
                "actionCode": "",
                "parameters": [{"name": RECIPIENT, "value": "", "required": True}],
            },
            cookies=_cookies(testUser),
        )

        assert response.status_code == 200, response.text


class TestAtSend:
    """What the actions executor asks right before it sends."""

    @pytest.fixture(autouse=True)
    def job_key(self, monkeypatch):
        monkeypatch.setattr(settings.temporal_settings, "api_key", JOB_KEY)

    def _ask(self, client, workspace, form, address, key=JOB_KEY):
        return client.post(
            f"/api/v1/temporal/workspaces/{workspace.id}/forms/{form.form_id}"
            "/copy-recipient",
            json={"address": address},
            headers={"api-key": key},
        )

    @pytest.mark.parametrize(
        "address, allowed",
        [
            ("owner@acme.example", True),
            (" EDITOR@acme.EXAMPLE ", True),
            ("outsider@elsewhere.example", False),
            ("owner+x@acme.example", False),
            ("owner@acme.example\r\nBcc: a@b.example", False),
        ],
    )
    async def test_members_yes_others_no(
        self, client: AsyncClient, workspace, workspace_form, address, allowed
    ):
        response = await self._ask(client, workspace, workspace_form, address)

        assert response.status_code == 200, response.text
        assert response.json() == {"allowed": allowed}

    async def test_a_creator_removed_between_save_and_send_is_not_allowed(
        self, client: AsyncClient, workspace, workspace_form, mail_action
    ):
        saved = await _attach(
            client, workspace, workspace_form, mail_action, "owner@acme.example"
        )
        assert saved.status_code == 200, saved.text
        before = await self._ask(client, workspace, workspace_form, "owner@acme.example")
        await _remove_member(workspace, testUser)

        after = await self._ask(client, workspace, workspace_form, "owner@acme.example")

        assert before.json() == {"allowed": True}
        assert after.json() == {"allowed": False}

    async def test_a_creator_disabled_between_save_and_send_is_not_allowed(
        self, client: AsyncClient, workspace, workspace_form, mail_action
    ):
        saved = await _attach(
            client, workspace, workspace_form, mail_action, "owner@acme.example"
        )
        assert saved.status_code == 200, saved.text
        await _disable_member(workspace, testUser)

        after = await self._ask(client, workspace, workspace_form, "owner@acme.example")

        assert after.json() == {"allowed": False}

    @pytest.mark.parametrize("address", ["", "   ", "\t\n", "a" * 255, "a" * 300])
    async def test_a_blank_or_overlong_address_is_a_422(
        self, client: AsyncClient, workspace, workspace_form, address
    ):
        response = await self._ask(client, workspace, workspace_form, address)

        assert response.status_code == 422, response.text

    async def test_an_address_of_the_longest_length_is_answered(
        self, client: AsyncClient, workspace, workspace_form
    ):
        address = "a" * 242 + "@acme.test"
        assert len(address) == 252

        response = await self._ask(client, workspace, workspace_form, address)

        assert response.json() == {"allowed": False}

    async def test_a_creator_who_changed_their_email_is_not_mailed_at_the_old_one(
        self, client: AsyncClient, workspace, workspace_form, monkeypatch
    ):
        # the creator's address is read live from the account, not kept
        # with the action: the old one stops working once they change it
        before = await self._ask(
            client, workspace, workspace_form, "owner@acme.example"
        )
        monkeypatch.setitem(EMAILS, testUser.id, "owner-new@acme.example")

        old = await self._ask(client, workspace, workspace_form, "owner@acme.example")
        new = await self._ask(
            client, workspace, workspace_form, "owner-new@acme.example"
        )

        assert before.json() == {"allowed": True}
        assert old.json() == {"allowed": False}
        assert new.json() == {"allowed": True}

    async def test_a_member_removed_since_the_save_is_no_longer_allowed(
        self, client: AsyncClient, workspace, workspace_form, mail_action
    ):
        saved = await _attach(
            client, workspace, workspace_form, mail_action, "editor@acme.example"
        )
        assert saved.status_code == 200, saved.text
        before = await self._ask(
            client, workspace, workspace_form, "editor@acme.example"
        )
        membership = await container.workspace_user_repo().find_workspace_user(
            workspace.id, invited_user.id
        )
        await container.workspace_user_repo().delete_by_id(membership.id)

        after = await self._ask(
            client, workspace, workspace_form, "editor@acme.example"
        )

        assert before.json() == {"allowed": True}
        assert after.json() == {"allowed": False}

    async def test_a_form_of_another_workspace_allows_nothing(
        self, client: AsyncClient, workspace, workspace_form, workspace_1
    ):
        response = await self._ask(
            client, workspace_1, workspace_form, "outsider@elsewhere.example"
        )

        assert response.json() == {"allowed": False}

    async def test_the_job_key_is_needed(
        self, client: AsyncClient, workspace, workspace_form
    ):
        response = await self._ask(
            client, workspace, workspace_form, "owner@acme.example", key="wrong"
        )

        assert response.status_code == 403
        assert '"allowed"' not in response.text


class TestNormalise:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("A@B.C", "a@b.c"),
            ("  a@b.c ", "a@b.c"),
            ("a+t@b.c", "a+t@b.c"),
            ("a.b@b.c", "a.b@b.c"),
            (None, None),
            (7, None),
            ("", None),
            ("a@b.c\x00", None),
            ("a@b.c x", None),
            ("a" * 260 + "@b.c", None),
        ],
    )
    def test_trim_and_case_fold_only(self, value, expected):
        assert normalize_address(value) == expected
