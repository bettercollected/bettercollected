"""Registration configuration: secrets are write-only and sealed, addresses are
checked, a form can only use its own workspace's service, only what is mapped
can be chosen, and the respondent's form names the destination."""

import json

import pytest
from httpx import AsyncClient
from loguru import logger

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.registration import client
from backend.app.services.registration.secrets import SecretUnreadable, unseal
from backend.app.services.registration.service import (
    FormRegistrationUpdateDto,
    ServiceCreateDto,
    ServiceUpdateDto,
    VariableMappingDto,
)
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.registration.helpers import configure, make_service, publish
from tests.app.registration.tls_server import PUBLIC_ADDRESS

pytestmark = pytest.mark.asyncio

SECRET = "Token s3cret-value"


@pytest.fixture()
def logs():
    lines = []
    handler = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    yield lines
    logger.remove(handler)


@pytest.fixture(autouse=True)
def public_dns(monkeypatch, registration_on):
    async def resolve(host, port=443):
        return [PUBLIC_ADDRESS]

    monkeypatch.setattr(client, "resolve", resolve)


def service():
    return container.registration_service()


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def code_of(error: HTTPException) -> str:
    content = error.content
    return content["code"] if isinstance(content, dict) else str(content)


async def test_the_secret_is_sealed_write_only_and_never_logged(workspace, logs):
    created = await make_service(workspace)
    dump = created.model_dump_json(by_alias=True)
    assert SECRET not in dump and "secret" not in json.loads(dump).keys()
    assert created.has_secret and created.secret_set_at
    listed = await service().list_services(workspace.id, testUser)
    assert SECRET not in json.dumps([s.model_dump(mode="json") for s in listed])
    row = await container.registration_service_repo().get(workspace.id, created.id)
    assert SECRET not in json.dumps(row.model_dump(mode="json")) and row.secret_sealed
    # sealed for this workspace and service: it opens only for them
    crypto = container.crypto()
    assert unseal(crypto, workspace.id, created.id, row.secret_sealed) == SECRET
    with pytest.raises(SecretUnreadable):
        unseal(crypto, workspace.id, "another-service", row.secret_sealed)
    with pytest.raises(SecretUnreadable):
        unseal(crypto, "another-workspace", created.id, row.secret_sealed)
    with pytest.raises(SecretUnreadable):
        unseal(crypto, workspace.id, created.id, "not a ciphertext")
    assert not any(SECRET in line for line in logs)
    # the request model does not print it either
    assert SECRET not in repr(
        ServiceCreateDto(
            name="n",
            base_url="https://case.example.org/",
            auth="header",
            auth_name="X",
            secret=SECRET,
        )
    )


async def test_update_keeps_the_secret_unless_the_target_moves(workspace):
    created = await make_service(workspace)
    renamed = await service().update_service(
        workspace.id,
        created.id,
        ServiceUpdateDto(name="New name", organisation_name="Org B"),
        testUser,
    )
    assert (
        renamed.name == "New name"
        and renamed.organisation_name == "Org B"
        and renamed.has_secret
    )
    row = await container.registration_service_repo().get(workspace.id, created.id)
    assert (
        unseal(container.crypto(), workspace.id, created.id, row.secret_sealed)
        == SECRET
    )

    for change in (
        ServiceUpdateDto(base_url="https://elsewhere.example.org/"),
        ServiceUpdateDto(auth_name="X-Other"),
    ):
        error = await refused(
            service().update_service(workspace.id, created.id, change, testUser)
        )
        assert error.status_code == 422 and code_of(error) == "secret_required"
    moved = await service().update_service(
        workspace.id,
        created.id,
        ServiceUpdateDto(base_url="https://elsewhere.example.org/", secret="Token new"),
        testUser,
    )
    assert moved.base_url == "https://elsewhere.example.org/"
    row = await container.registration_service_repo().get(workspace.id, created.id)
    assert (
        unseal(container.crypto(), workspace.id, created.id, row.secret_sealed)
        == "Token new"
    )
    # dropping authentication drops the stored secret
    open_service = await service().update_service(
        workspace.id, created.id, ServiceUpdateDto(auth="none"), testUser
    )
    assert not open_service.has_secret
    row = await container.registration_service_repo().get(workspace.id, created.id)
    assert row.secret_sealed is None


@pytest.mark.parametrize(
    "url,code",
    [
        ("http://case.example.org/", "invalid_url"),
        ("https://case.example.org:8443/", "invalid_url"),
        ("https://user:pw@case.example.org/", "invalid_url"),
        ("https://case.example.org/?token=1", "invalid_url"),
        ("ftp://case.example.org/", "invalid_url"),
        ("not a url", "invalid_url"),
    ],
)
async def test_addresses_must_be_plain_https(workspace, url, code):
    error = await refused(make_service(workspace, base_url=url))
    assert error.status_code == 422 and code_of(error) == code


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "::ffff:10.0.0.1", "fd00::1"],
)
async def test_a_name_that_resolves_inward_is_refused_when_saved(
    workspace, monkeypatch, address
):
    async def resolve(host, port=443):
        return [PUBLIC_ADDRESS, address]

    monkeypatch.setattr(client, "resolve", resolve)
    error = await refused(make_service(workspace))
    assert error.status_code == 422 and code_of(error) == "not_allowed"


async def test_a_name_that_does_not_resolve_is_refused_when_saved(
    workspace, monkeypatch
):
    async def resolve(host, port=443):
        raise OSError("nope")

    monkeypatch.setattr(client, "resolve", resolve)
    assert code_of(await refused(make_service(workspace))) == "unreachable"


@pytest.mark.parametrize(
    "kwargs,code",
    [
        (dict(auth="header", auth_name=None, secret="x"), "invalid_auth_name"),
        (dict(auth="header", auth_name="Bad Name", secret="x"), "invalid_auth_name"),
        (
            dict(auth="header", auth_name="X-Key", secret="a\r\nEvil: 1"),
            "invalid_secret",
        ),
        (dict(auth="header", auth_name="X-Key", secret=None), "secret_required"),
        (dict(auth="basic", auth_name=None, secret="x"), "invalid_auth_name"),
    ],
)
async def test_authentication_is_checked(workspace, kwargs, code):
    error = await refused(make_service(workspace, **kwargs))
    assert error.status_code == 422 and code_of(error) == code


async def test_names_are_unique_per_workspace_and_services_in_use_stay(
    workspace, workspace_1
):
    first = await make_service(workspace)
    assert code_of(await refused(make_service(workspace))) == "name_taken"
    await make_service(workspace_1, user=testUser1)  # the same name elsewhere is fine
    form = await publish(workspace)
    await configure(workspace, form, first, ["name"])
    error = await refused(service().delete_service(workspace.id, first.id, testUser))
    assert error.status_code == 409 and code_of(error) == "service_in_use"
    await configure(
        workspace, form, None, [], enabled=False
    )  # no longer used? still referenced by id only if set
    await service().delete_service(workspace.id, first.id, testUser)
    assert await service().list_services(workspace.id, testUser) == []


async def test_a_form_cannot_use_another_workspaces_service(workspace, workspace_1):
    foreign = await make_service(workspace_1, user=testUser1)
    form = await publish(workspace)
    error = await refused(configure(workspace, form, foreign, ["name"]))
    assert error.status_code == 404 and code_of(error) == "service_not_found"
    # nor can its service be read, tested, changed or deleted through this workspace
    for call in (
        service().update_service(
            workspace.id, foreign.id, ServiceUpdateDto(name="x"), testUser
        ),
        service().test_service(workspace.id, foreign.id, testUser),
        service().delete_service(workspace.id, foreign.id, testUser),
    ):
        assert (await refused(call)).status_code == 404
    assert (
        await container.form_registration_repo().get_for_form(
            workspace.id, form.form_id
        )
        is None
    )


async def test_a_form_of_another_workspace_cannot_be_configured(workspace, workspace_1):
    mine = await make_service(workspace)
    theirs = await publish(workspace_1, user=testUser1)
    request = FormRegistrationUpdateDto(
        enabled=True, service_id=mine.id, variables=[VariableMappingDto(source="name")]
    )
    for call in (
        service().put_form_registration(
            workspace.id, theirs.form_id, request, testUser
        ),
        service().list_variables(workspace.id, theirs.form_id, testUser),
        service().get_form_registration(workspace.id, theirs.form_id, testUser),
    ):
        assert (await refused(call)).status_code == 404


@pytest.mark.parametrize(
    "variables,kwargs,code",
    [
        (["nope"], {}, "unknown_variable"),
        (
            ["people.pname"],
            {},
            "unknown_variable",
        ),  # items are reached through the group
        (["intro"], {}, "variable_not_supported"),
        ([], {}, "variables_required"),
        ([VariableMappingDto(source="name", key="a b")], {}, "invalid_key"),
        (
            [
                VariableMappingDto(source="name", key="k"),
                VariableMappingDto(source="age", key="k"),
            ],
            {},
            "invalid_key",
        ),
        (["name"], dict(transform_to_list=["name"]), "invalid_transform"),
        (["name"], dict(path="../x"), "invalid_path"),
        (["name"], dict(path="https://evil.example.org/"), "invalid_path"),
    ],
)
async def test_the_choice_of_variables_is_checked(workspace, variables, kwargs, code):
    form = await publish(workspace)
    created = await make_service(workspace)
    error = await refused(configure(workspace, form, created, variables, **kwargs))
    assert error.status_code == 422 and code_of(error) == code


async def test_enabling_needs_a_service(workspace):
    form = await publish(workspace)
    error = await refused(configure(workspace, form, None, ["name"]))
    assert code_of(error) == "service_required"


async def test_internal_fields_cannot_be_sent(workspace):
    form = await publish(
        workspace,
        fields=[
            {"id": "name", "type": "short_text", "title": "Name"},
            {
                "id": "staff",
                "type": "short_text",
                "title": "Staff note",
                "internal": True,
            },
        ],
    )
    created = await make_service(workspace)
    assert (
        code_of(await refused(configure(workspace, form, created, ["staff"])))
        == "unknown_variable"
    )
    variables = await service().list_variables(workspace.id, form.form_id, testUser)
    assert [v.source for v in variables] == ["name"]


async def test_the_variables_list_says_what_can_be_sent(workspace):
    form = await publish(workspace, hidden=["utm_source"])
    variables = {
        v.source: v
        for v in await service().list_variables(workspace.id, form.form_id, testUser)
    }
    assert variables["name"].supported and variables["people"].type == "group"
    assert (
        not variables["intro"].supported
        and variables["intro"].reason == "not_an_answer"
    )
    assert variables["utm_source"].supported and "people.pname" not in variables


async def test_the_respondents_form_names_the_destination(
    client: AsyncClient, workspace, monkeypatch
):
    form = await publish(workspace)
    created = await make_service(workspace, organisation_name="Example Org")
    await configure(workspace, form, created, ["name"])

    async def payload(key=None):
        response = await client.get(
            f"/api/v1/workspaces/{workspace.id}/forms/{key or form.form_id}",
            params={"published": True},
        )
        assert response.status_code == 200, response.text
        return response.json()

    assert (await payload())["registrationDestination"] == {
        "organisation": "Example Org"
    }
    # by the form's custom address as well
    workspace_form = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    slug = workspace_form.settings.custom_url
    assert (await payload(slug))["registrationDestination"] == {
        "organisation": "Example Org"
    }
    # nothing named when the registration is off for the form ...
    await configure(workspace, form, created, ["name"], enabled=False)
    assert not (await payload()).get("registrationDestination")
    # ... or the switch is off
    await configure(workspace, form, created, ["name"], enabled=True)
    monkeypatch.setattr(settings.registration, "REGISTRATION", "off")
    assert not (await payload()).get("registrationDestination")


async def test_the_service_test_sends_a_marked_body_and_reports_a_code_only(
    workspace, tls
):
    created = await make_service(workspace)
    result = await service().test_service(workspace.id, created.id, testUser)
    assert result.ok and result.http_status == 200
    (request,) = tls.requests
    assert json.loads(request.body)["metadata"] == {"test": True}
    tls.script.answers = [(500, {}, b"the destination's words")]
    failed = await service().test_service(workspace.id, created.id, testUser)
    assert (failed.ok, failed.code, failed.http_status) == (False, "http_5xx", 500)
    assert "words" not in failed.model_dump_json()


async def test_no_endpoint_response_carries_the_secret(
    client: AsyncClient, workspace, tls, logs
):
    cookies = _cookies(testUser)
    base = f"/api/v1/workspaces/{workspace.id}/registration"
    created = await client.post(
        f"{base}/services",
        cookies=cookies,
        json={
            "name": "Via API",
            "baseUrl": "https://case.example.org/api/",
            "auth": "header",
            "authName": "Authorization",
            "secret": SECRET,
        },
    )
    assert created.status_code == 201, created.text
    service_id = created.json()["id"]
    texts = [created.text]
    texts.append((await client.get(f"{base}/services", cookies=cookies)).text)
    texts.append(
        (
            await client.patch(
                f"{base}/services/{service_id}",
                cookies=cookies,
                json={"name": "Renamed"},
            )
        ).text
    )
    texts.append(
        (await client.post(f"{base}/services/{service_id}/test", cookies=cookies)).text
    )
    assert created.json()["hasSecret"] is True
    for text in texts:
        assert (
            SECRET not in text
            and "secretSealed" not in text
            and "secret_sealed" not in text
        )
    assert not any(SECRET in line for line in logs)
    # a body that sends the stored secret nowhere: the request carried it, the server got it once
    assert tls.requests[0].headers["authorization"] == SECRET


async def test_deleting_a_workspace_deletes_its_services_registrations_and_deliveries(
    workspace,
):
    form = await publish(workspace)
    created = await make_service(workspace)
    await configure(workspace, form, created, ["name"])
    await service().delete_for_workspaces([workspace.id])
    assert (
        await container.registration_service_repo().list_by_workspace(workspace.id)
        == []
    )
    assert (
        await container.form_registration_repo().get_for_form(
            workspace.id, form.form_id
        )
        is None
    )
