"""The run's report: pass/fail, timings and test-workspace ids, nothing else.

Written as ``report.json`` and ``summary.md`` (the markdown is also appended
to ``$GITHUB_STEP_SUMMARY``, ready to paste on a release issue). Every string
goes through the redactor when it is written, so a code, token or address
that slipped into a detail never reaches a file.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from smoke.redact import Redactor

PASS = "pass"
FAIL = "fail"
SKIP = "skip"
SYMBOL = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}
MAX_DETAIL = 300


class Abort(Exception):
    """Stops the run: what follows cannot work, or would be unsafe. Raised in
    a check, it fails that check and still propagates."""


@dataclass
class CheckResult:
    number: str
    name: str
    status: str = PASS
    seconds: float = 0.0
    ids: Dict[str, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


class Report:
    def __init__(self, redactor: Redactor, target: str, run_tag: str) -> None:
        self.redactor = redactor
        self.target = target
        self.run_tag = run_tag
        self.started = dt.datetime.now(dt.timezone.utc)
        self.checks: List[CheckResult] = []
        self.cleanup: List[str] = []

    # -- recording -----------------------------------------------------------
    def check(self, number: str, name: str) -> "_Timer":
        result = CheckResult(number=number, name=name)
        self.checks.append(result)
        return _Timer(result, self.redactor)

    def note_cleanup(self, text: str) -> None:
        self.cleanup.append(self.redactor.scrub(text)[:MAX_DETAIL])

    @property
    def ok(self) -> bool:
        return all(c.status != FAIL for c in self.checks)

    # -- output ----------------------------------------------------------------
    def as_dict(self) -> dict:
        data = {
            "result": "pass" if self.ok else "fail",
            "target": self.target,
            "run": self.run_tag,
            "started": self.started.isoformat(timespec="seconds"),
            "checks": [
                {
                    "check": c.number,
                    "name": c.name,
                    "status": c.status,
                    "seconds": round(c.seconds, 1),
                    "ids": c.ids,
                    "notes": c.notes,
                }
                for c in self.checks
            ],
            "cleanup": self.cleanup,
        }
        return self.redactor.scrub_tree(data)

    def markdown(self) -> str:
        data = self.as_dict()
        lines = [
            f"### Smoke test: {data['result'].upper()}",
            "",
            f"Target `{data['target']}` · run `{data['run']}` · started {data['started']}",
            "",
            "| # | Check | Result | Time | Notes |",
            "|---|---|---|---|---|",
        ]
        for c in data["checks"]:
            ids = ", ".join(f"{k} `{v}`" for k, v in c["ids"].items())
            notes = "; ".join(n.replace("|", "/") for n in c["notes"])
            text = "; ".join(t for t in (notes, ids) if t)
            lines.append(
                f"| {c['check']} | {c['name']} | {SYMBOL.get(c['status'], c['status'])}"
                f" | {c['seconds']:.1f} s | {text} |"
            )
        if data["cleanup"]:
            lines += ["", "Cleanup: " + "; ".join(data["cleanup"])]
        return self.redactor.scrub("\n".join(lines) + "\n")

    def write(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "report.json").write_text(
            json.dumps(self.as_dict(), indent=2) + "\n"
        )
        markdown = self.markdown()
        (directory / "summary.md").write_text(markdown)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write(markdown)


class _Timer:
    """``with report.check(...) as c:`` times the check; an exception marks
    it failed with the exception's (scrubbed) message and is not re-raised."""

    def __init__(self, result: CheckResult, redactor: Redactor) -> None:
        self.result = result
        self.redactor = redactor
        self._start = 0.0

    def __enter__(self) -> "_Timer":
        self._start = time.monotonic()
        return self

    def __exit__(self, kind, error, traceback) -> bool:
        self.result.seconds = time.monotonic() - self._start
        if isinstance(error, Abort):
            self.fail(str(error))
            return False
        if isinstance(error, Exception):
            self.fail(f"{kind.__name__}: {error}")
            return True  # never propagate: the next check still runs
        return False

    # -- inside a check ---------------------------------------------------------
    def id(self, name: str, value: Optional[str]) -> None:
        if value:
            self.result.ids[name] = self.redactor.scrub(value)[:80]

    def note(self, text: str) -> None:
        self.result.notes.append(self.redactor.scrub(text)[:MAX_DETAIL])

    def fail(self, text: str) -> None:
        self.result.status = FAIL
        self.note(text)

    def skip(self, text: str) -> None:
        if self.result.status != FAIL:
            self.result.status = SKIP
        self.note(text)

    @property
    def failed(self) -> bool:
        return self.result.status == FAIL
