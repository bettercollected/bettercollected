"""Removing someone's authenticator app: a workspace owner, the platform
administrator; and the mails about second-factor changes."""

import datetime as dt
from unittest.mock import AsyncMock

import pytest
from common.ids import RecordId
from common.models.user import User

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.session import SessionDocument
from backend.app.schemas.workspace_audit_event import (
    NO_WORKSPACE,
    TOTP_ENROLLED,
    TOTP_RESET,
)
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from tests.app.controllers.data import testUser
from tests.app.mfa.helpers import (
    code_now,
    cookies_of_user,
    enrolled,
    give_factor,
    member,
    new_clock,
    service,
    signed_in,
)
from tests.app.sso_helpers import DOMAIN, verify_domain

pytestmark = pytest.mark.usefixtures("totp_on")

RESET = "/api/v1/workspaces/{}/members/{}/totp"
ADMIN_RESET = "/api/v1/admin/users/{}/totp"
OWNER = testUser
# the same people in a session that has presented the second factor (the reset
# routes need it, like the workspace rule's own setting)
OWNER_MFA = testUser.model_copy(update={"mfa": True})


def lookup(monkeypatch, roles=None, **emails):
    """What the auth service says about an account: its address and roles."""
    async def get(url, params=None, **kwargs):
        wanted = params["user_ids"][0]
        return {
            "users_info": [
                {
                    "_id": wanted,
                    "email": emails.get(wanted, "x@x.org"),
                    "roles": (roles or {}).get(wanted, ["FORM_CREATOR"]),
                }
            ]
        }

    monkeypatch.setattr(
        container.workspace_totp_service()._http_client, "get", AsyncMock(side_effect=get)
    )


async def live_session(user_id: str) -> SessionDocument:
    now = dt.datetime.now(dt.timezone.utc)
    return await container.session_repo().save(
        SessionDocument(
            id=RecordId(), user_id=user_id, refresh_jti="j", expires_at=now + dt.timedelta(days=1)
        )
    )


async def test_an_owner_resets_a_member_of_only_this_workspace(
    client, workspace, notices, monkeypatch
):
    target = await member(workspace, "t@example.org")
    await give_factor(target.id)
    session = await live_session(target.id)
    lookup(monkeypatch)
    reply = await client.delete(
        RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER_MFA)
    )
    assert reply.status_code == 204, reply.text
    assert await container.user_totp_repo().confirmed(target.id) is None
    assert (await container.session_repo().get(str(session.id))).revoke_reason == "mfa_reset"
    events = await container.workspace_audit_repo().many()
    assert [e.event for e in events] == [TOTP_RESET]
    assert events[0].user_id == OWNER.id and events[0].target_user_id == target.id
    assert events[0].workspace_id == workspace.id
    await container.mfa_notifier().flush()
    assert notices == [
        {
            "user_id": target.id,
            "kind": "reset_owner",
            "workspace_title": workspace.title,
        }
    ]


async def test_nobody_below_owner_may_reset(client, workspace, monkeypatch):
    target = await member(workspace, "t@example.org")
    await give_factor(target.id)
    lookup(monkeypatch)
    for role in (WorkspaceRoles.ADMIN, WorkspaceRoles.COLLABORATOR, WorkspaceRoles.VIEWER):
        user = await member(workspace, f"{role.value}@example.org", role)
        reply = await client.delete(
            RESET.format(workspace.id, target.id), cookies=cookies_of_user(user)
        )
        assert reply.status_code == 403, role
    assert await container.user_totp_repo().confirmed(target.id) is not None


async def test_not_ones_own_a_non_member_or_nothing_to_reset(client, workspace, monkeypatch):
    lookup(monkeypatch)
    own = await client.delete(
        RESET.format(workspace.id, OWNER.id), cookies=cookies_of_user(OWNER_MFA)
    )
    assert own.status_code == 409 and own.json()["code"] == "reset_self"
    stranger = str(RecordId())
    await give_factor(stranger)
    away = await client.delete(
        RESET.format(workspace.id, stranger), cookies=cookies_of_user(OWNER_MFA)
    )
    assert away.status_code == 404
    assert await container.user_totp_repo().confirmed(stranger) is not None
    plain = await member(workspace, "plain@example.org")
    none = await client.delete(
        RESET.format(workspace.id, plain.id), cookies=cookies_of_user(OWNER_MFA)
    )
    assert none.status_code == 404


async def test_a_person_who_reaches_another_workspace_is_not_the_owners_to_reset(
    client, workspace, workspace_1, monkeypatch
):
    target = await member(workspace, "t@elsewhere.org")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace_1.id, user_id=target.id, roles=[WorkspaceRoles.COLLABORATOR]
        )
    )
    await give_factor(target.id)
    lookup(monkeypatch, **{target.id: "t@elsewhere.org"})
    reply = await client.delete(
        RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER_MFA)
    )
    assert reply.status_code == 409 and reply.json()["code"] == "reset_not_allowed"
    assert await container.user_totp_repo().confirmed(target.id) is not None
    # unless the workspace has verified the person's address domain
    await verify_domain(workspace.id)
    lookup(monkeypatch, **{target.id: f"t@{DOMAIN}"})
    reply = await client.delete(
        RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER_MFA)
    )
    assert reply.status_code == 204, reply.text
    assert await container.user_totp_repo().confirmed(target.id) is None


async def test_a_domain_another_workspace_verified_does_not_count(
    client, workspace, workspace_1, monkeypatch
):
    await verify_domain(workspace_1.id)  # not this workspace
    target = await member(workspace, f"t@{DOMAIN}")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace_1.id, user_id=target.id, roles=[WorkspaceRoles.COLLABORATOR]
        )
    )
    await give_factor(target.id)
    lookup(monkeypatch, **{target.id: f"t@{DOMAIN}"})
    reply = await client.delete(
        RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER_MFA)
    )
    assert reply.status_code == 409 and reply.json()["code"] == "reset_not_allowed"


async def test_the_platform_administrator_resets_anyone_but_themselves(
    client, notices
):
    target = str(RecordId())
    await give_factor(target)
    session = await live_session(target)
    reply = await client.delete(ADMIN_RESET.format(target), cookies=cookies_of_user(OWNER_MFA))
    assert reply.status_code == 204, reply.text
    assert await container.user_totp_repo().confirmed(target) is None
    assert (await container.session_repo().get(str(session.id))).revoke_reason == "mfa_reset"
    (event,) = await container.workspace_audit_repo().many()
    assert event.event == TOTP_RESET and event.target_user_id == target
    assert str(event.workspace_id) == NO_WORKSPACE and event.user_id == OWNER.id
    await container.mfa_notifier().flush()
    assert notices == [{"user_id": target, "kind": "reset"}]
    own = await client.delete(ADMIN_RESET.format(OWNER.id), cookies=cookies_of_user(OWNER_MFA))
    assert own.status_code == 409 and own.json()["code"] == "reset_self"
    gone = await client.delete(ADMIN_RESET.format(target), cookies=cookies_of_user(OWNER_MFA))
    assert gone.status_code == 404


async def test_a_workspace_owner_is_not_a_platform_administrator(client, workspace):
    target = str(RecordId())
    await give_factor(target)
    plain_owner = User(id=OWNER.id, sub=OWNER.sub, roles=["FORM_CREATOR"])
    reply = await client.delete(ADMIN_RESET.format(target), cookies=cookies_of_user(plain_owner))
    assert reply.status_code == 403
    assert await container.user_totp_repo().confirmed(target) is not None


async def test_the_reset_routes_answer_422_while_the_switch_is_off(client, workspace, monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings.totp, "ENABLED", False)
    target = await member(workspace, "t@example.org")
    await give_factor(target.id)
    for url in (RESET.format(workspace.id, target.id), ADMIN_RESET.format(target.id)):
        reply = await client.delete(url, cookies=cookies_of_user(OWNER_MFA))
        assert reply.status_code == 422 and reply.json()["code"] == "totp_off"
    assert await container.user_totp_repo().confirmed(target.id) is not None


# ---- the mails about changes ----------------------------------------------


async def test_every_change_to_the_factor_mails_the_account_and_nothing_secret(notices):
    clock = new_clock()
    svc = service(clock, notifier=container.mfa_notifier())
    account = await signed_in("n@example.org", now=clock.now())
    secret, codes = await enrolled(svc, clock, account)
    clock.advance(30)
    await svc.check_code(account.user, codes[0])  # a recovery code
    for _ in range(5):  # the fifth wrong code locks
        try:
            await svc.check_code(account.user, "000000")
        except Exception:  # noqa: BLE001
            pass
    clock.advance(16 * 60)
    await svc.disable(account.user, code_now(secret, clock))
    await container.mfa_notifier().flush()
    kinds = [n["kind"] for n in notices]
    assert kinds == ["enrolled", "recovery_used", "locked", "removed"]
    assert notices[1]["recovery_left"] == 9 and notices[2]["minutes"] == 15
    for notice in notices:
        assert notice["user_id"] == account.user.id
        assert set(notice) <= {"user_id", "kind", "recovery_left", "minutes", "workspace_title", "locale"}
        assert secret not in str(notice) and not any(c in str(notice) for c in codes)
    assert TOTP_ENROLLED in [e.event for e in await container.workspace_audit_repo().many()]


async def test_a_notice_carries_the_language_of_the_request(monkeypatch):
    from backend.app.services.mfa import notifier as module
    from backend.app.services.request_context import bind_request, unbind_request

    token = bind_request({"headers": [(b"accept-language", b"nl-NL,nl;q=0.9,en;q=0.8")]})
    try:
        assert module.request_locale() == "nl-NL"
    finally:
        unbind_request(token)
    assert module.request_locale() is None


async def test_a_failing_mail_is_logged_without_the_account_and_never_raises(monkeypatch, caplog):
    from backend.app.services.mfa.notifier import MfaNotifier

    sent = AsyncMock(side_effect=RuntimeError("down ann@example.org"))
    notifier = MfaNotifier(http_client=type("C", (), {"post": sent})())
    # the autouse recorder replaced _send; use the real one
    monkeypatch.undo()
    notifier.notify("5f0000000000000000000001", "enrolled")
    await notifier.flush()
    sent.assert_awaited_once()
    assert sent.await_args.kwargs["json"] == {"user_id": "5f0000000000000000000001", "kind": "enrolled"}
    assert "ann@example.org" not in caplog.text


async def test_deleting_an_account_removes_its_factor_even_through_the_duplicate_drop(monkeypatch):
    """The 4.1 case-duplicate cleanup drops an account through the product's
    account deletion (``AuthService.delete_user``): the factor goes with it."""
    auth = container.auth_service()
    user = User(id=str(RecordId()), sub="dup@example.org", roles=["FORM_CREATOR"])
    await give_factor(user.id)
    other = str(RecordId())
    await give_factor(other)
    for name in (
        "refuse_deleting_billing_owner_of_shared_workspaces",
        "delete_workspaces_of_user_with_forms",
        "forget_exports_of_user",
    ):
        monkeypatch.setattr(auth.workspace_service, name, AsyncMock(), raising=False)
    monkeypatch.setattr(auth, "delete_user_form_auth", AsyncMock())
    monkeypatch.setattr(auth, "delete_credentials_from_integrations", AsyncMock())
    monkeypatch.setattr(auth.draft_service, "delete_for_account", AsyncMock())
    await auth.delete_user(user)
    assert await container.user_totp_repo().confirmed(user.id) is None
    assert await container.user_totp_repo().confirmed(other) is not None


# ---- the caller's own second factor ------------------------------------------


async def test_a_session_that_passed_only_the_first_factor_cannot_reset_anyone(client, workspace, monkeypatch):
    lookup(monkeypatch)
    target = await member(workspace, "t@example.org")
    await give_factor(target.id)
    own_session = cookies_of_user(OWNER)  # an owner and a platform administrator, no second factor
    owner_route = await client.delete(RESET.format(workspace.id, target.id), cookies=own_session)
    assert owner_route.status_code == 409 and owner_route.json()["code"] == "enrol_first"
    admin_route = await client.delete(ADMIN_RESET.format(target.id), cookies=own_session)
    assert admin_route.status_code == 409 and admin_route.json()["code"] == "enrol_first"
    assert await container.user_totp_repo().confirmed(target.id) is not None
    assert await container.workspace_audit_repo().many() == []
    # a person who is neither gets the plain refusal first
    editor = await member(workspace, "e@example.org", mfa=True)
    assert (await client.delete(RESET.format(workspace.id, target.id), cookies=cookies_of_user(editor))).status_code == 403


# ---- whose factor an owner may reset --------------------------------------------


async def test_an_owner_cannot_reset_a_platform_administrator(client, workspace, monkeypatch):
    by_role = await member(workspace, "ops@example.org")
    by_address = await member(workspace, "Boss@Example.org")
    for target in (by_role, by_address):
        await give_factor(target.id)
    from backend.config import settings

    monkeypatch.setattr(settings.verified_domains, "PLATFORM_ADMIN_EMAILS", "boss@example.org, other@x.org")
    lookup(monkeypatch, roles={by_role.id: ["FORM_CREATOR", "ADMIN"]}, **{by_role.id: "ops@example.org", by_address.id: "Boss@Example.org"})
    for target in (by_role, by_address):
        reply = await client.delete(RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER_MFA))
        assert reply.status_code == 409, target.sub
        assert reply.json()["code"] == "reset_admin_not_allowed"
        assert await container.user_totp_repo().confirmed(target.id) is not None


async def test_a_platform_administrator_may_reset_another_one_as_the_design_says(client, notices):
    other_admin = str(RecordId())
    await give_factor(other_admin)
    reply = await client.delete(ADMIN_RESET.format(other_admin), cookies=cookies_of_user(OWNER_MFA))
    assert reply.status_code == 204
    (event,) = await container.workspace_audit_repo().many()
    assert event.target_user_id == other_admin and event.user_id == OWNER.id


async def test_the_member_directory_being_down_refuses_instead_of_guessing(client, workspace, monkeypatch):
    target = await member(workspace, "t@example.org")
    await give_factor(target.id)
    monkeypatch.setattr(
        container.workspace_totp_service()._http_client, "get", AsyncMock(side_effect=RuntimeError("down"))
    )
    reply = await client.delete(RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER_MFA))
    assert reply.status_code == 503 and reply.json()["code"] == "directory_unavailable"
    assert await container.user_totp_repo().confirmed(target.id) is not None


# ---- the verified-domain rule ---------------------------------------------------


@pytest.mark.parametrize(
    "address,allowed",
    [
        (f"t@{DOMAIN}", True),
        (f"T@{DOMAIN.upper()}", True),  # case
        (f"t@{DOMAIN}.", True),  # a trailing dot is the same name
        (f"  t@{DOMAIN} ", True),
        (f"t@mail.{DOMAIN}", False),  # a sub-domain is not the verified domain
        (f"t@x{DOMAIN}", False),  # nor a longer name that ends the same
        (f"t@{DOMAIN}@evil.org", False),  # the domain is what follows the last @
        (f"{DOMAIN}", False),  # no address at all
        ("", False),
        (None, False),
        (f"@{DOMAIN}", False),
        ("t@", False),
    ],
)
async def test_which_addresses_the_verified_domain_vouches_for(client, workspace, workspace_1, monkeypatch, address, allowed):
    await verify_domain(workspace.id)
    target = await member(workspace, "t@example.org")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace_1.id, user_id=target.id, roles=[WorkspaceRoles.COLLABORATOR])
    )
    await give_factor(target.id)
    lookup(monkeypatch, **{target.id: address})
    reply = await client.delete(RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER_MFA))
    assert reply.status_code == (204 if allowed else 409), (address, reply.text)


# ---- ids ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["not-an-id", "..", "x" * 300, "0" * 23, "%00", "5f0000000000000000000zzz"])
async def test_a_malformed_or_unknown_id_is_a_plain_404(client, workspace, monkeypatch, bad):
    lookup(monkeypatch)
    owner = await client.delete(RESET.format(workspace.id, bad), cookies=cookies_of_user(OWNER_MFA))
    admin = await client.delete(ADMIN_RESET.format(bad), cookies=cookies_of_user(OWNER_MFA))
    assert owner.status_code == 404 and admin.status_code == 404
    unknown = str(RecordId())
    assert (await client.delete(RESET.format(workspace.id, unknown), cookies=cookies_of_user(OWNER_MFA))).status_code == 404
    assert (await client.delete(ADMIN_RESET.format(unknown), cookies=cookies_of_user(OWNER_MFA))).status_code == 404


async def test_a_member_removed_while_the_reset_runs_is_left_alone(client, workspace, monkeypatch):
    target = await member(workspace, "t@example.org")
    await give_factor(target.id)
    lookup(monkeypatch)
    repo = container.workspace_user_repo()
    real = repo.find_workspace_user
    calls = {"n": 0}

    async def vanishing(workspace_id, user_id):
        calls["n"] += 1
        # present for the first reads, gone when the delete is about to happen
        return await real(workspace_id, user_id) if calls["n"] < 2 else None

    monkeypatch.setattr(repo, "find_workspace_user", vanishing)
    reply = await client.delete(RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER_MFA))
    assert reply.status_code == 404
    assert await container.user_totp_repo().confirmed(target.id) is not None
    assert await container.workspace_audit_repo().many() == []


# ---- the target's language -----------------------------------------------------


async def test_a_notice_about_a_reset_uses_the_targets_language_not_the_callers(client, workspace, notices, monkeypatch):
    lookup(monkeypatch)
    dutch = await member(workspace, "nl@example.org")
    await give_factor(dutch.id, locale="nl-NL")
    plain = await member(workspace, "plain@example.org")
    await give_factor(plain.id)
    for target in (dutch, plain):
        reply = await client.delete(
            RESET.format(workspace.id, target.id),
            cookies=cookies_of_user(OWNER_MFA),
            headers={"Accept-Language": "fr-FR,fr;q=0.9"},
        )
        assert reply.status_code == 204
    await container.mfa_notifier().flush()
    by_user = {n["user_id"]: n for n in notices}
    assert by_user[dutch.id]["locale"] == "nl-NL"
    assert "locale" not in by_user[plain.id]  # no stored language: the instance's default, never the caller's
    # and the administrator's reset the same
    admin_target = str(RecordId())
    await give_factor(admin_target, locale="nl")
    await client.delete(ADMIN_RESET.format(admin_target), cookies=cookies_of_user(OWNER_MFA), headers={"Accept-Language": "fr"})
    await container.mfa_notifier().flush()
    assert [n for n in notices if n["user_id"] == admin_target] == [{"user_id": admin_target, "kind": "reset", "locale": "nl"}]


async def test_the_language_of_a_persons_own_use_is_kept_for_later(monkeypatch):
    from backend.app.services.request_context import bind_request, unbind_request

    clock = new_clock()
    svc = service(clock)
    account = await signed_in("l@example.org", now=clock.now())
    token = bind_request({"headers": [(b"accept-language", b"nl-NL,nl;q=0.9")]})
    try:
        secret, codes = await enrolled(svc, clock, account)
    finally:
        unbind_request(token)
    assert (await container.user_totp_repo().confirmed(account.user.id)).locale == "nl-NL"
    clock.advance(30)
    token = bind_request({"headers": [(b"accept-language", b"en-GB")]})
    try:
        await svc.check_code(account.user, code_now(secret, clock))
    finally:
        unbind_request(token)
    assert (await container.user_totp_repo().confirmed(account.user.id)).locale == "en-GB"
