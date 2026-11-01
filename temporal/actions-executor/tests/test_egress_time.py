"""Bounded time: a destination that is slow, or that sends a byte every few
seconds, costs the run its own time and never the executor's. The whole call has
a deadline (not only each operation), and every blocking step of a built-in
action runs off the event loop."""

import asyncio
import http.server
import json
import threading
import time

import pytest

from settings.application import settings
from utilities import actions, egress


class _Slow(http.server.BaseHTTPRequestHandler):
    mode = "drip"
    delay = 0.0
    seen = 0

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        _Slow.seen += 1
        if _Slow.mode == "late":
            time.sleep(_Slow.delay)
        self.send_response(200)
        self.end_headers()
        if _Slow.mode == "drip":
            try:
                for _ in range(100):  # a byte every 0.3 s: each read is in time
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.3)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


@pytest.fixture
def slow_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Slow)
    server.daemon_threads = True
    _Slow.mode, _Slow.delay, _Slow.seen = "drip", 0.0, 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    thread.join(5)


def test_a_server_that_drips_its_reply_is_cut_off_at_the_deadline(
    slow_server, monkeypatch
):
    monkeypatch.setattr(egress, "resolve", lambda host, port: ["127.0.0.1"])
    monkeypatch.setattr(egress, "TOTAL_TIMEOUT_SECONDS", 1.0)
    started = time.monotonic()
    with pytest.raises(egress.EgressRefused) as refused:
        egress.post(
            f"http://hooks.internal:{slow_server}/",
            json_body={},
            allow=[("hooks.internal", slow_server)],
        )
    assert refused.value.code == "timeout"
    # the deadline, plus at most one drip: nowhere near the 30 s the drip would last
    assert time.monotonic() - started < 3


def test_the_deadline_is_a_property_of_the_call_not_of_the_next_read(monkeypatch):
    # a clock past the deadline refuses even when every read were instant
    monkeypatch.setattr(egress, "TOTAL_TIMEOUT_SECONDS", -1.0)
    monkeypatch.setattr(egress, "resolve", lambda host, port: ["127.0.0.1"])
    server = http.server.HTTPServer(("127.0.0.1", 0), _Slow)
    _Slow.mode = "late"
    _Slow.delay = 0.0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with pytest.raises(egress.EgressRefused) as refused:
            egress.post(
                f"http://hooks.internal:{port}/",
                json_body={},
                allow=[("hooks.internal", port)],
            )
        assert refused.value.code == "timeout"
    finally:
        server.shutdown()
        thread.join(5)


def hook_action():
    return {"id": "act-1", "name": "send_webhook", "predefined": True, "parameters": []}


def run_slow_action(port, ticker):
    form = {
        "builder_version": "v2",
        "form_id": "f1",
        "title": "Survey",
        "welcome_page": {"title": "Survey", "description": ""},
        "fields": [],
    }
    workspace = {
        "id": "w1",
        "title": "Acme",
        "workspace_name": "acme",
        "parameters": {
            "act-1": [
                {"name": "Webhook URL", "value": f"http://hooks.internal:{port}/in"}
            ]
        },
    }

    async def go():
        ticks = []

        async def tick():
            while True:
                ticks.append(time.monotonic())
                await asyncio.sleep(0.05)

        task = asyncio.ensure_future(tick())
        started = time.monotonic()
        try:
            await actions.run_action(
                json.dumps(hook_action()),
                json.dumps(form),
                json.dumps({"answers": {}}),
                workspace=json.dumps(workspace),
            )
        finally:
            task.cancel()
        return ticks, time.monotonic() - started

    return asyncio.run(go())


def test_a_slow_destination_does_not_stall_the_event_loop(slow_server, monkeypatch):
    monkeypatch.setattr(egress, "resolve", lambda host, port: ["127.0.0.1"])
    monkeypatch.setattr(
        settings, "action_egress_allow", f"hooks.internal:{slow_server}"
    )
    _Slow.mode, _Slow.delay = "late", 1.5
    ticks, took = run_slow_action(slow_server, None)
    assert _Slow.seen == 1 and took >= 1.4
    # the loop kept running the whole time the call waited: a tick every ~50 ms
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert len(ticks) > 15 and max(gaps) < 0.5


def test_a_slow_name_lookup_does_not_stall_the_event_loop(slow_server, monkeypatch):
    def slow_resolve(host, port):
        time.sleep(1.2)
        return ["127.0.0.1"]

    monkeypatch.setattr(egress, "resolve", slow_resolve)
    monkeypatch.setattr(
        settings, "action_egress_allow", f"hooks.internal:{slow_server}"
    )
    _Slow.mode, _Slow.delay = "late", 0.0
    ticks, took = run_slow_action(slow_server, None)
    assert took >= 1.1
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert max(gaps) < 0.5
