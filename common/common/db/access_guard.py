"""Static check: Beanie documents are read and written only by repositories.

The routing layer (:mod:`common.db.routing`) sees a call only when it goes
through a routed repository. A service that calls ``document.save()`` or
``SomeDocument.find_one(...)`` itself talks to Mongo alone: in ``dual`` mode
the write never reaches Postgres, and once a group reads from Postgres the
change is lost (or the read sees stale Mongo data). Each service's test suite
runs :func:`find_direct_access` over its package and fails on any hit outside
the repositories, the migration CLI and an explicit, documented allow-list.

Two rules, both purely syntactic:

* **class calls** — a query or write method called on a document class, also
  at the root of a chain: ``UserDocument.find_one(...)``,
  ``UserDocument.find(...).delete()``. Document classes are the transitive
  subclasses of Beanie's ``Document`` (and ``MongoDocument``) found in the
  scanned sources and ``common``.
* **instance writes** — an awaited ``save()``, ``insert()``, ``delete()``,
  ``replace()``, ``set()``, ``update()``, ``inc()``, ``save_changes()`` or
  ``upsert()`` on a local variable. Types are unknown statically, so a
  variable whose name says it is something else (``*repo*``,
  ``*service*``, ``*client*``, ...) is skipped; name such variables
  accordingly.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DOCUMENT_BASES = frozenset({"Document", "MongoDocument"})

# Beanie's query/write class methods, plus MongoDocument's helpers.
CLASS_METHODS = frozenset(
    {
        "find",
        "find_one",
        "find_all",
        "find_many",
        "get",
        "aggregate",
        "count",
        "distinct",
        "insert_one",
        "insert_many",
        "delete_all",
        "update_all",
        "replace_many",
        "bulk_writer",
        "get_motor_collection",
        "get_pymongo_collection",
        "inspect_collection",
        "find_one_by_args",
        "find_sync",
        "get_sync",
        # instance writes called through the class
        "save",
        "insert",
        "delete",
        "replace",
        "set",
        "update",
        "inc",
    }
)

INSTANCE_WRITES = frozenset(
    {
        "save",
        "insert",
        "delete",
        "replace",
        "set",
        "update",
        "inc",
        "save_changes",
        "upsert",
    }
)

# A local variable named like this is not a document (heuristic, see above).
NOT_A_DOCUMENT = re.compile(
    r"repo|repository|service|client|handle|store|cache|session|writer|limiter",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Hit:
    path: str  # relative to the scanned root, with forward slashes
    line: int
    call: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.call}"


def _python_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if any(part in {".venv", "__pycache__", "node_modules"} for part in path.parts):
            continue
        yield path


def _parse(path: Path):
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return None


def document_classes(roots: Sequence[Path]) -> frozenset:
    """Names of the classes that (transitively) subclass a Beanie document."""
    bases: dict = {}
    for root in roots:
        for path in _python_files(root):
            tree = _parse(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    names = bases.setdefault(node.name, set())
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            names.add(base.id)
                        elif isinstance(base, ast.Attribute):
                            names.add(base.attr)
    found = set(DOCUMENT_BASES)
    changed = True
    while changed:
        changed = False
        for name, parents in bases.items():
            if name not in found and parents & found:
                found.add(name)
                changed = True
    return frozenset(found)


def _chain_root(node: ast.AST):
    """The Name at the root of ``a.b(...).c[...]...``, if any."""
    while True:
        if isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, (ast.Attribute, ast.Subscript)):
            node = node.value
        else:
            return node if isinstance(node, ast.Name) else None


def _scan(tree: ast.AST, documents: frozenset):
    awaited = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Await)}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        method = node.func.attr
        receiver = node.func.value
        root = _chain_root(receiver)
        if root is not None and root.id in documents and method in CLASS_METHODS:
            yield node.lineno, f"{root.id}...{method}()"
        elif (
            id(node) in awaited
            and method in INSTANCE_WRITES
            and isinstance(receiver, ast.Name)
            and receiver.id not in documents
            and not NOT_A_DOCUMENT.search(receiver.id)
        ):
            yield node.lineno, f"{receiver.id}.{method}()"


def find_direct_access(
    package: Path,
    *,
    document_roots: Sequence[Path],
    allowed: Mapping[str, str],
) -> list:
    """Hits under ``package`` outside the ``allowed`` paths.

    ``allowed`` maps a path relative to ``package`` (a file, or a directory
    ending in ``/``) to the reason it may touch documents directly; every
    entry must carry a reason. ``document_roots`` are the sources the
    document classes are collected from (the service and ``common``)."""
    for prefix, reason in allowed.items():
        if not (isinstance(reason, str) and reason.strip()):
            raise ValueError(f"allow-list entry {prefix!r} has no reason")
    documents = document_classes(document_roots)
    hits = []
    for path in _python_files(package):
        rel = path.relative_to(package).as_posix()
        if any(
            rel == prefix or (prefix.endswith("/") and rel.startswith(prefix))
            for prefix in allowed
        ):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        hits.extend(Hit(rel, line, call) for line, call in _scan(tree, documents))
    return sorted(hits, key=lambda h: (h.path, h.line))


def unused_allow_entries(package: Path, allowed: Mapping[str, str]) -> list:
    """Allow-list entries that name nothing (a moved or deleted module)."""
    return sorted(prefix for prefix in allowed if not (package / prefix).exists())
