"""Registration in an Objects API: configuration (a token only, an object types
address that fences the form's object type URL, target paths), the record we
create, and the duplicate guard: a retry looks for the object before sending
and never takes an object it cannot show to be its own for delivered. A fake
Objects API on a local https server with a test CA stands in for the real one
(``objects_fake.py``); the manual run against the real images is in the PR."""

import datetime as dt
import json
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

import pytest
from loguru import logger

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.registration import DeliveryStatus
from backend.app.services.registration import client, objects_api
from backend.app.services.registration.service import (
    FormRegistrationUpdateDto,
    ServiceCreateDto,
    ServiceUpdateDto,
    VariableMappingDto,
)
from backend.app.services.registration.secrets import unseal
from tests.app.controllers.data import testUser
from tests.app.registration.helpers import ANSWERS, publish, submit
from tests.app.registration.objects_fake import TOKEN, TYPE_URL, FakeObjectsApi

pytestmark = pytest.mark.asyncio

PERSONAL = ["Ada Example", "ada@example.test", "Synthetic story.", "1990-01-02"]
OBJECTS_BASE = "https://case.example.org/api/v2/"
TYPES_BASE = "https://types.example.org/api/v2/"
MAPPING = [
    ("name", ["person", "name"]),
    ("age", ["person", "age"]),
    ("colours", ["colours"]),
    ("born", ["birth"]),
    ("people", ["people"]),
]


@pytest.fixture()
def logs():
    lines = []
    handler = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    yield lines
    logger.remove(handler)


def svc():
    return container.registration_service()


async def refused(awaitable) -> str:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    content = raised.value.content
    return content["code"] if isinstance(content, dict) else str(content)


async def make_objects_service(workspace, user=testUser, **overrides):
    values = dict(
        name="Objects",
        kind="objects_api",
        base_url=OBJECTS_BASE,
        objecttypes_base_url=TYPES_BASE,
        secret=TOKEN,
        organisation_name="Example Org",
    )
    values.update(overrides)
    return await svc().create_service(workspace.id, ServiceCreateDto(**values), user)


async def configure_objects(
    workspace, form, service, mapping=MAPPING, user=testUser, **kwargs
):
    values = dict(
        enabled=True,
        service_id=service.id,
        variables=[VariableMappingDto(source=s, target_path=p) for s, p in mapping],
        object_type_url=TYPE_URL,
        object_type_version=3,
    )
    values.update(kwargs)
    return await svc().put_form_registration(
        workspace.id, form.form_id, FormRegistrationUpdateDto(**values), user
    )


@pytest.fixture()
async def setup(workspace, registration_on, memory_jobs, tls):
    fake = FakeObjectsApi()
    tls.handler = fake.handle
    form = await publish(workspace)
    service = await make_objects_service(workspace)
    await configure_objects(workspace, form, service)
    return SimpleNamespace(
        workspace=workspace, form=form, service=service, fake=fake, tls=tls
    )


async def delivery_of(setup, response):
    rows = await container.registration_delivery_repo().many()
    (row,) = [r for r in rows if r.response_id == response.response_id]
    return row


async def row_of(delivery):
    return await container.registration_delivery_repo().get(delivery.id)


async def run(delivery, attempt=0):
    return await svc().run_delivery(str(delivery.id), job_attempt=attempt)


def methods(setup):
    return [r.method for r in setup.tls.requests]


async def first_attempt_fails_with_503(setup):
    """The first attempt got nothing created (a 503): the next one looks first."""
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.fake.canned["POST"] = (503, {}, b"down")
    out = await run(delivery, 0)
    assert out.status == "retrying" and setup.fake.created == 0
    setup.fake.canned["POST"] = None
    return response, delivery


# ------------------------------------------------------------ the services


async def test_an_objects_service_takes_a_token_only_and_two_addresses(
    workspace, registration_on, tls, monkeypatch, logs
):
    created = await make_objects_service(workspace)
    assert created.kind == "objects_api" and created.auth == "token"
    assert created.objecttypes_base_url == TYPES_BASE and created.has_secret
    dump = created.model_dump_json(by_alias=True)
    assert TOKEN not in dump
    row = await container.registration_service_repo().get(workspace.id, created.id)
    assert TOKEN not in json.dumps(row.model_dump(mode="json"))
    assert (
        unseal(container.crypto(), workspace.id, created.id, row.secret_sealed) == TOKEN
    )
    assert not any(TOKEN in line for line in logs)
    for auth in ("none", "basic", "header"):
        code = await refused(
            make_objects_service(workspace, name=f"x-{auth}", auth=auth, auth_name="u")
        )
        assert code == "invalid_auth", auth
    assert await refused(make_objects_service(workspace, name="a", secret=None)) in (
        "secret_required",
    )
    assert (
        await refused(
            make_objects_service(workspace, name="b", objecttypes_base_url=None)
        )
        == "objecttypes_base_required"
    )
    for secret in ("two words", "with\nnewline", "tökén"):
        assert (
            await refused(make_objects_service(workspace, name="c", secret=secret))
            == "invalid_secret"
        )
    for bad in (
        "http://types.example.org/",
        "https://types.example.org:8443/",
        "https://user:pw@types.example.org/",
        "https://types.example.org/?q=1",
    ):
        assert (
            await refused(
                make_objects_service(workspace, name="d", objecttypes_base_url=bad)
            )
            == "invalid_url"
        ), bad

    async def private(host, port=443):
        return ["10.0.0.7"]

    monkeypatch.setattr(client, "resolve", private)
    assert await refused(make_objects_service(workspace, name="e")) == "not_allowed"


async def test_the_object_types_address_is_checked_like_the_objects_address(
    workspace, registration_on, tls, monkeypatch
):
    async def private(host, port=443):
        return ["169.254.169.254"] if host.startswith("types") else ["93.184.216.34"]

    monkeypatch.setattr(client, "resolve", private)
    assert await refused(make_objects_service(workspace)) == "not_allowed"


async def test_kinds_do_not_mix(workspace, registration_on, tls):
    assert (
        await refused(
            svc().create_service(
                workspace.id,
                ServiceCreateDto(
                    name="g", base_url=OBJECTS_BASE, objecttypes_base_url=TYPES_BASE
                ),
                testUser,
            )
        )
        == "objecttypes_base_not_applicable"
    )
    assert (
        await refused(
            svc().create_service(
                workspace.id,
                ServiceCreateDto(
                    name="g", base_url=OBJECTS_BASE, auth="token", secret="abc"
                ),
                testUser,
            )
        )
        == "invalid_auth"
    )


async def test_changing_the_objects_address_needs_the_token_again(
    workspace, registration_on, tls
):
    service = await make_objects_service(workspace)
    code = await refused(
        svc().update_service(
            workspace.id,
            service.id,
            ServiceUpdateDto(base_url="https://other.example.org/api/v2/"),
            testUser,
        )
    )
    assert code == "secret_required"
    # the object types address is never connected to: no token needed
    updated = await svc().update_service(
        workspace.id,
        service.id,
        ServiceUpdateDto(objecttypes_base_url="https://types2.example.org/api/"),
        testUser,
    )
    assert updated.objecttypes_base_url == "https://types2.example.org/api/"
    assert (
        await refused(
            svc().update_service(
                workspace.id, service.id, ServiceUpdateDto(auth="basic"), testUser
            )
        )
        == "invalid_auth"
    )


async def test_testing_an_objects_service_sends_nothing(setup):
    result = await svc().test_service(setup.workspace.id, setup.service.id, testUser)
    assert (result.ok, result.code) == (False, "use_form_check")
    assert setup.tls.requests == []


# ----------------------------------------------------- the form's settings

UUID = "3f5e8a10-0b1c-4d2e-9a3b-5c6d7e8f9a0b"


@pytest.mark.parametrize(
    "url, code",
    [
        (
            f"https://types.example.org.evil.test/api/v2/objecttypes/{UUID}",
            "object_type_outside_base",
        ),
        (
            f"https://types.example.org@evil.test/api/v2/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://evil.test@types.example.org/api/v2/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://user:pw@types.example.org/api/v2/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org\\@evil.test/api/v2/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2/../x/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2/./objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2/%2e%2e/x/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2/..%2fx/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2/%2E%2E%2Fobjecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2//objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2;x/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2x/objecttypes/{UUID}",
            "object_type_outside_base",
        ),
        (
            f"https://types.example.org/api/objecttypes/{UUID}",
            "object_type_outside_base",
        ),
        (
            f"https://other.example.org/api/v2/objecttypes/{UUID}",
            "object_type_outside_base",
        ),
        (
            f"http://types.example.org/api/v2/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org:8443/api/v2/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2/objecttypes/{UUID}?x=1",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2/objecttypes/{UUID}#frag",
            "invalid_object_type_url",
        ),
        (
            "https://types.example.org/api/v2/objecttypes/not-a-uuid",
            "invalid_object_type_url",
        ),
        ("https://types.example.org/api/v2/", "invalid_object_type_url"),
        (
            f"https://tyрes.example.org/api/v2/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f"https://types.example.org/api/v2/{'a' * 1000}/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        (
            f" https://types.example.org/ api/v2/objecttypes/{UUID}",
            "invalid_object_type_url",
        ),
        ("", "object_type_required"),
    ],
)
async def test_an_object_type_url_outside_the_base_is_refused(setup, url, code):
    assert (
        await refused(
            configure_objects(
                setup.workspace, setup.form, setup.service, object_type_url=url
            )
        )
        == code
    )
    # the stored settings are untouched by a refused save
    kept = await svc().get_form_registration(
        setup.workspace.id, setup.form.form_id, testUser
    )
    assert kept.object_type_url == TYPE_URL


async def test_an_object_type_url_is_stored_normalised(setup):
    saved = await configure_objects(
        setup.workspace,
        setup.form,
        setup.service,
        object_type_url=f"https://TYPES.Example.org:443/api/v2/objecttypes/{UUID}",
    )
    assert saved.object_type_url == TYPE_URL


@pytest.mark.parametrize(
    "version, ok", [(0, False), (-1, False), (1, True), (10000, True), (10001, False)]
)
async def test_the_object_type_version_is_one_to_ten_thousand(setup, version, ok):
    attempt = configure_objects(
        setup.workspace, setup.form, setup.service, object_type_version=version
    )
    if ok:
        assert (await attempt).object_type_version == version
    else:
        assert await refused(attempt) == "invalid_object_type_version"


async def test_an_enabled_form_needs_its_object_type(setup):
    for missing in (dict(object_type_url=""), dict(object_type_version=None)):
        assert (
            await refused(
                configure_objects(setup.workspace, setup.form, setup.service, **missing)
            )
            == "object_type_required"
        )
    saved = await configure_objects(
        setup.workspace,
        setup.form,
        setup.service,
        enabled=False,
        object_type_url="",
        object_type_version=None,
    )
    assert not saved.enabled


@pytest.mark.parametrize(
    "path",
    [
        None,
        [],
        ["a"] * 9,
        ["1a"],
        ["_a"],
        ["a__b"],
        ["a_"],
        ["a-b"],
        ["a b"],
        ["a.b"],
        ["a" * 65],
        [""],
        ["ä"],
        ["a\n"],
        ["ok\n"],
        ["ok", "a\n"],
        ["ok", "a__b"],
    ],
)
async def test_a_target_path_has_one_to_eight_plain_names(setup, path):
    mapping = [("name", path)]
    assert (
        await refused(
            configure_objects(setup.workspace, setup.form, setup.service, mapping)
        )
        == "invalid_target_path"
    )


async def test_target_paths_are_unique_and_none_sits_inside_another(setup):
    for mapping in (
        [("name", ["a"]), ("age", ["a"])],
        [("name", ["a"]), ("age", ["a", "b"])],
        [("name", ["a", "b"]), ("age", ["a"])],
        [("name", ["a", "b"]), ("age", ["a", "b", "c"])],
    ):
        assert (
            await refused(
                configure_objects(setup.workspace, setup.form, setup.service, mapping)
            )
            == "target_path_conflict"
        ), mapping
    ok = await configure_objects(
        setup.workspace,
        setup.form,
        setup.service,
        [("name", ["a", "b"]), ("age", ["a", "c"]), ("born", ["a_b"])],
    )
    assert len(ok.variables) == 3


async def test_the_reference_path_follows_the_same_rules(setup):
    for path in ([], ["a__b"], ["1"], ["a"] * 9, ["x_"], ["a\n"]):
        assert (
            await refused(
                configure_objects(
                    setup.workspace, setup.form, setup.service, reference_path=path
                )
            )
            == "invalid_reference_path"
        ), path
    for path in (
        ["person"],
        ["person", "name"],
        ["person", "name", "deeper"],
        ["colours"],
    ):
        assert (
            await refused(
                configure_objects(
                    setup.workspace, setup.form, setup.service, reference_path=path
                )
            )
            == "reference_path_conflict"
        ), path
    saved = await configure_objects(
        setup.workspace, setup.form, setup.service, reference_path=["meta", "ref"]
    )
    assert saved.reference_path == ["meta", "ref"]
    default = await configure_objects(setup.workspace, setup.form, setup.service)
    assert default.reference_path == ["bettercollected_reference"]


async def test_a_file_question_cannot_be_mapped(setup):
    code = await refused(
        configure_objects(
            setup.workspace, setup.form, setup.service, [("upload", ["document"])]
        )
    )
    assert code == "variable_not_supported"
    assert (
        await refused(
            configure_objects(
                setup.workspace, setup.form, setup.service, [("nope", ["x"])]
            )
        )
        == "unknown_variable"
    )


async def test_settings_of_the_wrong_kind_are_refused(setup):
    generic = await svc().create_service(
        setup.workspace.id,
        ServiceCreateDto(name="Plain", base_url=OBJECTS_BASE, auth="none"),
        testUser,
    )
    code = await refused(
        svc().put_form_registration(
            setup.workspace.id,
            setup.form.form_id,
            FormRegistrationUpdateDto(
                enabled=True,
                service_id=generic.id,
                variables=[VariableMappingDto(source="name")],
                object_type_url=TYPE_URL,
            ),
            testUser,
        )
    )
    assert code == "not_an_objects_api"
    assert (
        await refused(
            configure_objects(setup.workspace, setup.form, setup.service, path="x")
        )
        == "invalid_path"
    )
    assert (
        await refused(
            configure_objects(
                setup.workspace,
                setup.form,
                setup.service,
                transform_to_list=["colours"],
            )
        )
        == "invalid_transform"
    )


async def test_the_form_reads_back_without_the_old_generic_fields(setup):
    got = await svc().get_form_registration(
        setup.workspace.id, setup.form.form_id, testUser
    )
    assert got.kind == "objects_api" and got.object_type_version == 3
    assert (
        got.variables[0].target_path == ["person", "name"]
        and got.variables[0].key is None
    )


# ----------------------------------------------------- the record we create


def test_the_start_date_is_the_amsterdam_date_all_year():
    zone = ZoneInfo("Europe/Amsterdam")
    start = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    for minutes in range(0, 60 * 24 * 366 * 3, 37):
        moment = start + dt.timedelta(minutes=minutes)
        assert (
            objects_api.amsterdam_date(moment)
            == moment.astimezone(zone).date().isoformat()
        )
    # the two nights of the change, and the hours UTC would get wrong
    cases = {
        dt.datetime(2026, 3, 29, 0, 59, tzinfo=dt.timezone.utc): "2026-03-29",
        dt.datetime(2026, 3, 29, 22, 30, tzinfo=dt.timezone.utc): "2026-03-30",
        dt.datetime(2026, 7, 1, 22, 30, tzinfo=dt.timezone.utc): "2026-07-02",
        dt.datetime(2026, 12, 31, 23, 30, tzinfo=dt.timezone.utc): "2027-01-01",
        dt.datetime(2026, 10, 25, 22, 30, tzinfo=dt.timezone.utc): "2026-10-25",
        dt.datetime(2026, 10, 25, 23, 30, tzinfo=dt.timezone.utc): "2026-10-26",
    }
    for moment, expected in cases.items():
        assert objects_api.amsterdam_date(moment) == expected
    assert objects_api.amsterdam_date(dt.datetime(2026, 7, 1, 21, 59)) == "2026-07-01"


async def test_the_object_is_created_with_the_mapped_answers_only(setup, logs):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    out = await run(delivery)
    assert out.status == "delivered"
    (request,) = setup.tls.requests  # the first attempt does not look
    assert request.method == "POST" and request.target == "/api/v2/objects"
    assert request.headers["authorization"] == f"Token {TOKEN}"
    assert request.headers["content-crs"] == "EPSG:4326"
    assert request.headers["content-type"] == "application/json"
    sent = json.loads(request.body)
    assert list(sent) == ["type", "record"] and sent["type"] == TYPE_URL
    record = sent["record"]
    assert set(record) == {"typeVersion", "data", "startAt"}  # never geometry
    assert record["typeVersion"] == 3
    assert record["startAt"] == await start_date_of(setup, response)
    data = record["data"]
    reference = objects_api.reference_for(delivery.id)
    assert data["bettercollected_reference"] == reference
    assert data["person"] == {"name": "Ada Example", "age": 36}
    assert data["colours"] == ["Red", "Blue"] and data["birth"] == "1990-01-02"
    assert (
        data["people"][0] == {"pname": "Bo", "pyears": 3} and len(data["people"]) == 2
    )
    assert set(data) == {
        "person",
        "colours",
        "birth",
        "people",
        "bettercollected_reference",
    }
    for text in ("Synthetic story.", "ada@example.test"):
        assert text.encode() not in request.body  # not mapped, not sent
    # what we keep: ids, status, counts and the object's UUID
    done = await row_of(delivery)
    assert done.status is DeliveryStatus.DELIVERED and done.last_http_status == 201
    assert done.remote_id == setup.fake.objects[0]["uuid"]
    stored = json.dumps(done.model_dump(mode="json"))
    for text in PERSONAL + [TOKEN]:
        assert text not in stored
    # the settings of the first send are kept (configuration, no answers)
    assert done.objects_snapshot.object_type_url == TYPE_URL
    assert done.objects_snapshot.reference_path == ["bettercollected_reference"]
    assert done.objects_snapshot.service_host == "case.example.org"
    for text in PERSONAL + [TOKEN, TYPE_URL]:
        assert not any(text in line for line in logs), text
    assert (await run(delivery)).status == "skipped" and len(setup.fake.objects) == 1


async def start_date_of(setup, response):
    """What startAt must be: the stored submission time in Amsterdam."""
    stored = await container.form_response_service().workspace_response(
        setup.workspace.id, response.response_id
    )
    return objects_api.amsterdam_date(stored.created_at)


async def test_a_multiple_choice_is_a_list_and_unanswered_questions_are_left_out(setup):
    answers = {k: v for k, v in ANSWERS.items() if k not in ("age", "born")}
    response = await submit(setup.workspace, setup.form, answers)
    delivery = await delivery_of(setup, response)
    assert (await run(delivery)).status == "delivered"
    data = json.loads(setup.tls.requests[0].body)["record"]["data"]
    assert data["person"] == {"name": "Ada Example"} and "birth" not in data


async def test_a_reply_we_cannot_read_still_counts_as_delivered(setup):
    # the object was created: a lost UUID is not a lost submission
    for index, reply in enumerate(
        [
            b"<html>not json</html>",
            b'{"uuid": "nope"}',
            b'{"uuid": "%s\\n"}' % UUID.encode(),
            b'{"uuid": ["%s"]}' % UUID.encode(),
            b"[]",
            b"x" * (70 * 1024),
        ]
    ):
        response = await submit(setup.workspace, setup.form)
        delivery = await delivery_of(setup, response)
        setup.fake.canned["POST"] = (201, {}, reply)
        out = await run(delivery)
        row = await row_of(delivery)
        assert out.status == "delivered", index
        assert row.status is DeliveryStatus.DELIVERED and row.remote_id is None, index
        await container.registration_delivery_repo().delete_by_response_id(
            response.response_id
        )


async def test_a_schema_error_is_permanent_and_nothing_is_retried(setup):
    setup.fake.required = ["a_field_the_form_does_not_send"]
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    out = await run(delivery)
    row = await row_of(delivery)
    assert (out.status, out.retry) == ("failed", False)
    assert row.last_error_code == "http_4xx" and row.last_http_status == 400
    assert methods(setup) == ["POST"] and setup.fake.created == 0


async def test_5xx_retries_and_the_next_attempt_looks_before_sending(setup):
    response, delivery = await first_attempt_fails_with_503(setup)
    row = await row_of(delivery)
    assert row.status is DeliveryStatus.RETRYING and row.last_error_code == "http_5xx"
    out = await run(delivery, 1)
    assert out.status == "delivered"
    assert methods(setup) == ["POST", "GET", "POST"] and setup.fake.created == 1


# ------------------------------------------------------ no duplicate objects


async def test_a_lost_reply_then_a_retry_that_finds_the_object_creates_nothing(setup):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.fake.drop_reply_next = 1
    out = await run(delivery, 0)
    row = await row_of(delivery)
    assert out.status == "retrying" and row.last_error_code == "unreachable"
    assert len(setup.fake.objects) == 1  # it was created; we never saw the reply
    out = await run(delivery, 1)
    row = await row_of(delivery)
    assert out.status == "delivered" and row.status is DeliveryStatus.DELIVERED
    assert row.remote_id == setup.fake.objects[0]["uuid"]
    assert len(setup.fake.objects) == 1 and setup.fake.created == 1
    assert methods(setup) == ["POST", "GET"]
    # the lookup asked for exactly this delivery, from validated settings only
    lookup = urlsplit(setup.tls.requests[1].target)
    assert lookup.path == "/api/v2/objects"
    assert dict(parse_qsl(lookup.query, keep_blank_values=True)) == {
        "type": TYPE_URL,
        "data_attr": f"bettercollected_reference__exact__{objects_api.reference_for(delivery.id)}",
        "date": await start_date_of(setup, response),
        "pageSize": "1",
    }
    for text in PERSONAL:
        assert text not in setup.tls.requests[1].target
    assert setup.tls.requests[1].headers["authorization"] == f"Token {TOKEN}"
    assert setup.tls.requests[1].body == b""


async def test_the_reference_is_the_same_on_every_attempt_and_differs_per_delivery(
    setup,
):
    first = await delivery_of(setup, await submit(setup.workspace, setup.form))
    second = await delivery_of(
        setup,
        await submit(
            setup.workspace,
            setup.form,
            {**ANSWERS, "name": {"type": "text", "text": "Bo"}},
        ),
    )
    assert objects_api.reference_for(first.id) == objects_api.reference_for(first.id)
    assert objects_api.reference_for(first.id) != objects_api.reference_for(second.id)
    assert str(__import__("uuid").UUID(objects_api.reference_for(first.id)))


async def test_a_manual_retry_also_looks_first(setup):
    setup.fake.required = ["nothing_we_send"]
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    assert (await run(delivery)).status == "failed"  # a 400: nothing created
    setup.fake.required = []
    await svc().retry_delivery(
        setup.workspace.id, setup.form.form_id, str(delivery.id), testUser
    )
    assert (await run(delivery)).status == "delivered"
    assert methods(setup) == ["POST", "GET", "POST"] and setup.fake.created == 1


async def test_a_manual_retry_after_a_lost_reply_that_ran_out_of_attempts_finds_it(
    setup,
):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.fake.drop_reply_next = 1
    out = await run(delivery, 5)  # the last attempt: failed
    assert out.status == "failed" and len(setup.fake.objects) == 1
    await svc().retry_delivery(
        setup.workspace.id, setup.form.form_id, str(delivery.id), testUser
    )
    assert (await run(delivery)).status == "delivered"
    assert setup.fake.created == 1 and methods(setup) == ["POST", "GET"]


async def test_a_filter_that_is_ignored_never_gives_delivered_without_a_send(setup):
    # somebody else's objects of the same type; the server lists them whatever we ask
    setup.fake.objects = [
        {
            "uuid": "11111111-1111-4111-8111-111111111111",
            "type": TYPE_URL,
            "record": {"data": {"bettercollected_reference": "someone-else"}},
        },
        {
            "uuid": "22222222-2222-4222-8222-222222222222",
            "type": TYPE_URL,
            "record": {"data": {"other": 1}},
        },
    ]
    setup.fake.ignore_filter = True
    response, delivery = await first_attempt_fails_with_503(setup)
    out = await run(delivery, 1)
    row = await row_of(delivery)
    assert out.status == "failed" and row.status is DeliveryStatus.FAILED
    assert row.last_error_code == "lookup_failed" and row.remote_id is None
    assert methods(setup) == ["POST", "GET"]  # the second attempt did not send
    assert setup.fake.created == 0
    # a manual retry meets the same wall: still not delivered, still no send
    await svc().retry_delivery(
        setup.workspace.id, setup.form.form_id, str(delivery.id), testUser
    )
    assert (await run(delivery)).status == "failed"
    assert methods(setup) == ["POST", "GET", "GET"] and setup.fake.created == 0


async def test_an_ignored_filter_that_lists_our_object_is_still_verified_by_its_data(
    setup,
):
    setup.fake.ignore_filter = True
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.fake.drop_reply_next = 1
    await run(delivery, 0)
    setup.fake.objects.insert(
        0,
        {
            "uuid": "33333333-3333-4333-8333-333333333333",
            "type": TYPE_URL,
            "record": {"data": {"bettercollected_reference": "someone-else"}},
        },
    )
    out = await run(delivery, 1)
    row = await row_of(delivery)
    # our object is among the listed ones and its data carries our reference
    assert out.status == "delivered" and setup.fake.created == 1
    assert row.remote_id not in (None, "33333333-3333-4333-8333-333333333333")


@pytest.mark.parametrize(
    "answer",
    [
        # a hit whose data cannot be read, or does not carry our reference
        {"count": 1, "results": [{"uuid": "1", "record": {"data": "text"}}]},
        {"count": 1, "results": [{"uuid": "1", "record": {"data": ["x"]}}]},
        {"count": 1, "results": [{"uuid": "1", "record": None}]},
        {"count": 1, "results": [{"uuid": "1"}]},
        {"count": 1, "results": ["not an object"]},
        {
            "count": 1,
            "results": [{"record": {"data": {"bettercollected_reference": 5}}}],
        },
        {
            "count": 1,
            "results": [{"record": {"data": {"bettercollected_reference": ["x"]}}}],
        },
        {
            "count": 1,
            "results": [
                {"record": {"data": {"other": {"bettercollected_reference": "x"}}}}
            ],
        },
        {
            "count": 1,
            "results": [{"record": {"data": {"bettercollected_reference": "REF"}}}],
        },
        # shapes that are not a list of objects
        {"count": 1},
        {"count": 3, "results": []},
        {"results": "x"},
        [],
        "text",
        None,
    ],
)
async def test_a_hit_that_does_not_show_our_reference_fails_the_lookup(setup, answer):
    response, delivery = await first_attempt_fails_with_503(setup)
    reference = objects_api.reference_for(delivery.id)
    # "REF": a reference that is not ours (one character off)
    other = reference[:-1] + ("1" if reference[-1] == "0" else "0")
    body = json.dumps(answer).replace("REF", other).encode()
    setup.fake.canned["GET"] = (200, {}, body)
    out = await run(delivery, 1)
    row = await row_of(delivery)
    assert out.status == "failed" and row.last_error_code == "lookup_failed"
    assert methods(setup) == ["POST", "GET"] and setup.fake.created == 0


@pytest.mark.parametrize("body", [b"<html>", b"", b"\xff\xfe", b"x" * (70 * 1024)])
async def test_a_lookup_reply_that_is_malformed_or_oversized_fails_the_lookup(
    setup, body
):
    response, delivery = await first_attempt_fails_with_503(setup)
    setup.fake.canned["GET"] = (200, {}, body)
    out = await run(delivery, 1)
    row = await row_of(delivery)
    assert out.status == "failed" and row.last_error_code == "lookup_failed"
    assert methods(setup) == ["POST", "GET"]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
async def test_a_lookup_4xx_fails_with_lookup_failed_and_is_never_sent_blind(
    setup, status
):
    response, delivery = await first_attempt_fails_with_503(setup)
    setup.fake.canned["GET"] = (status, {}, b"no")
    out = await run(delivery, 1)
    row = await row_of(delivery)
    assert (out.status, out.retry) == ("failed", False)
    assert row.last_error_code == "lookup_failed" and row.last_http_status == status
    assert methods(setup) == ["POST", "GET"] and setup.fake.created == 0


@pytest.mark.parametrize("status", [429, 502, 503])
async def test_a_lookup_that_is_busy_or_down_is_retried_like_a_send(setup, status):
    response, delivery = await first_attempt_fails_with_503(setup)
    setup.fake.canned["GET"] = (status, {}, b"later")
    out = await run(delivery, 1)
    row = await row_of(delivery)
    assert (out.status, out.retry) == ("retrying", True)
    assert row.status is DeliveryStatus.RETRYING and row.last_http_status == status
    assert methods(setup) == ["POST", "GET"]
    setup.fake.canned["GET"] = None
    assert (await run(delivery, 2)).status == "delivered"
    assert methods(setup) == ["POST", "GET", "GET", "POST"] and setup.fake.created == 1


# ---------------------------------------------------------- network refusals


async def test_a_redirect_is_refused_for_the_send_and_for_the_lookup(setup):
    setup.fake.canned["POST"] = (
        302,
        {"Location": "https://elsewhere.example.org/"},
        b"",
    )
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    out = await run(delivery)
    assert out.status == "failed"
    assert (await row_of(delivery)).last_error_code == "redirect_refused"
    assert not any("elsewhere" in str(r.target) for r in setup.tls.requests)
    # now the lookup
    setup.fake.canned["POST"] = None
    setup.fake.canned["GET"] = (
        301,
        {"Location": "https://elsewhere.example.org/"},
        b"",
    )
    await svc().retry_delivery(
        setup.workspace.id, setup.form.form_id, str(delivery.id), testUser
    )
    assert (await run(delivery)).status == "failed"
    assert (await row_of(delivery)).last_error_code == "redirect_refused"
    assert methods(setup) == ["POST", "GET"] and setup.fake.created == 0


async def test_a_private_address_is_refused_at_connect_time_for_both_calls(
    setup, monkeypatch
):
    async def rebound(host, port=443):
        return ["169.254.169.254"]

    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    monkeypatch.setattr(client, "resolve", rebound)
    out = await run(delivery)
    assert out.status == "failed"
    assert (await row_of(delivery)).last_error_code == "not_allowed"
    assert setup.tls.requests == []
    await svc().retry_delivery(
        setup.workspace.id, setup.form.form_id, str(delivery.id), testUser
    )
    assert (await run(delivery)).status == "failed"  # the lookup: refused as well
    assert (await row_of(delivery)).last_error_code == "not_allowed"
    assert setup.tls.requests == [] and setup.tls.dialled == []


# ------------------------------------------ stored settings are not trusted


async def test_an_object_type_that_ended_up_outside_the_base_is_not_used(setup):
    await svc().update_service(
        setup.workspace.id,
        setup.service.id,
        ServiceUpdateDto(objecttypes_base_url="https://types2.example.org/api/"),
        testUser,
    )
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    out = await run(delivery)
    assert out.status == "failed"
    assert (await row_of(delivery)).last_error_code == "config_invalid"
    assert setup.tls.requests == []


async def test_a_stored_form_with_bad_paths_or_a_file_mapping_sends_nothing(setup):
    registration = await container.form_registration_repo().get_for_form(
        setup.workspace.id, setup.form.form_id
    )
    registration.variables[0].target_path = ["a__b"]
    await container.form_registration_repo().save(registration)
    delivery = await delivery_of(setup, await submit(setup.workspace, setup.form))
    assert (await run(delivery)).status == "failed"
    assert (await row_of(delivery)).last_error_code == "config_invalid"
    registration.variables[0].target_path = ["upload"]
    registration.variables[0].source = "upload"
    await container.form_registration_repo().save(registration)
    second = await delivery_of(setup, await submit(setup.workspace, setup.form))
    assert (await run(second)).status == "failed"
    assert (await row_of(second)).last_error_code == "config_invalid"
    assert setup.tls.requests == []


# ---------------------------------------------------------- switch and check


async def test_switch_off_answers_410_and_sends_nothing(setup, monkeypatch):
    from backend.config import settings

    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    monkeypatch.setattr(settings.registration, "REGISTRATION", "off")
    assert (await run(delivery)).status == "skipped"
    assert (
        await refused(
            svc().check_connection(setup.workspace.id, setup.form.form_id, testUser)
        )
        == "registration_off"
    )
    assert setup.tls.requests == []


async def test_the_connection_check_looks_up_a_reference_that_cannot_exist(setup, logs):
    result = await svc().check_connection(
        setup.workspace.id, setup.form.form_id, testUser
    )
    assert (result.ok, result.code) == (True, None) and result.http_status == 200
    first, second = setup.tls.requests
    assert [first.method, second.method] == ["GET", "GET"]
    query = dict(parse_qsl(urlsplit(first.target).query))
    assert query["type"] == TYPE_URL and query["pageSize"] == "1"
    assert query["data_attr"].startswith("bettercollected_reference__exact__")
    assert query[
        "data_attr"
    ] != "bettercollected_reference__exact__" + objects_api.reference_for("x")
    assert first.headers["authorization"] == f"Token {TOKEN}"
    # it reads no records and keeps nothing; the malformed filter was refused
    assert (
        setup.fake.created == 0
        and await container.registration_delivery_repo().many() == []
    )
    assert not any(TOKEN in line for line in logs)


async def test_the_check_notices_a_filter_that_is_ignored_even_on_an_empty_type(setup):
    setup.fake.ignore_filter = True
    result = await svc().check_connection(
        setup.workspace.id, setup.form.form_id, testUser
    )
    assert (result.ok, result.code) == (False, "filter_not_supported")
    # with objects of the type listed whatever we ask, the first lookup shows it
    setup.fake.objects = [
        {
            "uuid": "11111111-1111-4111-8111-111111111111",
            "type": TYPE_URL,
            "record": {"data": {"x": 1}},
        }
    ]
    result = await svc().check_connection(
        setup.workspace.id, setup.form.form_id, testUser
    )
    assert (result.ok, result.code) == (False, "filter_not_supported")


@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_the_check_reports_a_refused_lookup_as_lookup_failed(setup, status):
    setup.fake.canned["GET"] = (status, {}, b"no")
    result = await svc().check_connection(
        setup.workspace.id, setup.form.form_id, testUser
    )
    assert (result.ok, result.code, result.http_status) == (
        False,
        "lookup_failed",
        status,
    )


async def test_the_check_reports_unreachable_and_wrong_token(setup):
    setup.fake.token = "another"
    result = await svc().check_connection(
        setup.workspace.id, setup.form.form_id, testUser
    )
    assert (result.ok, result.code, result.http_status) == (False, "lookup_failed", 401)
    setup.fake.canned["GET"] = (503, {}, b"down")
    setup.fake.token = TOKEN
    result = await svc().check_connection(
        setup.workspace.id, setup.form.form_id, testUser
    )
    assert (result.ok, result.code, result.http_status) == (False, "http_5xx", 503)


async def test_the_check_needs_saved_objects_settings(setup, workspace):
    other = await publish(workspace)
    result = await svc().check_connection(workspace.id, other.form_id, testUser)
    assert (result.ok, result.code) == (False, "not_configured")
    assert setup.tls.requests == []


# --------------------------------------------- review fixes: caps, regexes, snapshot


def big_hit(reference, size):
    """A lookup answer whose one object carries ``reference`` and ``size``
    bytes of other data (a large stored record)."""
    return json.dumps(
        {
            "count": 1,
            "results": [
                {
                    "uuid": "44444444-4444-4444-8444-444444444444",
                    "record": {
                        "data": {
                            "bettercollected_reference": reference,
                            "padding": "x" * size,
                        }
                    },
                }
            ],
        }
    ).encode()


async def test_a_large_hit_is_found_and_a_reply_over_the_lookup_cap_is_not(setup):
    response, delivery = await first_attempt_fails_with_503(setup)
    reference = objects_api.reference_for(delivery.id)
    # over the 64 KiB cap of other replies, under the lookup's own
    setup.fake.canned["GET"] = (200, {}, big_hit(reference, 300 * 1024))
    out = await run(delivery, 1)
    row = await row_of(delivery)
    assert (
        out.status == "delivered"
        and row.remote_id == "44444444-4444-4444-8444-444444444444"
    )
    assert methods(setup) == ["POST", "GET"] and setup.fake.created == 0
    # over the cap: unreadable, so never a "no" and never a blind send
    second = await submit(setup.workspace, setup.form)
    other = await delivery_of(setup, second)
    setup.fake.canned["POST"] = (503, {}, b"down")
    await run(other, 0)
    setup.fake.canned["GET"] = (
        200,
        {},
        big_hit(
            objects_api.reference_for(other.id), client.MAX_LOOKUP_REPLY_BYTES + 10
        ),
    )
    out = await run(other, 1)
    assert out.status == "failed"
    assert (await row_of(other)).last_error_code == "lookup_failed"
    assert methods(setup)[-1] == "GET"


def test_segments_and_uuids_are_matched_whole():
    for segment in ("abc\n", "abc ", "a\nb", "", "a" * 65, "a_", "a__b", "1a"):
        assert objects_api.segment_problem(segment), repr(segment)
    assert not objects_api.segment_problem("abc_d")
    assert objects_api.read_created(b'{"uuid": "%s\\n"}' % UUID.encode()) is None
    assert objects_api.read_created(b'{"uuid": "%s"}' % UUID.upper().encode()) == UUID


async def test_the_settings_of_the_first_send_are_used_for_the_lookup_after_an_edit(
    setup,
):
    other_type = TYPE_URL.replace("3f5e8a10", "aaaaaaaa")
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.fake.drop_reply_next = 1
    await run(delivery, 0)  # created under the first settings, reply lost
    assert len(setup.fake.objects) == 1
    # an admin edits the form before the retry: another type, version and reference path
    await configure_objects(
        setup.workspace,
        setup.form,
        setup.service,
        object_type_url=other_type,
        object_type_version=7,
        reference_path=["meta", "ref"],
    )
    out = await run(delivery, 1)
    row = await row_of(delivery)
    assert out.status == "delivered" and setup.fake.created == 1
    assert row.remote_id == setup.fake.objects[0]["uuid"]
    query = dict(parse_qsl(urlsplit(setup.tls.requests[1].target).query))
    assert query["type"] == TYPE_URL
    assert query["data_attr"].startswith("bettercollected_reference__exact__")


async def test_a_send_after_an_edit_still_goes_out_under_the_first_settings(setup):
    other_type = TYPE_URL.replace("3f5e8a10", "aaaaaaaa")
    response, delivery = await first_attempt_fails_with_503(setup)
    await configure_objects(
        setup.workspace,
        setup.form,
        setup.service,
        object_type_url=other_type,
        object_type_version=7,
        reference_path=["meta", "ref"],
    )
    assert (await run(delivery, 1)).status == "delivered"
    sent = json.loads(setup.tls.requests[-1].body)
    assert sent["type"] == TYPE_URL and sent["record"]["typeVersion"] == 3
    assert sent["record"]["data"]["bettercollected_reference"] == (
        objects_api.reference_for(delivery.id)
    )
    assert "meta" not in sent["record"]["data"]


async def test_a_delivery_whose_service_is_gone_is_not_sent_elsewhere(setup):
    response, delivery = await first_attempt_fails_with_503(setup)
    other = await make_objects_service(setup.workspace, name="Another")
    await configure_objects(setup.workspace, setup.form, other)
    await svc().delete_service(setup.workspace.id, setup.service.id, testUser)
    out = await run(delivery, 1)
    assert out.status == "failed"
    assert (await row_of(delivery)).last_error_code == "config_invalid"
    assert methods(setup) == ["POST"]


async def test_a_delivery_whose_service_moved_host_is_not_sent_there(setup):
    response, delivery = await first_attempt_fails_with_503(setup)
    await svc().update_service(
        setup.workspace.id,
        setup.service.id,
        ServiceUpdateDto(
            base_url="https://elsewhere.example.org/api/v2/", secret=TOKEN
        ),
        testUser,
    )
    out = await run(delivery, 1)
    assert out.status == "failed"
    assert (await row_of(delivery)).last_error_code == "config_invalid"
    assert methods(setup) == ["POST"]


async def test_a_response_without_a_creation_time_is_not_looked_up_by_the_clock(
    setup, monkeypatch
):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    real = container.form_response_service().workspace_response

    async def without_time(workspace_id, response_id):
        found = await real(workspace_id, response_id)
        found.created_at = None
        return found

    monkeypatch.setattr(
        container.form_response_service(), "workspace_response", without_time
    )
    out = await run(delivery)
    assert out.status == "failed"
    assert (await row_of(delivery)).last_error_code == "internal_error"
    assert setup.tls.requests == []


@pytest.mark.parametrize(
    "path",
    [
        "/api/../x/",
        "/api/./x/",
        "/api/%2e%2e/x/",
        "/api/%2E%2E/",
        "/api/%252e%252e/x/",
        "/api/..%2fx/",
        "/api/.%2e/",
        "/api/%2e/",
    ],
)
async def test_a_service_address_with_dot_segments_is_refused_fail_closed(
    workspace, registration_on, tls, path
):
    base = f"https://case.example.org{path}"
    assert (
        await refused(make_objects_service(workspace, base_url=base)) == "invalid_url"
    )
    assert (
        await refused(make_objects_service(workspace, objecttypes_base_url=base))
        == "invalid_url"
    )
    service = await make_objects_service(workspace)
    assert (
        await refused(
            svc().update_service(
                workspace.id,
                service.id,
                ServiceUpdateDto(base_url=base, secret=TOKEN),
                testUser,
            )
        )
        == "invalid_url"
    )


async def test_the_connection_check_is_rate_limited_per_workspace(setup):
    for _ in range(10):
        assert (
            await svc().check_connection(
                setup.workspace.id, setup.form.form_id, testUser
            )
        ).ok
    assert len(setup.tls.requests) == 20
    with pytest.raises(HTTPException) as raised:
        await svc().check_connection(setup.workspace.id, setup.form.form_id, testUser)
    assert raised.value.status_code == 429
    assert raised.value.content["code"] == "rate_limited"
    assert "Retry-After" in raised.value.headers
    assert len(setup.tls.requests) == 20  # nothing more was sent
