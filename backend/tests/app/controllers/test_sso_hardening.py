"""Single sign-on hardening before it goes on (docs/sso.md): SSO sessions are
bound to the workspace whose identity provider signed them in, an owner's
break-glass is audited, the owners see the API keys that predate the
requirement, and an owner is asked before switching it on from a session the
requirement would refuse."""

import asyncio
import datetime as dt

import pytest
from common.ids import RecordId
from common.models.user import User
from loguru import logger

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.sso_connection import SsoConnectionStatus
from backend.app.schemas.workspace_audit_event import WorkspaceAuditEventDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from backend.app.services.session_service import decode_token
from backend.app.services.sso import policy as policy_module
from backend.config import settings
from tests.app.auth_helpers import access_token
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_sso_every_request import (  # noqa: F401 — fixtures
    _cookies,
    _member,
    _membership,
    _otp_sign_in,
    _require,
    _sso_required,
    forms_url,
    permissions_url,
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
    enabled_connection_id,
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
    # the table has one row per request: 4 + 1 + 1 (the log line is the throttled one)
    rows = await container.workspace_audit_repo().page(required.id, 50)
    assert sorted(r.session_id for r in rows) == sorted([owner.sid] * 5 + [other.sid])
    assert {r.event for r in rows} == {"sso_break_glass_request"}
    assert {r.user_id for r in rows} == {owner.id}
    assert "boss@" not in str([r.model_dump() for r in rows])


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
        sso_connection_id=await enabled_connection_id(required.id),
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
        "createdByFormerMember",
        "createdAt",
        "lastUsedAt",
        "createdAfterRequirement",
    }
    assert key["createdAfterRequirement"] is False
    assert first.token not in reply.text and "keyHash" not in reply.text


async def test_the_overview_lists_every_live_key_and_flags_the_newer_ones(
    client, sso_workspace, workspace_1
):
    await _key(sso_workspace, "before")
    await container.workspace_api_key_repo().save(
        WorkspaceAPIKeyDocument(
            workspace_id=workspace_1.id,
            name="elsewhere",
            key_hash="h" * 64,
            prefix="bc_aaaaaaaa",
            scopes=["forms:read"],
            created_by=testUser1.id,
        )
    )
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
    keys = {k["name"]: k for k in reply.json()["settings"]["apiKeys"]}
    # all of this workspace's live keys, none of another workspace's
    assert sorted(keys) == ["after", "before"]
    assert keys["before"]["createdAfterRequirement"] is False
    assert keys["after"]["createdAfterRequirement"] is True
    assert after.token not in reply.text


async def test_an_admin_sees_the_key_list_but_cannot_change_the_setting(
    client, sso_workspace
):
    await _key(sso_workspace, "ops")
    await _require(client, sso_workspace)
    _, cookies = await _member(
        sso_workspace, "admin@partner-corp.org", "otp", WorkspaceRoles.ADMIN
    )
    reply = await client.get(overview_url(sso_workspace), cookies=cookies)
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["canManage"] is False
    assert [k["name"] for k in body["settings"]["apiKeys"]] == ["ops"]


async def _creator(workspace, name, member=True):
    _, auth = sso_on_of()
    account = auth.add_account("maker@" + DOMAIN, name=name)
    if member:
        await container.workspace_user_repo().save(
            WorkspaceUserDocument(
                workspace_id=workspace.id,
                user_id=account["id"],
                roles=[WorkspaceRoles.COLLABORATOR],
            )
        )
    created = await _key(workspace, "ops")
    repo = container.workspace_api_key_repo()
    document = await repo.get_or_404(RecordId(created.id))
    document.created_by = account["id"]
    await repo.save(document)
    return account, created


async def test_the_creator_is_named_only_while_a_member(client, sso_workspace):
    account, created = await _creator(sso_workspace, "Mia Maker")
    await _require(client, sso_workspace)
    reply = await client.get(overview_url(sso_workspace), cookies=_cookies(testUser))
    (key,) = reply.json()["settings"]["apiKeys"]
    assert key["createdBy"] == account["id"]
    assert key["createdByLabel"] == "Mia Maker"
    assert key["createdByFormerMember"] is False
    assert "maker@" not in reply.text


async def test_a_former_member_creator_is_not_looked_up_or_disclosed(
    client, sso_workspace
):
    account, _ = await _creator(sso_workspace, "Mia Maker", member=False)
    _, auth = sso_on_of()
    await _require(client, sso_workspace)
    auth.calls.clear()
    reply = await client.get(overview_url(sso_workspace), cookies=_cookies(testUser))
    (key,) = reply.json()["settings"]["apiKeys"]
    assert key["createdBy"] == account["id"]
    assert key["createdByLabel"] is None
    assert key["createdByFormerMember"] is True
    # no name and no address anywhere, and auth was not even asked about them
    assert "Mia" not in reply.text and "maker@" not in reply.text
    assert not [
        c for c in auth.calls if c[1].endswith("/users") and account["id"] in str(c[2])
    ]


async def test_the_creator_lookup_is_bounded_and_fails_soft(
    client, sso_workspace, monkeypatch
):
    account, _ = await _creator(sso_workspace, "Mia Maker")
    _, auth = sso_on_of()
    await _require(client, sso_workspace)
    auth.timeouts.clear()
    await client.get(overview_url(sso_workspace), cookies=_cookies(testUser))
    assert any(p.endswith("/users") and t == 10 for p, t in auth.timeouts)
    original = auth.get

    async def failing(url, *args, **kwargs):
        if url.endswith("/users"):
            raise RuntimeError("auth is down")
        return await original(url, *args, **kwargs)

    monkeypatch.setattr(auth, "get", failing)
    reply = await client.get(overview_url(sso_workspace), cookies=_cookies(testUser))
    assert reply.status_code == 200, reply.text
    (key,) = reply.json()["settings"]["apiKeys"]
    assert key["createdBy"] == account["id"] and key["createdByLabel"] is None


async def test_the_list_carries_last_use(client, sso_workspace):
    created = await _key(sso_workspace, "ops")
    repo = container.workspace_api_key_repo()
    assert await repo.touch_last_used(RecordId(created.id), dt.datetime.now(dt.timezone.utc))
    await _require(client, sso_workspace)
    reply = await client.get(overview_url(sso_workspace), cookies=_cookies(testUser))
    (key,) = reply.json()["settings"]["apiKeys"]
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
        sso_connection_id=await enabled_connection_id(sso_workspace.id),
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


# -- the persisted break-glass audit -------------------------------------------------
async def _entries(workspace):
    return await container.workspace_audit_repo().page(workspace.id, 50)


async def test_every_break_glass_request_writes_one_row_with_a_path_template(
    client, required
):
    owner = User(
        id=testUser.id, sub="boss@" + DOMAIN, auth_method="otp", sid=str(RecordId())
    )
    cookies = _cookies(owner)
    for _ in range(3):
        # a query string with a value that must never be stored
        reply = await client.get(
            forms_url(required) + "?search=secret-value", cookies=cookies
        )
        assert reply.status_code == 200, reply.text
    rows = await _entries(required)
    assert len(rows) == 3
    for row in rows:
        assert row.event == "sso_break_glass_request"
        assert (row.user_id, row.session_id) == (owner.id, owner.sid)
        assert str(row.workspace_id) == str(required.id)
        assert row.method == "GET"
        # the template, not the workspace id and not the query
        assert row.path == "/workspaces/{workspace_id}/forms"
        assert str(required.id) not in row.path
        assert "secret-value" not in str(row.model_dump())
        assert row.created_at is not None


async def test_a_request_authorised_several_times_still_writes_one_row(
    client, required
):
    owner = User(
        id=testUser.id, sub="boss@" + DOMAIN, auth_method="otp", sid=str(RecordId())
    )
    # the permissions route and the forms route each authorise more than once
    for url in (permissions_url(required), forms_url(required)):
        assert (await client.get(url, cookies=_cookies(owner))).status_code == 200
    assert len(await _entries(required)) == 2


async def test_a_failing_audit_never_blocks_is_logged_and_retried(
    client, required, monkeypatch, audit_lines
):
    policy = container.sso_policy_service()
    policy._audit_pending.clear()
    repo = policy._audit
    original = repo.record
    outage = {"on": True}

    async def flaky(document):
        if outage["on"]:
            raise RuntimeError("database down")
        return await original(document)

    monkeypatch.setattr(repo, "record", flaky)
    owner = User(
        id=testUser.id, sub="boss@" + DOMAIN, auth_method="otp", sid=str(RecordId())
    )
    cookies = _cookies(owner)
    # access is never refused for want of an audit write
    assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200
    assert await _entries(required) == []
    assert len(policy._audit_pending) == 1
    errors = [m for m in audit_lines if m.startswith("AUDIT sso_break_glass NOT STORED")]
    assert errors and owner.id in errors[0] and owner.sid in errors[0]
    assert "boss@" not in errors[0]
    # the next request stores the missed row and its own
    outage["on"] = False
    assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200
    assert len(await _entries(required)) == 2
    assert len(policy._audit_pending) == 0


async def test_a_slow_audit_write_is_cut_short_and_queued(
    client, required, monkeypatch
):
    policy = container.sso_policy_service()
    policy._audit_pending.clear()
    monkeypatch.setattr(policy_module, "AUDIT_WRITE_TIMEOUT_SECONDS", 0.05)

    async def slow(document):
        await asyncio.sleep(1)

    monkeypatch.setattr(policy._audit, "record", slow)
    owner = User(
        id=testUser.id, sub="boss@" + DOMAIN, auth_method="otp", sid=str(RecordId())
    )
    assert (
        await client.get(forms_url(required), cookies=_cookies(owner))
    ).status_code == 200
    assert len(policy._audit_pending) == 1
    policy._audit_pending.clear()


async def test_an_owners_email_code_sign_in_is_recorded_without_a_workspace_request(
    client, sso_workspace
):
    workspace = sso_workspace
    owner_id, owner_email = str(RecordId()), "olga@" + DOMAIN
    await _membership(workspace, owner_id, WorkspaceRoles.OWNER)
    await _require(client, workspace)
    await _otp_sign_in(client, owner_email, owner_id, WorkspaceRoles.OWNER)
    (entry,) = await _entries(workspace)
    assert entry.event == "sso_break_glass_sign_in"
    assert entry.user_id == owner_id and entry.session_id is None
    assert (entry.method, entry.path) == ("POST", "/auth/otp/validate")
    assert owner_email not in str(entry.model_dump())


async def test_a_member_whose_code_is_refused_leaves_no_entry(client, sso_workspace):
    workspace = sso_workspace
    await _require(client, workspace)
    member_id = str(RecordId())
    await _membership(workspace, member_id, WorkspaceRoles.COLLABORATOR)
    _, auth = sso_on_of()
    account = auth.add_account("mia@" + DOMAIN, user_id=member_id)
    auth.otp_user = {**account, "email_verified": True}
    reply = await client.post(
        "/api/v1/auth/otp/validate", json={"email": "mia@" + DOMAIN, "otp_code": "X"}
    )
    assert reply.status_code == 403
    assert await _entries(workspace) == []


async def test_the_sso_page_lists_the_entries_with_member_names(client, required):
    _, auth = sso_on_of()
    member = auth.add_account("olga@" + DOMAIN, name="Olga Owner")
    await _membership(required, member["id"], WorkspaceRoles.OWNER)
    former = str(RecordId())
    repo = container.workspace_audit_repo()
    for user_id, sid in ((member["id"], "s1"), (former, "s2")):
        await repo.record(
            WorkspaceAuditEventDocument(
                id=RecordId(),
                workspace_id=required.id,
                user_id=user_id,
                session_id=sid,
                event="sso_break_glass_request",
            )
        )
    for cookies in (
        _cookies(testUser),
        (await _member(required, "adm@partner-corp.org", "otp", WorkspaceRoles.ADMIN))[1],
    ):
        reply = await client.get(overview_url(required), cookies=cookies)
        assert reply.status_code == 200, reply.text
        entries = {e["userId"]: e for e in reply.json()["audit"]}
        assert entries[member["id"]]["userLabel"] == "Olga Owner"
        assert entries[member["id"]]["userIsMember"] is True
        assert entries[former]["userLabel"] is None
        assert entries[former]["userIsMember"] is False
        assert entries[former]["sessionId"] == "s2" and entries[former]["at"]
        assert "olga@" not in reply.text
    # only those who can open the page
    _, viewer = await _member(required, "v@partner-corp.org", "otp", WorkspaceRoles.VIEWER)
    assert (await client.get(overview_url(required), cookies=viewer)).status_code == 403


async def test_the_audit_is_kept_a_year_and_goes_with_the_workspace(
    client, required, workspace_1
):
    policy = container.sso_policy_service()
    repo = container.workspace_audit_repo()
    now = dt.datetime.now(dt.timezone.utc)
    for age_days, sid in ((400, "old"), (10, "new")):
        document = WorkspaceAuditEventDocument(
            id=RecordId(),
            workspace_id=required.id,
            user_id="u",
            session_id=sid,
            event="sso_break_glass_request",
        )
        document.created_at = now - dt.timedelta(days=age_days)
        await repo.record(document)
    assert await policy.purge_audit(now) == 1
    assert [e.session_id for e in await repo.page(required.id, 50)] == ["new"]
    await repo.record(
        WorkspaceAuditEventDocument(
            id=RecordId(),
            workspace_id=workspace_1.id,
            user_id="u",
            session_id="x",
            event="sso_break_glass_request",
        )
    )
    await container.sso_connection_service().release_workspaces([required.id])
    assert await repo.page(required.id, 50) == []
    assert len(await repo.page(workspace_1.id, 50)) == 1


# -- a replaced identity provider ends its sessions ----------------------------------
async def _replace_connection(workspace):
    for connection in await container.sso_connection_repo().list_by_workspace(
        workspace.id
    ):
        connection.status = SsoConnectionStatus.DISABLED
        await container.sso_connection_repo().save(connection)
    return await add_connection(workspace.id)


async def test_a_session_of_a_replaced_connection_is_refused_and_ends_at_refresh(
    client, required, fake_status
):
    signed_in = await sign_in(client)
    claims = decode_token(signed_in.cookies.get("Authorization"))
    assert claims["sso_connection_id"] == await enabled_connection_id(required.id)
    cookies = {
        "Authorization": signed_in.cookies.get("Authorization"),
        "RefreshToken": signed_in.cookies.get("RefreshToken"),
    }
    assert (await client.get(forms_url(required), cookies=cookies)).status_code == 200
    await _replace_connection(required)
    container.sso_policy_service()._enabled_cache.clear()
    container.sso_policy_service()._requirement_cache.clear()
    _sso_required(await client.get(forms_url(required), cookies=cookies))
    fake_status.email = "jane@" + DOMAIN
    ended = await refresh(client, cookies["RefreshToken"])
    assert ended.status_code == 401
    assert "connection" in ended.text


async def test_a_replaced_connection_ends_sessions_even_without_the_requirement(
    client, sso_workspace, fake_status
):
    signed_in = await sign_in(client)
    refresh_token = signed_in.cookies.get("RefreshToken")
    await _replace_connection(sso_workspace)
    fake_status.email = "jane@" + DOMAIN
    ended = await refresh(client, refresh_token)
    assert ended.status_code == 401


async def test_without_an_enabled_connection_nothing_ends(
    client, sso_workspace, fake_status
):
    signed_in = await sign_in(client)
    for connection in await container.sso_connection_repo().list_by_workspace(
        sso_workspace.id
    ):
        connection.status = SsoConnectionStatus.DISABLED
        await container.sso_connection_repo().save(connection)
    fake_status.email = "jane@" + DOMAIN
    kept = await refresh(client, signed_in.cookies.get("RefreshToken"))
    assert kept.status_code == 200, kept.text


# -- every path that re-issues the access token keeps the binding ----------------------
async def _sso_cookies(client):
    signed_in = await sign_in(client)
    client.cookies.clear()
    cookies = {
        "Authorization": signed_in.cookies.get("Authorization"),
        "RefreshToken": signed_in.cookies.get("RefreshToken"),
    }
    claims = decode_token(cookies["Authorization"])
    return cookies, claims


def _reminted(reply, claims):
    new = decode_token(reply.cookies.get("Authorization"))
    assert new is not None, reply.text
    assert new["sid"] == claims["sid"]
    assert new["auth_method"] == "sso"
    assert new["sso_workspace_id"] == claims["sso_workspace_id"]
    assert new["sso_connection_id"] == claims["sso_connection_id"]


async def test_the_import_oauth_callback_keeps_the_binding(
    client, sso_workspace, monkeypatch
):
    cookies, claims = await _sso_cookies(client)
    service = container.auth_service()
    _, auth = sso_on_of()
    email = "jane@" + DOMAIN

    class Provider:
        auth_callback_url = "http://plugin/callback"

    async def provider(*args, **kwargs):
        return Provider()

    async def proxied(*args, **kwargs):
        return {"email": email}

    async def passthrough(url, *args, **kwargs):
        return url

    class Callback:
        async def get(self, url, **kwargs):
            return {"id": claims["id"], "sub": email, "roles": ["FORM_CREATOR"]}

    monkeypatch.setattr(service.form_provider_service, "get_provider_if_enabled", provider)
    monkeypatch.setattr(service.plugin_proxy_service, "pass_request", proxied)
    monkeypatch.setattr(service, "http_client", Callback())
    monkeypatch.setattr(service, "safe_login_redirect", passthrough)
    monkeypatch.setattr(
        service,
        "import_return_url",
        lambda *a, **k: passthrough("http://localhost:3000/after"),
    )
    monkeypatch.setattr(
        service.crypto, "decrypt", lambda state: '{"client_referer_uri": null}'
    )
    reply = await client.get(
        "/api/v1/auth/google/oauth/callback",
        params={"state": "s", "code": "c"},
        cookies=cookies,
    )
    assert reply.status_code in (302, 307), reply.text
    _reminted(reply, claims)


def _coupon_code() -> str:
    body = "A" * 24
    return body + str(sum(map(ord, body)) % 10)


async def test_coupon_redeem_and_price_suggestion_keep_the_binding(
    client, sso_workspace, monkeypatch
):
    cookies, claims = await _sso_cookies(client)
    monkeypatch.setattr(settings.coupon_settings, "ENABLED", True)
    monkeypatch.setattr(settings, "ENABLE_SUGGEST_PRICE", True)

    async def done(*args, **kwargs):
        return None

    monkeypatch.setattr(container.coupon_service(), "redeem_coupon", done)
    monkeypatch.setattr(
        container.price_suggestion_service(),
        "save_price_suggestion_and_upgrade_user",
        done,
    )
    coupon = await client.post(f"/api/v1/coupons/redeem/{_coupon_code()}", cookies=cookies)
    assert coupon.status_code == 200, coupon.text
    _reminted(coupon, claims)
    price = await client.post(
        "/api/v1/suggest-price", json={"price": 5}, cookies=cookies
    )
    assert price.status_code == 200, price.text
    _reminted(price, claims)


async def test_the_selection_marks_a_workspace_the_session_was_not_signed_in_through(
    client, required, workspace_1
):
    """An SSO session of workspace A, and the domain now belongs to B, which
    requires SSO: B's row starts B's sign-in instead of opening B."""
    _, cookies = await _member(
        workspace_1,
        "jane@" + DOMAIN,
        "sso",
        sso_workspace_id=str(required.id),
        sso_connection_id=await enabled_connection_id(required.id),
    )
    await _move_domain_claim(workspace_1)
    await add_connection(workspace_1.id)
    await container.workspace_repo().set_fields(workspace_1, {"sso_required": True})
    policy = container.sso_policy_service()
    policy._requirement_cache.clear()
    policy._enabled_cache.clear()
    reply = await client.get(
        "/api/v1/workspaces/mine/selection",
        params={"next": f"/{workspace_1.workspace_name}/dashboard"},
        cookies=cookies,
    )
    assert reply.status_code == 200, reply.text
    body = reply.json()
    rows = {w["workspaceName"]: w for w in body["workspaces"]}
    assert rows[workspace_1.workspace_name]["ssoRequired"] is True
    assert body["next"] is None


# -- the audit list is paged -----------------------------------------------------------
async def _fill_audit(workspace, count):
    repo = container.workspace_audit_repo()
    base = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    ids = []
    for i in range(count):
        document = WorkspaceAuditEventDocument(
            id=RecordId(),
            workspace_id=workspace.id,
            user_id="u",
            session_id=f"s{i}",
            event="sso_break_glass_request",
            method="GET",
            path="/x/{id}",
        )
        document.created_at = base + dt.timedelta(seconds=i)
        await repo.record(document)
        ids.append(f"s{i}")
    return ids


def audit_url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/sso/audit"


async def test_the_audit_list_is_paged_newest_first(client, required):
    await _fill_audit(required, 45)
    first = await client.get(overview_url(required), cookies=_cookies(testUser))
    body = first.json()
    assert [e["sessionId"] for e in body["audit"]][:2] == ["s44", "s43"]
    assert len(body["audit"]) == 20 and body["auditNextCursor"]
    seen = [e["sessionId"] for e in body["audit"]]
    cursor = body["auditNextCursor"]
    while cursor:
        page = await client.get(
            audit_url(required), params={"cursor": cursor}, cookies=_cookies(testUser)
        )
        assert page.status_code == 200, page.text
        data = page.json()
        seen += [e["sessionId"] for e in data["entries"]]
        cursor = data["nextCursor"]
    # every entry once, newest first, nothing repeated or skipped
    assert seen == [f"s{i}" for i in range(44, -1, -1)]


async def test_the_page_size_has_a_ceiling_and_a_bad_cursor_is_refused(client, required):
    await _fill_audit(required, 3)
    too_big = await client.get(
        audit_url(required), params={"limit": 1000}, cookies=_cookies(testUser)
    )
    assert too_big.status_code == 422
    one = await client.get(
        audit_url(required), params={"limit": 1}, cookies=_cookies(testUser)
    )
    assert len(one.json()["entries"]) == 1 and one.json()["nextCursor"]
    bad = await client.get(
        audit_url(required), params={"cursor": "not-a-cursor"}, cookies=_cookies(testUser)
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "invalid_cursor" if "code" in bad.json() else True


async def test_the_audit_pages_are_for_those_who_manage_security(client, required):
    await _fill_audit(required, 2)
    _, admin = await _member(required, "adm@partner-corp.org", "otp", WorkspaceRoles.ADMIN)
    assert (await client.get(audit_url(required), cookies=admin)).status_code == 200
    _, viewer = await _member(required, "v@partner-corp.org", "otp", WorkspaceRoles.VIEWER)
    assert (await client.get(audit_url(required), cookies=viewer)).status_code == 403


async def test_a_page_never_shows_another_workspaces_entries(
    client, required, workspace_1
):
    await _fill_audit(workspace_1, 3)
    reply = await client.get(audit_url(required), cookies=_cookies(testUser))
    assert reply.json()["entries"] == []


async def test_a_key_without_a_creator_is_not_called_a_former_member(
    client, sso_workspace
):
    created = await _key(sso_workspace, "ops")
    repo = container.workspace_api_key_repo()
    document = await repo.get_or_404(RecordId(created.id))
    document.created_by = ""
    await repo.save(document)
    await _require(client, sso_workspace)
    reply = await client.get(overview_url(sso_workspace), cookies=_cookies(testUser))
    (key,) = reply.json()["settings"]["apiKeys"]
    assert not key["createdBy"] and key["createdByFormerMember"] is False
