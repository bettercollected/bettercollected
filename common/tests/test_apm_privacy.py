"""common.utils.apm_privacy: what an APM event keeps of a request."""

import pytest

from common.utils.apm_privacy import (
    EVENT_TYPES,
    make_processor,
    private_client_class,
    redact_event,
    without_query,
)

SECRET = "ABC-123"
URL = f"https://api.example.test/api/v1/auth/otp/validate?otp_code={SECRET}#x"


def event(**request):
    return {
        "name": f"GET /api/v1/auth/otp/validate?otp_code={SECRET}",
        "context": {
            "request": {
                "method": "GET",
                "url": {
                    "full": URL,
                    "pathname": "/api/v1/auth/otp/validate",
                    "search": f"?otp_code={SECRET}",
                    "hash": "#x",
                    "hostname": "api.example.test",
                },
                **request,
            }
        },
    }


def frames():
    return [{"function": "check", "vars": {"otp_code": SECRET}}]


def test_without_query_keeps_scheme_host_and_path():
    assert without_query(URL) == "https://api.example.test/api/v1/auth/otp/validate"
    assert without_query("/a/b?c=d", lambda t: t.replace("b", "<r>")) == "/a/<r>"


@pytest.mark.parametrize("strict", [False, True])
def test_no_query_string_in_url_or_name(strict):
    out = redact_event(event(), strict=strict)
    assert SECRET not in repr(out)
    url = out["context"]["request"]["url"]
    assert url["full"] == "https://api.example.test/api/v1/auth/otp/validate"
    assert "search" not in url and "hash" not in url
    assert url["hostname"] == "api.example.test"
    assert out["name"] == "GET /api/v1/auth/otp/validate"


def test_a_plain_string_url_loses_its_query_too():
    out = redact_event({"context": {"request": {"url": URL}}})
    assert out["context"]["request"]["url"].endswith("/otp/validate")


def test_by_default_headers_stay_but_a_referer_loses_its_query():
    headers = {"Referer": f"https://app.example.test/x?code={SECRET}", "Accept": "*/*"}
    out = redact_event(event(headers=headers))
    assert out["context"]["request"]["headers"] == {
        "Referer": "https://app.example.test/x",
        "Accept": "*/*",
    }


def test_strict_drops_headers_cookies_body_env_and_frame_variables():
    error = event(
        headers={"X-Internal-Key": "k"},
        cookies={"s": "v"},
        body={"otp_code": SECRET},
        env={"SERVER_NAME": "x"},
    )
    error["exception"] = {"stacktrace": frames(), "cause": [{"stacktrace": frames()}]}
    error["log"] = {"stacktrace": frames()}

    out = redact_event(error, strict=True)

    assert set(out["context"]["request"]) == {"method", "url"}
    assert SECRET not in repr(out) and "'vars'" not in repr(out)
    assert out["exception"]["stacktrace"] == [{"function": "check"}]


def test_frame_variables_stay_unless_strict():
    error = {"exception": {"stacktrace": frames()}}
    assert redact_event(error)["exception"]["stacktrace"] == frames()


def test_the_redaction_runs_on_the_name_and_url():
    out = redact_event(event(), redact=lambda t: t.replace("validate", "<r>"))
    assert out["name"].endswith("/otp/<r>")
    assert out["context"]["request"]["url"]["pathname"].endswith("/otp/<r>")


@pytest.mark.parametrize("shape", [{}, {"context": {}}, {"context": {"request": {}}}])
def test_an_event_without_a_request_passes_through(shape):
    assert redact_event(dict(shape), strict=True) == shape


def test_the_processor_runs_on_transactions_and_errors_only():
    processor = make_processor(strict=True)
    assert processor.event_types == {"transaction", "error"} == set(EVENT_TYPES)
    assert SECRET not in repr(processor(None, event()))


def test_the_client_class_always_loads_the_processor():
    pytest.importorskip("elasticapm")
    processor = make_processor()
    cls = private_client_class(processor, ignore_url=lambda u: "/skip/" in u)
    client = cls(
        {
            "SERVICE_NAME": "t",
            "SERVER_URL": "http://127.0.0.1:1",
            "ENABLED": False,
            "PROCESSORS": [],
        }
    )
    try:
        assert client.load_processors()[-1] is processor
        assert client.should_ignore_url("/api/skip/1")
        assert not client.should_ignore_url("/api/keep/1")
    finally:
        client.close()
