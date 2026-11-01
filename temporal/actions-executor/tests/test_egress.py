"""Where the executor may send a run's data (utilities/egress.py): a creator's
address never reaches an internal service, whatever its spelling, and a name
that changes its answer between the check and the connection reaches nothing
else."""

import http.server
import threading

import pytest

from utilities import egress
from utilities.egress import EgressRefused


def refused(code, call, *args, **kwargs):
    with pytest.raises(EgressRefused) as raised:
        call(*args, **kwargs)
    assert raised.value.code == code, raised.value.code
    return raised.value


@pytest.mark.parametrize(
    "address",
    [
        "8.8.8.8",
        "93.184.216.34",
        "2606:4700:4700::1111",
        "::ffff:8.8.8.8",
    ],
)
def test_public_addresses_are_public(address):
    assert egress.is_public_address(address)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",  # the cloud metadata address
        "100.64.0.1",  # carrier-grade NAT
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "fd00:ec2::254",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "2002:7f00:1::",  # 6to4 of 127.0.0.1
        "64:ff9b::7f00:1",  # NAT64 of 127.0.0.1
        "2001:0:4136:e378:8000:63bf:3fff:fdd2",  # Teredo
        "not an address",
    ],
)
def test_internal_addresses_are_not(address):
    assert not egress.is_public_address(address)


def test_an_ordinary_https_address_passes_the_syntax_check():
    d = egress.check_url("https://Hooks.Example.org/a/b?x=1#frag")
    assert (d.scheme, d.host, d.port, d.exempt) == (
        "https",
        "hooks.example.org",
        443,
        False,
    )
    assert d.url == "https://hooks.example.org/a/b?x=1"  # no fragment


@pytest.mark.parametrize(
    "url, code",
    [
        ("http://hooks.example.org/", "not_https"),
        ("ftp://hooks.example.org/", "not_https"),
        ("file:///etc/passwd", "not_https"),
        ("gopher://hooks.example.org/", "not_https"),
        ("https://hooks.example.org:8443/", "invalid_url"),
        ("https://user:pw@hooks.example.org/", "invalid_url"),
        ("https://hooks.example.org@evil.example/", "invalid_url"),
        ("https://127.0.0.1/", "invalid_url"),
        ("https://[::1]/", "invalid_url"),
        ("https://2130706433/", "invalid_url"),  # 127.0.0.1 as a number
        ("https://0x7f.1/", "invalid_url"),
        ("https://0177.0.0.1/", "invalid_url"),
        ("https://localhost/", "not_allowed"),  # resolves (patched) but see below
        ("https://hooks.example.org/\r\nHost: x", "invalid_url"),
        ("https://hooks.example.org/a b", "invalid_url"),
        ("https://hooks.example.org/\\evil", "invalid_url"),
        ("https:///path", "invalid_url"),
        ("", "invalid_url"),
        (None, "invalid_url"),
        (12, "invalid_url"),
        ("https://" + "a" * 3000 + ".example/", "invalid_url"),
    ],
)
def test_addresses_are_refused_by_their_syntax(url, code, monkeypatch):
    if url == "https://localhost/":
        # a plain name: the syntax passes, the answer decides
        monkeypatch.setattr(egress, "resolve", lambda host, port: ["127.0.0.1"])
        destination = egress.check_url(url)
        refused("not_allowed", egress.checked_address, destination)
        return
    refused(code, egress.check_url, url)


def test_every_answer_must_be_public(monkeypatch):
    destination = egress.check_url("https://hooks.example.org/")
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["8.8.8.8", "10.0.0.5"])
    refused("not_allowed", egress.checked_address, destination)
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["8.8.8.8", "1.1.1.1"])
    assert egress.checked_address(destination) == "8.8.8.8"
    monkeypatch.setattr(egress, "resolve", lambda h, p: [])
    refused("unreachable", egress.checked_address, destination)

    def broken(host, port):
        raise OSError("no such host")

    monkeypatch.setattr(egress, "resolve", broken)
    refused("unreachable", egress.checked_address, destination)


def test_an_internal_name_set_by_the_operator_may_be_called(monkeypatch):
    allow = egress.parse_allow("Hooks.Internal, relay.internal:2525 ,")
    assert allow == [("hooks.internal", None), ("relay.internal", 2525)]
    d = egress.check_url("http://hooks.internal/x", allow=allow)
    assert d.exempt and d.scheme == "http"
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["10.1.2.3"])
    assert egress.checked_address(d) == "10.1.2.3"
    # only the entry's host (and port), nothing next to it
    refused("not_https", egress.check_url, "http://other.internal/x", allow=allow)
    refused(
        "invalid_url", egress.check_url, "https://hooks.internal:9999/", allow=allow
    )
    d = egress.check_url("https://relay.internal:2525/", allow=allow)
    assert d.exempt


def test_the_origins_of_the_action_itself_are_trusted_not_the_host():
    origins = egress.trusted_origins_of(
        [
            "https://Hooks.Corp.Example/path",
            "plain text",
            5,
            None,
            "587",
            "http://a.b:81/",
            "ftp://c.d/",
        ]
    )
    assert origins == [
        ("https", "hooks.corp.example", 443),
        ("http", "a.b", 81),
    ]
    assert egress.trusted_hosts_of(["https://Hooks.Corp.Example/p"]) == [
        "hooks.corp.example"
    ]
    d = egress.check_url("https://hooks.corp.example/x", trusted=origins)
    assert d.exempt
    assert not egress.check_url("https://other.example/x", trusted=origins).exempt
    # the same host on another scheme or port is not what the administrators set
    refused(
        "not_https", egress.check_url, "http://hooks.corp.example/x", trusted=origins
    )
    refused(
        "invalid_url",
        egress.check_url,
        "https://hooks.corp.example:8443/x",
        trusted=origins,
    )
    assert egress.check_url("http://a.b:81/x", trusted=origins).exempt
    refused("not_https", egress.check_url, "http://a.b:82/x", trusted=origins)


def test_smtp_destinations(monkeypatch):
    egress.check_smtp("smtp.acme.example", 587)  # public (patched), a submission port
    egress.check_smtp("smtp.acme.example", "465")
    refused("not_allowed", egress.check_smtp, "smtp.acme.example", 22)
    refused("not_allowed", egress.check_smtp, "smtp.acme.example", 6379)
    refused("invalid_url", egress.check_smtp, "10.0.0.5", 25)
    refused("invalid_url", egress.check_smtp, "smtp.acme.example/x", 25)
    refused("invalid_url", egress.check_smtp, "user@smtp.acme.example", 25)
    refused("invalid_url", egress.check_smtp, "smtp.acme.example", "x")
    refused("invalid_url", egress.check_smtp, None, 25)
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["10.0.0.5"])
    refused("not_allowed", egress.check_smtp, "mail.acme.example", 587)
    # the instance's own settings are not judged; nor is an operator's entry
    egress.check_smtp("mailhog", 1025, trusted=True)
    egress.check_smtp("relay.internal", 25, allow=[("relay.internal", None)])
    refused(
        "not_allowed",
        egress.check_smtp,
        "relay.internal",
        25,
        allow=[("relay.internal", 2525)],
    )


# ---- the real call, against a local server --------------------------------


class _Handler(http.server.BaseHTTPRequestHandler):
    seen = []
    behaviour = "ok"

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        _Handler.seen.append(
            {"path": self.path, "headers": dict(self.headers), "body": body}
        )
        if _Handler.behaviour == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
            self.end_headers()
            return
        payload = b"x" * 200_000 if _Handler.behaviour == "big" else b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    _Handler.seen = []
    _Handler.behaviour = "ok"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    thread.join(5)


def test_the_call_connects_to_the_address_that_was_checked(local_server, monkeypatch):
    # the name resolves (as checked) to 127.0.0.1, which the operator allowed for
    # this name and port: the request goes there with the NAME in Host
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["127.0.0.1"])
    allow = [("hooks.internal", local_server)]
    reply = egress.post(
        f"http://hooks.internal:{local_server}/in?x=1",
        params={"a": "b c"},
        json_body={"k": "v"},
        headers={"X-Token": "abc", "Content-Type": "application/json"},
        allow=allow,
    )
    assert reply.status_code == 200 and reply.text == '{"ok": true}'
    seen = _Handler.seen[0]
    assert seen["path"] == "/in?x=1&a=b+c"
    assert seen["body"] == b'{"k": "v"}'
    assert seen["headers"]["Host"] == f"hooks.internal:{local_server}"
    sent = {name.lower(): value for name, value in seen["headers"].items()}
    assert sent["x-token"] == "abc"
    assert sent["content-type"] == "application/json"
    assert sent["user-agent"] == egress.USER_AGENT


def test_a_form_body_and_the_forbidden_headers(local_server, monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["127.0.0.1"])
    allow = [("hooks.internal", local_server)]
    egress.post(
        f"http://hooks.internal:{local_server}/",
        form={"a": 1, "b": "x y"},
        allow=allow,
    )
    assert _Handler.seen[0]["body"] == b"a=1&b=x+y"
    for header in (
        {"Host": "evil"},
        {"Content-Length": "1"},
        {"X": "a\r\nB: c"},
        {"bad name": "x"},
    ):
        refused(
            "invalid_url",
            egress.post,
            f"http://hooks.internal:{local_server}/",
            headers=header,
            allow=allow,
        )


def test_a_redirect_is_never_followed(local_server, monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["127.0.0.1"])
    _Handler.behaviour = "redirect"
    refused(
        "redirect_refused",
        egress.post,
        f"http://hooks.internal:{local_server}/",
        json_body={},
        allow=[("hooks.internal", local_server)],
    )
    assert len(_Handler.seen) == 1


def test_a_big_reply_is_cut_and_a_big_body_refused(local_server, monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["127.0.0.1"])
    allow = [("hooks.internal", local_server)]
    _Handler.behaviour = "big"
    reply = egress.post(
        f"http://hooks.internal:{local_server}/", json_body={}, allow=allow
    )
    assert len(reply.content) <= egress.MAX_REPLY_BYTES
    refused(
        "too_large",
        egress.post,
        f"http://hooks.internal:{local_server}/",
        content=b"x" * (egress.MAX_BODY_BYTES + 1),
        allow=allow,
    )


def test_nothing_is_connected_to_when_the_answer_is_internal(monkeypatch):
    def no_connection(*args, **kwargs):
        raise AssertionError("a connection was attempted")

    monkeypatch.setattr(egress.PinnedBackend, "connect_tcp", no_connection)
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["10.0.0.5"])
    refused("not_allowed", egress.post, "https://hooks.example.org/", json_body={})
    monkeypatch.setattr(egress, "resolve", lambda h, p: ["169.254.169.254"])
    refused("not_allowed", egress.post, "https://hooks.example.org/", json_body={})


def test_the_name_is_resolved_at_every_call_so_a_rebind_is_caught(monkeypatch):
    answers = iter([["93.184.216.34"], ["10.0.0.5"]])
    monkeypatch.setattr(egress, "resolve", lambda h, p: next(answers))
    seen = []

    def connect(self, host, port, **kwargs):
        seen.append(host)
        raise egress.httpcore.ConnectError("stop here")

    # the socket layer under the pin: it is told the address, not the name
    monkeypatch.setattr(egress.httpcore.SyncBackend, "connect_tcp", connect)
    refused("unreachable", egress.post, "https://hooks.example.org/", json_body={})
    assert seen == ["93.184.216.34"]  # the checked address, not the name
    refused("not_allowed", egress.post, "https://hooks.example.org/", json_body={})
    assert seen == ["93.184.216.34"]


def test_the_pinned_backend_connects_only_to_its_own_host():
    backend = egress.PinnedBackend("hooks.example.org", "93.184.216.34")
    with pytest.raises(egress.httpcore.ConnectError):
        backend.connect_tcp("other.example.org", 443)
    with pytest.raises(egress.httpcore.ConnectError):
        backend.connect_unix_socket("/var/run/docker.sock")


def test_the_exact_addresses_of_the_action_itself():
    urls = egress.trusted_urls_of(
        [
            "https://Hooks.Corp.Example/in/abc?room=1",
            "https://hooks.corp.example:443/in/abc?room=1",  # the same address
            "https://a.example",  # no path is the root path
            "http://a.b:81/p",
            "plain text",
            5,
            None,
            "ftp://c.d/",
            "https://user:pw@d.example/x",  # userinfo is never an address
            "https://e.example/x#frag",  # nor is a fragment
        ]
    )
    assert urls == [
        ("https", "hooks.corp.example", 443, "/in/abc", "room=1"),
        ("https", "a.example", 443, "/", ""),
        ("http", "a.b", 81, "/p", ""),
    ]


@pytest.mark.parametrize(
    "url, same",
    [
        ("https://hooks.corp.example/in/abc?room=1", True),
        ("https://HOOKS.corp.example:443/in/abc?room=1", True),
        ("https://hooks.corp.example/in/abc", False),  # the query counts
        ("https://hooks.corp.example/in/abc?room=2", False),
        ("https://hooks.corp.example/in/other?room=1", False),  # the path counts
        ("https://hooks.corp.example/in/abc/?room=1", False),
        ("https://hooks.corp.example/in/../in/abc?room=1", False),  # as written
        ("https://hooks.corp.example/in/%61bc?room=1", False),  # as written
        ("http://hooks.corp.example/in/abc?room=1", False),
        ("https://hooks.corp.example:8443/in/abc?room=1", False),
    ],
)
def test_a_destination_is_the_configured_address_only_when_every_part_is(url, same):
    configured = egress.trusted_urls_of(["https://hooks.corp.example/in/abc?room=1"])
    destination = egress.check_url(
        url,
        trusted=[
            ("https", "hooks.corp.example", 443),
            ("http", "hooks.corp.example", 80),
            ("https", "hooks.corp.example", 8443),
        ],
    )
    assert (destination.exact in configured) is same
