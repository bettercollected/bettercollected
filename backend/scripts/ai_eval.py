"""AI form quality eval: generation and chat edits, scored by the checker.

Two modes, both writing ``report.json`` and ``report.md`` (per case: quality
score, findings, tokens, latency) into ``--out``, a directory outside the
repository:

- **Replay (default, no provider):** the golden replies in
  ``tests/fixtures/ai_evals/`` through the real pipeline. ``backend/.env`` is
  not loaded, so no provider key is ever read.
- **Live (opt-in, never in CI):** the prompts in ``prompts.json`` against the
  configured provider. Runs only with ``--live`` AND ``AI_EVAL_ALLOW_LIVE=1``;
  it sends the synthetic prompts (nothing else) to the provider and costs
  tokens. ``--prompts`` must name a file inside ``tests/fixtures/ai_evals/``.

The live run goes through the same AI limits as the app
(``services/ai/usage.AIUsageGuard``, counted in memory for one run): the
per-user and per-workspace windows (it waits out ``ai_rate_limited``) and the
daily request and token budgets (it stops at ``ai_daily_limit``).
``--ignore-limits`` skips them for this run only; ``--token-budget`` caps the
run's tokens.

From backend/:
    uv run python -m scripts.ai_eval --out /tmp/ai-eval
    AI_EVAL_ALLOW_LIVE=1 uv run python -m scripts.ai_eval --live --out /tmp/ai-eval \\
        [--provider openai|google|compatible] [--only NAME ...] [--limit N]

The report names cases, codes and ids; it never contains a model reply.
"""

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
FIXTURES = BACKEND_DIR / "tests" / "fixtures" / "ai_evals"
DEFAULT_PROMPTS = FIXTURES / "prompts.json"
ALLOW_LIVE_ENV = "AI_EVAL_ALLOW_LIVE"
# The run's stand-ins for the user and the workspace the AI limits count.
EVAL_WORKSPACE = "ai-eval"
EVAL_USER = "ai-eval"
KINDS = ("generate", "chat")


class EvalError(Exception):
    """A usage error: reported on stderr, exit status 2."""


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ai_eval",
        description="Score AI form generation and chat edits.",
    )
    parser.add_argument(
        "--out", required=True, help="directory for report.json and report.md (outside the repo)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=f"call the configured provider (also needs {ALLOW_LIVE_ENV}=1)",
    )
    parser.add_argument(
        "--prompts",
        default=str(DEFAULT_PROMPTS),
        help="live prompts file, inside tests/fixtures/ai_evals/",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "google", "compatible"),
        help="live provider (default: AI_DEFAULT_PROVIDER)",
    )
    parser.add_argument("--only", action="append", default=[], help="run only this case (repeatable)")
    parser.add_argument("--limit", type=int, help="run at most this many cases")
    parser.add_argument(
        "--ignore-limits",
        action="store_true",
        help="live: skip the AI rate limits and daily budget for this run",
    )
    parser.add_argument(
        "--token-budget",
        type=int,
        help="live: stop once the run has used this many tokens (default: AI_DAILY_TOKEN_BUDGET)",
    )
    return parser.parse_args(argv)


def output_dir(path: str) -> Path:
    out = Path(path).expanduser().resolve()
    if out == REPO_ROOT or REPO_ROOT in out.parents:
        raise EvalError("--out must be outside the repository: reports are never committed.")
    return out


def prompts_path(path: str) -> Path:
    """The real path of a prompts file inside FIXTURES; anything else (also
    through a symlink or ``..``) is refused."""
    fixtures = FIXTURES.resolve()
    try:
        resolved = Path(path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise EvalError(
            "--prompts must name an existing file in tests/fixtures/ai_evals/."
        ) from None
    if fixtures not in resolved.parents or not resolved.is_file():
        raise EvalError("--prompts must name a file in tests/fixtures/ai_evals/.")
    return resolved


def _select(cases: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    if args.only:
        known = {c["name"] for c in cases}
        unknown = sorted(set(args.only) - known)
        if unknown:
            raise EvalError(f"unknown case(s): {', '.join(unknown)}")
        cases = [c for c in cases if c["name"] in args.only]
    if args.limit is not None:
        cases = cases[: max(0, args.limit)]
    return cases


def load_fixtures() -> List[Dict[str, Any]]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(FIXTURES.glob("*.json"))
        if p.name != DEFAULT_PROMPTS.name
    ]


def load_prompts(path: Path) -> List[Dict[str, Any]]:
    prompts = json.loads(prompts_path(str(path)).read_text(encoding="utf-8"))["prompts"]
    names = set()
    fixtures = {f["name"]: f for f in load_fixtures()}
    for entry in prompts:
        name = entry.get("name")
        if not name or name in names:
            raise EvalError(f"prompt names must be present and unique ({name!r})")
        names.add(name)
        if entry.get("kind") not in KINDS or not entry.get("prompt"):
            raise EvalError(f"prompt {name}: needs a kind ({'|'.join(KINDS)}) and a prompt")
        if entry["kind"] == "chat":
            base = fixtures.get(entry.get("base_fixture") or "")
            if not base or "base_form" not in base:
                raise EvalError(f"prompt {name}: base_fixture must name a chat fixture")
            entry["base_form"] = base["base_form"]
    return prompts


# ---------------------------------------------------------------------------
# One case
# ---------------------------------------------------------------------------


def _result(case: Dict[str, Any], status: str, started: float, **extra) -> Dict[str, Any]:
    result = {
        "name": case["name"],
        "kind": case.get("kind", "generate"),
        "language": case.get("language"),
        "status": status,
        "score": None,
        "passed": False,
        "findings": [],
        "failed_ops": 0,
        "tokens": None,
        "latency_s": round(time.monotonic() - started, 2),
    }
    result.update(extra)
    return result


def _scored(case, form, raw, results, started, **extra) -> Dict[str, Any]:
    from backend.app.services.ai import eval_pipeline

    report = eval_pipeline.score(form, case, raw=raw).as_dict()
    return _result(
        case,
        "ok",
        started,
        score=report["score"],
        passed=report["passed"],
        findings=report["findings"],
        failed_ops=sum(1 for r in results if not r.ok),
        **extra,
    )


def replay_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """A golden reply through the pipeline (no provider)."""
    from backend.app.services.ai import eval_pipeline
    from backend.app.services.ai.structured import InvalidReply

    started = time.monotonic()
    try:
        if case["kind"] == "chat":
            form, results = eval_pipeline.chat_reply_to_form(case["base_form"], case["reply"])
            raw = None
        else:
            raw, form = eval_pipeline.generation_reply_to_form(case["reply"])
            results = []
    except InvalidReply:
        return _result(case, "unusable_reply", started)
    return _scored(case, form, raw, results, started)


class _MemoryCounters:
    """The rate limiter's counter store, in memory for one run."""

    def __init__(self):
        self._counts: Dict[str, int] = {}

    async def hit(self, counter_id: str, expires_at: Any, amount: int = 1) -> int:
        self._counts[counter_id] = self._counts.get(counter_id, 0) + amount
        return self._counts[counter_id]


def _provider(name: Optional[str]):
    from backend.app.services.google_ai_provider import GoogleAIFormProvider
    from backend.app.services.openai_compatible_provider import OpenAICompatibleFormProvider
    from backend.app.services.openai_provider import OpenAIFormProvider
    from backend.app.services.unsplash_service import UnsplashService
    from backend.config import settings

    name = name or settings.ai.DEFAULT_PROVIDER or "openai"
    if name == "openai":
        return name, settings.open_ai.MODAL, OpenAIFormProvider(UnsplashService())
    if name == "google":
        return name, settings.google_ai.MODEL, GoogleAIFormProvider(UnsplashService())
    if name == "compatible":
        if not settings.ai.COMPAT_BASE_URL:
            raise EvalError("AI_COMPAT_BASE_URL is not set.")
        return name, settings.ai.COMPAT_MODEL, OpenAICompatibleFormProvider()
    raise EvalError(f"unknown provider {name!r}")


async def _admit(guard) -> None:
    """One AI request under the app's limits: waits out a rate-limit
    window, raises ``AIError`` (``ai_daily_limit``) at the budget."""
    from backend.app.services.ai.errors import AIError

    while True:
        try:
            await guard.admit(EVAL_WORKSPACE, EVAL_USER)
            return
        except AIError as error:
            if error.code != "ai_rate_limited":
                raise
            wait = int((error.headers or {}).get("Retry-After") or 1)
            print(f"rate limited: waiting {wait}s", file=sys.stderr)
            await asyncio.sleep(wait)


async def live_case(case: Dict[str, Any], provider, guard) -> Dict[str, Any]:
    from common.models.standard_form import StandardForm

    from backend.app.services.ai import eval_pipeline
    from backend.app.services.ai.chat import UNUSABLE_CHAT_REPLY, _ChatTurnReply
    from backend.app.services.ai.errors import AIError
    from backend.app.services.ai.ops import apply_form_ops
    from backend.app.services.ai.prompt_builder import (
        build_chat_system_prompt,
        compose_generation_prompt,
        project_form,
    )
    from backend.app.services.ai.structured import chat_json
    from backend.app.services.ai.usage import bind_usage
    from backend.config import settings

    bind_usage(guard, EVAL_WORKSPACE)
    _, tokens_before = await guard.usage_today(EVAL_WORKSPACE)
    started = time.monotonic()

    async def tokens() -> int:
        _, tokens_after = await guard.usage_today(EVAL_WORKSPACE)
        return tokens_after - tokens_before

    try:
        if case["kind"] == "chat":
            base = StandardForm.model_validate(case["base_form"])
            system = build_chat_system_prompt(project_form(base), None)
            turn = await chat_json(
                provider,
                system,
                [{"role": "user", "content": case["prompt"]}],
                _ChatTurnReply,
                max_output_tokens=settings.ai.MAX_OUTPUT_TOKENS_CHAT,
                unusable_message=UNUSABLE_CHAT_REPLY,
            )
            form, results = apply_form_ops(base, turn._parsed_ops)
            raw = None
        else:
            raw = await provider.generate_form(
                compose_generation_prompt(case["prompt"], None, None)
            )
            form = eval_pipeline.form_from_generation(raw)
            results = []
    except AIError as error:
        return _result(case, error.code, started, tokens=await tokens())
    except Exception as error:  # noqa: BLE001 — reported by type, never by message
        return _result(case, type(error).__name__, started, tokens=await tokens())
    return _scored(case, form, raw, results, started, tokens=await tokens())


async def run_live(cases, args) -> Dict[str, Any]:
    from backend.app.services.ai.errors import AIError
    from backend.app.services.ai.usage import AIUsageGuard
    from backend.app.services.rate_limiter import FixedWindowRateLimiter
    from backend.config import settings

    if args.token_budget is not None:
        settings.ai.DAILY_TOKEN_BUDGET = max(0, args.token_budget)
    provider_name, model, provider = _provider(args.provider)
    guard = AIUsageGuard(FixedWindowRateLimiter(_MemoryCounters(), secret=EVAL_WORKSPACE))
    results = []
    stopped = None
    for number, case in enumerate(cases, start=1):
        if stopped:
            results.append(_result(case, "skipped_" + stopped, time.monotonic()))
            continue
        if not args.ignore_limits:
            try:
                await _admit(guard)
            except AIError as error:
                stopped = error.code
                results.append(_result(case, "skipped_" + stopped, time.monotonic()))
                continue
        print(f"[{number}/{len(cases)}] {case['name']}", file=sys.stderr)
        results.append(await live_case(case, provider, guard))
    return {
        "mode": "live",
        "provider": provider_name,
        "model": model,
        "limits": "ignored" if args.ignore_limits else "applied",
        "results": results,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def summarise(report: Dict[str, Any]) -> Dict[str, Any]:
    results = report["results"]
    scored = [r for r in results if r["score"] is not None]
    token_counts = [r["tokens"] for r in results if r["tokens"] is not None]
    return {
        "cases": len(results),
        "scored": len(scored),
        "passed": sum(1 for r in scored if r["passed"]),
        "mean_score": round(sum(r["score"] for r in scored) / len(scored), 1) if scored else None,
        "tokens": sum(token_counts) if token_counts else None,
        "latency_s": round(sum(r["latency_s"] for r in results), 2),
    }


def markdown(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# AI eval ({report['mode']})",
        "",
        f"- Run: {report['started_at']}",
    ]
    if report["mode"] == "live":
        lines.append(
            f"- Provider: {report['provider']} ({report['model']}), limits {report['limits']}"
        )
    lines += [
        f"- Cases: {summary['cases']}, scored {summary['scored']}, passed {summary['passed']}, "
        f"mean score {summary['mean_score']}",
        f"- Tokens: {summary['tokens'] if summary['tokens'] is not None else 'n/a'}, "
        f"latency {summary['latency_s']} s",
        "",
        "| Case | Kind | Lang | Status | Score | Findings | Tokens | Latency (s) |",
        "|---|---|---|---|---:|---|---:|---:|",
    ]
    for r in report["results"]:
        codes = ", ".join(f["code"] for f in r["findings"]) or "-"
        if r["failed_ops"]:
            codes += f" ({r['failed_ops']} op(s) failed)"
        lines.append(
            "| {name} | {kind} | {lang} | {status} | {score} | {codes} | {tokens} | {latency} |".format(
                name=r["name"],
                kind=r["kind"],
                lang=r["language"] or "-",
                status=r["status"],
                score="-" if r["score"] is None else r["score"],
                codes=codes,
                tokens="-" if r["tokens"] is None else r["tokens"],
                latency=r["latency_s"],
            )
        )
    return "\n".join(lines) + "\n"


def write_report(report: Dict[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out / "report.md").write_text(markdown(report), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = parse_args(argv)
        out = output_dir(args.out)
        prompts = prompts_path(args.prompts)
        if args.live and os.environ.get(ALLOW_LIVE_ENV) != "1":
            raise EvalError(
                f"--live calls a real AI provider and costs tokens: set {ALLOW_LIVE_ENV}=1 as well."
            )
        if not args.live and "backend.config" not in sys.modules:
            # Replay calls no provider: never load backend/.env and its keys.
            # It runs in the test suite's environment instead (CI's test-only
            # MASTER_ENCRYPTION_KEYSET, .github/workflows/ci.yml).
            if not os.environ.get("MASTER_ENCRYPTION_KEYSET"):
                raise EvalError(
                    "replay runs in the test environment and never reads backend/.env: "
                    "set MASTER_ENCRYPTION_KEYSET to CI's test value (.github/workflows/ci.yml)."
                )
            os.environ["DOTENV_PATH"] = os.devnull
            # the one setting without a default; replay searches no images
            os.environ.setdefault("UNSPLASH_ACCESS_KEY", "")
        started_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        if args.live:
            cases = _select(load_prompts(prompts), args)
            report = asyncio.run(run_live(cases, args))
        else:
            cases = _select(load_fixtures(), args)
            report = {"mode": "replay", "results": [replay_case(c) for c in cases]}
    except EvalError as error:
        print(f"ai_eval: {error}", file=sys.stderr)
        return 2
    report = {"started_at": started_at, **report}
    report["summary"] = summarise(report)
    write_report(report, out)
    print(f"ai_eval: wrote {out / 'report.json'} and {out / 'report.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
