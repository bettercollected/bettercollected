"""GOOGLE_FORMS_IMPORT on this service: readonly (403) and off (410) refuse
every Google Forms route before any credential is read; the Sheets routes and
deleting stored credentials stay."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from googleform.app.asgi import get_application
from googleform.app.services.forms_mode import google_forms_import_mode
from googleform.app.services.google import GoogleService
from googleform.config import settings

ROOT = settings.API_ROOT_PATH

FORMS_ROUTES = [
    ("GET", "/google/forms"),
    ("GET", "/google/forms/form-1"),
    ("POST", "/google/forms/convert/standard_form"),
    ("GET", "/google/forms/oauth/verify"),
    ("GET", "/google/forms/read_google_sheet?google_sheet_id=s1"),
    ("GET", "/google/oauth/authorize?state=s"),
    ("GET", "/google/oauth/callback?user_id=u"),
    ("GET", "/google/credentials?email=user@example.com"),
]


@pytest.fixture()
def client():
    return TestClient(get_application(), raise_server_exceptions=False)


@pytest.fixture()
def mode(monkeypatch):
    return lambda value: monkeypatch.setattr(settings, "GOOGLE_FORMS_IMPORT", value)


def test_the_default_is_on():
    from googleform.config.application import Application

    assert Application.model_fields["GOOGLE_FORMS_IMPORT"].default == "on"


@pytest.mark.parametrize(
    "value,expected",
    [("on", "on"), (" ReadOnly ", "readonly"), ("OFF", "off"), ("bogus", "off"), ("", "on")],
)
def test_unknown_values_are_the_strictest_mode(mode, value, expected):
    mode(value)
    assert google_forms_import_mode() == expected


@pytest.mark.parametrize("method,path", FORMS_ROUTES)
@pytest.mark.parametrize(
    "value,status,code",
    [("readonly", 403, "google_forms_readonly"), ("off", 410, "google_forms_off")],
)
def test_forms_routes_refuse_before_reading_a_credential(
    client, mode, method, path, value, status, code
):
    mode(value)
    with patch(
        "googleform.app.services.user_service.OauthCredentialRepository.get",
        AsyncMock(side_effect=AssertionError("no credential may be read")),
    ):
        response = client.request(method, ROOT + path, json={})

    assert response.status_code == status
    assert response.json()["code"] == code


@pytest.mark.parametrize("method,path", FORMS_ROUTES[:5])
def test_on_serves_them_as_before(client, mode, method, path):
    mode("on")
    # no access token: the usual 401, so the route itself ran
    response = client.request(method, ROOT + path, json={})
    assert response.status_code == 401


@pytest.mark.parametrize("value", ["on", "readonly", "off"])
def test_the_sheets_routes_are_not_google_forms_work(client, mode, value):
    mode(value)
    with patch.object(GoogleService, "create_sheet", return_value="sheet-1"):
        response = client.post(
            ROOT + "/google/forms/create_google_sheet",
            params={"title": "t", "credential": "c"},
        )
    assert response.status_code == 200
    assert response.json() == "sheet-1"


@pytest.mark.parametrize("value", ["on", "readonly", "off"])
def test_deleting_stored_credentials_always_works(client, mode, value):
    mode(value)
    with patch(
        "googleform.app.services.oauth_google.OauthGoogleService.delete_oauth_credentials_for_user",
        AsyncMock(return_value=None),
    ) as delete:
        response = client.delete(
            ROOT + "/google/oauth/credentials",
            params={"user_id": "u1", "email": "user@example.com"},
        )
    assert response.status_code == 200
    assert delete.await_count == 1
