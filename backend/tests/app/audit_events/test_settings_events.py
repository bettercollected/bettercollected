"""The workspace audit log's security-settings events: single sign-on
connections and policy, verified email domains, directory sync (SCIM), the AI
consent and the custom domain.

Each is written with the right kind and ids and nothing else (no name, no
hostname, no URL, no address, no token, no secret). The ones that open access,
hand something over or remove configuration are written *before* the change and
refuse it (503 ``audit_unavailable``, nothing changed) when the entry cannot be
stored; closing a way in and the inert ones are best effort. Everything here is
synthetic."""

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.workspace_audit_event import (
    AI_CONSENT_CHANGED,
    AUTOMATION_EVENTS,
    CUSTOM_DOMAIN_CHANGED,
    CUSTOM_DOMAIN_REMOVED,
    DOMAIN_CLAIMED,
    DOMAIN_REMOVED,
    DOMAIN_VERIFIED,
    SCIM_GROUP_ROLE_CHANGED,
    SCIM_TOKEN_CREATED,
    SCIM_TOKEN_REVOKED,
    SCIM_TOKEN_ROTATED,
    SETTINGS_EVENTS,
    SSO_CONNECTION_CREATED,
    SSO_CONNECTION_DELETED,
    SSO_CONNECTION_DISABLED,
    SSO_CONNECTION_ENABLED,
    SSO_DEFAULT_ROLE_CHANGED,
    SSO_REQUIRED_CHANGED,
)
from backend.app.services.audit_log import catalog
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser
from tests.app.domain_helpers import fake_dns  # noqa: F401 — fixture
from tests.app.form_access.helpers import audit_events, fail_audit
from tests.app.scim_helpers import (  # noqa: F401 — fixtures
    create_directory,
    deliver,
    event,
    group_data,
    members_list,
    scim_on,
)
from tests.app.sso_helpers import (  # noqa: F401 — fixtures
    SAML_XML,
    add_connection,
    sso_on,
    verify_domain,
)

pytestmark = pytest.mark.asyncio

OWNER = {"Authorization": access_token(testUser), "RefreshToken": access_token(testUser)}
RECORD = "_bettercollected-verification.acme.com"


def sso(workspace, suffix=""):
    return f"/api/v1/workspaces/{workspace.id}/sso{suffix}"


def scim(workspace, suffix=""):
    return f"/api/v1/workspaces/{workspace.id}/scim{suffix}"


def domains(workspace, *rest):
    return "/".join([f"/api/v1/workspaces/{workspace.id}/domains", *rest])


def dump(events) -> str:
    return str([e.model_dump(mode="json") for e in events])


def clean(events, *extra):
    """No URL, address, token or secret in any row; ``extra`` are strings of
    the test's own (a hostname, a name, a token) that must not appear either."""
    # (the kind itself may say "token": look at everything else)
    text = str(
        [e.model_dump(mode="json", exclude={"event"}) for e in events]
    )
    for forbidden in ("http", "@", "secret", "token", "bearer", *extra):
        assert forbidden not in text.lower(), forbidden


async def all_settings_events(workspace):
    return await audit_events(workspace, *SETTINGS_EVENTS)


def refused_unrecorded(reply):
    assert reply.status_code == 503, reply.text
    assert reply.json()["code"] == "audit_unavailable"


# -- single sign-on connections -------------------------------------------------
@pytest.fixture()
async def domain_verified(workspace):
    return await verify_domain(workspace.id, "connections-sso.org")


async def test_creating_a_connection_records_its_id_and_type_only(
    client: AsyncClient, workspace, sso_on, domain_verified
):
    reply = await client.post(
        sso(workspace, "/connections"),
        json={"type": "saml", "name": "Okta Example", "metadataXml": SAML_XML},
        cookies=OWNER,
    )
    assert reply.status_code == 201, reply.text

    (entry,) = await audit_events(workspace, SSO_CONNECTION_CREATED)
    assert (entry.user_id, entry.connection_id, entry.connection_type) == (
        testUser.id,
        reply.json()["id"],
        "saml",
    )
    # not the name, the IdP's entity id, nor any of its metadata
    clean([entry], "okta", "idp.", "entity")


async def test_creating_a_connection_is_best_effort(
    client: AsyncClient, workspace, sso_on, domain_verified, monkeypatch
):
    fail_audit(monkeypatch)
    reply = await client.post(
        sso(workspace, "/connections"),
        json={"type": "saml", "name": "Okta", "metadataXml": SAML_XML},
        cookies=OWNER,
    )
    assert reply.status_code == 201, reply.text
    assert len(await container.sso_connection_repo().list_by_workspace(workspace.id)) == 1
    assert await audit_events(workspace, SSO_CONNECTION_CREATED) == []


async def test_enabling_a_connection_is_recorded_and_refused_unrecorded(
    client: AsyncClient, workspace, sso_on, monkeypatch
):
    connection = await add_connection(workspace.id, enabled=False)
    url = sso(workspace, f"/connections/{connection.id}/enable")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.post(url, cookies=OWNER))
    assert not (await container.sso_connection_repo().get(connection.id)).is_enabled

    reply = await client.post(url, cookies=OWNER)
    assert reply.status_code == 200, reply.text
    (entry,) = await audit_events(workspace, SSO_CONNECTION_ENABLED)
    assert (entry.connection_id, entry.connection_type) == (str(connection.id), "saml")
    # enabling it again changes nothing and records nothing more
    assert (await client.post(url, cookies=OWNER)).status_code == 200
    assert len(await audit_events(workspace, SSO_CONNECTION_ENABLED)) == 1
    clean([entry], "acme")


async def test_disabling_a_connection_is_best_effort(
    client: AsyncClient, workspace, sso_on, monkeypatch
):
    connection = await add_connection(workspace.id)
    url = sso(workspace, f"/connections/{connection.id}/disable")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        reply = await client.post(url, cookies=OWNER)
        assert reply.status_code == 200 and reply.json()["status"] == "disabled"
    assert await audit_events(workspace, SSO_CONNECTION_DISABLED) == []

    again = await add_connection(workspace.id)
    reply = await client.post(
        sso(workspace, f"/connections/{again.id}/disable"), cookies=OWNER
    )
    assert reply.status_code == 200
    (entry,) = await audit_events(workspace, SSO_CONNECTION_DISABLED)
    assert entry.connection_id == str(again.id)


async def test_deleting_a_connection_is_recorded_and_refused_unrecorded(
    client: AsyncClient, workspace, sso_on, monkeypatch
):
    polis, _ = sso_on
    connection = await add_connection(workspace.id, enabled=False)
    url = sso(workspace, f"/connections/{connection.id}")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.delete(url, cookies=OWNER))
    # nothing was deleted, here or at the identity provider's broker
    assert await container.sso_connection_repo().get(connection.id) is not None
    assert ("delete", connection.polis_client_id) not in polis.calls

    assert (await client.delete(url, cookies=OWNER)).status_code == 204
    (entry,) = await audit_events(workspace, SSO_CONNECTION_DELETED)
    assert entry.connection_id == str(connection.id)
    clean([entry], connection.polis_client_id)


# -- single sign-on policy --------------------------------------------------------
async def test_requiring_sso_is_recorded_as_a_flag_and_refused_unrecorded(
    client: AsyncClient, workspace, sso_on, monkeypatch
):
    await verify_domain(workspace.id)
    await add_connection(workspace.id)
    url = sso(workspace, "/settings")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.put(url, json={"ssoRequired": True}, cookies=OWNER))
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert not stored.sso_required

    assert (await client.put(url, json={"ssoRequired": True}, cookies=OWNER)).status_code == 200
    # the same value again is no change and no entry
    assert (await client.put(url, json={"ssoRequired": True}, cookies=OWNER)).status_code == 200
    (entry,) = await audit_events(workspace, SSO_REQUIRED_CHANGED)
    assert (entry.user_id, entry.required) == (testUser.id, True)

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.put(url, json={"ssoRequired": False}, cookies=OWNER))
    assert (await container.workspace_repo().find_by_id(workspace.id)).sso_required

    assert (await client.put(url, json={"ssoRequired": False}, cookies=OWNER)).status_code == 200
    entries = await audit_events(workspace, SSO_REQUIRED_CHANGED)
    assert [e.required for e in entries] == [True, False]
    clean(entries)


async def test_changing_the_default_role_records_both_roles_as_enums(
    client: AsyncClient, workspace, sso_on, monkeypatch
):
    url = sso(workspace, "/settings")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.put(url, json={"defaultRole": "EDITOR"}, cookies=OWNER))
    assert (await container.workspace_repo().find_by_id(workspace.id)).sso_default_role is None

    assert (await client.put(url, json={"defaultRole": "REVIEWER"}, cookies=OWNER)).status_code == 200
    assert (await client.put(url, json={"defaultRole": "EDITOR"}, cookies=OWNER)).status_code == 200
    # the role it already has is no change
    assert (await client.put(url, json={"defaultRole": "EDITOR"}, cookies=OWNER)).status_code == 200

    first, second = await audit_events(workspace, SSO_DEFAULT_ROLE_CHANGED)
    assert (first.role, first.previous_role) == ("REVIEWER", None)
    stored = (await container.workspace_repo().find_by_id(workspace.id)).sso_default_role
    assert (second.role, second.previous_role) == (stored, "REVIEWER")
    clean([first, second])


# -- verified email domains -------------------------------------------------------
async def test_claiming_a_domain_records_the_claim_not_the_name_or_the_token(
    client: AsyncClient, workspace, monkeypatch
):
    with monkeypatch.context() as patched:
        fail_audit(patched)
        # a claim is inert until it is verified: best effort
        reply = await client.post(domains(workspace), json={"domain": "acme.com"}, cookies=OWNER)
        assert reply.status_code == 201, reply.text
    assert await audit_events(workspace, DOMAIN_CLAIMED) == []

    reply = await client.post(domains(workspace), json={"domain": "acme.org"}, cookies=OWNER)
    assert reply.status_code == 201, reply.text
    (entry,) = await audit_events(workspace, DOMAIN_CLAIMED)
    assert (entry.user_id, entry.domain_id) == (testUser.id, reply.json()["id"])
    clean([entry], "acme", reply.json()["txtRecordValue"])


async def test_verifying_a_domain_is_recorded_before_it_is_stored(
    client: AsyncClient, workspace, fake_dns, monkeypatch
):
    claim = (await client.post(domains(workspace), json={"domain": "acme.com"}, cookies=OWNER)).json()
    fake_dns.set_txt(RECORD, "v=spf1 -all", claim["txtRecordValue"])
    url = domains(workspace, claim["id"], "verify")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.post(url, cookies=OWNER))
    assert (await container.workspace_domain_repo().get(claim["id"])).status.value != "verified"

    reply = await client.post(url, cookies=OWNER)
    assert reply.status_code == 200 and reply.json()["status"] == "verified"
    # checking a verified domain again records nothing more
    assert (await client.post(url, cookies=OWNER)).status_code == 200
    (entry,) = await audit_events(workspace, DOMAIN_VERIFIED)
    assert (entry.user_id, entry.domain_id) == (testUser.id, claim["id"])
    clean([entry], "acme", claim["txtRecordValue"])


async def test_a_failed_check_is_not_a_verification(
    client: AsyncClient, workspace, fake_dns
):
    claim = (await client.post(domains(workspace), json={"domain": "acme.com"}, cookies=OWNER)).json()
    reply = await client.post(domains(workspace, claim["id"], "verify"), cookies=OWNER)
    assert reply.status_code == 200 and reply.json()["status"] != "verified"
    assert await audit_events(workspace, DOMAIN_VERIFIED) == []


async def test_removing_a_domain_is_recorded_and_refused_unrecorded(
    client: AsyncClient, workspace, monkeypatch
):
    claim = (await client.post(domains(workspace), json={"domain": "acme.com"}, cookies=OWNER)).json()
    url = domains(workspace, claim["id"])

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.delete(url, cookies=OWNER))
    assert await container.workspace_domain_repo().get(claim["id"]) is not None

    assert (await client.delete(url, cookies=OWNER)).status_code == 204
    (entry,) = await audit_events(workspace, DOMAIN_REMOVED)
    assert entry.domain_id == claim["id"]
    clean([entry], "acme")


# -- directory sync (SCIM) --------------------------------------------------------
async def test_creating_the_directory_records_the_token_creation_without_the_token(
    client: AsyncClient, workspace, scim_on, members_list, monkeypatch
):
    polis, _ = scim_on
    await verify_domain(workspace.id)
    url = scim(workspace, "/directory")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.post(url, json={"type": "okta-scim-v2"}, cookies=OWNER))
    # no token was minted and nothing was stored
    assert polis.directories == {}
    assert await container.scim_directory_repo().find_by_workspace(workspace.id) is None

    reply = await client.post(url, json={"type": "okta-scim-v2"}, cookies=OWNER)
    assert reply.status_code == 201, reply.text
    directory = await container.scim_directory_repo().find_by_workspace(workspace.id)
    (entry,) = await audit_events(workspace, SCIM_TOKEN_CREATED)
    assert (entry.user_id, entry.directory_id, entry.directory_type) == (
        testUser.id,
        str(directory.id),
        "okta-scim-v2",
    )
    body = reply.json()
    assert body["bearerToken"]
    clean([entry], body["bearerToken"], body["scimEndpoint"])


async def test_rotating_the_token_is_recorded_after_and_never_blocked(
    client: AsyncClient, workspace, scim_on, members_list, monkeypatch
):
    polis, _ = scim_on
    directory, _ = await create_directory(client, workspace, OWNER)
    old_polis_id = directory.polis_directory_id
    url = scim(workspace, "/directory/rotate")

    # the audit store is down: rotating is the way to stop a leaked token, so
    # it still works, the old token stops working and the new one is issued
    with monkeypatch.context() as patched:
        fail_audit(patched)
        reply = await client.post(url, cookies=OWNER)
        assert reply.status_code == 200, reply.text
        assert reply.json()["bearerToken"]
    assert old_polis_id not in polis.directories
    stored = await container.scim_directory_repo().get(directory.id)
    assert stored.polis_directory_id != old_polis_id
    assert stored.polis_directory_id in polis.directories
    assert await audit_events(workspace, SCIM_TOKEN_ROTATED) == []

    reply = await client.post(url, cookies=OWNER)
    assert reply.status_code == 200, reply.text
    entries = await audit_events(workspace, SCIM_TOKEN_ROTATED)
    assert [(e.directory_id, e.directory_type) for e in entries] == [
        (str(directory.id), "okta-scim-v2")
    ]
    clean(entries, reply.json()["bearerToken"])


async def test_deleting_the_directory_records_the_revocation_and_refuses_unrecorded(
    client: AsyncClient, workspace, scim_on, members_list, monkeypatch
):
    polis, _ = scim_on
    directory, _ = await create_directory(client, workspace, OWNER)
    url = scim(workspace, "/directory")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.delete(url, cookies=OWNER))
    assert await container.scim_directory_repo().get(directory.id) is not None
    assert directory.polis_directory_id in polis.directories

    assert (await client.delete(url, cookies=OWNER)).status_code == 200
    (entry,) = await audit_events(workspace, SCIM_TOKEN_REVOKED)
    assert (entry.directory_id, entry.directory_type) == (str(directory.id), "okta-scim-v2")
    assert await container.scim_directory_repo().get(directory.id) is None
    clean([entry], directory.polis_directory_id)


async def test_mapping_a_group_to_a_role_records_ids_and_enum_roles(
    client: AsyncClient, workspace, scim_on, members_list, monkeypatch
):
    polis, _ = scim_on
    directory, _ = await create_directory(client, workspace, OWNER)
    await deliver(
        client, directory, polis, event(directory, "group.created", group_data("g-a", "Finance Team"))
    )
    (group,) = (await client.get(scim(workspace), cookies=OWNER)).json()["groups"]
    url = scim(workspace, f"/groups/{group['id']}")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.put(url, json={"role": "REVIEWER"}, cookies=OWNER))
    assert (await client.get(scim(workspace), cookies=OWNER)).json()["groups"][0]["role"] is None

    assert (await client.put(url, json={"role": "REVIEWER"}, cookies=OWNER)).status_code == 200
    # the same role again is no change and no entry
    assert (await client.put(url, json={"role": "REVIEWER"}, cookies=OWNER)).status_code == 200
    assert (await client.put(url, json={"role": "VIEWER"}, cookies=OWNER)).status_code == 200

    first, second = await audit_events(workspace, SCIM_GROUP_ROLE_CHANGED)
    assert (first.directory_group_id, first.role, first.previous_role) == (group["id"], "REVIEWER", None)
    assert (second.role, second.previous_role) == ("VIEWER", "REVIEWER")
    assert first.directory_id == str(directory.id)
    # the group's name is not in the log
    clean([first, second], "finance")


# -- AI consent -------------------------------------------------------------------
@pytest.fixture()
def openai_configured(monkeypatch):
    monkeypatch.setattr(settings.open_ai, "API_KEY", "sk-test")
    monkeypatch.setattr(settings.ai, "DEFAULT_PROVIDER", "openai")


async def test_switching_ai_on_is_recorded_first_and_off_is_best_effort(
    client: AsyncClient, workspace, openai_configured, monkeypatch
):
    url = f"/api/v1/workspaces/{workspace.id}/ai-settings"

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(await client.put(url, json={"enabled": True}, cookies=OWNER))
    assert not (await container.workspace_repo().find_by_id(workspace.id)).ai_enabled

    assert (await client.put(url, json={"enabled": True}, cookies=OWNER)).status_code == 200
    # on again: no change, no entry
    assert (await client.put(url, json={"enabled": True}, cookies=OWNER)).status_code == 200
    (on,) = await audit_events(workspace, AI_CONSENT_CHANGED)
    assert (on.user_id, on.enabled, on.provider) == (testUser.id, True, "openai")

    with monkeypatch.context() as patched:
        fail_audit(patched)
        reply = await client.put(url, json={"enabled": False}, cookies=OWNER)
        assert reply.status_code == 200 and reply.json()["enabled"] is False
    assert len(await audit_events(workspace, AI_CONSENT_CHANGED)) == 1

    assert (await client.put(url, json={"enabled": True}, cookies=OWNER)).status_code == 200
    assert (await client.put(url, json={"enabled": False}, cookies=OWNER)).status_code == 200
    entries = await audit_events(workspace, AI_CONSENT_CHANGED)
    assert [(e.enabled, e.provider) for e in entries] == [
        (True, "openai"),
        (True, "openai"),
        (False, "openai"),
    ]
    clean(entries, "sk-test")


# -- the custom domain -------------------------------------------------------------
async def test_the_custom_domain_is_recorded_best_effort_without_the_hostname(
    client: AsyncClient, workspace_pro, test_pro_user_cookies, monkeypatch
):
    from tests.app.controllers.data import workspace_attribute

    url = f"/api/v1/workspaces/{workspace_pro.id}"
    hostname = workspace_attribute["custom_domain"]

    with monkeypatch.context() as patched:
        fail_audit(patched)
        # the store being down never blocks the workspace's own hostname
        reply = await client.patch(url, cookies=test_pro_user_cookies, data=workspace_attribute)
        assert reply.status_code == 200, reply.text
    assert await audit_events(workspace_pro, CUSTOM_DOMAIN_CHANGED) == []

    # removing the hostname the failed write left: this one is recorded
    reply = await client.delete(f"{url}/custom-domain", cookies=test_pro_user_cookies)
    assert reply.status_code == 200, reply.text
    (removed,) = await audit_events(workspace_pro, CUSTOM_DOMAIN_REMOVED)
    reply = await client.patch(url, cookies=test_pro_user_cookies, data=workspace_attribute)
    assert reply.status_code == 200, reply.text
    (changed,) = await audit_events(workspace_pro, CUSTOM_DOMAIN_CHANGED)
    assert changed.user_id == removed.user_id
    assert changed.workspace_id == workspace_pro.id
    # a delete with no hostname set has nothing to remove and records nothing
    await client.delete(f"{url}/custom-domain", cookies=test_pro_user_cookies)
    await client.delete(f"{url}/custom-domain", cookies=test_pro_user_cookies)
    assert len(await audit_events(workspace_pro, CUSTOM_DOMAIN_REMOVED)) == 2
    clean([changed, removed], hostname)


def test_the_settings_kinds_are_distinct_and_listed():
    assert len(set(SETTINGS_EVENTS)) == len(SETTINGS_EVENTS) == 16
    assert RecordId  # the ids above are record ids


async def test_the_reader_lists_the_new_kinds_in_their_areas_with_only_the_enum_fields(
    client: AsyncClient, workspace, sso_on, monkeypatch
):
    from tests.app.form_access.helpers import api, cookies

    monkeypatch.setattr(settings, "AUDIT_LOG_UI_ENABLED", True)
    connection = await add_connection(workspace.id, enabled=False)
    reply = await client.post(
        sso(workspace, f"/connections/{connection.id}/enable"), cookies=OWNER
    )
    assert reply.status_code == 200, reply.text
    for kind in SETTINGS_EVENTS:
        assert catalog.area_of(kind) == "security", kind
    for kind in AUTOMATION_EVENTS:
        assert catalog.area_of(kind) == "integrations", kind

    page = await client.get(
        f"{api(workspace)}/audit-log", params={"area": "security"}, cookies=cookies(testUser)
    )
    assert page.status_code == 200, page.text
    (entry,) = page.json()["entries"]
    assert (entry["event"], entry["area"], entry["connectionType"]) == (
        SSO_CONNECTION_ENABLED,
        "security",
        "saml",
    )
    # ids with no screen of their own are not returned
    assert "connectionId" not in entry


async def test_enabling_a_connection_records_each_one_it_replaces(
    client: AsyncClient, workspace, sso_on, monkeypatch
):
    first = await add_connection(workspace.id, enabled=True)
    second = await add_connection(workspace.id, enabled=True)
    third = await add_connection(workspace.id, enabled=False)

    reply = await client.post(
        sso(workspace, f"/connections/{third.id}/enable"), cookies=OWNER
    )
    assert reply.status_code == 200, reply.text

    (enabled,) = await audit_events(workspace, SSO_CONNECTION_ENABLED)
    assert enabled.connection_id == str(third.id)
    disabled = await audit_events(workspace, SSO_CONNECTION_DISABLED)
    assert sorted(e.connection_id for e in disabled) == sorted([str(first.id), str(second.id)])
    clean(disabled)


async def test_a_verification_another_workspace_won_is_not_recorded(
    client: AsyncClient, workspace, fake_dns, monkeypatch
):
    from backend.app.repositories.postgres.identity import DomainVerifiedElsewhere

    claim = (await client.post(domains(workspace), json={"domain": "acme.com"}, cookies=OWNER)).json()
    fake_dns.set_txt(RECORD, "v=spf1 -all", claim["txtRecordValue"])

    repo = container.workspace_domain_repo()
    save = repo.save

    async def lost_the_race(document):
        if document.status.value == "verified":
            raise DomainVerifiedElsewhere()
        return await save(document)

    monkeypatch.setattr(repo, "save", lost_the_race)
    reply = await client.post(domains(workspace, claim["id"], "verify"), cookies=OWNER)
    assert reply.status_code == 200, reply.text
    assert reply.json()["status"] != "verified"
    assert await audit_events(workspace, DOMAIN_VERIFIED) == []


async def _claim_with_a_stale_value(client, workspace, fake_dns):
    claim = (await client.post(domains(workspace), json={"domain": "acme.com"}, cookies=OWNER)).json()
    fake_dns.set_txt(RECORD, "v=spf1 -all", claim["txtRecordValue"])
    repo = container.workspace_domain_repo()
    document = await repo.get(claim["id"])
    # a value the claim held before (not verified): it has to come back
    document.verified_domain = "previous.example"
    await repo.save(document)
    return claim, repo


async def test_a_refused_verification_puts_back_the_previous_values(
    client: AsyncClient, workspace, fake_dns, monkeypatch
):
    claim, repo = await _claim_with_a_stale_value(client, workspace, fake_dns)

    with monkeypatch.context() as patched:
        fail_audit(patched)
        refused_unrecorded(
            await client.post(domains(workspace, claim["id"], "verify"), cookies=OWNER)
        )
    stored = await repo.get(claim["id"])
    assert stored.status.value != "verified"
    assert stored.verified_domain == "previous.example"
    assert stored.verified_at is None and stored.verified_by is None


async def test_a_take_back_that_fails_is_logged_with_ids_only(
    client: AsyncClient, workspace, fake_dns, monkeypatch
):
    from loguru import logger

    claim, repo = await _claim_with_a_stale_value(client, workspace, fake_dns)
    save = repo.save
    calls = []

    async def fails_the_second_save(document):
        calls.append(document.status.value)
        if len(calls) >= 2:
            raise RuntimeError("store down acme.com")
        return await save(document)

    lines = []
    handler = logger.add(lambda message: lines.append(str(message)), level="ERROR")
    try:
        with monkeypatch.context() as patched:
            fail_audit(patched)
            patched.setattr(repo, "save", fails_the_second_save)
            refused_unrecorded(
                await client.post(domains(workspace, claim["id"], "verify"), cookies=OWNER)
            )
    finally:
        logger.remove(handler)
    text = " ".join(lines)
    assert "NOT TAKEN BACK" in text and claim["id"] in text
    # ids and the error's type only: not its message, not the domain
    assert "acme.com" not in text and "store down" not in text
