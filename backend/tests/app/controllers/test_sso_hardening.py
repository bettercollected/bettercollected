"""Single sign-on hardening before it goes on (docs/sso.md): SSO sessions are
bound to the workspace whose identity provider signed them in, an owner's
break-glass is audited, the owners see the API keys that predate the
requirement, and an owner is asked before switching it on from a session the
requirement would refuse."""

import datetime as dt

import pytest
from common.ids import RecordId
from common.models.user import User
from loguru import logger

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from backend.app.services.session_service import decode_token
from backend.app.services.sso import policy as policy_module
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser
from tests.app.controllers.test_sso_every_request import (  # noqa: F401 — fixtures
    _cookies,
    _member,
    _require,
    _sso_required,
    forms_url,
    required,
    sso_workspace,
)
from tests.app.controllers.test_sso_login import sign_in, sso_on_of
from tests.app.controllers.test_sso_review import (  # noqa: F401 — fixture
    _refresh_token,
    fake_status,
    refresh,
)
from tests.app.sso_helpers import (  # noqa: F401 — fixtures
    DOMAIN,
    add_connection,
    sso_on,
    verify_domain,
)


def settings_url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/sso/settings"


def overview_url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/sso"


# -- sessions are bound to the workspace ----------------------------------------
async def test_an_sso_sign_in_binds_the_session_to_the_workspace(client, sso_workspace):
    reply = await sign_in(client)
    claims = decode_token(reply.cookies.get("Authorization"))
    assert claims["auth_method"] == "sso"
    assert claims["sso_workspace_id"] == str(sso_workspace.id)
    session = await container.session_repo().get(claims["sid"])
    assert session.sso_workspace_id == str(sso_workspace.id)


async def test_a_refresh_keeps_the_binding(client, sso_workspace, fake_status):
    reply = await sign_in(client)
    claims = decode_token(reply.cookies.get("Authorization"))
    fake_status.email = "jane@" + DOMAIN
    refreshed = await refresh(client, reply.cookies.get("RefreshToken"))
    assert refreshed.status_code == 200, refreshed.text
    assert decode_token(refreshed.cookies.get("Authorization"))[
        "sso_workspace_id"
    ] == str(sso_workspace.id)


async def test_only_an_sso_session_carries_the_binding():
    user = User(
        id=str(RecordId()),
        sub="a@" + DOMAIN,
        auth_method="otp",
        sso_workspace_id=str(RecordId()),
    )
    assert "sso_workspace_id" not in decode_token(access_token(user))


async def _move_domain_claim(to_workspace):
    repo = container.workspace_domain_repo()
    claim = await repo.find_verified(DOMAIN)
    claim.workspace_id = to_workspace.id
    await repo.save(claim)


async def test_a_domain_claim_that_moves_cannot_carry_sso_sessions_over(
    client, required, workspace_1, fake_status
):
    """Signed in through workspace A; the domain is later claimed by B (which
    requires SSO with its own connection): A's session is refused at B, on the
    next request and at its refresh."""
    signed_in = await sign_in(client)
    claims = decode_token(signed_in.cookies.get("Authorization"))
    cookies = {
        "Authorization": signed_in.cookies.get("Authorization"),
        "RefreshToken": signed_in.cookies.get("RefreshToken"),
    }
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace_1.id,
            user_id=claims["id"],
            roles=[WorkspaceRoles.COLLABORATOR],
        )
    )
    assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200

    await _move_domain_claim(workspace_1)
    await add_connection(workspace_1.id)
    await container.workspace_repo().set_fields(workspace_1, {"sso_required": True})
    container.sso_policy_service()._requirement_cache.clear()

    _sso_required(await client.get(forms_url(workspace_1), cookies=cookies))

    fake_status.email = "jane@" + DOMAIN
    ended = await refresh(client, cookies["RefreshToken"])
    assert ended.status_code == 401
    assert "single sign-on" in ended.text


async def test_a_session_signed_in_through_this_workspace_is_accepted_and_free(
    client, required, monkeypatch
):
    policy = container.sso_policy_service()
    policy._requirement_cache.clear()
    reads = []
    original = policy._domains.sso_domain_claim

    async def spy(*args, **kwargs):
        reads.append(1)
        return await original(*args, **kwargs)

    monkeypatch.setattr(policy._domains, "sso_domain_claim", spy)
    _, cookies = await _member(required, "jane@" + DOMAIN, "sso")
    for _ in range(3):
        assert (
            await client.get(forms_url(required), cookies=cookies)
        ).status_code == 200
    assert reads == []


@pytest.mark.parametrize("binding", ["other", "none"])
async def test_an_sso_session_of_another_workspace_or_without_a_binding_is_refused(
    client, required, binding
):
    extra = {"sso_workspace_id": str(RecordId()) if binding == "other" else None}
    _, cookies = await _member(required, "jane@" + DOMAIN, "sso", **extra)
    _sso_required(await client.get(forms_url(required), cookies=cookies))


async def test_an_unbound_sso_session_ends_at_refresh(client, required, fake_status):
    user = User(id=str(RecordId()), sub="jane@" + DOMAIN, email_verified=True)
    token = await _refresh_token(user, method="sso")
    reply = await refresh(client, token)
    assert reply.status_code == 401
    assert "single sign-on" in reply.text


async def test_an_sso_session_of_another_workspace_ends_at_refresh(
    client, required, fake_status
):
    user = User(id=str(RecordId()), sub="jane@" + DOMAIN, email_verified=True)
    token = await _refresh_token(
        user, method="sso", sso_workspace_id=str(RecordId())
    )
    assert (await refresh(client, token)).status_code == 401


async def test_the_binding_is_only_read_where_the_workspace_requires_sso(
    client, sso_workspace, workspace_1
):
    """An SSO session bound elsewhere is no problem on a workspace that does
    not require SSO, and guests on other domains are not subject to it."""
    _, cookies = await _member(
        workspace_1, "jane@" + DOMAIN, "sso", sso_workspace_id=str(RecordId())
    )
    assert (await client.get(forms_url(workspace_1), cookies=cookies)).status_code == 200
    await _require(client, sso_workspace)
    _, cookies = await _member(
        sso_workspace, "guest@partner-corp.org", "sso", sso_workspace_id=str(RecordId())
    )
    assert (
        await client.get(forms_url(sso_workspace), cookies=cookies)
    ).status_code == 200


async def test_owner_break_glass_is_unchanged_by_the_binding(client, required):
    otp = User(id=testUser.id, sub="boss@" + DOMAIN, auth_method="otp")
    assert (
        await client.get(forms_url(required), cookies=_cookies(otp))
    ).status_code == 200
    # an owner's SSO session bound elsewhere is no email code: no break-glass
    stray = User(
        id=testUser.id,
        sub="boss@" + DOMAIN,
        auth_method="sso",
        sso_workspace_id=str(RecordId()),
    )
    _sso_required(await client.get(forms_url(required), cookies=_cookies(stray)))
    # nor is a token without a recorded method
    none = User(id=testUser.id, sub="boss@" + DOMAIN)
    _sso_required(await client.get(forms_url(required), cookies=_cookies(none)))


# -- break-glass is audited ---------------------------------------------------------
@pytest.fixture()
def audit_lines():
    lines = []
    sink = logger.add(lambda m: lines.append(m.record["message"]), level="WARNING")
    yield lines
    logger.remove(sink)


def _audits(lines):
    return [m for m in lines if m.startswith("AUDIT sso_break_glass")]


async def test_break_glass_is_audited_once_per_session_and_hour(
    client, required, audit_lines, monkeypatch
):
    policy = container.sso_policy_service()
    policy._break_glass_seen.clear()
    now = {"t": 5000.0}
    monkeypatch.setattr(policy, "_clock", lambda: now["t"])
    owner = User(
        id=testUser.id, sub="boss@" + DOMAIN, auth_method="otp", sid=str(RecordId())
    )
    cookies = _cookies(owner)
    for _ in range(4):
        assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200
    (line,) = _audits(audit_lines)
    # ids only: the workspace, the user and the session; never the address
    assert str(required.id) in line and owner.id in line and owner.sid in line
    assert "boss@" not in line and DOMAIN not in line

    # another session of the same owner is another entry; after an hour, again
    other = owner.model_copy(update={"sid": str(RecordId())})
    assert (
        await client.get(forms_url(required), cookies=_cookies(other))
    ).status_code == 200
    assert len(_audits(audit_lines)) == 2
    now["t"] += policy_module.BREAK_GLASS_AUDIT_SECONDS + 1
    assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200
    assert len(_audits(audit_lines)) == 3


async def test_nothing_is_audited_when_break_glass_was_not_needed(
    client, required, audit_lines
):
    container.sso_policy_service()._break_glass_seen.clear()
    # an SSO session of this workspace, a guest owner, an API key's user
    sso = User(
        id=testUser.id,
        sub="boss@" + DOMAIN,
        auth_method="sso",
        sso_workspace_id=str(required.id),
    )
    guest = User(id=testUser.id, sub="boss@partner-corp.org", auth_method="otp")
    for user in (sso, guest):
        assert (
            await client.get(forms_url(required), cookies=_cookies(user))
        ).status_code == 200
    # a refused session is not break-glass either
    google = User(id=testUser.id, sub="boss@" + DOMAIN, auth_method="google")
    _sso_required(await client.get(forms_url(required), cookies=_cookies(google)))
    assert _audits(audit_lines) == []


async def test_nothing_is_audited_without_the_requirement(client, sso_workspace, audit_lines):
    owner = User(id=testUser.id, sub="boss@" + DOMAIN, auth_method="otp")
    assert (
        await client.get(forms_url(sso_workspace), cookies=_cookies(owner))
    ).status_code == 200
    assert _audits(audit_lines) == []


# -- the API keys the requirement does not cover ------------------------------------
async def _key(workspace, name, created_by=None):
    created = await container.api_key_service().create_key(
        workspace.id,
        CreateAPIKeyDto(name=name, scopes=["forms:read"]),
        User(id=created_by or testUser.id, sub=testUser.sub),
    )
    return created


def _key_names(settings):
    return sorted(k["name"] for k in settings["apiKeys"])


async def test_switching_the_requirement_on_lists_the_existing_keys(
    client, sso_workspace
):
    first = await _key(sso_workspace, "ops")
    revoked = await _key(sso_workspace, "old")
    await container.api_key_service().revoke_key(
        sso_workspace.id, revoked.id, testUser
    )
    reply = await client.put(
        settings_url(sso_workspace),
        json={"ssoRequired": True},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 200, reply.text
    keys = reply.json()["apiKeys"]
    assert [k["name"] for k in keys] == ["ops"]
    (key,) = keys
    assert key["id"] == first.id and key["createdBy"] == testUser.id
    assert key["createdAt"] and key["lastUsedAt"] is None
    # no secret of any kind
    assert set(key) == {
        "id",
        "name",
        "prefix",
        "scopes",
        "createdBy",
        "createdByLabel",
        "createdAt",
        "lastUsedAt",
    }
    assert first.token not in reply.text and "keyHash" not in reply.text


async def test_the_overview_lists_only_keys_created_before_the_requirement(
    client, sso_workspace
):
    await _key(sso_workspace, "before")
    await _require(client, sso_workspace)
    changed = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=1)
    await container.workspace_repo().set_fields(
        sso_workspace, {"sso_required_changed_at": changed}
    )
    after = await _key(sso_workspace, "after")
    repo = container.workspace_api_key_repo()
    document = await repo.get_or_404(RecordId(after.id))
    document.created_at = changed + dt.timedelta(seconds=30)
    await repo.save(document)
    reply = await client.get(overview_url(sso_workspace), cookies=_cookies(testUser))
    assert reply.status_code == 200, reply.text
    assert _key_names(reply.json()["settings"]) == ["before"]
    assert after.token not in reply.text


async def test_the_list_carries_last_use_and_the_creator_name(client, sso_workspace):
    _, auth = sso_on_of()
    creator = auth.add_account("maker@" + DOMAIN)
    created = await _key(sso_workspace, "ops")
    repo = container.workspace_api_key_repo()
    document = await repo.get_or_404(RecordId(created.id))
    document.created_by = creator["id"]
    await repo.save(document)
    assert await repo.touch_last_used(RecordId(created.id), dt.datetime.now(dt.timezone.utc))
    await _require(client, sso_workspace)
    reply = await client.get(overview_url(sso_workspace), cookies=_cookies(testUser))
    (key,) = reply.json()["settings"]["apiKeys"]
    assert key["createdBy"] == creator["id"]
    # the fake auth only knows an address; a name is used when auth sends one
    assert key["createdByLabel"] == "maker@" + DOMAIN
    assert key["lastUsedAt"] is not None


async def test_no_key_list_without_the_requirement(client, sso_workspace):
    await _key(sso_workspace, "ops")
    reply = await client.get(overview_url(sso_workspace), cookies=_cookies(testUser))
    assert reply.json()["settings"]["apiKeys"] is None


async def test_the_key_list_stays_with_those_who_manage_security(
    client, required
):
    await _key(required, "ops")
    _, cookies = await _member(required, "viewer@partner-corp.org", "otp", WorkspaceRoles.VIEWER)
    assert (
        await client.get(overview_url(required), cookies=cookies)
    ).status_code == 403


async def test_the_keys_stay_valid(client, sso_workspace):
    """Exempt by decision: listing them changes nothing about them."""
    created = await _key(sso_workspace, "ops")
    await _require(client, sso_workspace)
    reply = await client.get(
        "/api/v1/public/v1/forms",
        headers={"Authorization": f"Bearer {created.token}"},
    )
    assert reply.status_code == 200


# -- warn before lock-out ---------------------------------------------------------------
LOCKOUT = "sso_lockout_unconfirmed"


async def _put(client, workspace, user, **body):
    return await client.put(
        settings_url(workspace),
        json={"ssoRequired": True, **body},
        cookies=_cookies(user),
    )


@pytest.mark.parametrize("method", ["google", None])
async def test_an_owner_who_would_lock_themself_out_must_confirm(
    client, sso_workspace, method
):
    owner = User(id=testUser.id, sub="boss@" + DOMAIN, auth_method=method)
    overview = await client.get(overview_url(sso_workspace), cookies=_cookies(owner))
    assert overview.json()["settings"]["callerWouldBeLockedOut"] is True

    refused = await _put(client, sso_workspace, owner)
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == LOCKOUT
    stored = await container.workspace_repo().find_by_id(sso_workspace.id)
    assert not stored.sso_required

    accepted = await _put(client, sso_workspace, owner, confirmLockout=True)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["ssoRequired"] is True
    stored = await container.workspace_repo().find_by_id(sso_workspace.id)
    assert stored.sso_required is True


@pytest.mark.parametrize(
    "owner",
    [
        # an email-code session keeps break-glass
        User(id=testUser.id, sub="boss@" + DOMAIN, auth_method="otp"),
        # an address off the SSO domains is not subject to it
        User(id=testUser.id, sub="boss@partner-corp.org", auth_method="google"),
    ],
)
async def test_no_warning_when_the_session_would_not_be_refused(
    client, sso_workspace, owner
):
    overview = await client.get(overview_url(sso_workspace), cookies=_cookies(owner))
    assert overview.json()["settings"]["callerWouldBeLockedOut"] is False
    reply = await _put(client, sso_workspace, owner)
    assert reply.status_code == 200, reply.text


async def test_an_sso_session_of_this_workspace_needs_no_confirmation(
    client, sso_workspace
):
    owner = User(
        id=testUser.id,
        sub="boss@" + DOMAIN,
        auth_method="sso",
        sso_workspace_id=str(sso_workspace.id),
    )
    assert (await _put(client, sso_workspace, owner)).status_code == 200


async def test_an_unbound_sso_session_must_confirm(client, sso_workspace):
    owner = User(id=testUser.id, sub="boss@" + DOMAIN, auth_method="sso")
    assert (await _put(client, sso_workspace, owner)).status_code == 409


async def test_switching_the_requirement_off_never_asks(client, sso_workspace):
    owner = User(id=testUser.id, sub="boss@" + DOMAIN, auth_method="google")
    assert (
        await _put(client, sso_workspace, owner, confirmLockout=True)
    ).status_code == 200
    reply = await client.put(
        settings_url(sso_workspace),
        json={"ssoRequired": False},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 200
