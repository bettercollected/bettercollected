"""Signing in with single sign-on (docs/sso.md): the backend's checks around
auth's Polis code flow. Polis and auth are stand-ins (tests/app/sso_helpers)."""

from urllib.parse import urlsplit

import pytest
from beanie import PydanticObjectId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.session_service import decode_token
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1
from tests.app.sso_helpers import (  # noqa: F401 — fixtures
    DOMAIN,
    LOGIN_PAGE,
    POLIS_URL,
    add_connection,
    query_of,
    sso_on,
    state_of,
    verify_domain,
)

LOGIN = "/api/v1/auth/sso/login"
CALLBACK = "/api/v1/auth/sso/callback"


@pytest.fixture()
async def sso_workspace(workspace, sso_on):
    await verify_domain(workspace.id)
    connection = await add_connection(workspace.id)
    return workspace, connection


async def start(client: AsyncClient, email="Jane@" + DOMAIN, referer=LOGIN_PAGE):
    return await client.get(
        LOGIN, params={"email": email}, headers={"referer": referer}
    )


async def sign_in(client: AsyncClient, email="jane@" + DOMAIN, referer=LOGIN_PAGE):
    started = await start(client, email, referer)
    assert started.status_code == 307, started.text
    assert started.headers["location"].startswith(POLIS_URL), started.headers[
        "location"
    ]
    return await client.get(
        CALLBACK, params={"code": "c", "state": state_of(started.headers["location"])}
    )


def sso_error(reply) -> str:
    return query_of(reply.headers["location"]).get("sso_error")


# -- start --------------------------------------------------------------------
async def test_start_sends_the_browser_to_the_workspaces_connection(
    client, sso_workspace
):
    workspace, connection = sso_workspace
    _, auth = sso_on_of()

    reply = await start(client)

    assert reply.status_code == 307
    query = query_of(reply.headers["location"])
    assert query["client_id"] == connection.polis_client_id
    assert query["login_hint"] == "jane@" + DOMAIN
    call = [c for c in auth.calls if c[1].endswith("/sso/authorize")][0][2]
    assert call["tenant"] == str(workspace.id)


def sso_on_of():
    service = container.sso_login_service()
    return container.sso_connection_service()._polis, service._http


@pytest.mark.parametrize(
    "email", ["jane@unclaimed-corp.org", "not-an-email", "", "@" + DOMAIN]
)
async def test_start_without_a_verified_domain_is_refused(client, sso_workspace, email):
    reply = await start(client, email)
    assert reply.status_code == 307
    assert reply.headers["location"].startswith(LOGIN_PAGE)
    assert sso_error(reply) == "sso_not_configured"


async def test_an_unverified_claim_is_never_used(client, workspace, sso_on):
    # a pending claim: the domain is claimed but not proven
    from backend.app.schemas.workspace_domain import WorkspaceDomainDocument

    await container.workspace_domain_repo().create(
        WorkspaceDomainDocument(
            id=PydanticObjectId(),
            workspace_id=workspace.id,
            domain=DOMAIN,
            verification_token="0" * 32,
            created_by="test",
        )
    )
    await add_connection(workspace.id)
    assert sso_error(await start(client)) == "sso_not_configured"


async def test_a_lost_domain_is_never_used(client, workspace, sso_on):
    await verify_domain(workspace.id, lost=True)
    await add_connection(workspace.id)
    assert sso_error(await start(client)) == "sso_not_configured"


async def test_a_disabled_connection_is_not_used(client, workspace, sso_on):
    await verify_domain(workspace.id)
    await add_connection(workspace.id, enabled=False)
    assert sso_error(await start(client)) == "sso_not_configured"


async def test_sso_off_is_refused(client, sso_workspace, monkeypatch):
    monkeypatch.setattr(settings.sso, "ENABLED", False)
    assert sso_error(await start(client)) == "sso_disabled"


async def test_a_platform_admin_domain_is_never_used(
    client, sso_workspace, monkeypatch
):
    # reserved after it was verified: SSO must not control the admin grant
    monkeypatch.setattr(
        settings.verified_domains, "PLATFORM_ADMIN_EMAILS", "root@" + DOMAIN
    )
    assert sso_error(await start(client)) == "sso_not_configured"


async def test_a_foreign_referer_is_not_followed(client, sso_workspace):
    reply = await start(client, "nobody@unclaimed-corp.org", "https://evil.test/login")
    assert reply.headers["location"].startswith(settings.api_settings.CLIENT_URL)


# -- callback -----------------------------------------------------------------
async def test_sign_in_creates_member_session_and_redirects(client, sso_workspace):
    workspace, _ = sso_workspace
    _, auth = sso_on_of()

    reply = await sign_in(client)

    assert reply.status_code == 307, reply.text
    location = urlsplit(reply.headers["location"])
    assert f"{location.scheme}://{location.netloc}" == "http://localhost:3000"
    assert location.path == f"/{workspace.workspace_name}/dashboard/forms"
    account = auth.accounts["jane@" + DOMAIN]
    member = await container.workspace_user_repo().find_workspace_user(
        workspace.id, PydanticObjectId(account["id"])
    )
    assert member.roles == [WorkspaceRoles.COLLABORATOR]
    token = reply.cookies.get("Authorization")
    claims = decode_token(token)
    assert claims["sid"] and claims["auth_method"] == "sso"
    assert claims["email_verified"] is True

    # the session is listed like any other, marked as SSO
    sessions = await client.get(
        "/api/v1/auth/sessions",
        cookies={
            "Authorization": token,
            "RefreshToken": reply.cookies.get("RefreshToken"),
        },
    )
    assert sessions.status_code == 200
    listed = sessions.json()
    assert [s["id"] for s in listed] == [claims["sid"]]
    assert listed[0]["method"] == "sso" and listed[0]["current"] is True


async def test_sso_users_get_no_personal_workspace_or_new_user_tag(
    client, sso_workspace
):
    _, auth = sso_on_of()
    await sign_in(client)
    account = auth.accounts["jane@" + DOMAIN]
    owned = await container.workspace_repo().get_default_workspace_by_owner_id(
        account["id"]
    )
    assert owned is None
    tags = await container.user_tags_service().get_user_tags_by_id(account["id"])
    assert not tags


async def test_an_unassignable_default_role_falls_back(
    client, sso_workspace, monkeypatch
):
    workspace, _ = sso_workspace
    # a role from the enum, validated (ADMIN is never assignable)
    await container.workspace_repo().set_fields(
        workspace, {"sso_default_role": "ADMIN"}
    )
    _, auth = sso_on_of()
    await sign_in(client)
    member = await container.workspace_user_repo().find_workspace_user(
        workspace.id, PydanticObjectId(auth.accounts["jane@" + DOMAIN]["id"])
    )
    assert member.roles == [WorkspaceRoles.COLLABORATOR]


async def test_an_existing_member_is_never_downgraded(client, sso_workspace):
    workspace, _ = sso_workspace
    _, auth = sso_on_of()
    account = auth.add_account("jane@" + DOMAIN)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=account["id"],
            roles=[WorkspaceRoles.ADMIN],
        )
    )

    reply = await sign_in(client)

    assert reply.status_code == 307 and not sso_error(reply)
    member = await container.workspace_user_repo().find_workspace_user(
        workspace.id, PydanticObjectId(account["id"])
    )
    assert member.roles == [WorkspaceRoles.ADMIN]


async def test_a_full_workspace_refuses_before_the_account_exists(
    client, sso_workspace, monkeypatch
):
    monkeypatch.setattr(settings.api_settings, "ALLOWED_COLLABORATORS", 1)
    _, auth = sso_on_of()

    reply = await sign_in(client)

    assert sso_error(reply) == "sso_seat_limit"
    assert "Authorization" not in reply.cookies
    assert auth.created_accounts() == []  # shortcut 2: no auth user created


async def test_a_full_workspace_still_lets_existing_members_in(
    client, sso_workspace, monkeypatch
):
    workspace, _ = sso_workspace
    monkeypatch.setattr(settings.api_settings, "ALLOWED_COLLABORATORS", 1)
    _, auth = sso_on_of()
    account = auth.add_account("jane@" + DOMAIN)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=account["id"],
            roles=[WorkspaceRoles.COLLABORATOR],
        )
    )
    reply = await sign_in(client)
    assert not sso_error(reply) and "Authorization" in reply.cookies


async def test_another_workspaces_domain_is_refused(client, sso_workspace, workspace_1):
    # the IdP asserts an address on a domain verified by another workspace
    await verify_domain(workspace_1.id, "other-corp.org")
    _, auth = sso_on_of()
    auth.idp_email = "mallory@other-corp.org"

    reply = await sign_in(client)

    assert sso_error(reply) == "sso_email_domain_not_allowed"
    assert "Authorization" not in reply.cookies
    assert auth.created_accounts() == []


@pytest.mark.parametrize("email", ["mallory@unclaimed-corp.org", "jane@eng." + DOMAIN])
async def test_an_address_outside_the_verified_domains_is_refused(
    client, sso_workspace, email
):
    _, auth = sso_on_of()
    auth.idp_email = email
    reply = await sign_in(client)
    assert sso_error(reply) == "sso_email_domain_not_allowed"
    assert auth.created_accounts() == []


async def test_a_tenant_mismatch_is_refused(client, sso_workspace, workspace_1):
    _, auth = sso_on_of()
    auth.tenant_override = str(workspace_1.id)
    reply = await sign_in(client)
    assert sso_error(reply) == "sso_tenant_mismatch"
    assert auth.created_accounts() == []


async def test_a_code_from_another_connection_is_refused(client, sso_workspace):
    _, auth = sso_on_of()
    auth.client_id_override = "another-connection"
    reply = await sign_in(client)
    assert sso_error(reply) == "sso_tenant_mismatch"


async def test_a_connection_disabled_mid_sign_in_is_refused(client, sso_workspace):
    workspace, connection = sso_workspace
    started = await start(client)
    connection.status = "disabled"
    await container.sso_connection_repo().save(connection)
    reply = await client.get(
        CALLBACK, params={"code": "c", "state": state_of(started.headers["location"])}
    )
    assert sso_error(reply) == "sso_not_configured"


async def test_a_disabled_workspace_is_refused_before_the_account(
    client, sso_workspace
):
    workspace, _ = sso_workspace
    started = await start(client)
    await container.workspace_repo().set_fields(workspace, {"disabled": True})
    _, auth = sso_on_of()
    reply = await client.get(
        CALLBACK, params={"code": "c", "state": state_of(started.headers["location"])}
    )
    assert sso_error(reply) == "sso_workspace_unavailable"
    assert auth.created_accounts() == []


async def test_an_account_conflict_is_refused(client, sso_workspace):
    _, auth = sso_on_of()
    auth.account_conflict = True
    assert sso_error(await sign_in(client)) == "sso_account_conflict"


async def test_an_idp_error_goes_back_to_the_login_page(client, sso_workspace):
    started = await start(client)
    reply = await client.get(
        CALLBACK,
        params={
            "error": "access_denied",
            "state": state_of(started.headers["location"]),
        },
    )
    assert reply.headers["location"].startswith(LOGIN_PAGE)
    assert sso_error(reply) == "sso_failed"


async def test_a_callback_without_state_is_refused(client, sso_workspace):
    reply = await client.get(CALLBACK, params={"code": "c"})
    assert sso_error(reply) == "sso_failed"


async def test_the_success_redirect_ignores_a_foreign_referer(client, sso_workspace):
    workspace, _ = sso_workspace
    reply = await sign_in(client, referer="https://evil.test/login")
    location = urlsplit(reply.headers["location"])
    assert location.netloc == "localhost:3000"
    assert location.path == f"/{workspace.workspace_name}/dashboard/forms"


async def test_an_allowed_origin_referer_is_followed(
    client, sso_workspace, monkeypatch
):
    origins = container.allowed_origins_repo()

    async def listed():
        return ["https://admin.example.test"]

    monkeypatch.setattr(origins, "list_origins", listed)
    reply = await sign_in(client, referer="https://admin.example.test/login")
    assert reply.headers["location"].startswith("https://admin.example.test/")


async def test_free_text_error_codes_are_not_reflected(
    client, sso_workspace, monkeypatch
):
    from common.exceptions.http import HTTPException as CommonHTTPException

    _, auth = sso_on_of()

    async def failing(*args, **kwargs):
        raise CommonHTTPException(400, {"code": "<script>alert(1)</script>"})

    monkeypatch.setattr(auth, "get", failing)
    reply = await start(client)
    assert sso_error(reply) == "sso_failed"


# -- platform admin -----------------------------------------------------------
async def test_an_sso_session_never_asks_for_the_admin_grant(client, sso_workspace):
    from backend.app.services import session_service as session_module

    reply = await sign_in(client)
    seen = []

    class Auth:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, params=None, **kwargs):
            seen.append(params)

            class Reply:
                status_code = 200

                @staticmethod
                def json():
                    return {
                        "id": params["user_id"],
                        "email": "jane@" + DOMAIN,
                        "roles": [],
                    }

            return Reply()

    original = session_module.auth_http_client
    session_module.auth_http_client = Auth
    try:
        refreshed = await client.post(
            "/api/v1/auth/refresh",
            cookies={"RefreshToken": reply.cookies.get("RefreshToken")},
        )
    finally:
        session_module.auth_http_client = original
    assert refreshed.status_code == 200, refreshed.text
    assert seen and seen[0]["email_verified"] is False
    assert decode_token(refreshed.cookies.get("Authorization"))["auth_method"] == "sso"


# -- test a connection --------------------------------------------------------
TEST = "/api/v1/workspaces/{ws}/sso/connections/{c}/test"


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def test_a_connection_test_records_success_without_signing_in(
    client, workspace, sso_on
):
    await verify_domain(workspace.id)
    connection = await add_connection(workspace.id, enabled=False, tested=False)
    _, auth = sso_on
    page = f"http://localhost:3000/{workspace.workspace_name}/dashboard/sso"

    started = await client.get(
        TEST.format(ws=workspace.id, c=connection.id),
        cookies=_cookies(testUser),
        headers={"referer": page},
    )
    assert started.status_code == 307, started.text
    reply = await client.get(
        CALLBACK,
        params={"code": "c", "state": state_of(started.headers["location"])},
        cookies=_cookies(testUser),
    )

    assert reply.headers["location"].startswith(page)
    assert query_of(reply.headers["location"])["sso_test"] == "ok"
    assert "Authorization" not in reply.cookies
    assert auth.created_accounts() == []
    stored = await container.sso_connection_repo().get(connection.id)
    assert stored.is_tested and stored.tested_by == testUser.id


async def test_a_failed_test_is_recorded(client, workspace, sso_on):
    await verify_domain(workspace.id)
    connection = await add_connection(workspace.id, enabled=False, tested=False)
    _, auth = sso_on
    auth.idp_email = "someone@unclaimed-corp.org"
    started = await client.get(
        TEST.format(ws=workspace.id, c=connection.id), cookies=_cookies(testUser)
    )
    reply = await client.get(
        CALLBACK,
        params={"code": "c", "state": state_of(started.headers["location"])},
        cookies=_cookies(testUser),
    )
    assert (
        query_of(reply.headers["location"])["sso_test"]
        == "sso_email_domain_not_allowed"
    )
    stored = await container.sso_connection_repo().get(connection.id)
    assert not stored.is_tested
    assert stored.last_test_error == "sso_email_domain_not_allowed"


async def test_only_the_admin_who_started_the_test_completes_it(
    client, workspace, sso_on
):
    await verify_domain(workspace.id)
    connection = await add_connection(workspace.id, enabled=False, tested=False)
    started = await client.get(
        TEST.format(ws=workspace.id, c=connection.id), cookies=_cookies(testUser)
    )
    reply = await client.get(
        CALLBACK,
        params={"code": "c", "state": state_of(started.headers["location"])},
        cookies=_cookies(testUser1),
    )
    assert query_of(reply.headers["location"])["sso_test"] == "sso_test_not_allowed"
    stored = await container.sso_connection_repo().get(connection.id)
    assert not stored.is_tested


async def test_testing_needs_security_manage(client, workspace, sso_on):
    connection = await add_connection(workspace.id, enabled=False)
    reply = await client.get(
        TEST.format(ws=workspace.id, c=connection.id), cookies=_cookies(testUser1)
    )
    assert reply.status_code == 403
