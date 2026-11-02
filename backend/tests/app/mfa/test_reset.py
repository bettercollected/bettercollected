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


def lookup(monkeypatch, **emails):
    """What the auth service says an account's address is."""
    async def get(url, params=None, **kwargs):
        wanted = params["user_ids"][0]
        return {"users_info": [{"_id": wanted, "email": emails.get(wanted, "x@x.org")}]}

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
        RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER)
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
        RESET.format(workspace.id, OWNER.id), cookies=cookies_of_user(OWNER)
    )
    assert own.status_code == 409 and own.json()["code"] == "reset_self"
    stranger = str(RecordId())
    await give_factor(stranger)
    away = await client.delete(
        RESET.format(workspace.id, stranger), cookies=cookies_of_user(OWNER)
    )
    assert away.status_code == 404
    assert await container.user_totp_repo().confirmed(stranger) is not None
    plain = await member(workspace, "plain@example.org")
    none = await client.delete(
        RESET.format(workspace.id, plain.id), cookies=cookies_of_user(OWNER)
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
        RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER)
    )
    assert reply.status_code == 409 and reply.json()["code"] == "reset_not_allowed"
    assert await container.user_totp_repo().confirmed(target.id) is not None
    # unless the workspace has verified the person's address domain
    await verify_domain(workspace.id)
    lookup(monkeypatch, **{target.id: f"t@{DOMAIN}"})
    reply = await client.delete(
        RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER)
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
        RESET.format(workspace.id, target.id), cookies=cookies_of_user(OWNER)
    )
    assert reply.status_code == 409 and reply.json()["code"] == "reset_not_allowed"


async def test_the_platform_administrator_resets_anyone_but_themselves(
    client, notices
):
    target = str(RecordId())
    await give_factor(target)
    session = await live_session(target)
    reply = await client.delete(ADMIN_RESET.format(target), cookies=cookies_of_user(OWNER))
    assert reply.status_code == 204, reply.text
    assert await container.user_totp_repo().confirmed(target) is None
    assert (await container.session_repo().get(str(session.id))).revoke_reason == "mfa_reset"
    (event,) = await container.workspace_audit_repo().many()
    assert event.event == TOTP_RESET and event.target_user_id == target
    assert str(event.workspace_id) == NO_WORKSPACE and event.user_id == OWNER.id
    await container.mfa_notifier().flush()
    assert notices == [{"user_id": target, "kind": "reset"}]
    own = await client.delete(ADMIN_RESET.format(OWNER.id), cookies=cookies_of_user(OWNER))
    assert own.status_code == 409 and own.json()["code"] == "reset_self"
    gone = await client.delete(ADMIN_RESET.format(target), cookies=cookies_of_user(OWNER))
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
        reply = await client.delete(url, cookies=cookies_of_user(OWNER))
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
