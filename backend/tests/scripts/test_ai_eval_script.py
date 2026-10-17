"""The AI eval runner (scripts/ai_eval.py) without any real provider: the
replay mode, the live gate, the prompts file and the live loop driven by a
fake provider (``run_live`` is called directly, never through the gate)."""

import argparse
import json

import pytest

from backend.app.services.ai.usage import record_tokens
from backend.config import settings
from scripts import ai_eval


def _args(**overrides) -> argparse.Namespace:
    values = dict(
        out=None,
        live=False,
        prompts=str(ai_eval.DEFAULT_PROMPTS),
        provider=None,
        only=[],
        limit=None,
        ignore_limits=False,
        token_budget=None,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def test_ai_eval_replay_writes_both_reports(tmp_path):
    out = tmp_path / "report"
    assert ai_eval.main(["--out", str(out)]) == 0

    report = json.loads((out / "report.json").read_text())
    fixtures = ai_eval.load_fixtures()
    assert report["mode"] == "replay"
    assert len(report["results"]) == len(fixtures) >= 20
    by_name = {r["name"]: r for r in report["results"]}
    for case in fixtures:
        result = by_name[case["name"]]
        if case.get("expect_invalid"):
            assert result["status"] == "unusable_reply"
            continue
        assert sorted(f["code"] for f in result["findings"]) == sorted(
            case["expected_findings"]
        )
    summary = report["summary"]
    assert summary["cases"] == len(fixtures)
    assert summary["passed"] <= summary["scored"] < summary["cases"]
    assert summary["tokens"] is None

    table = (out / "report.md").read_text()
    assert "| Case | Kind | Lang | Status | Score | Findings | Tokens | Latency (s) |" in table
    for case in fixtures:
        assert f"| {case['name']} |" in table
    # names, codes and numbers only: no reply text
    assert "What is your email address?" not in table + json.dumps(report)


def test_ai_eval_replay_selects_cases(tmp_path):
    assert ai_eval.main(
        ["--out", str(tmp_path), "--only", "gen_en_good_feedback", "--only", "gen_nl_short_form"]
    ) == 0
    names = [r["name"] for r in json.loads((tmp_path / "report.json").read_text())["results"]]
    assert names == ["gen_en_good_feedback", "gen_nl_short_form"]
    assert ai_eval.main(["--out", str(tmp_path), "--only", "nope"]) == 2


@pytest.mark.parametrize("allow", [None, "", "0", "yes", "true"])
def test_ai_eval_live_needs_the_flag_and_the_env_var(tmp_path, monkeypatch, allow):
    if allow is None:
        monkeypatch.delenv(ai_eval.ALLOW_LIVE_ENV, raising=False)
    else:
        monkeypatch.setenv(ai_eval.ALLOW_LIVE_ENV, allow)

    def no_provider(*_):
        raise AssertionError("a provider was built")

    monkeypatch.setattr(ai_eval, "_provider", no_provider)
    out = tmp_path / "live"
    assert ai_eval.main(["--live", "--out", str(out)]) == 2
    assert not out.exists()


def test_ai_eval_never_writes_into_the_repository(tmp_path):
    inside = ai_eval.BACKEND_DIR / "ai-eval-report"
    assert ai_eval.main(["--out", str(inside)]) == 2
    assert ai_eval.main(["--out", str(ai_eval.REPO_ROOT)]) == 2
    assert not inside.exists()


def test_ai_eval_prompts_cover_languages_lengths_and_theme_requests():
    prompts = ai_eval.load_prompts(ai_eval.DEFAULT_PROMPTS)
    assert len(prompts) >= 25
    assert {p["language"] for p in prompts} == {"en", "nl"}
    assert {p["kind"] for p in prompts} == {"generate", "chat"}
    themed = [p for p in prompts if p.get("theme_requested")]
    assert any("Plain" in p["prompt"] for p in themed if p["language"] == "en")
    assert any("Plain" in p["prompt"] for p in themed if p["language"] == "nl")
    assert any(p.get("max_questions") for p in prompts if p["language"] == "en")
    assert any(p.get("max_questions") for p in prompts if p["language"] == "nl")
    assert all("base_form" in p for p in prompts if p["kind"] == "chat")


def test_ai_eval_prompts_file_is_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_eval, "FIXTURES", tmp_path)
    bad = tmp_path / "prompts.json"
    bad.write_text(json.dumps({"prompts": [{"name": "a", "kind": "chat", "prompt": "x"}]}))
    with pytest.raises(ai_eval.EvalError):
        ai_eval.load_prompts(bad)
    bad.write_text(
        json.dumps({"prompts": [{"name": "a", "kind": "generate", "prompt": "x"}] * 2})
    )
    with pytest.raises(ai_eval.EvalError):
        ai_eval.load_prompts(bad)


def test_ai_eval_prompts_must_be_inside_the_fixtures(tmp_path):
    outside = tmp_path / "prompts.json"
    outside.write_text(ai_eval.DEFAULT_PROMPTS.read_text(encoding="utf-8"))
    traversal = ai_eval.FIXTURES / ".." / ".." / ".." / "pyproject.toml"
    for path in (outside, traversal, ai_eval.FIXTURES, ai_eval.FIXTURES / "missing.json"):
        with pytest.raises(ai_eval.EvalError):
            ai_eval.prompts_path(str(path))
        with pytest.raises(ai_eval.EvalError):
            ai_eval.load_prompts(path)
    assert ai_eval.prompts_path(str(ai_eval.DEFAULT_PROMPTS)) == (
        ai_eval.DEFAULT_PROMPTS.resolve()
    )


def test_ai_eval_prompts_symlink_out_of_the_fixtures_is_refused(tmp_path, monkeypatch):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    secret = tmp_path / "elsewhere.json"
    secret.write_text(json.dumps({"prompts": []}))
    (fixtures / "link.json").symlink_to(secret)
    (fixtures / "real.json").write_text(json.dumps({"prompts": []}))
    monkeypatch.setattr(ai_eval, "FIXTURES", fixtures)
    with pytest.raises(ai_eval.EvalError):
        ai_eval.prompts_path(str(fixtures / "link.json"))
    assert ai_eval.prompts_path(str(fixtures / "real.json")) == (fixtures / "real.json").resolve()


@pytest.mark.parametrize("live", [False, True])
def test_ai_eval_main_refuses_prompts_outside_the_fixtures(tmp_path, monkeypatch, live):
    monkeypatch.setenv(ai_eval.ALLOW_LIVE_ENV, "1")

    def no_provider(*_):
        raise AssertionError("a provider was built")

    monkeypatch.setattr(ai_eval, "_provider", no_provider)
    outside = tmp_path / "prompts.json"
    outside.write_text(ai_eval.DEFAULT_PROMPTS.read_text(encoding="utf-8"))
    out = tmp_path / "report"
    argv = ["--out", str(out), "--prompts", str(outside)] + (["--live"] if live else [])
    assert ai_eval.main(argv) == 2
    assert not out.exists()


def test_ai_eval_help_warns_against_live_runs_on_production(capsys):
    with pytest.raises(SystemExit):
        ai_eval.parse_args(["--help"])
    assert "Never run --live on a production host." in capsys.readouterr().out


class _FakeProvider:
    """Answers with golden replies and reports tokens like a real one."""

    def __init__(self):
        fixtures = {f["name"]: f for f in ai_eval.load_fixtures()}
        # generation is outline-first: the outline call asks for its schema
        self.outline = json.dumps(fixtures["outline_en_good_feedback"]["reply"])
        self.turn = json.dumps(fixtures["chat_en_make_it_short"]["reply"])
        self.calls = 0

    async def outline_reply(self):
        await record_tokens(1000)
        return self.outline

    async def chat(
        self, system, messages, *, max_output_tokens=None, json_mode=False, json_schema=None
    ):
        self.calls += 1
        if json_schema is not None:
            return await self.outline_reply()
        await record_tokens(400)
        return self.turn


@pytest.fixture
def fake_provider(monkeypatch):
    provider = _FakeProvider()
    monkeypatch.setattr(ai_eval, "_provider", lambda name: ("fake", "fake-model", provider))
    # run_live may set the token budget: restored after the test
    monkeypatch.setattr(settings.ai, "DAILY_TOKEN_BUDGET", 0)
    monkeypatch.setattr(settings.ai, "DAILY_REQUEST_BUDGET", 0)
    monkeypatch.setattr(settings.ai, "RATE_LIMIT_PER_USER", 0)
    monkeypatch.setattr(settings.ai, "RATE_LIMIT_PER_WORKSPACE", 0)
    return provider


def _cases(*names):
    prompts = {p["name"]: p for p in ai_eval.load_prompts(ai_eval.DEFAULT_PROMPTS)}
    return [prompts[n] for n in names]


async def test_ai_eval_live_loop_scores_counts_tokens_and_times(fake_provider):
    cases = _cases("en_feedback_bakery", "en_plain_theme", "chat_en_make_it_short")
    report = await ai_eval.run_live(cases, _args(live=True))

    assert report["provider"] == "fake" and report["limits"] == "applied"
    first, themed, chat = report["results"]
    assert (first["status"], first["score"], first["findings"]) == ("ok", 100, [])
    assert first["tokens"] == 1000
    assert [f["code"] for f in themed["findings"]] == ["theme_request_ignored"]
    assert chat["kind"] == "chat" and chat["tokens"] == 400
    assert chat["failed_ops"] == 1
    assert all(r["latency_s"] >= 0 for r in report["results"])
    assert fake_provider.calls == 3


async def test_ai_eval_live_loop_stops_at_the_daily_budget(fake_provider, monkeypatch):
    monkeypatch.setattr(settings.ai, "DAILY_REQUEST_BUDGET", 2)
    cases = _cases("en_feedback_bakery", "en_nps", "en_appointment", "nl_contact_simple")
    report = await ai_eval.run_live(cases, _args(live=True))
    assert [r["status"] for r in report["results"]] == [
        "ok",
        "ok",
        "skipped_ai_daily_limit",
        "skipped_ai_daily_limit",
    ]
    assert fake_provider.calls == 2


async def test_ai_eval_live_loop_token_budget_and_ignoring_limits(fake_provider):
    cases = _cases("en_feedback_bakery", "en_nps", "en_appointment")
    report = await ai_eval.run_live(cases, _args(live=True, token_budget=1500))
    assert [r["status"] for r in report["results"]] == [
        "ok",
        "ok",
        "skipped_ai_daily_limit",
    ]

    fake_provider.calls = 0
    report = await ai_eval.run_live(
        cases, _args(live=True, token_budget=1500, ignore_limits=True)
    )
    assert report["limits"] == "ignored"
    assert [r["status"] for r in report["results"]] == ["ok", "ok", "ok"]
    assert fake_provider.calls == 3


async def test_ai_eval_live_loop_reports_provider_errors_by_code(fake_provider):
    from backend.app.services.ai.errors import ai_timeout

    async def times_out():
        await record_tokens(10)
        raise ai_timeout()

    fake_provider.outline_reply = times_out
    report = await ai_eval.run_live(_cases("en_nps"), _args(live=True))
    (result,) = report["results"]
    assert result["status"] == "ai_timeout"
    assert result["score"] is None and result["tokens"] == 10
