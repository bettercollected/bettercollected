"""Codes, tokens, cookies, addresses and mail contents never reach a report."""

import json

import pytest

from smoke.redact import Redactor
from smoke.report import Abort, Report
from tests.conftest import API_KEY, APP_PASSWORD, CLIENT_SECRET, REFRESH_TOKEN

CODE = "Q7X-4KD"
ADDRESS = "smoke+smoke-123-1-abcdef@gmail.com"
ACCESS_TOKEN = "ya29.a0AfB_fakeAccessTokenValue_0123456789"
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzbW9rZSJ9.c2lnbmF0dXJlLXZhbHVl"
FORBIDDEN = [
    CODE,
    ADDRESS,
    ACCESS_TOKEN,
    JWT,
    API_KEY,
    APP_PASSWORD,
    REFRESH_TOKEN,
    CLIENT_SECRET,
]
PATTERNED = [CODE, ADDRESS, ACCESS_TOKEN, JWT, API_KEY, REFRESH_TOKEN]


def leaky_report(tmp_path, registered: bool):
    redactor = Redactor()
    if registered:
        for value in (
            API_KEY,
            APP_PASSWORD,
            REFRESH_TOKEN,
            CLIENT_SECRET,
            ADDRESS,
            CODE,
        ):
            redactor.add(value)
    report = Report(redactor, "https://admin.example.com", "smoke-123-1-abcdef")
    with report.check("1", "Sign-in") as c:
        c.note(f"read code {CODE} for {ADDRESS}")
        c.id("session", JWT)
        raise RuntimeError(
            f"POST failed: Authorization: Bearer {API_KEY} cookie: access_token={JWT}"
        )
    with report.check("2", "Mailbox") as c:
        c.note(f"token {ACCESS_TOKEN} refresh {REFRESH_TOKEN} secret {CLIENT_SECRET}")
        c.note(f"password {APP_PASSWORD}")
    with report.check("3", "Fine") as c:
        c.id("form", "6add1ec59947c7bd75b36282")
    report.note_cleanup(f"deleted mail to {ADDRESS} with code {CODE}")
    report.write(tmp_path)
    return report


@pytest.mark.parametrize(
    "registered", [True, False], ids=["registered", "patterns-only"]
)
def test_nothing_secret_reaches_any_output(tmp_path, monkeypatch, registered):
    summary = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    report = leaky_report(tmp_path, registered)
    outputs = {
        "report.json": (tmp_path / "report.json").read_text(),
        "summary.md": (tmp_path / "summary.md").read_text(),
        "step summary": summary.read_text(),
        "markdown": report.markdown(),
    }
    # Without registration only the shapes the patterns know are caught; the
    # suite always registers the configured secrets and every code it reads.
    forbidden = FORBIDDEN if registered else PATTERNED
    for name, text in outputs.items():
        for value in forbidden:
            assert value not in text, f"{name} leaks a secret"


def test_the_report_keeps_what_it_is_for(tmp_path):
    leaky_report(tmp_path, registered=True)
    data = json.loads((tmp_path / "report.json").read_text())
    assert data["result"] == "fail"
    assert [c["status"] for c in data["checks"]] == ["fail", "pass", "pass"]
    assert data["checks"][2]["ids"] == {"form": "6add1ec59947c7bd75b36282"}
    assert all(isinstance(c["seconds"], float) for c in data["checks"])
    assert "RuntimeError" in data["checks"][0]["notes"][-1]
    assert data["cleanup"]


def test_a_failing_check_does_not_stop_the_next_but_abort_does():
    report = Report(Redactor(), "t", "r")
    with report.check("1", "one") as c:
        raise ValueError("boom")
    assert c.failed
    with pytest.raises(Abort):
        with report.check("2", "two"):
            raise Abort("stop here")
    assert report.checks[1].status == "fail"
    assert not report.ok


def test_skips_do_not_fail_the_run():
    report = Report(Redactor(), "t", "r")
    with report.check("6", "google") as c:
        c.skip("not offered")
    assert report.ok and report.checks[0].status == "skip"


def test_scrub_patterns():
    r = Redactor()
    assert r.scrub("code AB1-2CD.") == "code [code]."
    assert r.scrub("id 6add1ec59947c7bd75b36282") == "id 6add1ec59947c7bd75b36282"
    assert "bc_" not in r.scrub("key bc_" + "a" * 64)
    assert r.scrub("mail a.b+c@d.example") == "mail [address]"
    assert r.scrub_tree({"k AB1-2CD": ["x@y.org"]}) == {"k [code]": ["[address]"]}
    # short values are not registered (they would shred ordinary text)
    r.add("abc")
    assert r.scrub("abc") == "abc"
