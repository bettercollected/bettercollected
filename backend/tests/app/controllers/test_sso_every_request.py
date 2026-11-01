"""A workspace that requires single sign-on refuses a session that doesn't
meet the requirement on every request, not only at its next token refresh
(docs/sso.md, "Existing sessions"): 403 ``sso_required`` from the workspace
authorisation, break-glass for owners, nothing for guests on other domains,
API keys and SSO off, and no extra reads beyond one cached lookup."""

import pytest
from common.ids import RecordId
from common.models.user import User

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser
from tests.app.sso_helpers import (  # noqa: F401 — fixtures
    DOMAIN,
    add_connection,
    sso_on,
    verify_domain,
)

PUBLIC_API = "/api/v1/public/v1"


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def _member(workspace, email, method, role=WorkspaceRoles.COLLABORATOR, **extra):
    """A member of the workspace with an address ``email``, and the cookies of
    a session signed in with ``method``."""
    user = User(id=str(RecordId()), sub=email, auth_method=method, **extra)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=user.id, roles=[role]
        )
    )
    return user, _cookies(user)


@pytest.fixture()
async def sso_workspace(workspace, sso_on):
    await verify_domain(workspace.id)
    await add_connection(workspace.id)
    return workspace


async def _require(client, workspace):
    reply = await client.put(
        f"/api/v1/workspaces/{workspace.id}/sso/settings",
        json={"ssoRequired": True},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 200, reply.text


@pytest.fixture()
async def required(client, sso_workspace):
    await _require(client, sso_workspace)
    return sso_workspace


def permissions_url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/permissions"


def forms_url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/forms"


def _sso_required(reply):
    assert reply.status_code == 403, reply.text
    body = reply.json()
    assert body["code"] == "sso_required", body
    assert "single sign-on" in body["message"]


# -- the window is gone --------------------------------------------------------
@pytest.mark.parametrize("method", ["otp", "google", None])
async def test_a_plain_session_is_refused_at_once(client, required, method):
    _, cookies = await _member(required, "jane@" + DOMAIN, method)
    _sso_required(await client.get(forms_url(required), cookies=cookies))
    # the permissions answer (also read on public pages) is empty, not an error
    reply = await client.get(permissions_url(required), cookies=cookies)
    assert reply.status_code == 200 and reply.json()["permissions"] == []


async def test_switching_the_requirement_on_refuses_a_live_session_next_request(
    client, sso_workspace
):
    """The session was fine a moment ago: the same token, no refresh."""
    _, cookies = await _member(sso_workspace, "jane@" + DOMAIN, "otp")
    assert (
        await client.get(forms_url(sso_workspace), cookies=cookies)
    ).status_code == 200
    await _require(client, sso_workspace)
    _sso_required(await client.get(forms_url(sso_workspace), cookies=cookies))
    # and back: the requirement is read from the workspace on each request
    reply = await client.put(
        f"/api/v1/workspaces/{sso_workspace.id}/sso/settings",
        json={"ssoRequired": False},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 200, reply.text
    assert (
        await client.get(forms_url(sso_workspace), cookies=cookies)
    ).status_code == 200


async def test_an_sso_session_is_accepted(client, required):
    _, cookies = await _member(required, "jane@" + DOMAIN, "sso")
    assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200
    reply = await client.get(permissions_url(required), cookies=cookies)
    assert reply.status_code == 200 and reply.json()["permissions"]


async def test_the_has_permission_branches_fail_closed_without_the_error(
    client, required
):
    user, _ = await _member(required, "jane@" + DOMAIN, "otp")
    authorization = container.authorization_service()
    # a bool question never raises: no permission
    from backend.app.models.enum.permission import Permission

    assert not await authorization.has_permission(
        user, Permission.FORM_READ, required.id
    )
    assert await authorization.effective_permissions(user, required.id) == frozenset()


# -- exceptions ----------------------------------------------------------------
@pytest.mark.parametrize(
    "method,allowed",
    [("otp", True), ("google", False), (None, False), ("sso", True)],
)
async def test_an_owner_keeps_break_glass_by_email_code(
    client, required, method, allowed
):
    # an owner whose own address is on the SSO domain
    owner = User(id=testUser.id, sub="boss@" + DOMAIN, auth_method=method)
    reply = await client.get(forms_url(required), cookies=_cookies(owner))
    if allowed:
        assert reply.status_code == 200, reply.text
    else:
        _sso_required(reply)


async def test_a_member_owner_by_role_keeps_break_glass_too(client, required):
    _, cookies = await _member(
        required, "co@" + DOMAIN, "otp", role=WorkspaceRoles.OWNER
    )
    assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200


async def test_a_disabled_owner_membership_is_no_break_glass(client, required):
    user = User(id=str(RecordId()), sub="co@" + DOMAIN, auth_method="otp")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=required.id,
            user_id=user.id,
            roles=[WorkspaceRoles.OWNER],
            disabled=True,
        )
    )
    reply = await client.get(forms_url(required), cookies=_cookies(user))
    # no membership at all: plain 403, never a hint about SSO
    assert reply.status_code == 403
    assert "sso_required" not in reply.text


async def test_a_guest_on_another_domain_is_not_subject_to_it(client, required):
    _, cookies = await _member(required, "guest@partner-corp.org", "otp")
    assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200
    _, cookies = await _member(required, "guest2@partner-corp.org", "google")
    assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200


async def test_a_plain_session_elsewhere_is_left_alone(client, required, workspace_1):
    """Only the workspace that requires SSO refuses: another workspace the
    same address belongs to is unaffected (the refresh ends the session)."""
    user, cookies = await _member(workspace_1, "jane@" + DOMAIN, "otp")
    assert (await client.get(forms_url(workspace_1), cookies=cookies)).status_code == 200


async def test_a_workspace_without_a_connection_refuses_nothing(client, workspace, sso_on):
    """Required but no enabled connection: members could not sign in with SSO
    either, so nothing is refused (the policy's own precondition)."""
    await verify_domain(workspace.id)
    await container.workspace_repo().set_fields(workspace, {"sso_required": True})
    _, cookies = await _member(workspace, "jane@" + DOMAIN, "otp")
    assert (await client.get(forms_url(workspace), cookies=cookies)).status_code == 200


# -- API keys and MCP ----------------------------------------------------------
async def _key_token(workspace, name="ops-key"):
    created = await container.api_key_service().create_key(
        workspace.id,
        CreateAPIKeyDto(name=name, scopes=["forms:read"]),
        testUser,
    )
    return created.token


async def test_api_keys_are_machine_credentials_and_stay_as_they_are(
    client, required
):
    token = await _key_token(required)
    reply = await client.get(
        f"{PUBLIC_API}/forms", headers={"Authorization": f"Bearer {token}"}
    )
    assert reply.status_code == 200, reply.text


async def test_a_key_named_like_an_address_on_the_domain_is_not_a_session(
    client, required
):
    """The acting user's ``sub`` is ``api-key:<name>``: a name that looks like
    an address on the SSO domain must not make the key a plain session."""
    token = await _key_token(required, name="ops@" + DOMAIN)
    reply = await client.get(
        f"{PUBLIC_API}/forms", headers={"Authorization": f"Bearer {token}"}
    )
    assert reply.status_code == 200, reply.text


# -- SSO off: nothing changes --------------------------------------------------
async def test_with_sso_off_nothing_is_refused_and_nothing_is_read(
    client, required, monkeypatch
):
    monkeypatch.setattr(settings.sso, "ENABLED", False)
    policy = container.sso_policy_service()
    calls = _spy(policy, monkeypatch)
    _, cookies = await _member(required, "jane@" + DOMAIN, "otp")
    for _ in range(3):
        assert (
            await client.get(forms_url(required), cookies=cookies)
        ).status_code == 200
    assert calls == {"claim": 0, "connection": 0}


# -- cost ----------------------------------------------------------------------
def _spy(policy, monkeypatch):
    calls = {"claim": 0, "connection": 0}
    claim, connection = policy._domains.sso_domain_claim, policy._connections.find_enabled

    async def counted_claim(*args, **kwargs):
        calls["claim"] += 1
        return await claim(*args, **kwargs)

    async def counted_connection(*args, **kwargs):
        calls["connection"] += 1
        return await connection(*args, **kwargs)

    monkeypatch.setattr(policy._domains, "sso_domain_claim", counted_claim)
    monkeypatch.setattr(policy._connections, "find_enabled", counted_connection)
    return calls


async def test_a_refused_session_costs_one_cached_lookup(client, required, monkeypatch):
    policy = container.sso_policy_service()
    policy._requirement_cache.clear()
    calls = _spy(policy, monkeypatch)
    _, cookies = await _member(required, "jane@" + DOMAIN, "otp")
    for _ in range(5):
        _sso_required(await client.get(forms_url(required), cookies=cookies))
    assert calls == {"claim": 1, "connection": 1}


async def test_the_lookup_is_refreshed_after_its_ttl(client, required, monkeypatch):
    policy = container.sso_policy_service()
    policy._requirement_cache.clear()
    now = {"t": 1000.0}
    monkeypatch.setattr(policy, "_clock", lambda: now["t"])
    calls = _spy(policy, monkeypatch)
    _, cookies = await _member(required, "jane@" + DOMAIN, "otp")
    _sso_required(await client.get(forms_url(required), cookies=cookies))
    _sso_required(await client.get(forms_url(required), cookies=cookies))
    assert calls["claim"] == 1
    now["t"] += 31
    _sso_required(await client.get(forms_url(required), cookies=cookies))
    assert calls["claim"] == 2


async def test_an_sso_session_and_a_plain_workspace_cost_nothing_extra(
    client, required, workspace_1, monkeypatch
):
    policy = container.sso_policy_service()
    policy._requirement_cache.clear()
    calls = _spy(policy, monkeypatch)
    _, sso_cookies = await _member(required, "jane@" + DOMAIN, "sso")
    for _ in range(3):
        assert (
            await client.get(forms_url(required), cookies=sso_cookies)
        ).status_code == 200
    # a workspace that doesn't require SSO is never looked up
    _, cookies = await _member(workspace_1, "jane2@" + DOMAIN, "otp")
    assert (await client.get(forms_url(workspace_1), cookies=cookies)).status_code == 200
    assert calls == {"claim": 0, "connection": 0}


# -- one rule ------------------------------------------------------------------
@pytest.mark.parametrize("method", ["otp", "google", "sso", None])
@pytest.mark.parametrize("is_owner", [True, False])
@pytest.mark.parametrize("scope", [None, "respondent"])
async def test_the_request_check_is_the_refresh_rule(
    client, required, method, is_owner, scope
):
    """``blocks_session`` (every request) and ``unmet_requirement`` (refresh,
    the selection screen) never disagree for a member of the workspace."""
    policy = container.sso_policy_service()
    policy._requirement_cache.clear()
    user_id = testUser.id if is_owner else str(RecordId())
    email = "someone@" + DOMAIN
    workspace = await container.workspace_repo().find_by_id(required.id)
    expected = await policy.unmet_requirement(email, method, scope, user_id)
    blocked = await policy.blocks_session(
        workspace, email, method, scope, is_owner=is_owner
    )
    assert blocked == (expected is not None)
