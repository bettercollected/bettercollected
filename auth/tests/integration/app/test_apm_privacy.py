"""Elastic APM on the auth service keeps what a request carries out of every
event it sends (transactions, spans, errors): no query string (the backend
sends the email and the sign-in code there), no headers (the internal key), no
body, no frame variables (the code is a local while it is mailed or checked)
and no database parameters, whatever the ``ELASTIC_APM_*`` settings say
(app/apm_privacy.py)."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from elasticapm.contrib.starlette import ElasticAPM
from elasticapm.transport.base import Transport
from fastapi.testclient import TestClient

from auth.app.apm_privacy import PrivateAPMClient, redact_apm_event
from auth.app.asgi import get_application
from auth.app.services.auth_service import AuthService
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
        if event_type in ("transaction", "span", "error"):
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
        # every span kept, each with its stack trace
        "SPAN_STACK_TRACE_MIN_DURATION": "0ms",
        "SPAN_FRAMES_MIN_DURATION": "0ms",
        "EXIT_SPAN_MIN_DURATION": "0ms",
        "SPAN_COMPRESSION_ENABLED": "false",
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


def test_strict_mode_never_collects_local_variables(traced_app):
    _, client, _ = traced_app
    # ELASTIC_APM_COLLECT_LOCAL_VARIABLES=all is set: the client keeps "off"
    assert client.config.collect_local_variables == "off"


def test_a_code_sent_and_checked_leaves_no_trace_of_code_email_or_key(traced_app):
    app, _, events = traced_app
    with patch("auth.app.services.auth_service.MailService") as mail, patch.object(
        AuthService, "generate_otp", return_value=CODE
    ):
        mail.return_value.send_message = AsyncMock()
        with TestClient(
            app,
            base_url=f"http://testserver{settings.API_ROOT_PATH}",
            headers={"X-Internal-Key": INTERNAL_KEY},
        ) as client:
            sent = client.get(
                "auth/otp/send", params={"receiver_email": EMAIL, "creator": True}
            )
            checked = client.get(
                "auth/otp/validate", params={"email": EMAIL, "otp_code": CODE}
            )
    assert sent.status_code == 200
    assert checked.status_code == 200 and checked.json()["user"]["sub"] == EMAIL

    kinds = {kind for kind, _ in events}
    assert {"transaction", "span"} <= kinds, kinds
    recorded = json.dumps([data for _, data in events], default=str)
    secrets = (CODE, "otp_code", "apm-check", "example.com", INTERNAL_KEY, '"vars"')
    # a list, not `x not in recorded`: pytest's diff of the whole dump is slow
    assert [secret for secret in secrets if secret in recorded] == []

    transactions = [data for kind, data in events if kind == "transaction"]
    paths = set()
    for transaction in transactions:
        request = transaction["context"]["request"]
        assert "?" not in request["url"]["full"] and "search" not in request["url"]
        assert "?" not in transaction["name"]
        assert not {"headers", "cookies", "body", "env"} & set(request)
        paths.add(request["url"]["pathname"])
    assert paths == {"/api/v1/auth/otp/send", "/api/v1/auth/otp/validate"}


def test_the_database_engine_hides_statement_parameters():
    from auth.app.container import container

    assert container.pg_engine().sync_engine.hide_parameters is True


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


def test_a_duplicate_key_error_records_no_email(traced_app):
    """A real unique violation: the email reaches the error text through
    Postgres' DETAIL line, which hide_parameters does not cover."""
    import asyncio
    import uuid

    from sqlalchemy.exc import IntegrityError

    from auth.app.container import container
    from auth.app.schemas.user import UserDocument

    _, client, events = traced_app
    email = f"dup-{uuid.uuid4().hex[:10]}@example.com"
    repo = container.user_repository()

    async def insert_twice():
        try:
            await repo.save_document(UserDocument(email=email))
            await repo.save_document(UserDocument(email=email.upper()))
        finally:
            await container.pg_engine().dispose()

    with pytest.raises(IntegrityError) as raised:
        asyncio.run(insert_twice())
    text = str(raised.value)
    # the unscrubbed text does carry it (else this test proves nothing)
    assert email in text.lower() and "DETAIL" in text

    try:
        raise raised.value
    except IntegrityError:
        client.capture_exception()

    errors = [data for kind, data in events if kind == "error"]
    assert errors, "the error was not captured"
    recorded = json.dumps(errors, default=str).lower()
    assert [s for s in (email, "dup-") if s in recorded] == []
    assert "detail:  redacted" in recorded
