"""The workspace selection screen after sign-in (``GET
/workspaces/mine/selection``): the workspaces the caller may open and where a
sign-in that started from a workspace page goes. Nothing about another
workspace leaks: not its name, not how many there are, not whether a
workspace by some name exists."""

import pytest
from common.ids import RecordId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.workspace_selection_service import (
    app_path,
    target_workspace_name,
)
from tests.app.auth_helpers import access_token
from tests.app.sso_helpers import (  # noqa: F401 — fixtures
    DOMAIN,
    add_connection,
    sso_on,
    verify_domain,
)

SELECTION = "/api/v1/workspaces/mine/selection"
CREATOR = ["FORM_RESPONDER", "FORM_CREATOR"]

owner = User(id=str(RecordId()), sub="owner@example.org", roles=CREATOR)
member = User(id=str(RecordId()), sub="member@example.org", roles=CREATOR)
stranger = User(id=str(RecordId()), sub="stranger@example.org", roles=CREATOR)


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def _workspace(name: str, title: str, owner_id: str, **fields):
    return await container.workspace_repo().save(
        WorkspaceDocument(
            title=title,
            workspace_name=name,
            owner_id=owner_id,
            description="",
            **fields,
        )
    )


async def _join(workspace, user: User, roles, disabled=False):
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=user.id,
            roles=roles,
            disabled=disabled,
        )
    )


async def _owned(name: str, title: str, user: User = owner, **fields):
    workspace = await _workspace(name, title, user.id, **fields)
    await _join(workspace, user, [WorkspaceRoles.OWNER])
    return workspace


async def _select(client: AsyncClient, user: User, next_path=None):
    params = {"next": next_path} if next_path is not None else {}
    reply = await client.get(SELECTION, params=params, cookies=_cookies(user))
    assert reply.status_code == 200, reply.text
    return reply.json()


def _names(selection) -> list:
    return [w["workspaceName"] for w in selection["workspaces"]]


# -- the list -----------------------------------------------------------------


async def test_signing_in_is_required(client: AsyncClient):
    assert (await client.get(SELECTION)).status_code == 401


async def test_the_list_is_never_cached(client: AsyncClient):
    reply = await client.get(SELECTION, cookies=_cookies(owner))
    assert reply.status_code == 200, reply.text
    assert "no-store" in reply.headers["cache-control"]


async def test_no_workspace(client: AsyncClient):
    selection = await _select(client, stranger)

    assert selection["workspaces"] == []
    assert selection["isCreator"] is True
    # a free plan can't add a workspace
    assert selection["canCreateWorkspace"] is False
    assert selection["next"] is None and selection["notice"] is None


async def test_no_workspace_on_pro_may_create_one(client: AsyncClient):
    pro = stranger.model_copy(update={"plan": "PRO"})
    assert (await _select(client, pro))["canCreateWorkspace"] is True


async def test_a_respondent_has_no_workspace_and_creates_none(client: AsyncClient):
    respondent = User(
        id=str(RecordId()), sub="r@example.org", roles=["FORM_RESPONDER"], plan="PRO"
    )
    selection = await _select(client, respondent)

    assert selection["workspaces"] == []
    assert selection["isCreator"] is False
    assert selection["canCreateWorkspace"] is False


async def test_one_workspace(client: AsyncClient):
    await _owned("solo", "Solo")

    selection = await _select(client, owner)

    assert _names(selection) == ["solo"]
    (row,) = selection["workspaces"]
    assert row["title"] == "Solo"
    assert row["role"] == "OWNER" and row["isOwner"] is True
    assert row["disabled"] is False and row["ssoRequired"] is False


async def test_several_workspaces_ordered_by_name_with_the_role_and_domain(
    client: AsyncClient,
):
    zeta = await _owned("zeta", "Zeta", user=stranger)
    await _join(zeta, owner, [WorkspaceRoles.VIEWER])
    alpha = await _owned("alpha", "alpha", user=stranger)
    await _join(alpha, owner, [WorkspaceRoles.ADMIN])
    await _owned(
        "mine",
        "Mine",
        custom_domain="forms.example.org",
        custom_domain_verified=True,
    )
    await _owned(
        "pending",
        "Pending domain",
        custom_domain="unverified.example.org",
        custom_domain_verified=False,
    )
    # a workspace the user isn't in
    await _owned("other", "Other", user=stranger)

    selection = await _select(client, owner)

    assert _names(selection) == ["alpha", "mine", "pending", "zeta"]
    rows = {w["workspaceName"]: w for w in selection["workspaces"]}
    assert rows["alpha"]["role"] == "ADMIN" and rows["alpha"]["isOwner"] is False
    assert rows["zeta"]["role"] == "VIEWER"
    assert rows["mine"]["customDomain"] == "forms.example.org"
    # only a verified domain is shown
    assert rows["pending"]["customDomain"] is None


async def test_a_disabled_membership_is_not_listed(client: AsyncClient):
    workspace = await _owned("team", "Team", user=stranger)
    await _join(workspace, member, [WorkspaceRoles.EDITOR], disabled=True)

    assert (await _select(client, member))["workspaces"] == []


async def test_a_disabled_workspace_shows_to_its_owner_as_disabled(
    client: AsyncClient,
):
    workspace = await _owned("downgraded", "Downgraded", disabled=True)
    # a member whose membership was (wrongly) left enabled
    await _join(workspace, member, [WorkspaceRoles.EDITOR])

    (row,) = (await _select(client, owner))["workspaces"]
    assert row["workspaceName"] == "downgraded" and row["disabled"] is True

    assert (await _select(client, member))["workspaces"] == []
    # the plain list agrees
    mine = await client.get("/api/v1/workspaces/mine", cookies=_cookies(member))
    assert mine.status_code == 200, mine.text
    assert [w["workspaceName"] for w in mine.json()] == []


async def test_a_disabled_workspace_shows_to_a_second_owner(client: AsyncClient):
    workspace = await _owned("downgraded", "Downgraded", user=stranger, disabled=True)
    await _join(workspace, owner, [WorkspaceRoles.OWNER])

    (row,) = (await _select(client, owner))["workspaces"]
    assert row["disabled"] is True and row["isOwner"] is True


async def test_a_respondent_scoped_session_lists_nothing(client: AsyncClient):
    await _owned("solo", "Solo")
    scoped = owner.model_copy(
        update={"session_scope": "respondent", "scope_workspace_id": str(RecordId())}
    )
    selection = await _select(client, scoped)
    assert selection["workspaces"] == []
    assert selection["isCreator"] is False


# -- deep links ---------------------------------------------------------------


async def test_a_deep_link_to_a_member_workspace_goes_there(client: AsyncClient):
    await _owned("acme", "Acme")
    target = "/acme/dashboard/forms/f1/responses?page=2"

    selection = await _select(client, owner, target)

    assert selection["next"] == target
    assert selection["notice"] is None


async def test_a_deep_link_to_a_disabled_workspace_goes_there_for_its_owner(
    client: AsyncClient,
):
    await _owned("old", "Old", disabled=True)
    assert (await _select(client, owner, "/old/dashboard"))["next"] == "/old/dashboard"


async def test_non_member_and_nonexistent_workspaces_answer_the_same(
    client: AsyncClient,
):
    await _owned("acme", "Acme")
    await _owned("secret", "Secret", user=stranger)

    not_member = await _select(client, owner, "/secret/dashboard/forms")
    missing = await _select(client, owner, "/no-such-workspace/dashboard/forms")

    assert not_member["notice"] == "no_access"
    assert not_member["next"] is None
    assert not_member == missing
    assert "secret" not in str(not_member).lower()


async def test_a_deep_link_to_a_downgraded_workspace_is_no_access_for_a_member(
    client: AsyncClient,
):
    workspace = await _owned("old", "Old", user=stranger, disabled=True)
    await _join(workspace, member, [WorkspaceRoles.EDITOR])

    selection = await _select(client, member, "/old/dashboard/forms")
    assert selection["notice"] == "no_access" and selection["next"] is None


@pytest.mark.parametrize(
    "target",
    [
        "/",
        "/login",
        "/workspace/create",
        "/dashboard",
    ],
)
async def test_a_target_naming_no_workspace_is_a_plain_sign_in(
    client: AsyncClient, target
):
    await _owned("acme", "Acme")
    selection = await _select(client, owner, target)
    assert selection["next"] is None and selection["notice"] is None


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example.com/acme/dashboard",
        "//evil.example.com/acme/dashboard",
        "/\\evil.example.com/acme/dashboard",
        "\\\\evil.example.com",
        "javascript:alert(1)",
        "acme/dashboard",
        "/acme/dashboard/../../evil",
        "/acme/dashboard/%2e%2e/x",
        "/acme/dashboard\t/x",
        "/acme/dashboard/" + "x" * 3000,
    ],
)
async def test_an_external_or_odd_target_is_never_followed(client: AsyncClient, target):
    await _owned("acme", "Acme")
    selection = await _select(client, owner, target)
    assert selection["next"] is None
    assert selection["notice"] is None


def test_app_path():
    assert app_path("/acme/dashboard/forms?x=1#frag") == "/acme/dashboard/forms?x=1"
    assert app_path("/acme/dashboard") == "/acme/dashboard"
    for bad in (None, "", "acme", "//x", "/\\x", "http://x/y", "/a/../b", "/a\nb"):
        assert app_path(bad) is None, bad
    assert target_workspace_name("/acme/dashboard/forms") == "acme"
    assert target_workspace_name("/acme%20co/dashboard") == "acme co"
    assert target_workspace_name("/acme/forms/f1") is None
    assert target_workspace_name("/dashboard") is None


# -- single sign-on -------------------------------------------------------------


@pytest.fixture()
async def sso_required(sso_on):  # noqa: F811
    """``acme`` requires its SSO for DOMAIN; the SSO user is a viewer there
    and also a member of ``plain``."""
    acme = await _owned("acme", "Acme", user=stranger)
    await verify_domain(acme.id)
    await add_connection(acme.id)
    await container.workspace_repo().set_fields(acme, {"sso_required": True})
    plain = await _owned("plain", "Plain", user=stranger)
    return acme, plain


def _sso_user(method):
    return User(
        id=str(RecordId()),
        sub="jane@" + DOMAIN,
        roles=CREATOR,
        auth_method=method,
    )


@pytest.mark.parametrize("method", ["otp", "google", None])
async def test_a_session_not_from_the_sso_marks_that_row(
    client: AsyncClient, sso_required, method
):
    acme, plain = sso_required
    jane = _sso_user(method)
    await _join(acme, jane, [WorkspaceRoles.VIEWER])
    await _join(plain, jane, [WorkspaceRoles.EDITOR])

    selection = await _select(client, jane, "/acme/dashboard/forms")

    rows = {w["workspaceName"]: w for w in selection["workspaces"]}
    assert rows["acme"]["ssoRequired"] is True
    assert rows["plain"]["ssoRequired"] is False
    # never straight in through the plain session
    assert selection["next"] is None and selection["notice"] is None
    assert (await _select(client, jane, "/plain/dashboard"))["next"] == (
        "/plain/dashboard"
    )


async def test_an_sso_session_opens_the_workspace(client: AsyncClient, sso_required):
    acme, _ = sso_required
    jane = _sso_user("sso").model_copy(update={"sso_workspace_id": str(acme.id)})
    await _join(acme, jane, [WorkspaceRoles.VIEWER])

    selection = await _select(client, jane, "/acme/dashboard")

    (row,) = [w for w in selection["workspaces"] if w["workspaceName"] == "acme"]
    assert row["ssoRequired"] is False
    assert selection["next"] == "/acme/dashboard"


@pytest.mark.parametrize("method,marked", [("otp", False), ("google", True)])
async def test_an_owners_email_code_is_break_glass(
    client: AsyncClient, sso_required, method, marked
):
    acme, _ = sso_required
    boss = _sso_user(method)
    await _join(acme, boss, [WorkspaceRoles.OWNER])

    (row,) = [
        w
        for w in (await _select(client, boss))["workspaces"]
        if w["workspaceName"] == "acme"
    ]
    assert row["ssoRequired"] is marked


async def test_an_address_off_the_sso_domains_is_not_marked(
    client: AsyncClient, sso_required
):
    acme, _ = sso_required
    await _join(acme, member, [WorkspaceRoles.EDITOR])
    (row,) = (await _select(client, member))["workspaces"]
    assert row["ssoRequired"] is False


# -- the dashboard's check: where ``next`` goes, without the list -------------

TARGET = SELECTION + "/target"


async def _target(client: AsyncClient, user: User, next_path):
    reply = await client.get(TARGET, params={"next": next_path}, cookies=_cookies(user))
    assert reply.status_code == 200, reply.text
    assert "no-store" in reply.headers["cache-control"]
    return reply.json()


async def test_the_target_check_needs_a_sign_in(client: AsyncClient):
    reply = await client.get(TARGET, params={"next": "/acme/dashboard"})
    assert reply.status_code == 401


async def test_the_target_check_answers_like_the_selection(client: AsyncClient):
    await _owned("acme", "Acme")
    await _owned("secret", "Secret", user=stranger)

    for path in (
        "/acme/dashboard",
        "/secret/dashboard",
        "/no-such-workspace/dashboard",
        "https://evil.example.com/acme/dashboard",
        "/",
    ):
        full = await _select(client, owner, path)
        assert await _target(client, owner, path) == {
            "next": full["next"],
            "notice": full["notice"],
        }, path
    assert await _target(client, owner, "/acme/dashboard") == {
        "next": "/acme/dashboard",
        "notice": None,
    }
    # the same for a non-member and a workspace that doesn't exist
    assert await _target(client, owner, "/secret/dashboard") == await _target(
        client, owner, "/no-such-workspace/dashboard"
    )


async def test_the_target_check_never_asks_about_creating(
    client: AsyncClient, monkeypatch
):
    await _owned("acme", "Acme")
    service = container.workspace_selection_service()

    async def refuse(*args, **kwargs):
        raise AssertionError("not needed for the check")

    monkeypatch.setattr(service, "_may_create", refuse)
    assert (await _target(client, owner, "/acme/dashboard"))["next"] == (
        "/acme/dashboard"
    )


async def test_the_target_check_sends_an_sso_required_workspace_to_the_screen(
    client: AsyncClient, sso_required
):
    acme, _ = sso_required
    jane = _sso_user("otp")
    await _join(acme, jane, [WorkspaceRoles.VIEWER])
    assert await _target(client, jane, "/acme/dashboard") == {
        "next": None,
        "notice": None,
    }
