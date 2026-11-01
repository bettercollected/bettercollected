"""The broker's side of the contract: it sends code only to a child that
reported that it confined itself, ends a run on anything that is not the
protocol, and caps what a child says. The child here is a stand-in script, so
none of this depends on what the kernel allows."""

import asyncio
import json
import os
import sys

import pytest

from sandbox import broker

GOOD = {
    "arch": "x86_64",
    "rlimits": True,
    "unprivileged": True,
    "no_new_privs": True,
    "filesystem": "landlock",
    "seccomp": True,
}


def facts(**changes):
    out = dict(GOOD)
    out.update(changes)
    return {key: value for key, value in out.items() if value is not None}


@pytest.mark.parametrize(
    "report, missing",
    [
        (GOOD, []),
        (facts(seccomp=False), ["seccomp"]),
        (facts(seccomp=None), ["seccomp"]),
        (facts(no_new_privs=False), ["no_new_privs"]),
        (facts(rlimits=False), ["rlimits"]),
        (facts(unprivileged=False), ["unprivileged"]),
        (facts(filesystem="none"), ["filesystem"]),
        (facts(filesystem=None), ["filesystem"]),
        (facts(filesystem="chroot"), []),
        (facts(filesystem="chroot+landlock"), []),
        (
            {"error": "PermissionError"},
            [
                "confinement",
                "rlimits",
                "no_new_privs",
                "seccomp",
                "unprivileged",
                "filesystem",
            ],
        ),
        (facts(seccomp="yes"), ["seccomp"]),  # only a real True counts
    ],
)
def test_required_confinement(report, missing):
    assert broker.required_confinement(report, require_filesystem=True) == missing


def test_a_missing_filesystem_cut_is_only_tolerated_when_not_required():
    weak = facts(filesystem="none")
    assert broker.required_confinement(weak, require_filesystem=False) == []


FAKE_CHILD = """
import json, os, sys
marker = {marker!r}
facts = {facts!r}
sys.stdout.write(json.dumps({{"t": "ready", "facts": facts}}) + "\\n")
sys.stdout.flush()
line = sys.stdin.readline()
if line:
    open(marker, "w").write("code arrived")
sys.stdout.write(json.dumps({{"t": "done", "log": [], "error": None}}) + "\\n")
"""


def fake_child(monkeypatch, tmp_path, report=None, body=None):
    marker = tmp_path / "code-arrived"
    script = tmp_path / "fake_child.py"
    script.write_text(body or FAKE_CHILD.format(marker=str(marker), facts=report))
    monkeypatch.setattr(broker, "CHILD", str(script))
    return marker


def run(code="log('x')", **kwargs):
    kwargs.setdefault("timeout_seconds", 10)
    return asyncio.run(broker.run_code(code, {}, {}, **kwargs))


@pytest.mark.parametrize(
    "report",
    [
        facts(seccomp=False),
        facts(no_new_privs=False),
        facts(rlimits=False),
        facts(unprivileged=False),
        facts(filesystem="none"),
        {"error": "PermissionError"},
    ],
)
def test_the_broker_sends_no_code_to_a_child_that_is_not_confined(
    monkeypatch, tmp_path, report
):
    marker = fake_child(monkeypatch, tmp_path, report)
    with pytest.raises(broker.SandboxUnavailable) as refused:
        run("SECRET_CODE = 1")
    assert "not confined" in str(refused.value)
    assert not marker.exists()  # the run message never reached it


def test_a_confined_child_gets_its_code(monkeypatch, tmp_path):
    marker = fake_child(monkeypatch, tmp_path, GOOD)
    outcome = run()
    assert outcome.error is None and marker.exists()


def test_a_child_that_never_says_it_is_ready_is_refused(monkeypatch, tmp_path):
    fake_child(monkeypatch, tmp_path, body="import time\ntime.sleep(60)\n")
    monkeypatch.setattr(broker, "READY_TIMEOUT_SECONDS", 1)
    with pytest.raises((broker.SandboxUnavailable, asyncio.TimeoutError)):
        run()


def test_a_child_that_dies_at_start_is_refused(monkeypatch, tmp_path):
    fake_child(monkeypatch, tmp_path, body="import sys\nsys.exit(3)\n")
    with pytest.raises(broker.SandboxUnavailable):
        run()


CHATTY = """
import json, sys
sys.stdout.write(json.dumps({{"t": "ready", "facts": {facts!r}}}) + "\\n")
sys.stdout.flush()
sys.stdin.readline()
{after}
"""


def chatty(monkeypatch, tmp_path, after):
    fake_child(monkeypatch, tmp_path, body=CHATTY.format(facts=GOOD, after=after))


def test_a_line_nested_past_the_parser_ends_the_run_without_crashing_the_broker(
    monkeypatch, tmp_path
):
    chatty(
        monkeypatch,
        tmp_path,
        "sys.stdout.write('[' * 200000 + ']' * 200000 + '\\n')",
    )
    outcome = run()
    assert outcome.error["kind"] == "killed"


def test_a_line_that_is_not_json_or_not_the_protocol_ends_the_run(
    monkeypatch, tmp_path
):
    chatty(monkeypatch, tmp_path, "sys.stdout.write('not json\\n')")
    assert run().error["kind"] == "killed"
    chatty(monkeypatch, tmp_path, 'sys.stdout.write(\'{"t": "mystery"}\\n\')')
    assert run().error["kind"] == "killed"
    chatty(monkeypatch, tmp_path, "sys.stdout.write('[1, 2]\\n')")
    assert run().error["kind"] == "killed"


def test_what_the_child_reports_is_capped_by_the_broker(monkeypatch, tmp_path):
    done = {
        "t": "done",
        "log": ["x" * 3000] * 1500,
        "error": {"kind": "error", "class": "C" * 5000, "message": "m" * 50_000},
    }
    chatty(monkeypatch, tmp_path, f"sys.stdout.write({json.dumps(done)!r} + '\\n')")
    outcome = run()
    assert len(outcome.log) == broker.MAX_LOG_LINES
    assert all(len(line) <= broker.MAX_LOG_LINE for line in outcome.log)
    assert len(outcome.error["message"]) == broker.MAX_ERROR_MESSAGE
    assert len(outcome.error["class"]) == 100


def test_clean_error_and_clean_log_shape_anything():
    assert broker.clean_error(None) is None
    assert broker.clean_error("a string") == {"kind": "error", "message": ""}
    assert broker.clean_error({"kind": "made-up", "message": None}) == {
        "kind": "error",
        "message": "",
    }
    assert broker.clean_error({"kind": "http", "message": "m"})["kind"] == "http"
    assert broker.clean_log("not a list") == []
    assert broker.clean_log([1, None]) == ["1", "None"]


@pytest.mark.skipif(
    os.geteuid() != 0, reason="the chroot and user drop need a root start"
)
def test_started_as_root_the_child_changes_root_and_gives_up_root():
    # CI runs unprivileged and cannot reach this; it runs wherever the tests do
    # run as root (a root container, docs/executor-isolation.md)
    outcome = asyncio.run(broker.run_code("log('x')", {}, {}, timeout_seconds=20))
    assert "chroot" in outcome.facts["filesystem"]
    assert outcome.facts["unprivileged"] is True
