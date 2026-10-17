import pytest

from bettercollected import BetterCollected, BetterCollectedError, FormSpec
from tests.fake_api import KEY, FakeApi

SPEC = {
    "specVersion": "1",
    "title": "Event sign-up",
    "pages": [
        {
            "id": "page-1",
            "fields": [
                {
                    "id": "name",
                    "type": "short_text",
                    "title": "Your name",
                    "validations": {"required": True},
                }
            ],
        }
    ],
}


@pytest.fixture
def api():
    return FakeApi()


@pytest.fixture
def client(api):
    with BetterCollected(
        KEY, "https://forms.example.org/", transport=api.transport()
    ) as c:
        yield c


def test_create_get_and_replace_with_versions(api, client):
    created = client.create_form(FormSpec.model_validate(SPEC), idempotency_key="k1")
    assert created.form_id == "f1"
    assert created.form.title == "Event sign-up"
    assert api.requests[0].headers["Idempotency-Key"] == "k1"
    assert api.requests[0].headers["Authorization"] == f"Bearer {KEY}"
    assert api.requests[0].url.path == "/api/v1/public/v1/forms"

    current = client.get_form("f1")
    assert current.etag == created.etag
    assert current.value.pages[0].fields[0].validations.required is True

    renamed = dict(SPEC, title="Renamed")
    replaced = client.replace_form("f1", renamed, if_match=current.etag)
    assert replaced.value.title == "Renamed"
    assert replaced.etag != current.etag

    with pytest.raises(BetterCollectedError) as stale:
        client.replace_form("f1", SPEC, if_match=current.etag)
    assert (stale.value.status, stale.value.code) == (412, "precondition_failed")


def test_spec_models_are_strict_and_round_trip():
    spec = FormSpec.model_validate(SPEC)
    assert spec.model_dump(mode="json", by_alias=True, exclude_none=True) == SPEC
    with pytest.raises(ValueError):
        FormSpec.model_validate(dict(SPEC, colour="red"))


def test_errors_carry_code_and_locations(api, client):
    api.add("f9", SPEC)
    with pytest.raises(BetterCollectedError) as failed:
        client.apply_ops("f9", [{"op": "remove_field", "fieldId": "nope"}])
    error = failed.value
    assert (error.status, error.code) == (422, "ops_failed")
    assert error.errors[0].path == "/ops/0"
    assert "/ops/0: No such field." in str(error)
    assert (
        api.requests[-1].read()
        == b'{"ops":[{"op":"remove_field","fieldId":"nope"}],"atomic":true}'
    )


def test_validate_and_list(api, client):
    result = client.validate_form(dict(SPEC, specVersion="2"))
    assert result.valid is False and result.errors[0].path == "/specVersion"
    api.add("f1", SPEC)
    assert client.list_forms().items[0].form_id == "f1"


def test_unknown_key_is_401():
    api = FakeApi()
    with BetterCollected("bc_wrong", "https://x.test", transport=api.transport()) as c:
        with pytest.raises(BetterCollectedError) as failed:
            c.list_forms()
    assert failed.value.code == "unauthorized"


def test_needs_a_key():
    with pytest.raises(ValueError):
        BetterCollected("", "https://x.test")


def test_warns_when_the_key_would_travel_over_plain_http(recwarn):
    for url in ("http://localhost:8000", "http://127.0.0.1", "https://x.test"):
        BetterCollected(KEY, url).close()
    assert len(recwarn) == 0
    with pytest.warns(UserWarning, match="unencrypted"):
        BetterCollected(KEY, "http://forms.example.org").close()


def test_trailing_slashes_are_dropped(api):
    with BetterCollected(KEY, "https://x.test///", transport=api.transport()) as c:
        c.list_forms()
    assert api.requests[-1].url.path == "/api/v1/public/v1/forms"
