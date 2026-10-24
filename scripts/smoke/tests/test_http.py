import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from smoke.checks import (
    api_urls,
    forms_base_from,
    is_local,
    public_config,
    same_site,
    script_paths,
)
from smoke.http import Http, HttpError

SECRET_BODY = {"code": "rate_limited", "message": "secret answer AB1-2CD"}


class Handler(BaseHTTPRequestHandler):
    plan = []
    seen = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        Handler.seen.append((self.path, self.headers.get("Authorization")))
        status, headers, body = Handler.plan.pop(0)
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    Handler.plan, Handler.seen = [], []
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_a_short_429_is_waited_out_once(server):
    Handler.plan = [(429, {"Retry-After": "2"}, SECRET_BODY), (200, {}, {"ok": True})]
    naps = []
    reply = Http(server, headers={"Authorization": "Bearer x"}, sleep=naps.append).get(
        "/forms"
    )
    assert reply.body == {"ok": True}
    assert naps == [3]
    assert len(Handler.seen) == 2


def test_no_retry_storm(server):
    Handler.plan = [(429, {"Retry-After": "2"}, SECRET_BODY)] * 2
    with pytest.raises(HttpError) as error:
        Http(server, sleep=lambda s: None).get("/forms")
    assert error.value.status == 429 and len(Handler.seen) == 2
    Handler.plan, Handler.seen = [(429, {"Retry-After": "600"}, SECRET_BODY)], []
    with pytest.raises(HttpError):
        Http(server, sleep=lambda s: pytest.fail("must not wait 10 minutes")).get(
            "/forms"
        )
    assert len(Handler.seen) == 1


def test_errors_carry_status_and_code_never_the_body_or_query(server):
    Handler.plan = [(403, {}, {"code": "missing_scope", "message": "AB1-2CD secret"})]
    with pytest.raises(HttpError) as error:
        Http(server).get("/forms?token=abc")
    text = str(error.value)
    assert text == "GET /forms answered 403 (missing_scope)"


def test_public_config_and_forms_host():
    script = 'window.PUBLIC_CONFIG = {"FORM_DOMAIN":"forms.example.com","HTTP_SCHEME":"https://","X":null}\n'
    values = public_config(script)
    assert values == {"FORM_DOMAIN": "forms.example.com", "HTTP_SCHEME": "https://"}
    assert (
        forms_base_from(values, "https://admin.example.com")
        == "https://forms.example.com"
    )
    assert (
        forms_base_from({}, "https://admin.example.com") == "https://admin.example.com"
    )
    hostile = {"FORM_DOMAIN": "evil.example/path?x", "HTTP_SCHEME": "javascript:"}
    assert (
        forms_base_from(hostile, "https://admin.example.com")
        == "https://admin.example.com"
    )
    assert public_config("nothing") == {}


def test_is_local():
    assert is_local("http://localhost:3000") and is_local("http://127.0.0.1:8000/api")
    assert not is_local("https://admin.example.com")


def test_api_address_from_the_app_scripts():
    html = (
        '<script src="/_next/static/chunks/a1.js" async=""></script>'
        '<script src="https://cdn.example.net/x.js"></script>'
        '<link rel="preload" href="/_next/static/chunks/a1.js"/>'
        '<script src="/_next/static/chunks/app/layout-b2.js"></script>'
    )
    assert script_paths(html) == [
        "/_next/static/chunks/a1.js",
        "/_next/static/chunks/app/layout-b2.js",
    ]
    script = 'let e="https://api.example.com/api/v1",t=e+"/forms";fetch("http://localhost:8000/api/v1/x")'
    assert api_urls(script) == [
        "https://api.example.com/api/v1",
        "http://localhost:8000/api/v1",
    ]
    assert api_urls('"javascript:alert(1)/api/v1"') == []


def test_the_key_only_goes_to_the_apps_site():
    assert same_site("https://admin.example.com", "https://example.com/api/v1")
    assert same_site("https://admin.example.com", "https://api.example.com/api/v1")
    assert same_site("http://localhost:3000", "http://127.0.0.1:8000/api/v1")
    assert not same_site("https://admin.example.com", "https://example.net/api/v1")
    assert not same_site("https://admin.example.com", "https://localhost/api/v1")
