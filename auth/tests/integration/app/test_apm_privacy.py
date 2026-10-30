"""Elastic APM on the auth service records a request's method and path only:
no query string (the backend sends the email and the sign-in code there), no
headers (the internal key), no body and no frame variables, whatever the
``ELASTIC_APM_*`` settings say (app/apm_privacy.py)."""

import json

import pytest
from elasticapm.contrib.starlette import ElasticAPM
from elasticapm.transport.base import Transport
from fastapi.testclient import TestClient

from auth.app.apm_privacy import PrivateAPMClient, redact_apm_event
from auth.app.asgi import get_application
from auth.config import settings
from tests.integration.conftest import INTERNAL_KEY

CODE = "QRS-987"
EMAIL = "apm-check@example.com"


class RecordingTransport(Transport):
    """Keeps each event as it would be sent (after every processor) instead
    of sending it; no thread, no connection."""

    def __init__(self, *args, url=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []

    def queue(self, event_type, data, flush=False):
        if event_type in ("transaction", "error"):
            self.events.append((event_type, self._process_event(event_type, data)))

    def start_thread(self, pid=None):
        pass

    def close(self):
        self._closed = True


@pytest.fixture
def traced_app(monkeypatch, _postgres_schema):
    """The app with APM configured to record as much as it can, and the events
    it would send (after every processor) collected instead of sent."""
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", INTERNAL_KEY)
    monkeypatch.setattr(settings.apm_settings, "service_name", "auth-test")
    monkeypatch.setattr(settings.apm_settings, "server_url", "http://127.0.0.1:1")
    for name, value in {
        "SERVICE_NAME": "auth-test",
        "SERVER_URL": "http://127.0.0.1:1",
        "DISABLE_SEND": "false",
        "TRANSPORT_CLASS": f"{__name__}.RecordingTransport",
        "CENTRAL_CONFIG": "false",
        "METRICS_INTERVAL": "0s",
        "CLOUD_PROVIDER": "none",
        # settings that would record more: none of them may switch the guard off
        "CAPTURE_BODY": "all",
        "CAPTURE_HEADERS": "true",
        "SANITIZE_FIELD_NAMES": "nothing-matches-this",
        "PROCESSORS": "elasticapm.processors.sanitize_stacktrace_locals",
        "COLLECT_LOCAL_VARIABLES": "all",
    }.items():
        monkeypatch.setenv(f"ELASTIC_APM_{name}", value)

    app = get_application()
    (middleware,) = [m for m in app.user_middleware if m.cls is ElasticAPM]
    client = middleware.kwargs["client"]
    events = client._transport.events
    try:
        yield app, client, events
    finally:
        client.close()


def test_the_app_traces_with_the_private_client(traced_app):
    _, client, _ = traced_app
    assert isinstance(client, PrivateAPMClient)
    assert redact_apm_event in client.load_processors()
    assert redact_apm_event in client._transport._processors


def test_a_code_check_records_no_query_string_header_or_code(traced_app):
    app, _, events = traced_app
    with TestClient(
        app,
        base_url=f"http://testserver{settings.API_ROOT_PATH}",
        headers={"X-Internal-Key": INTERNAL_KEY},
    ) as client:
        response = client.get(
            "auth/otp/validate", params={"email": EMAIL, "otp_code": CODE}
        )
    assert response.status_code == 200

    transactions = [data for kind, data in events if kind == "transaction"]
    assert transactions, "the request was not traced"
    recorded = json.dumps(transactions, default=str)
    for secret in (CODE, "otp_code", "apm-check", "example.com", INTERNAL_KEY):
        assert secret not in recorded, secret
    (transaction,) = transactions
    request = transaction["context"]["request"]
    assert request["url"]["full"].endswith("/api/v1/auth/otp/validate")
    assert "?" not in request["url"]["full"] and "search" not in request["url"]
    assert "?" not in transaction["name"]
    assert not {"headers", "cookies", "body", "env"} & set(request)


def test_an_error_records_no_frame_variables(traced_app):
    _, client, events = traced_app

    def check(otp_code):
        raise ValueError("boom")

    try:
        check(CODE)
    except ValueError:
        client.capture_exception()

    errors = [data for kind, data in events if kind == "error"]
    assert errors, "the error was not captured"
    recorded = json.dumps(errors, default=str)
    assert CODE not in recorded
    assert '"vars"' not in recorded
