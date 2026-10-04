"""Single sign-on administration and the SSO-required policy (docs/sso.md).
Polis's admin API and the auth service are stand-ins (tests/app/sso_helpers)."""

import pytest
from beanie import PydanticObjectId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.session import SessionDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.session_service import utcnow
from backend.app.services.sso.polis_client import PolisError, PolisUnavailable
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import invited_user, testUser, testUser1
from tests.app.sso_helpers import (  # noqa: F401 — fixtures
    DISCOVERY_URL,
    METADATA_URL,
    discovery,
    DOMAIN,
    SAML_XML,
    add_connection,
    sso_on,
    verify_domain,
)

W = "/api/v1/workspaces/{ws}/sso"


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def url(workspace, suffix=""):
    return W.format(ws=workspace.id) + suffix


# -- overview -----------------------------------------------------------------
async def test_overview_shows_sp_values_domains_and_settings(client, workspace, sso_on):
    await verify_domain(workspace.id)
    await verify_domain(workspace.id, "lost-corp.org", lost=True)

    reply = await client.get(url(workspace), cookies=_cookies(testUser))

    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["available"] is True
    assert body["serviceProvider"] == {
        "acsUrl": "https://polis.test/api/oauth/saml",
        "entityId": "https://saml.bettercollected.test",
        "spMetadataUrl": "https://polis.test/.well-known/sp-metadata",
        "oidcRedirectUri": "https://polis.test/api/oauth/oidc",
    }
    assert body["domains"] == [DOMAIN]  # the lost one is not an SSO domain
    assert body["settings"]["ssoRequired"] is False
    assert body["settings"]["defaultRole"] == "COLLABORATOR"
    assert "ADMIN" not in body["settings"]["assignableRoles"]
    assert body["settings"]["ownerBreakGlass"] is True
    # the API key never reaches the browser
    assert "test-api-key" not in reply.text


async def test_overview_when_sso_is_off(client, workspace):
    reply = await client.get(url(workspace), cookies=_cookies(testUser))
    assert reply.status_code == 200
    assert reply.json()["available"] is False
    assert reply.json()["serviceProvider"] is None


# -- create -------------------------------------------------------------------
async def test_create_a_saml_connection_from_xml(client, workspace, sso_on):
    polis, _ = sso_on
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "name": "Okta", "metadataXml": SAML_XML},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 201, reply.text
    body = reply.json()
    assert body["status"] == "disabled" and body["tested"] is False
    assert body["idpEntityId"] == "https://idp.acme-sso.org/entity"
    assert polis.calls[0][:3] == ("create_saml", str(workspace.id), "Okta")
    stored = await container.sso_connection_repo().list_by_workspace(workspace.id)
    assert stored[0].polis_client_id == "polis-client-1"
    assert stored[0].polis_tenant == str(workspace.id)


async def test_create_a_saml_connection_from_a_public_url(client, workspace, sso_on):
    polis, _ = sso_on
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataUrl": METADATA_URL},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 201, reply.text
    # fetched by us through the guard; Polis gets the XML, never the URL
    assert polis.web.requested == [METADATA_URL]
    assert polis.calls[0][3] is True and polis.calls[0][4] is None
    assert reply.json()["metadataUrl"] == METADATA_URL


@pytest.mark.parametrize(
    "metadata_url,code",
    [
        ("http://idp.acme-sso.org/metadata", "https_required"),
        ("https://127.0.0.1/metadata", "private_address"),
        ("https://169.254.169.254/latest/meta-data", "private_address"),
        ("https://localhost:5225/metadata", "private_address"),
        ("https://user:pw@idp.acme-sso.org/", "invalid_url"),
    ],
)
async def test_ssrf_metadata_urls_are_refused_before_polis(
    client, workspace, sso_on, metadata_url, code
):
    polis, _ = sso_on
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataUrl": metadata_url},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 422, reply.text
    assert reply.json()["code"] == code
    assert polis.calls == []


async def test_a_name_resolving_privately_is_refused(
    client, workspace, sso_on, monkeypatch
):
    polis, _ = sso_on

    async def internal(host):
        return ["10.0.0.5"]

    monkeypatch.setattr(container.sso_connection_service(), "_resolver", internal)
    reply = await client.post(
        url(workspace, "/connections"),
        json={
            "type": "oidc",
            "discoveryUrl": "https://idp.internal-corp.org/.well-known/openid-configuration",
            "clientId": "a",
            "clientSecret": "b",
        },
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 422 and reply.json()["code"] == "private_address"
    assert polis.calls == []


@pytest.mark.parametrize(
    "body,code",
    [
        ({"type": "saml"}, "metadata_required"),
        (
            {"type": "saml", "metadataXml": SAML_XML, "metadataUrl": "https://x.org/m"},
            "metadata_required",
        ),
        ({"type": "saml", "metadataXml": "<html>not saml</html>"}, "invalid_metadata"),
        (
            {"type": "oidc", "discoveryUrl": "https://idp.acme-sso.org/x"},
            "oidc_fields_required",
        ),
    ],
)
async def test_incomplete_requests_are_refused(client, workspace, sso_on, body, code):
    reply = await client.post(
        url(workspace, "/connections"), json=body, cookies=_cookies(testUser)
    )
    assert reply.status_code == 422, reply.text
    assert reply.json()["code"] == code


async def test_create_an_oidc_connection_keeps_the_secret_out(
    client, workspace, sso_on
):
    polis, _ = sso_on
    reply = await client.post(
        url(workspace, "/connections"),
        json={
            "type": "oidc",
            "discoveryUrl": "https://login.acme-sso.org/.well-known/openid-configuration",
            "clientId": "bc-client",
            "clientSecret": "very-secret-value",
        },
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 201, reply.text
    assert "very-secret-value" not in reply.text
    stored = (await container.sso_connection_repo().list_by_workspace(workspace.id))[0]
    assert "very-secret-value" not in stored.model_dump_json()
    assert stored.oidc_client_id == "bc-client"
    assert polis.calls[0][0] == "create_oidc"


async def test_a_polis_refusal_is_a_clear_error(client, workspace, sso_on):
    polis, _ = sso_on
    polis.fail = PolisError(
        400, "EntityID already exists for different tenant", "idp_already_connected"
    )
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataXml": SAML_XML},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 409 and reply.json()["code"] == "idp_already_connected"
    polis.fail = PolisUnavailable()
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataXml": SAML_XML},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 503


async def test_the_connection_count_is_capped(client, workspace, sso_on, monkeypatch):
    monkeypatch.setattr(settings.sso, "MAX_CONNECTIONS_PER_WORKSPACE", 1)
    await add_connection(workspace.id)
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataXml": SAML_XML},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 422 and reply.json()["code"] == "too_many_connections"


async def test_creating_needs_sso_on(client, workspace):
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataXml": SAML_XML},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 404 and reply.json()["code"] == "sso_disabled"


# -- enable / disable / delete ------------------------------------------------
async def test_enabling_one_connection_disables_the_others(client, workspace, sso_on):
    first = await add_connection(workspace.id, enabled=True)
    second = await add_connection(workspace.id, enabled=False)

    reply = await client.post(
        url(workspace, f"/connections/{second.id}/enable"), cookies=_cookies(testUser)
    )

    assert reply.status_code == 200 and reply.json()["status"] == "enabled"
    repo = container.sso_connection_repo()
    assert (await repo.get(first.id)).status.value == "disabled"
    assert (await repo.find_enabled(workspace.id)).id == second.id


async def test_disable_and_delete(client, workspace, sso_on):
    polis, _ = sso_on
    connection = await add_connection(workspace.id)
    reply = await client.post(
        url(workspace, f"/connections/{connection.id}/disable"),
        cookies=_cookies(testUser),
    )
    assert reply.json()["status"] == "disabled"
    reply = await client.delete(
        url(workspace, f"/connections/{connection.id}"), cookies=_cookies(testUser)
    )
    assert reply.status_code == 204
    assert ("delete", connection.polis_client_id) in polis.calls
    assert await container.sso_connection_repo().get(connection.id) is None


async def test_another_workspaces_connection_is_404(
    client, workspace, workspace_1, sso_on
):
    other = await add_connection(workspace_1.id)
    for method, suffix in (
        ("POST", f"/connections/{other.id}/enable"),
        ("POST", f"/connections/{other.id}/disable"),
        ("DELETE", f"/connections/{other.id}"),
        ("GET", f"/connections/{other.id}/test"),
    ):
        reply = await client.request(
            method, url(workspace, suffix), cookies=_cookies(testUser)
        )
        assert reply.status_code == 404, (suffix, reply.text)


# -- settings and SSO required -------------------------------------------------
async def test_default_role_is_validated(client, workspace, sso_on):
    reply = await client.put(
        url(workspace, "/settings"),
        json={"defaultRole": "ADMIN"},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 422 and reply.json()["code"] == "invalid_role"
    reply = await client.put(
        url(workspace, "/settings"),
        json={"defaultRole": "COLLABORATOR"},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 200 and reply.json()["defaultRole"] == "COLLABORATOR"


@pytest.mark.parametrize(
    "setup,code",
    [
        ("none", "sso_connection_required"),
        ("untested", "sso_connection_untested"),
        ("no_domain", "sso_domain_required"),
    ],
)
async def test_requiring_sso_needs_an_enabled_tested_connection(
    client, workspace, sso_on, setup, code
):
    if setup != "no_domain":
        await verify_domain(workspace.id)
    if setup == "untested":
        await add_connection(workspace.id, tested=False)
    if setup == "no_domain":
        await add_connection(workspace.id)
    reply = await client.put(
        url(workspace, "/settings"),
        json={"ssoRequired": True},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 409, reply.text
    assert reply.json()["code"] == code


async def require_sso(client, workspace, revoke=False):
    reply = await client.put(
        url(workspace, "/settings"),
        json={"ssoRequired": True, "revokeSessions": revoke},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 200, reply.text
    return reply.json()


@pytest.fixture()
async def required(client, workspace, sso_on):
    await verify_domain(workspace.id)
    connection = await add_connection(workspace.id)
    return workspace, connection


async def test_the_enabled_connection_is_kept_while_sso_is_required(client, required):
    workspace, connection = required
    await require_sso(client, workspace)
    for method, suffix in (
        ("POST", f"/connections/{connection.id}/disable"),
        ("DELETE", f"/connections/{connection.id}"),
    ):
        reply = await client.request(
            method, url(workspace, suffix), cookies=_cookies(testUser)
        )
        assert reply.status_code == 409 and reply.json()["code"] == "sso_required_on"


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


async def test_requiring_sso_can_sign_out_the_domains_members(client, required, sso_on):
    workspace, _ = required
    _, auth = sso_on
    member = auth.add_account("bob@" + DOMAIN)
    outsider = auth.add_account("carol@elsewhere-corp.org")
    owner = auth.add_account("owner@" + DOMAIN, user_id=testUser.id)
    for account in (member, outsider):
        await container.workspace_user_repo().save(
            WorkspaceUserDocument(
                workspace_id=workspace.id,
                user_id=account["id"],
                roles=[WorkspaceRoles.COLLABORATOR],
            )
        )
    for account in (member, outsider, owner):
        await _session(account["id"])

    body = await require_sso(client, workspace, revoke=True)

    assert body["ssoRequired"] is True and body["revokedSessions"] == 1
    sessions = container.session_service()
    assert await sessions.list_for_user(member["id"]) == []
    assert len(await sessions.list_for_user(outsider["id"])) == 1  # other domain
    assert len(await sessions.list_for_user(owner["id"])) == 1  # break-glass owner


async def test_requiring_sso_without_revoking_keeps_sessions(client, required, sso_on):
    workspace, _ = required
    _, auth = sso_on
    member = auth.add_account("bob@" + DOMAIN)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=member["id"], roles=["COLLABORATOR"]
        )
    )
    await _session(member["id"])
    body = await require_sso(client, workspace)
    assert body["revokedSessions"] is None
    assert len(await container.session_service().list_for_user(member["id"])) == 1


# -- enforcement --------------------------------------------------------------
async def test_code_sign_in_is_refused_for_an_sso_required_domain(
    client, required, sso_on
):
    workspace, _ = required
    await require_sso(client, workspace)

    reply = await client.post(
        "/api/v1/auth/creator/otp/send", params={"receiver_email": "Bob@" + DOMAIN}
    )
    assert reply.status_code == 403, reply.text
    assert reply.json()["code"] == "sso_required"
    assert "Sign in with SSO" in reply.json()["message"]

    reply = await client.post(
        f"/api/v1/workspaces/{workspace.id}/auth/otp/send",
        params={"receiver_email": "bob@" + DOMAIN},
    )
    assert reply.status_code == 403 and reply.json()["code"] == "sso_required"

    # other domains are unaffected
    reply = await client.post(
        "/api/v1/auth/creator/otp/send",
        params={"receiver_email": "bob@elsewhere-corp.org"},
    )
    assert reply.status_code == 200


async def test_checking_a_code_is_refused_too(client, required, sso_on):
    workspace, _ = required
    _, auth = sso_on
    await require_sso(client, workspace)
    member = auth.add_account("bob@" + DOMAIN)
    auth.otp_user = {**member, "email_verified": True}

    reply = await client.post(
        "/api/v1/auth/otp/validate", json={"email": "bob@" + DOMAIN, "otp_code": "X"}
    )

    assert reply.status_code == 403 and reply.json()["code"] == "sso_required"
    assert "Authorization" not in reply.cookies


async def test_the_owner_keeps_the_email_code_break_glass(client, required, sso_on):
    workspace, _ = required
    _, auth = sso_on
    await require_sso(client, workspace)
    owner = auth.add_account("owner@" + DOMAIN, user_id=testUser.id)
    auth.otp_user = {**owner, "email_verified": True}

    sent = await client.post(
        "/api/v1/auth/creator/otp/send", params={"receiver_email": "Owner@" + DOMAIN}
    )
    assert sent.status_code == 200, sent.text
    reply = await client.post(
        "/api/v1/auth/otp/validate", json={"email": "owner@" + DOMAIN, "otp_code": "X"}
    )
    assert reply.status_code == 200, reply.text
    assert "Authorization" in reply.cookies


async def test_google_sign_in_is_refused_even_for_the_owner(client, required, sso_on):
    workspace, _ = required
    _, auth = sso_on
    await require_sso(client, workspace)
    service = container.auth_service()

    async def google_callback(url, params=None, **kwargs):
        return {
            "user": {
                "id": testUser.id,
                "sub": "owner@" + DOMAIN,
                "roles": ["FORM_CREATOR"],
            },
            "client_referer_url": "http://localhost:3000/login",
        }

    auth.get = google_callback
    user, redirect = await service.basic_auth_callback("google", "code", "state")
    assert user is None
    assert "login_error=sso_required" in redirect


async def test_nothing_is_enforced_without_an_enabled_connection(
    client, required, sso_on
):
    workspace, connection = required
    await require_sso(client, workspace)
    # an operator switching SSO off for the instance lifts the requirement
    from backend.config import settings as live

    live.sso.ENABLED = False
    try:
        reply = await client.post(
            "/api/v1/auth/creator/otp/send", params={"receiver_email": "bob@" + DOMAIN}
        )
    finally:
        live.sso.ENABLED = True
    assert reply.status_code == 200


async def test_a_lost_domain_is_not_enforced(client, workspace, sso_on):
    claim = await verify_domain(workspace.id)
    await add_connection(workspace.id)
    await require_sso(client, workspace)
    import datetime as dt

    claim.verification_lost_at = dt.datetime.now(dt.timezone.utc)
    await container.workspace_domain_repo().save(claim)
    reply = await client.post(
        "/api/v1/auth/creator/otp/send", params={"receiver_email": "bob@" + DOMAIN}
    )
    assert reply.status_code == 200


# -- workspace deletion -------------------------------------------------------
async def test_deleting_the_workspace_removes_its_connections(
    client, workspace, sso_on
):
    polis, _ = sso_on
    await add_connection(workspace.id)
    await container.sso_connection_service().release_workspaces([workspace.id])
    assert ("delete_tenant", str(workspace.id)) in polis.calls
    assert await container.sso_connection_repo().list_by_workspace(workspace.id) == []


# -- access -------------------------------------------------------------------
@pytest.mark.parametrize("user", [invited_user, testUser1])
async def test_members_and_outsiders_are_refused(client, workspace, sso_on, user):
    for method, suffix, body in (
        ("GET", "", None),
        ("POST", "/connections", {"type": "saml", "metadataXml": SAML_XML}),
        ("PUT", "/settings", {"ssoRequired": False}),
    ):
        reply = await client.request(
            method, url(workspace, suffix), json=body, cookies=_cookies(user)
        )
        assert reply.status_code == 403, (suffix, reply.text)


# -- review fixes: guarded fetches ---------------------------------------------
async def test_a_redirect_to_a_private_address_is_refused(client, workspace, sso_on):
    polis, _ = sso_on
    polis.web.pages[METADATA_URL] = (
        302,
        "",
        {"location": "https://169.254.169.254/latest/meta-data/"},
    )
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataUrl": METADATA_URL},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 422 and reply.json()["code"] == "private_address"
    assert polis.web.requested == [METADATA_URL]  # the private hop is never asked
    assert polis.calls == []


async def test_a_public_redirect_hop_is_followed(client, workspace, sso_on):
    polis, _ = sso_on
    moved = "https://cdn.acme-sso.org/metadata.xml"
    polis.web.pages[METADATA_URL] = (301, "", {"location": moved})
    polis.web.pages[moved] = (200, SAML_XML, {})
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataUrl": METADATA_URL},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 201, reply.text
    assert polis.web.requested == [METADATA_URL, moved]


async def test_too_many_redirects_are_refused(client, workspace, sso_on):
    polis, _ = sso_on
    polis.web.pages[METADATA_URL] = (302, "", {"location": METADATA_URL})
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataUrl": METADATA_URL},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 422 and reply.json()["code"] == "fetch_failed"


def _oidc(secret="s3cret"):
    return {
        "type": "oidc",
        "discoveryUrl": DISCOVERY_URL,
        "clientId": "bc",
        "clientSecret": secret,
    }


async def test_oidc_hands_polis_the_checked_endpoints(client, workspace, sso_on):
    polis, _ = sso_on
    reply = await client.post(
        url(workspace, "/connections"), json=_oidc(), cookies=_cookies(testUser)
    )
    assert reply.status_code == 201, reply.text
    metadata = polis.calls[0][3]
    assert metadata == {
        k: discovery()[k]
        for k in (
            "issuer",
            "authorization_endpoint",
            "token_endpoint",
            "userinfo_endpoint",
            "jwks_uri",
        )
    }


@pytest.mark.parametrize(
    "override,code",
    [
        ({"token_endpoint": "https://10.0.0.8/token"}, "private_address"),
        ({"jwks_uri": "https://169.254.169.254/keys"}, "private_address"),
        ({"userinfo_endpoint": "http://login.acme-sso.org/userinfo"}, "https_required"),
        ({"authorization_endpoint": "https://localhost/authorize"}, "private_address"),
        ({"jwks_uri": None}, "invalid_discovery"),
    ],
)
async def test_oidc_endpoints_must_be_public_https(
    client, workspace, sso_on, override, code
):
    import json as _json

    polis, _ = sso_on
    doc = {k: v for k, v in discovery(**override).items() if v is not None}
    polis.web.pages[DISCOVERY_URL] = (200, _json.dumps(doc), {})
    reply = await client.post(
        url(workspace, "/connections"), json=_oidc(), cookies=_cookies(testUser)
    )
    assert reply.status_code == 422, reply.text
    assert reply.json()["code"] == code
    assert polis.calls == []


async def test_a_test_rechecks_the_oidc_endpoints(
    client, workspace, sso_on, monkeypatch
):
    reply = await client.post(
        url(workspace, "/connections"), json=_oidc(), cookies=_cookies(testUser)
    )
    cid = reply.json()["id"]

    async def now_private(host):
        return ["10.1.2.3"]

    monkeypatch.setattr(container.sso_connection_service(), "_resolver", now_private)
    reply = await client.get(
        url(workspace, f"/connections/{cid}/test"), cookies=_cookies(testUser)
    )
    assert reply.status_code == 422 and reply.json()["code"] == "private_address"


# -- review fixes: owner only --------------------------------------------------
@pytest.fixture()
async def admin_member(workspace):
    admin = User(id=str(PydanticObjectId()), sub="admin@" + DOMAIN)
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=admin.id, roles=[WorkspaceRoles.ADMIN]
        )
    )
    return admin


async def test_an_admin_can_view_and_test_but_not_change(
    client, workspace, sso_on, admin_member
):
    polis, _ = sso_on
    connection = await add_connection(workspace.id, enabled=False)
    reply = await client.get(url(workspace), cookies=_cookies(admin_member))
    assert reply.status_code == 200 and reply.json()["canManage"] is False
    reply = await client.get(
        url(workspace, f"/connections/{connection.id}/test"),
        cookies=_cookies(admin_member),
    )
    assert reply.status_code == 307
    for method, suffix, body in (
        ("POST", "/connections", {"type": "saml", "metadataXml": SAML_XML}),
        ("POST", f"/connections/{connection.id}/enable", None),
        ("POST", f"/connections/{connection.id}/disable", None),
        ("DELETE", f"/connections/{connection.id}", None),
        ("PUT", "/settings", {"ssoRequired": True}),
        ("PUT", "/settings", {"defaultRole": "COLLABORATOR"}),
    ):
        reply = await client.request(
            method, url(workspace, suffix), json=body, cookies=_cookies(admin_member)
        )
        assert reply.status_code == 403, (method, suffix, reply.text)
    assert polis.calls == []
    stored = await container.sso_connection_repo().get(connection.id)
    assert stored.status.value == "disabled"


async def test_the_owner_can_manage(client, workspace, sso_on):
    reply = await client.get(url(workspace), cookies=_cookies(testUser))
    assert reply.json()["canManage"] is True


async def test_an_untested_connection_cannot_be_enabled(client, workspace, sso_on):
    connection = await add_connection(workspace.id, enabled=False, tested=False)
    reply = await client.post(
        url(workspace, f"/connections/{connection.id}/enable"),
        cookies=_cookies(testUser),
    )
    assert (
        reply.status_code == 409 and reply.json()["code"] == "sso_connection_untested"
    )


async def test_a_changed_configuration_must_be_tested_again(client, workspace, sso_on):
    polis, _ = sso_on
    first = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataXml": SAML_XML},
        cookies=_cookies(testUser),
    )
    stored = await container.sso_connection_repo().get(first.json()["id"])
    stored.tested_at = utcnow()
    await container.sso_connection_repo().save(stored)
    # Polis updates the connection of the same IdP in place
    polis._n -= 1
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataXml": SAML_XML},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 409 and reply.json()["code"] == "connection_exists"
    stored = await container.sso_connection_repo().get(first.json()["id"])
    assert not stored.is_tested and stored.last_test_error == "config_changed"


async def test_a_squatted_entity_id_suggests_support(client, workspace, sso_on):
    polis, _ = sso_on
    polis.fail = PolisError(
        400, "EntityID already exists for different tenant", "idp_already_connected"
    )
    reply = await client.post(
        url(workspace, "/connections"),
        json={"type": "saml", "metadataXml": SAML_XML},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 409
    assert "contact support" in reply.json()["message"]
