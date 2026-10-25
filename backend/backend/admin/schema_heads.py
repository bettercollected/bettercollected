"""The Alembic heads the deployed code expects for the other services' schemas.

The admin service runs from the backend image, which carries the backend's own
migrations and, copied in by ``backend/Dockerfile``, the ``versions``
directories of the auth service and the Google integration, at the same paths
as in the repository. The revision files are parsed (``ast``), never imported
or executed: only the literal ``revision`` and ``down_revision`` assignments are
read. A directory that is not there gives ``None`` (the page then shows the
expected head as unknown).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]

# schema -> the versions directory of the service that owns it
VERSIONS = {
    "app": ROOT / "backend" / "backend" / "migrations" / "versions",
    "auth": ROOT / "auth" / "auth" / "migrations" / "versions",
    "google": ROOT / "integrations" / "google" / "googleform" / "migrations" / "versions",
}


@dataclass(frozen=True)
class CodeRevisions:
    heads: tuple[str, ...]
    known: frozenset[str]


def _literal(node: Optional[ast.expr]) -> tuple[str, ...]:
    if node is None:
        return ()
    try:
        value = ast.literal_eval(node)
    except ValueError:
        return ()
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list)) and all(isinstance(v, str) for v in value):
        return tuple(value)
    return ()


def _assignments(path: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(revision, down_revisions) from one revision file's module-level assignments."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found[node.target.id] = _literal(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = _literal(node.value)
    return found.get("revision", ()), found.get("down_revision", ())


def parse_versions(directory: Path) -> Optional[CodeRevisions]:
    """Heads and every known revision of one versions directory, or ``None``."""
    if not directory.is_dir():
        return None
    known: set[str] = set()
    parents: set[str] = set()
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("__"):
            continue
        revision, down = _assignments(path)
        if len(revision) != 1:
            continue
        known.add(revision[0])
        parents.update(down)
    if not known:
        return None
    return CodeRevisions(tuple(sorted(known - parents)), frozenset(known))


@lru_cache(maxsize=None)
def code_revisions(schema: str) -> Optional[CodeRevisions]:
    directory = VERSIONS.get(schema)
    return parse_versions(directory) if directory is not None else None


__all__ = ["CodeRevisions", "VERSIONS", "code_revisions", "parse_versions"]
