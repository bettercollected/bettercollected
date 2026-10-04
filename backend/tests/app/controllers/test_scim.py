"""SCIM directory sync (docs/sso.md, "Directory sync"): the admin API, the
signed webhook, provisioning and deprovisioning, group-to-role mapping, the
SSO guard and the resync. Polis and auth are stand-ins
(tests/app/scim_helpers, tests/app/sso_helpers)."""

import json
import time

import pytest
from beanie import PydanticObjectId
from common.models.user import User

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.scim import ScimUserState
from backend.app.schemas.session import SessionDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.scim.roles import highest_role, mappable_roles
from backend.app.services.scim.signature import BadSignature, sign, verify
from backend.app.services.session_service import utcnow
from backend.app.services.sso.polis_client import PolisUnavailable
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser
from tests.app.scim_helpers import (  # noqa: F401 — fixtures
    WEBHOOK_BASE,
    create_directory,
    deliver,
    event,
    group_data,
    member_of,
    members_list,
    scim_on,
    signed,
    user_data,
)
from tests.app.sso_helpers import DOMAIN, add_connection, sso_on  # noqa: F401

JANE = "jane@" + DOMAIN
BOB = "bob@" + DOMAIN


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


OWNER = _cookies(testUser)


def url(workspace, suffix=""):
    return f"/api/v1/workspaces/{workspace.id}/scim{suffix}"


@pytest.fixture()
async def directory(client, workspace, scim_on, members_list):
    document, _ = await create_directory(client, workspace, OWNER)
    return document


async def _record(directory, polis_id):
    return await container.scim_user_repo().find(directory.id, polis_id)


async def _session(user_id: str) -> SessionDocument:
    now = utcnow()
    return await container.session_repo().save(
        SessionDocument(
            id=PydanticObjectId(),
            user_id=user_id,
            refresh_jti="j",
            expires_at=now.replace(year=now.year + 1),
        )
    )


# -- the signature ------------------------------------------------------------
def test_signature_valid_invalid_expired_and_malformed():
    body = b'{"event":"user.created"}'
    now = time.time()
    header = sign("s3cret", body, int(now * 1000))
    assert verify(header, body, "s3cret", 300, now=now) == int(now * 1000)
    for header_, body_, secret, code in (
        (header, body + b" ", "s3cret", "mismatch"),
        (header, body, "other", "mismatch"),
        (sign("s3cret", body, int((now - 301) * 1000)), body, "s3cret", "expired"),
        (sign("s3cret", body, int((now + 301) * 1000)), body, "s3cret", "expired"),
        (None, body, "s3cret", "missing"),
        ("t=abc,s=" + "0" * 64, body, "s3cret", "malformed"),
        ("t=1,s=short", body, "s3cret", "malformed"),
    ):
        with pytest.raises(BadSignature) as refused:
            verify(header_, body_, secret, 300, now=now)
        assert refused.value.code == code


# -- the admin API ------------------------------------------------------------
async def test_create_shows_the_url_and_token_once(client, workspace, scim_on):
    polis, _ = scim_on
    directory, reply = await create_directory(client, workspace, OWNER)

    body = reply.json()
    assert body["bearerToken"] == "bearer-token-1"
    assert body["scimEndpoint"] == "https://polis.test/api/scim/v2.0/dir-1"
    # Polis got our configured webhook URL with our own directory id
    assert polis.calls[0] == (
        "create",
        str(workspace.id),
        "Okta",
        "okta-scim-v2",
        f"{WEBHOOK_BASE}/{directory.id}",
    )
    secret = polis.secret("dir-1")
    # stored encrypted, never in clear
    assert directory.webhook_secret != secret
    assert container.crypto().decrypt(directory.webhook_secret) == secret

    overview = await client.get(url(workspace), cookies=OWNER)
    assert overview.status_code == 200
    assert "bearer-token-1" not in overview.text and secret not in overview.text
    assert directory.webhook_secret not in overview.text
    assert overview.json()["directory"]["typeLabel"] == "Okta"
    assert overview.json()["canManage"] is True


async def test_create_needs_a_verified_domain_and_a_known_type(
    client, workspace, scim_on
):
    reply = await client.post(
        url(workspace, "/directory"), json={"type": "okta-scim-v2"}, cookies=OWNER
    )
    assert reply.status_code == 409 and reply.json()["code"] == "sso_domain_required"
    from tests.app.sso_helpers import verify_domain

    await verify_domain(workspace.id)
    reply = await client.post(
        url(workspace, "/directory"), json={"type": "google"}, cookies=OWNER
    )
    assert reply.status_code == 422


async def test_one_directory_per_workspace(client, workspace, directory):
    reply = await client.post(
        url(workspace, "/directory"), json={"type": "okta-scim-v2"}, cookies=OWNER
    )
    assert reply.status_code == 409 and reply.json()["code"] == "scim_directory_exists"


async def test_unavailable_without_sso_or_a_webhook_url(
    client, workspace, scim_on, monkeypatch
):
    monkeypatch.setattr(settings.scim, "WEBHOOK_URL", "")
    reply = await client.post(
        url(workspace, "/directory"), json={"type": "okta-scim-v2"}, cookies=OWNER
    )
    assert reply.status_code == 404 and reply.json()["code"] == "scim_disabled"
    assert (await client.get(url(workspace), cookies=OWNER)).json()[
        "available"
    ] is False


async def test_polis_down_on_create(client, workspace, scim_on):
    polis, _ = scim_on
    polis.fail = PolisUnavailable()
    from tests.app.sso_helpers import verify_domain

    await verify_domain(workspace.id)
    reply = await client.post(
        url(workspace, "/directory"), json={"type": "okta-scim-v2"}, cookies=OWNER
    )
    assert reply.status_code == 503
    assert await container.scim_directory_repo().find_by_workspace(workspace.id) is None


@pytest.fixture()
async def admin_member(workspace):
    admin = User(id=str(PydanticObjectId()), sub="admin@" + DOMAIN)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=admin.id, roles=[WorkspaceRoles.ADMIN]
        )
    )
    return admin


async def test_admins_view_only_the_owner_changes(
    client, workspace, directory, admin_member
):
    admin = _cookies(admin_member)
    reply = await client.get(url(workspace), cookies=admin)
    assert reply.status_code == 200 and reply.json()["canManage"] is False
    group = await _group(directory, "g-1", "Staff")
    for method, suffix, body in (
        ("POST", "/directory/rotate", None),
        ("DELETE", "/directory", None),
        ("POST", "/resync", None),
        ("PUT", f"/groups/{group.id}", {"role": "ADMIN"}),
    ):
        reply = await client.request(
            method, url(workspace, suffix), json=body, cookies=admin
        )
        assert reply.status_code == 403, (suffix, reply.text)


async def test_rotate_replaces_the_directory_and_keeps_members(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    jane = auth.accounts[JANE]

    reply = await client.post(url(workspace, "/directory/rotate"), cookies=OWNER)

    assert reply.status_code == 200, reply.text
    assert reply.json()["bearerToken"] == "bearer-token-2"
    assert reply.json()["scimEndpoint"].endswith("/dir-2")
    assert ("delete", "dir-1") in polis.calls  # the old token stops working
    rotated = await container.scim_directory_repo().get(directory.id)
    assert rotated.polis_directory_id == "dir-2"
    # the old directory's signature no longer verifies
    assert polis.secret("dir-2") == container.crypto().decrypt(rotated.webhook_secret)
    # the member stays; the identity provider's new push is matched by email
    assert not (await member_of(workspace.id, jane["id"])).disabled
    reply = await deliver(
        client,
        rotated,
        polis,
        event(rotated, "user.created", user_data("new-u1", JANE)),
    )
    assert reply.status_code == 200, reply.text
    records = await container.scim_user_repo().list_by_directory(directory.id)
    assert [(r.polis_user_id, r.replaced) for r in records] == [("new-u1", False)]


async def test_delete_stops_syncing_and_keeps_members(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    reply = await client.delete(url(workspace, "/directory"), cookies=OWNER)
    assert reply.status_code == 204
    assert ("delete", "dir-1") in polis.calls
    assert await container.scim_directory_repo().find_by_workspace(workspace.id) is None
    assert await container.scim_user_repo().list_by_directory(directory.id) == []
    member = await member_of(workspace.id, auth.accounts[JANE]["id"])
    assert member is not None and not member.disabled
    # the members list no longer says "managed by your directory"
    members = await client.get(
        f"/api/v1/workspaces/{workspace.id}/members", cookies=OWNER
    )
    assert not any(m["managedByDirectory"] for m in members.json())


# -- the webhook --------------------------------------------------------------
async def test_user_created_provisions_a_member(client, workspace, directory, scim_on):
    polis, auth = scim_on
    reply = await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )

    assert reply.status_code == 200, reply.text
    assert reply.json() == {"applied": 1, "duplicates": 0}
    account = auth.accounts[JANE]
    member = await member_of(workspace.id, account["id"])
    assert member.provisioned_by == "scim" and not member.disabled
    assert member.roles == [WorkspaceRoles.COLLABORATOR]  # the default SSO role
    record = await _record(directory, "u1")
    assert record.state == ScimUserState.PROVISIONED and record.user_id == account["id"]
    fresh = await container.scim_directory_repo().get(directory.id)
    assert fresh.last_event_type == "user.created" and fresh.last_event_at
    members = await client.get(
        f"/api/v1/workspaces/{workspace.id}/members", cookies=OWNER
    )
    listed = [m for m in members.json() if m["id"] == account["id"]][0]
    assert listed["managedByDirectory"] is True and listed["provisionedBy"] == "scim"


async def test_existing_account_is_reused(client, workspace, directory, scim_on):
    polis, auth = scim_on
    existing = auth.add_account(JANE)
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    assert auth.directory_created_accounts() == []
    assert (await member_of(workspace.id, existing["id"])).provisioned_by == "scim"


@pytest.mark.parametrize(
    "mutate,status,code",
    [
        (lambda h, b: {**h, "BoxyHQ-Signature": ""}, 401, "invalid_signature"),
        (
            lambda h, b: {k: v for k, v in h.items() if k != "BoxyHQ-Signature"},
            401,
            "invalid_signature",
        ),
        (
            lambda h, b: {
                **h,
                "BoxyHQ-Signature": sign("wrong", b, int(time.time() * 1000)),
            },
            401,
            "invalid_signature",
        ),
        (
            lambda h, b: {
                **h,
                "BoxyHQ-Signature": h["BoxyHQ-Signature"].replace("s=", "s=0")[:-1],
            },
            401,
            "invalid_signature",
        ),
    ],
)
async def test_bad_signatures_are_refused(
    client, workspace, directory, scim_on, mutate, status, code
):
    polis, auth = scim_on
    body = json.dumps(event(directory, "user.created", user_data("u1", JANE))).encode()
    headers = mutate(signed(body, polis.secret("dir-1")), body)
    reply = await client.post(
        f"/api/v1/scim/webhook/{directory.id}", content=body, headers=headers
    )
    assert reply.status_code == status and reply.json()["code"] == code
    assert JANE not in auth.accounts
    assert await _record(directory, "u1") is None


async def test_old_signatures_are_refused(client, workspace, directory, scim_on):
    polis, auth = scim_on
    payload = event(directory, "user.created", user_data("u1", JANE))
    old = int((time.time() - 301) * 1000)
    reply = await deliver(client, directory, polis, payload, at_ms=old)
    assert reply.status_code == 401
    assert await _record(directory, "u1") is None


async def test_unknown_directories_are_refused(client, workspace, directory, scim_on):
    polis, _ = scim_on
    body = json.dumps(event(directory, "user.created", user_data("u1", JANE))).encode()
    for directory_id in (str(PydanticObjectId()), "not-an-id"):
        reply = await client.post(
            f"/api/v1/scim/webhook/{directory_id}",
            content=body,
            headers=signed(body, polis.secret("dir-1")),
        )
        assert reply.status_code == 401


async def test_a_replayed_event_is_applied_once(client, workspace, directory, scim_on):
    polis, auth = scim_on
    body = json.dumps(event(directory, "user.created", user_data("u1", JANE))).encode()
    headers = signed(body, polis.secret("dir-1"))
    first = await client.post(
        f"/api/v1/scim/webhook/{directory.id}", content=body, headers=headers
    )
    again = await client.post(
        f"/api/v1/scim/webhook/{directory.id}", content=body, headers=headers
    )
    assert first.json() == {"applied": 1, "duplicates": 0}
    assert again.status_code == 200 and again.json() == {"applied": 0, "duplicates": 1}
    lookups = [c for c in auth.calls if c[1].endswith("/directory-account")]
    assert len(lookups) == 2  # one look, one create: the replay touched nothing


@pytest.mark.parametrize("field", ["tenant", "product", "directory_id"])
async def test_tenant_mismatch_is_refused(client, workspace, directory, scim_on, field):
    polis, auth = scim_on
    payload = event(
        directory, "user.created", user_data("u1", JANE), **{field: "other"}
    )
    reply = await deliver(client, directory, polis, payload)
    assert reply.status_code == 403 and reply.json()["code"] == "tenant_mismatch"
    assert JANE not in auth.accounts


async def test_a_failed_event_is_retried(
    client, workspace, directory, scim_on, monkeypatch
):
    polis, auth = scim_on
    sync = container.scim_sync_service()
    original = sync.apply_user

    async def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(sync, "apply_user", broken)
    payload = event(directory, "user.created", user_data("u1", JANE))
    body = json.dumps(payload).encode()
    headers = signed(body, polis.secret("dir-1"))
    reply = await client.post(
        f"/api/v1/scim/webhook/{directory.id}", content=body, headers=headers
    )
    assert reply.status_code == 503
    monkeypatch.setattr(sync, "apply_user", original)
    # Polis's retry (the same signed request) is applied, not taken as a duplicate
    reply = await client.post(
        f"/api/v1/scim/webhook/{directory.id}", content=body, headers=headers
    )
    assert reply.json() == {"applied": 1, "duplicates": 0}


async def test_batched_events(client, workspace, directory, scim_on):
    polis, auth = scim_on
    reply = await deliver(
        client,
        directory,
        polis,
        [
            event(directory, "user.created", user_data("u1", JANE)),
            event(directory, "user.created", user_data("u2", BOB)),
        ],
    )
    assert reply.json() == {"applied": 2, "duplicates": 0}


# -- deprovisioning -----------------------------------------------------------
@pytest.mark.parametrize("kind", ["user.updated", "user.deleted"])
async def test_deactivated_users_are_disabled_and_signed_out(
    client, workspace, directory, scim_on, kind
):
    polis, auth = scim_on
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    jane = auth.accounts[JANE]
    session = await _session(jane["id"])
    # Jane's own workspace elsewhere is left alone
    elsewhere = PydanticObjectId()
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=elsewhere, user_id=jane["id"], roles=[WorkspaceRoles.ADMIN]
        )
    )

    reply = await deliver(
        client,
        directory,
        polis,
        event(directory, kind, user_data("u1", JANE, active=kind == "user.deleted")),
    )

    assert reply.status_code == 200, reply.text
    member = await member_of(workspace.id, jane["id"])
    assert member is not None and member.disabled  # disabled, never deleted
    revoked = await container.session_repo().get(session.id)
    assert (
        revoked.revoked_at is not None and revoked.revoke_reason == "scim_deprovisioned"
    )
    assert not (await member_of(elsewhere, jane["id"])).disabled
    record = await _record(directory, "u1")
    assert record.state == ScimUserState.DEPROVISIONED
    assert record.deleted is (kind == "user.deleted")


async def test_reactivation_enables_the_member_again(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    for active in (True, False, True):
        await deliver(
            client,
            directory,
            polis,
            event(directory, "user.updated", user_data("u1", JANE, active=active)),
        )
    member = await member_of(workspace.id, auth.accounts[JANE]["id"])
    assert not member.disabled and member.provisioned_by == "scim"


async def test_the_owner_is_never_touched(client, workspace, directory, scim_on):
    polis, auth = scim_on
    auth.add_account("owner@" + DOMAIN, user_id=testUser.id)
    owner_before = await member_of(workspace.id, testUser.id)
    session = await _session(testUser.id)
    for payload in (
        event(directory, "user.created", user_data("o1", "owner@" + DOMAIN)),
        event(
            directory, "user.updated", user_data("o1", "owner@" + DOMAIN, active=False)
        ),
        event(directory, "user.deleted", user_data("o1", "owner@" + DOMAIN)),
    ):
        assert (await deliver(client, directory, polis, payload)).status_code == 200
    owner = await member_of(workspace.id, testUser.id)
    assert not owner.disabled and owner.roles == owner_before.roles
    assert owner.provisioned_by is None
    assert (await container.session_repo().get(session.id)).revoked_at is None
    record = await _record(directory, "o1")
    assert (record.state, record.reason) == (ScimUserState.IGNORED, "owner_protected")


async def test_a_manually_invited_member_is_untouched(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    manual = auth.add_account(JANE)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=manual["id"],
            roles=[WorkspaceRoles.ADMIN],
        )
    )
    admins = await _group(directory, "g-a", "Admins", role="COLLABORATOR")
    for payload in (
        event(directory, "user.created", user_data("u1", JANE)),
        event(
            directory,
            "group.user_added",
            {**user_data("u1", JANE), "group": group_data("g-a", "Admins")},
        ),
        event(directory, "user.updated", user_data("u1", JANE, active=False)),
    ):
        await deliver(client, directory, polis, payload)
    member = await member_of(workspace.id, manual["id"])
    assert not member.disabled and member.roles == [WorkspaceRoles.ADMIN]
    assert member.provisioned_by is None
    record = await _record(directory, "u1")
    assert record.reason == "manual_member"
    assert admins.id


async def test_a_jit_member_is_taken_over(client, workspace, directory, scim_on):
    polis, auth = scim_on
    jit = auth.add_account(JANE)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=jit["id"],
            roles=[WorkspaceRoles.COLLABORATOR],
            provisioned_by="sso",
        )
    )
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    assert (await member_of(workspace.id, jit["id"])).provisioned_by == "scim"


@pytest.mark.parametrize(
    "email", ["jane@unverified-corp.org", "jane@gmail.com", "not-an-email"]
)
async def test_unverified_domains_are_ignored_and_recorded(
    client, workspace, directory, scim_on, email
):
    polis, auth = scim_on
    reply = await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", email)),
    )
    assert reply.status_code == 200
    assert auth.directory_created_accounts() == []
    record = await _record(directory, "u1")
    assert record.state == ScimUserState.FAILED
    assert record.reason in ("unverified_domain", "invalid_email")
    overview = (await client.get(url(workspace), cookies=OWNER)).json()
    assert overview["counts"]["failed"] == 1
    assert overview["issues"][0]["reason"] == record.reason
    assert overview["issues"][0]["message"]


async def test_a_full_workspace_refuses_and_creates_no_account(
    client, workspace, directory, scim_on, monkeypatch
):
    polis, auth = scim_on
    # the owner and the fixture's collaborator fill it
    monkeypatch.setattr(settings.api_settings, "ALLOWED_COLLABORATORS", 1)
    reply = await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    assert reply.status_code == 200
    assert auth.directory_created_accounts() == []
    record = await _record(directory, "u1")
    assert (record.state, record.reason) == (ScimUserState.FAILED, "seat_limit")
    issue = (await client.get(url(workspace), cookies=OWNER)).json()["issues"][0]
    assert issue["reason"] == "seat_limit" and "seat" in issue["message"]
    # a seat frees up: the next change (or a resync) provisions them
    monkeypatch.setattr(settings.api_settings, "ALLOWED_COLLABORATORS", 5)
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.updated", user_data("u1", JANE)),
    )
    assert (await _record(directory, "u1")).state == ScimUserState.PROVISIONED


# -- groups and roles ---------------------------------------------------------
async def _group(directory, polis_id, name, role=None):
    group = await container.scim_sync_service().apply_group(
        directory, group_data(polis_id, name)
    )
    if role:
        group.role = role
        await container.scim_group_repo().save(group)
    return group


async def _add(
    client, directory, polis, polis_user, email, group_id, name, kind="group.user_added"
):
    payload = event(
        directory,
        kind,
        {**user_data(polis_user, email), "group": group_data(group_id, name)},
    )
    reply = await deliver(client, directory, polis, payload)
    assert reply.status_code == 200, reply.text


def test_roles_come_from_the_enum_and_the_highest_wins():
    assert "ADMIN" in mappable_roles() and "OWNER" not in mappable_roles()
    assert set(mappable_roles()) == {r.value for r in WorkspaceRoles}
    assert highest_role(["COLLABORATOR", "ADMIN"]) == "ADMIN"
    assert highest_role(["COLLABORATOR", None, "OWNER", "nonsense"]) == "COLLABORATOR"
    assert highest_role([]) is None


async def test_group_mapping_highest_role_wins_and_recomputes(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    await deliver(
        client,
        directory,
        polis,
        event(directory, "group.created", group_data("g-a", "Admins")),
    )
    await deliver(
        client,
        directory,
        polis,
        event(directory, "group.created", group_data("g-s", "Staff")),
    )
    groups = {
        g["name"]: g
        for g in (await client.get(url(workspace), cookies=OWNER)).json()["groups"]
    }
    reply = await client.put(
        url(workspace, f"/groups/{groups['Admins']['id']}"),
        json={"role": "ADMIN"},
        cookies=OWNER,
    )
    assert reply.status_code == 200 and reply.json()["role"] == "ADMIN"
    reply = await client.put(
        url(workspace, f"/groups/{groups['Staff']['id']}"),
        json={"role": "COLLABORATOR"},
        cookies=OWNER,
    )
    assert reply.status_code == 200

    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    jane = auth.accounts[JANE]["id"]
    await _add(client, directory, polis, "u1", JANE, "g-s", "Staff")
    assert (await member_of(workspace.id, jane)).roles == [WorkspaceRoles.COLLABORATOR]
    await _add(client, directory, polis, "u1", JANE, "g-a", "Admins")
    assert (await member_of(workspace.id, jane)).roles == [WorkspaceRoles.ADMIN]

    # a rename keeps the mapping (by group id)
    await deliver(
        client,
        directory,
        polis,
        event(directory, "group.updated", group_data("g-a", "Administrators")),
    )
    assert (await member_of(workspace.id, jane)).roles == [WorkspaceRoles.ADMIN]
    overview = (await client.get(url(workspace), cookies=OWNER)).json()
    renamed = [g for g in overview["groups"] if g["id"] == groups["Admins"]["id"]][0]
    assert renamed["name"] == "Administrators" and renamed["members"] == 1

    await _add(
        client,
        directory,
        polis,
        "u1",
        JANE,
        "g-a",
        "Administrators",
        kind="group.user_removed",
    )
    assert (await member_of(workspace.id, jane)).roles == [WorkspaceRoles.COLLABORATOR]

    # remapping a group recomputes its members at once
    await _add(client, directory, polis, "u1", JANE, "g-a", "Administrators")
    await client.put(
        url(workspace, f"/groups/{groups['Admins']['id']}"),
        json={"role": None},
        cookies=OWNER,
    )
    assert (await member_of(workspace.id, jane)).roles == [WorkspaceRoles.COLLABORATOR]
    await client.put(
        url(workspace, f"/groups/{groups['Admins']['id']}"),
        json={"role": "ADMIN"},
        cookies=OWNER,
    )
    assert (await member_of(workspace.id, jane)).roles == [WorkspaceRoles.ADMIN]

    # a deleted group no longer counts
    await deliver(
        client,
        directory,
        polis,
        event(directory, "group.deleted", group_data("g-a", "Administrators")),
    )
    assert (await member_of(workspace.id, jane)).roles == [WorkspaceRoles.COLLABORATOR]


async def test_unmapped_members_follow_the_default_role(
    client, workspace, directory, scim_on, monkeypatch
):
    polis, auth = scim_on
    # a second assignable default role (Viewer once #801 lands)
    for module in ("policy", "connection_service"):
        monkeypatch.setattr(
            f"backend.app.services.sso.{module}.assignable_sso_roles",
            lambda: ["COLLABORATOR", "ADMIN"],
        )
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    jane = auth.accounts[JANE]["id"]
    await add_connection(workspace.id)
    reply = await client.put(
        f"/api/v1/workspaces/{workspace.id}/sso/settings",
        json={"defaultRole": "ADMIN"},
        cookies=OWNER,
    )
    assert reply.status_code == 200, reply.text
    assert (await member_of(workspace.id, jane)).roles == [WorkspaceRoles.ADMIN]


async def test_mapping_refuses_unknown_roles_and_the_owner(
    client, workspace, directory
):
    group = await _group(directory, "g-1", "Staff")
    for role in ("OWNER", "SUPERUSER"):
        reply = await client.put(
            url(workspace, f"/groups/{group.id}"), json={"role": role}, cookies=OWNER
        )
        assert reply.status_code == 422 and reply.json()["code"] == "invalid_role"
    reply = await client.put(
        url(workspace, f"/groups/{PydanticObjectId()}"),
        json={"role": "ADMIN"},
        cookies=OWNER,
    )
    assert reply.status_code == 404


async def test_a_member_added_to_a_group_before_creation_is_provisioned(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    await _add(client, directory, polis, "u1", JANE, "g-1", "Staff")
    assert (await _record(directory, "u1")).state == ScimUserState.PROVISIONED
    assert await member_of(workspace.id, auth.accounts[JANE]["id"])


# -- SSO is refused for deprovisioned users -------------------------------------
async def test_sso_sign_in_of_a_deprovisioned_user_is_refused(
    client, workspace, directory, scim_on
):
    from tests.app.controllers.test_sso_login import sign_in, sso_error

    polis, auth = scim_on
    await add_connection(workspace.id)
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.updated", user_data("u1", JANE, active=False)),
    )
    # even after the member was removed by hand (no disabled membership left)
    await container.workspace_user_repo().delete(
        workspace.id, auth.accounts[JANE]["id"]
    )
    auth.idp_email = JANE

    reply = await sign_in(client, JANE)

    assert sso_error(reply) == "sso_deprovisioned"
    assert await member_of(workspace.id, auth.accounts[JANE]["id"]) is None


async def test_sso_sign_in_of_an_active_directory_user_works(
    client, workspace, directory, scim_on
):
    from tests.app.controllers.test_sso_login import sign_in

    polis, auth = scim_on
    await add_connection(workspace.id)
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    auth.idp_email = JANE
    reply = await sign_in(client, JANE)
    assert "sso_error" not in reply.headers["location"]


# -- resync -------------------------------------------------------------------
async def test_resync_applies_missed_changes(client, workspace, directory, scim_on):
    polis, auth = scim_on
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u1", JANE)),
    )
    await deliver(
        client,
        directory,
        polis,
        event(directory, "user.created", user_data("u3", "carol@" + DOMAIN)),
    )
    group = await _group(directory, "g-a", "Admins", role="ADMIN")
    # what Polis holds now; none of these changes reached the webhook
    polis.users = [
        user_data("u1", JANE, active=False),  # deactivated
        user_data("u2", BOB),  # new, and an admin
    ]  # carol (u3) was deleted
    polis.groups = [group_data("g-a", "Admins")]
    polis.members = {"g-a": ["u2"]}

    reply = await client.post(url(workspace, "/resync"), cookies=OWNER)

    assert reply.status_code == 200, reply.text
    summary = reply.json()["summary"]
    assert summary["users"] == 2 and summary["removed"] == 1 and summary["groups"] == 1
    assert (await member_of(workspace.id, auth.accounts[JANE]["id"])).disabled
    assert (
        await member_of(workspace.id, auth.accounts["carol@" + DOMAIN]["id"])
    ).disabled
    bob = await member_of(workspace.id, auth.accounts[BOB]["id"])
    assert not bob.disabled and bob.roles == [WorkspaceRoles.ADMIN]
    assert group.id
    fresh = await container.scim_directory_repo().get(directory.id)
    assert fresh.last_resync_at and fresh.last_resync_summary == summary


async def test_resync_with_polis_down(client, workspace, directory, scim_on):
    polis, _ = scim_on
    polis.fail = PolisUnavailable()
    reply = await client.post(url(workspace, "/resync"), cookies=OWNER)
    assert reply.status_code == 503
    fresh = await container.scim_directory_repo().get(directory.id)
    assert fresh.last_resync_error == "scim_unavailable"


async def test_nightly_resync_covers_every_directory(
    client, workspace, directory, scim_on
):
    polis, auth = scim_on
    polis.users = [user_data("u1", JANE)]
    result = await container.scim_directory_service().resync_all("schedule")
    assert result == {"directories": 1, "failed": 0}
    assert await member_of(workspace.id, auth.accounts[JANE]["id"])


async def test_deleting_the_workspace_removes_its_directory(
    client, workspace, directory, scim_on
):
    polis, _ = scim_on
    await container.scim_directory_service().release_workspaces([workspace.id])
    assert ("delete", "dir-1") in polis.calls
    assert await container.scim_directory_repo().find_by_workspace(workspace.id) is None
