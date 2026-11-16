"""How a Python answer and a Rust answer are compared.

"Equal" means equal after JSON parse: the same status code, the same headers
except the transport ones listed below, and, for a JSON body, the same parsed
value (key order and whitespace do not matter; message wording does, because a
client may match on it). Any other body must be byte-equal.

The ignore rules are the whole list. A new rule is a reviewed change to this
file, with the reason beside it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

# header name (lower case) -> why it is not compared
IGNORED_HEADERS = {
    "date": "a clock",
    "server": "names the server software",
    "connection": "transport",
    "keep-alive": "transport",
    "transfer-encoding": "transport: framing of the body, not content",
    "content-length": "follows from the body, which is compared (JSON may be spaced differently)",
    # set only when the Rust edge runs with BC_SERVED_BY_HEADER; the harness reads it
    "x-bc-served-by": "debug marker of the Rust edge",
}


@dataclass
class Answer:
    status: int
    headers: dict  # lower-case name -> list of values, in the order received
    body: bytes
    error: Optional[str] = None

    @property
    def served_by(self) -> Optional[str]:
        values = self.headers.get("x-bc-served-by")
        return values[0] if values else None


@dataclass
class Verdict:
    differences: list = field(default_factory=list)

    @property
    def equal(self) -> bool:
        return not self.differences


def _is_json(answer: Answer) -> bool:
    return any("json" in v.lower() for v in answer.headers.get("content-type", []))


def _parse(body: bytes):
    try:
        return True, json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False, None


def comparable_headers(headers: dict) -> dict:
    """Headers without the ignored ones; the values of one name are compared as
    a set of values (a name sent twice is the same as in another order)."""
    return {
        name: sorted(values)
        for name, values in headers.items()
        if name not in IGNORED_HEADERS
    }


def describe_json_difference(a, b, limit: int = 240) -> str:
    """The keys that differ when both are objects, else the two values, cut short."""
    if isinstance(a, dict) and isinstance(b, dict):
        parts = [
            f"{key}: {json.dumps(a.get(key))} != {json.dumps(b.get(key))}"
            for key in sorted(set(a) | set(b))
            if a.get(key) != b.get(key)
        ]
        return "; ".join(parts)[:limit]
    return f"{json.dumps(a)[: limit // 2]} != {json.dumps(b)[: limit // 2]}"


def compare(python: Answer, rust: Answer) -> Verdict:
    verdict = Verdict()
    if python.error or rust.error:
        if python.error:
            verdict.differences.append(f"python request failed: {python.error}")
        if rust.error:
            verdict.differences.append(f"rust request failed: {rust.error}")
        return verdict
    if python.status != rust.status:
        verdict.differences.append(f"status {python.status} != {rust.status}")
    a, b = comparable_headers(python.headers), comparable_headers(rust.headers)
    if a != b:
        for name in sorted(set(a) | set(b)):
            if a.get(name) != b.get(name):
                verdict.differences.append(f"header {name}: {a.get(name)} != {b.get(name)}")
    if _is_json(python) and _is_json(rust):
        ok_a, value_a = _parse(python.body)
        ok_b, value_b = _parse(rust.body)
        if ok_a and ok_b:
            if value_a != value_b:
                verdict.differences.append("json body: " + describe_json_difference(value_a, value_b))
            return verdict
    if python.body != rust.body:
        verdict.differences.append(f"body: {python.body[:160]!r} != {rust.body[:160]!r}")
    return verdict
