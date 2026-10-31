"""Elastic APM records full URLs; what it records must carry no query string
(the typed search is a respondent's email; the calls to the auth service carry
emails and sign-in codes) and no receipt number."""

import pytest
from elasticapm.transport.base import Transport
from elasticapm.utils import get_url_dict

from backend.app.middlewares.apm_privacy import PrivateAPMClient, redact_apm_event

RECEIPT = "0b1c2d3e-aaaa-4bbb-8ccc-000000000001"
SEARCH = "someone.searched@example.test"
HOST = "https://api.example.test"


def event(url: str, name: str = None, **request) -> dict:
    return {
        "name": name,
        "context": {"request": {"method": "GET", "url": get_url_dict(url), **request}},
    }


def recorded(event_) -> str:
    return repr(event_)


@pytest.mark.parametrize(
    "url",
    [
        f"{HOST}/api/v1/workspaces/w1/forms/f1/submissions?dataOwnerIdentifier={SEARCH}",
        f"{HOST}/api/v1/workspaces/w1/submissions/by-uuid/{RECEIPT}",
        f"{HOST}/api/v1/workspaces/w1/submissions/by-uuid/{RECEIPT}?x={SEARCH}#top",
        f"{HOST}/api/v1/workspaces/w1/submissions/{RECEIPT}",
    ],
)
def test_the_event_keeps_no_query_string_and_no_receipt_number(url):
    out = redact_apm_event(None, event(url, name=url.split(HOST)[1]))

    text = recorded(out)
    assert SEARCH not in text
    assert RECEIPT not in text
    assert "dataOwnerIdentifier" not in text
    assert "search" not in out["context"]["request"]["url"]
    assert "?" not in out["context"]["request"]["url"]["full"]
    assert "?" not in out["name"]


def test_the_rest_of_the_url_is_kept():
    url = f"{HOST}/api/v1/workspaces/w1/submissions/by-uuid/{RECEIPT}?a=b"

    out = redact_apm_event(None, event(url))["context"]["request"]["url"]

    assert out["full"] == f"{HOST}/api/v1/workspaces/w1/submissions/by-uuid/<redacted>"
    assert out["pathname"] == "/api/v1/workspaces/w1/submissions/by-uuid/<redacted>"
    assert out["hostname"] == "api.example.test"
    assert out["protocol"] == "https:"


def test_a_referer_header_loses_its_query_string():
    headers = {"Referer": f"https://app.example.test/x?dataOwnerIdentifier={SEARCH}"}

    out = redact_apm_event(None, event(f"{HOST}/api/v1/workspaces/w1", headers=headers))

    assert out["context"]["request"]["headers"]["Referer"] == (
        "https://app.example.test/x"
    )


@pytest.mark.parametrize("shape", [{}, {"context": {}}, {"context": {"request": {}}}])
def test_an_event_without_a_request_passes_through(shape):
    assert redact_apm_event(None, dict(shape)) == shape


def test_the_processor_runs_on_transactions_spans_and_errors():
    assert redact_apm_event.event_types == {"transaction", "span", "error"}


def _client():
    return PrivateAPMClient(
        {"SERVICE_NAME": "t", "SERVER_URL": "http://127.0.0.1:1", "ENABLED": False}
    )


def test_the_client_always_loads_the_processor():
    client = _client()
    try:
        assert redact_apm_event in client.load_processors()
    finally:
        client.close()


def test_receipt_routes_are_not_traced_whatever_the_configuration():
    client = _client()
    try:
        assert client.should_ignore_url("/api/v1/workspaces/w1/submissions/by-uuid/x")
        assert not client.should_ignore_url("/api/v1/workspaces/w1/forms")
    finally:
        client.close()


def test_the_transport_runs_the_processor_before_anything_is_sent():
    client = PrivateAPMClient(
        {"SERVICE_NAME": "t", "SERVER_URL": "http://127.0.0.1:1", "DISABLE_SEND": True}
    )
    try:
        assert redact_apm_event in client._transport._processors
    finally:
        client.close()


def test_the_application_traces_with_the_private_client(monkeypatch):
    """Where APM is configured, the app's client is the one with the guards."""
    from elasticapm.contrib.starlette import ElasticAPM

    from backend.app.asgi import get_application
    from backend.config import settings

    monkeypatch.setattr(settings.apm_settings, "service_name", "t")
    monkeypatch.setattr(settings.apm_settings, "server_url", "http://127.0.0.1:1")
    monkeypatch.setenv("ELASTIC_APM_DISABLE_SEND", "true")

    app = get_application()

    (apm,) = [m for m in app.user_middleware if m.cls is ElasticAPM]
    client = apm.kwargs["client"]
    try:
        assert isinstance(client, PrivateAPMClient)
    finally:
        client.close()


class RecordingTransport(Transport):
    """Keeps each event as it would be sent (after every processor)."""

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


CODE = "QRS-987"
AUTH = "http://auth:8001/api/v1/auth"


@pytest.mark.parametrize(
    "url",
    [
        f"{AUTH}/otp/validate?email={SEARCH}&otp_code={CODE}",
        f"{AUTH}/otp/send?receiver_email={SEARCH}&creator=true&x={CODE}",
    ],
)
def test_a_call_to_the_auth_service_is_recorded_without_its_query(url, monkeypatch):
    """The span of an outgoing call, as the httpx instrumentation records it
    (``context.http.url``), loses the email and the code."""
    import elasticapm

    # the environment outranks the client's config (CI disables sending)
    monkeypatch.setenv("ELASTIC_APM_DISABLE_SEND", "false")

    client = PrivateAPMClient(
        {
            "SERVICE_NAME": "t",
            "SERVER_URL": "http://127.0.0.1:1",
            "TRANSPORT_CLASS": f"{__name__}.RecordingTransport",
            "CENTRAL_CONFIG": False,
            "METRICS_INTERVAL": "0s",
            "CLOUD_PROVIDER": "none",
            "EXIT_SPAN_MIN_DURATION": "0ms",
            "SPAN_COMPRESSION_ENABLED": False,
        }
    )
    try:
        client.begin_transaction("request")
        with elasticapm.capture_span(
            "GET auth:8001",
            span_type="external",
            span_subtype="http",
            extra={"http": {"url": url}},
            leaf=True,
        ):
            pass
        client.end_transaction("GET /api/v1/auth/otp/validate", "HTTP 2xx")

        spans = [data for kind, data in client._transport.events if kind == "span"]
        assert spans, "the call was not recorded"
        recorded = repr(client._transport.events)
        assert CODE not in recorded and SEARCH not in recorded
        assert spans[0]["context"]["http"]["url"] == url.split("?", 1)[0]
    finally:
        client.close()
