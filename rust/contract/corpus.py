"""The request corpus: one JSON file per route group, cases as data.

    {
      "group": "permissions",              # the BC_RUST_ROUTES name this file exercises
      "description": "...",
      "env": {"TOTP_ENABLED": "true"},     # set for BOTH servers; files with the same env share a run
      "python_env": {"SSO_ENABLED": "true"}, # set for the Python backend ONLY (a difference to look at on purpose)
      "store": {"SSO_ENABLED": true},      # rows written to the settings store the way the admin portal's writer
                                           # does (one-time import, signed and sealed); "@ENV:NAME" is the
                                           # value of that variable of the run (a throw-away secret)
      "tamper": [{"op": "value", "key": "SSO_ENABLED", "value": false}],   # then changed in the database
                                           # without signing again: "value", "blob" (a sealed secret),
                                           # "manifest_sig" (the signed manifest)
      "expect_start": "refused",           # both servers must refuse to start (no cases are sent)
      "defaults": {"served_by": "rust"},   # merged into every case
      "cases": [
        {
          "name": "person:{who}@{ws}",     # unique after expansion
          "method": "GET",
          "path": "/api/v1/workspaces/{ws.main}/permissions",
          "headers": {"Cookie": "Authorization={token.owner}"},
          "json": {...},                   # optional request body (sent as application/json)
          "body": "raw text",              # or a raw body
          "matrix": {"who": "@people", "ws": ["main", "other"]},   # cartesian product
          "served_by": "rust" | "python",  # optional: which side must have answered
          "db": {"tables": ["workspaces"], # optional: write case, see dbdiff.py
                 "ignore_columns": ["updated_at"]}
        }
      ]
    }

Placeholders in `name`, `path`, header values and bodies, filled from the
fixture the seeding wrote (seed.py) and from the matrix:

    {ws.NAME}            a workspace id            {token.NAME}   a throw-away token
    {person.NAME.id}     a person's id             {person.NAME.email}
    {NAME}               a matrix variable (matrix values may be "@people", "@workspaces", "@tokens")

A matrix variable is replaced first, so `{token.{who}}` works. A placeholder
that names nothing is an error. A token that the fixture holds as null (the
ring has no previous key) skips the case.
"""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")
SERVED_BY = {None, "rust", "python"}


class CorpusError(ValueError):
    pass


@dataclass
class Case:
    name: str
    method: str
    path: str
    headers: dict = field(default_factory=dict)
    body: Optional[bytes] = None
    served_by: Optional[str] = None
    db: Optional[dict] = None
    group: str = ""
    source: str = ""


@dataclass
class CorpusFile:
    path: str
    group: str
    description: str
    env: dict
    python_env: dict
    cases: list
    store: Optional[dict] = None  # None: the settings store is not touched (empty)
    tamper: list = field(default_factory=list)
    expect_start: Optional[str] = None


def _lookup(fixture: dict, dotted: str) -> Any:
    parts = dotted.split(".")
    roots = {
        "ws": fixture.get("workspaces", {}),
        "token": fixture.get("tokens", {}),
        "person": fixture.get("people", {}),
    }
    if parts[0] not in roots:
        raise CorpusError(f"unknown placeholder {{{dotted}}}")
    node: Any = roots[parts[0]]
    for part in parts[1:]:
        if not isinstance(node, dict) or part not in node:
            raise CorpusError(f"placeholder {{{dotted}}} names nothing in the fixture")
        node = node[part]
    return node


class _Skip(Exception):
    pass


def fill(text: str, fixture: dict, variables: dict) -> str:
    for name, value in variables.items():
        text = text.replace("{" + name + "}", str(value))

    def one(match: re.Match) -> str:
        value = _lookup(fixture, match.group(1))
        if value is None:
            raise _Skip()
        return str(value)

    return PLACEHOLDER.sub(one, text)


def _matrix_values(spec: Any, fixture: dict) -> list:
    if isinstance(spec, list):
        return spec
    if spec == "@people":
        return list(fixture.get("people", {}))
    if spec == "@workspaces":
        return list(fixture.get("workspaces", {}))
    if spec == "@tokens":
        return [k for k, v in fixture.get("tokens", {}).items() if v is not None]
    raise CorpusError(f"unknown matrix source {spec!r}")


def expand(entry: dict, defaults: dict, fixture: dict, group: str, source: str) -> list:
    merged = {**defaults, **entry}
    for key in ("name", "method", "path"):
        if key not in merged:
            raise CorpusError(f"{source}: a case has no {key}: {entry}")
    if merged.get("served_by") not in SERVED_BY:
        raise CorpusError(f"{source}: served_by must be rust or python in {merged['name']}")
    matrix = merged.get("matrix") or {}
    names = list(matrix)
    combos = itertools.product(*[_matrix_values(matrix[n], fixture) for n in names]) if names else [()]
    out = []
    for combo in combos:
        variables = dict(zip(names, combo))
        try:
            name = fill(merged["name"], fixture, variables)
            method = fill(merged["method"], fixture, variables).upper()
            path = fill(merged["path"], fixture, variables)
            headers = {k: fill(str(v), fixture, variables) for k, v in (merged.get("headers") or {}).items()}
            body = None
            if "json" in merged:
                body = fill(json.dumps(merged["json"]), fixture, variables).encode()
                headers.setdefault("Content-Type", "application/json")
            elif "body" in merged:
                body = fill(str(merged["body"]), fixture, variables).encode()
        except _Skip:
            continue
        out.append(
            Case(
                name=name,
                method=method,
                path=path,
                headers=headers,
                body=body,
                served_by=merged.get("served_by"),
                db=merged.get("db"),
                group=group,
                source=source,
            )
        )
    return out


def load_file(path: Path, fixture: dict) -> CorpusFile:
    raw = json.loads(path.read_text())
    group = raw.get("group")
    if not group or not re.fullmatch(r"[a-z][a-z0-9_-]*", group):
        raise CorpusError(f"{path.name}: group must be a lower-case name")
    cases = []
    for entry in raw.get("cases", []):
        cases.extend(expand(entry, raw.get("defaults") or {}, fixture, group, path.name))
    seen = set()
    for case in cases:
        if case.name in seen:
            raise CorpusError(f"{path.name}: two cases are named {case.name!r}")
        seen.add(case.name)
    # a null removes the variable from the run's environment (a stack that keeps it in the store only)
    env = {str(k): (None if v is None else str(v)) for k, v in (raw.get("env") or {}).items()}
    python_env = {str(k): str(v) for k, v in (raw.get("python_env") or {}).items()}
    store = raw.get("store")
    if store is not None and not isinstance(store, dict):
        raise CorpusError(f"{path.name}: store must be an object of key: value")
    tamper = raw.get("tamper") or []
    for step in tamper:
        if step.get("op") not in ("value", "blob", "manifest_sig") or (step["op"] != "manifest_sig" and "key" not in step):
            raise CorpusError(f"{path.name}: unknown tamper step {step}")
    expect_start = raw.get("expect_start")
    if expect_start not in (None, "refused"):
        raise CorpusError(f"{path.name}: expect_start can only be 'refused'")
    if expect_start and cases:
        raise CorpusError(f"{path.name}: a file that expects a refused start has no cases")
    if tamper and store is None:
        raise CorpusError(f"{path.name}: tamper needs a store")
    return CorpusFile(str(path), group, raw.get("description", ""), env, python_env, cases, store, tamper, expect_start)


def load_dir(directory: Path, fixture: dict, only_groups: Optional[set] = None) -> list:
    files = []
    for path in sorted(directory.glob("*.json")):
        corpus = load_file(path, fixture)
        if only_groups is None or corpus.group in only_groups:
            files.append(corpus)
    return files
