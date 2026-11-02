"""The workspace rule "require an authenticator app for members"."""

import pytest
from common.models.user import User

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_audit_event import TOTP_POLICY_CHANGED
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.mfa.helpers import (
    cookies_of_user,
    give_factor,
    member,
    require_totp,
)

# a route any member may call: it authorises ``form.read`` and nothing else
PROBE = "/api/v1/workspaces/{}/webhooks/status"
POLICY = "/api/v1/workspaces/{}/security/totp"

OWNER = testUser  # the owner of the ``workspace`` fixture (a platform admin too)


async def probe(client, workspace, user):
    return await client.get(PROBE.format(workspace.id), cookies=cookies_of_user(user))


async def test_a_workspace_without_the_rule_never_asks(client, totp_on, workspace):
    user = await member(workspace, "m@example.org")
    assert (await probe(client, workspace, user)).status_code == 200


async def test_a_member_without_a_second_factor_is_refused_on_every_request(
    client, totp_on, workspace
):
    await require_totp(workspace)
    user = await member(workspace, "m@example.org")
    for _ in range(2):  # every request, not only the first
        reply = await probe(client, workspace, user)
        assert reply.status_code == 403
        assert reply.json()["code"] == "mfa_required"
    # the owner too
    assert (await probe(client, workspace, OWNER)).json()["code"] == "mfa_required"


async def test_a_session_with_the_second_factor_passes(client, totp_on, workspace):
    await require_totp(workspace)
    user = await member(workspace, "m@example.org", mfa=True)
    assert (await probe(client, workspace, user)).status_code == 200
    assert (await probe(client, workspace, OWNER.model_copy(update={"mfa": True}))).status_code == 200


async def test_the_rule_is_inert_while_the_switch_is_off(client, workspace):
    assert settings.totp.ENABLED is False
    await require_totp(workspace)
    user = await member(workspace, "m@example.org")
    assert (await probe(client, workspace, user)).status_code == 200


async def test_api_keys_and_this_workspaces_sso_sessions_are_not_covered(
    client, totp_on, workspace
):
    await require_totp(workspace)
    key = await member(workspace, "api-key:ci", auth_method="api_key")
    assert (await probe(client, workspace, key)).status_code == 200
    sso = await member(
        workspace, "s@example.org", auth_method="sso", sso_workspace_id=str(workspace.id)
    )
    assert (await probe(client, workspace, sso)).status_code == 200
    # an SSO session of another workspace's identity provider is not
    other = await member(
        workspace, "o@example.org", auth_method="sso", sso_workspace_id="0" * 23 + "1"
    )
    assert (await probe(client, workspace, other)).json()["code"] == "mfa_required"


async def test_a_non_member_learns_nothing_from_the_rule(client, totp_on, workspace):
    await require_totp(workspace)
    stranger = User(id="5f00000000000000000000aa", sub="x@example.org", roles=["FORM_CREATOR"])
    reply = await probe(client, workspace, stranger)
    assert reply.status_code == 403
    assert "code" not in reply.json() or reply.json().get("code") != "mfa_required"


async def test_only_owners_set_the_rule_and_only_with_their_own_factor(
    client, totp_on, workspace
):
    url = POLICY.format(workspace.id)
    owner = OWNER
    # without a second factor in this very session: enrol first
    reply = await client.put(url, json={"required": True}, cookies=cookies_of_user(owner))
    assert reply.status_code == 409 and reply.json()["code"] == "enrol_first"
    assert not (await container.workspace_repo().find_by_id(workspace.id)).require_totp
    # an admin or an editor may not set it
    for role in (WorkspaceRoles.ADMIN, WorkspaceRoles.COLLABORATOR):
        user = await member(workspace, f"{role.value}@example.org", role, mfa=True)
        reply = await client.put(url, json={"required": True}, cookies=cookies_of_user(user))
        assert reply.status_code == 403, role
    reply = await client.put(
        url, json={"required": True}, cookies=cookies_of_user(owner.model_copy(update={"mfa": True}))
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["required"] is True and reply.json()["available"] is True
    assert (await container.workspace_repo().find_by_id(workspace.id)).require_totp is True
    events = await container.workspace_audit_repo().many()
    assert [e.event for e in events] == [TOTP_POLICY_CHANGED]
    assert events[0].workspace_id == workspace.id and events[0].user_id == owner.id
    assert events[0].required is True


async def test_turning_the_rule_off_takes_effect_at_once(client, totp_on, workspace):
    await require_totp(workspace)
    user = await member(workspace, "m@example.org")
    assert (await probe(client, workspace, user)).status_code == 403
    # the owner needs the second factor to change it, like any other request
    refused = await client.put(
        POLICY.format(workspace.id), json={"required": False}, cookies=cookies_of_user(OWNER)
    )
    assert refused.json()["code"] == "mfa_required"
    ok = await client.put(
        POLICY.format(workspace.id),
        json={"required": False},
        cookies=cookies_of_user(OWNER.model_copy(update={"mfa": True})),
    )
    assert ok.status_code == 200 and ok.json()["required"] is False
    assert (await probe(client, workspace, user)).status_code == 200
    # the audit trail says which way each change went
    changes = sorted(await container.workspace_audit_repo().many(), key=lambda e: e.created_at)
    assert [e.required for e in changes if e.event == TOTP_POLICY_CHANGED] == [False]


async def test_the_setting_answers_422_while_the_switch_is_off(client, workspace):
    reply = await client.put(
        POLICY.format(workspace.id),
        json={"required": True},
        cookies=cookies_of_user(OWNER.model_copy(update={"mfa": True})),
    )
    assert reply.status_code == 422 and reply.json()["code"] == "totp_off"


async def test_the_overview_counts_members_without_a_factor(client, totp_on, workspace):
    a = await member(workspace, "a@example.org")
    b = await member(workspace, "b@example.org")
    await member(workspace, "c@example.org")
    await give_factor(a.id)
    await give_factor(b.id)
    admin = await member(workspace, "admin@example.org", WorkspaceRoles.ADMIN)
    reply = await client.get(POLICY.format(workspace.id), cookies=cookies_of_user(admin))
    assert reply.status_code == 200, reply.text
    body = reply.json()
    # the owner, the workspace's invited editor, the admin and three members: two have a factor
    assert body == {"available": True, "required": False, "members": 6, "membersWithoutFactor": 4}
    # an editor may not read it
    editor = await member(workspace, "e@example.org")
    assert (
        await client.get(POLICY.format(workspace.id), cookies=cookies_of_user(editor))
    ).status_code == 403


def directory(monkeypatch, *users):
    """The auth service's answer for the member list: these accounts."""
    from unittest.mock import AsyncMock

    info = [{"_id": u.id, "email": u.sub, "first_name": "A", "last_name": "B"} for u in users]
    monkeypatch.setattr(
        container.workspace_members_service().http_client,
        "get",
        AsyncMock(return_value={"users_info": info}),
    )


async def test_the_member_list_shows_who_has_a_factor(client, totp_on, workspace, monkeypatch):
    a = await member(workspace, "a@example.org")
    await give_factor(a.id)
    directory(monkeypatch, a, OWNER)
    reply = await client.get(
        f"/api/v1/workspaces/{workspace.id}/members", cookies=cookies_of_user(OWNER)
    )
    assert reply.status_code == 200, reply.text
    flags = {m["id"]: m["totpEnabled"] for m in reply.json()}
    assert flags[a.id] is True and flags[OWNER.id] is False


async def test_the_member_list_has_no_column_while_the_switch_is_off(client, workspace, monkeypatch):
    a = await member(workspace, "a@example.org")
    await give_factor(a.id)
    directory(monkeypatch, a, OWNER)
    reply = await client.get(
        f"/api/v1/workspaces/{workspace.id}/members", cookies=cookies_of_user(OWNER)
    )
    assert all(m["totpEnabled"] is None for m in reply.json())


async def test_a_person_in_a_workspace_that_requires_one_cannot_turn_theirs_off(totp_on, workspace):
    from tests.app.mfa.helpers import enrolled, new_clock, service, signed_in
    from backend.app.exceptions import HTTPException
    import pytest as _pytest

    clock = new_clock()
    svc = service(clock)
    account = await signed_in("req@example.org", now=clock.now())
    secret, codes = await enrolled(svc, clock, account)
    from backend.app.schemas.workspace_user import WorkspaceUserDocument

    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=account.user.id, roles=[WorkspaceRoles.COLLABORATOR]
        )
    )
    await require_totp(workspace)
    clock.advance(30)
    with _pytest.raises(HTTPException) as refused:
        await svc.disable(account.user, codes[0])
    assert refused.value.status_code == 409
    assert refused.value.content["code"] == "required_by_workspace"
    # and nothing was removed
    assert await container.user_totp_repo().confirmed(account.user.id) is not None
    await require_totp(workspace, False)
    clock.advance(30)
    assert (await svc.disable(account.user, codes[1])).enabled is False
