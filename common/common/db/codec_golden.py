"""Golden fixtures for the ``doc`` codec (test support, shared by the services' suites).

Every Postgres row stores its document in ``doc`` (BSON Extended JSON, relaxed
mode; see :mod:`common.db.canonical`) and a checksum of it in ``_bc_checksum``.
Verification compares those checksums with Mongo, so any change in how a
document is encoded is a data change: rows written before and after it no
longer agree. A codec that replaces the Beanie one must therefore produce the
same bytes for the same document.

The fixtures pin those bytes. For every document class that is mirrored to
Postgres, :func:`synthesize` builds deterministic instances (all fields set,
only required ones, optionals explicitly ``None``, naive datetimes) and the
fixture file records the canonical ``doc`` and its checksum for each. A test
re-encodes the instances and compares, and decodes each pinned ``doc`` and
encodes it again (the read-then-write path of a repository).

Regenerating is deliberate, never automatic: run ``scripts/regenerate-codec-golden.sh``
(it sets ``BC_CODEC_GOLDEN_WRITE=1`` for the golden tests), then review the
diff. A changed ``doc`` or checksum for an existing case means stored rows
would change too, which needs a migration plan, not a fixture update.
"""

from __future__ import annotations

import datetime as dt
import enum
import hashlib
import json
import os
import types
import typing
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from bson import ObjectId
from pydantic import BaseModel

from common.db.beanie_bridge import from_row_doc, row_values, to_bson_dict
from common.db.canonical import canonical_document, canonical_json, checksum

WRITE_ENV = "BC_CODEC_GOLDEN_WRITE"

VARIANTS = ("full", "minimal", "nulls", "naive")

# Fixed values, chosen to exercise the encodings that are easy to get wrong.
CREATED = dt.datetime(2026, 1, 2, 3, 4, 5, 678901, tzinfo=dt.timezone.utc)
UPDATED = dt.datetime(2026, 2, 3, 4, 5, 6, 789012, tzinfo=dt.timezone.utc)
AWARE = dt.datetime(
    2026, 3, 4, 5, 6, 7, 891234, tzinfo=dt.timezone(dt.timedelta(hours=2))
)
NAIVE = dt.datetime(2026, 3, 4, 5, 6, 7, 891234)
LARGE_INT = 2**53 + 1  # beyond float precision: must stay an exact integer
FLOAT = 0.1 + 0.2
TEXT = 'tëxt ✓ "quoted" \\ line\nbreak'


def object_id(*parts: Any) -> ObjectId:
    """A deterministic ObjectId per (class, field path)."""
    return ObjectId(hashlib.sha1("/".join(map(str, parts)).encode()).digest()[:12])


def kitchen_sink(path: str, naive: bool) -> Dict[str, Any]:
    """An untyped mapping holding every value type a ``Dict[str, Any]`` field may carry."""
    return {
        "text": TEXT,
        "int": 7,
        "large_int": LARGE_INT,
        "negative": -LARGE_INT,
        "float": FLOAT,
        "bool": True,
        "none": None,
        "object_id": object_id(path, "sink"),
        "datetime": NAIVE if naive else AWARE,
        "decimal": Decimal("1234.5600"),
        "bytes": b"\x00\x01binary\xff",
        "list": [1, "two", {"three": [3.0]}, None],
        "nested": {"empty": {}, "empty_list": [], "z": 1, "a": 2},
    }


def _unwrap(annotation: Any) -> Tuple[Any, bool]:
    """(inner annotation, optional?) — strips Annotated and Optional."""
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        return _unwrap(typing.get_args(annotation)[0])
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        optional = len(args) < len(typing.get_args(annotation))
        inner, inner_optional = _unwrap(args[0])
        return inner, optional or inner_optional
    return annotation, False


def _value(annotation: Any, path: str, variant: str, depth: int) -> Any:
    naive = variant == "naive"
    annotation, _ = _unwrap(annotation)
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if annotation is Any or annotation is object:
        return kitchen_sink(path, naive)
    if origin is typing.Literal:
        return args[0]
    if origin in (list, List, set, frozenset, tuple, Iterable) or annotation in (
        list,
        tuple,
    ):
        item = args[0] if args else Any
        if depth > 3:
            return []
        return [
            _value(item, f"{path}[0]", variant, depth + 1),
            _value(item, f"{path}[1]", variant, depth + 1),
        ]
    if origin in (dict, Dict, Mapping) or annotation is dict:
        key_type, value_type = args if len(args) == 2 else (str, Any)
        if value_type is Any and key_type is str:
            return kitchen_sink(path, naive)
        key = _value(key_type, f"{path}.key", variant, depth + 1)
        if isinstance(key, enum.Enum):
            key = key.value
        return {str(key): _value(value_type, f"{path}.value", variant, depth + 1)}
    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum):
            return list(annotation)[-1]
        if issubclass(annotation, ObjectId):
            return object_id(path)
        if issubclass(annotation, bool):
            return True
        if issubclass(annotation, int):
            return LARGE_INT
        if issubclass(annotation, float):
            return FLOAT
        if issubclass(annotation, Decimal):
            return Decimal("1234.5600")
        if issubclass(annotation, bytes):
            return b"\x00\x01binary\xff"
        if issubclass(annotation, dt.datetime):
            return NAIVE if naive else AWARE
        if issubclass(annotation, dt.date):
            return dt.date(2026, 3, 4)
        if issubclass(annotation, dt.time):
            return dt.time(5, 6, 7, 891234)
        if issubclass(annotation, BaseModel):
            if depth > 6:
                return {}
            return fields_for(annotation, variant, path, depth + 1)
        if issubclass(annotation, str):
            return f"{path} {TEXT}"
    # anything else (EmailStr, HttpUrl, constrained types): a string pydantic accepts
    name = getattr(annotation, "__name__", str(annotation))
    if "Email" in name:
        return "person@example.org"
    if "Url" in name:
        return "https://example.org/path"
    return f"{path} {TEXT}"


def fields_for(
    model: type,
    variant: str,
    path: Optional[str] = None,
    depth: int = 0,
    overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Keyword arguments for ``model`` in ``variant``:

    ``full``     every field set, optionals included;
    ``minimal``  required fields only (optionals absent);
    ``nulls``    required fields, optionals explicitly ``None``;
    ``naive``    like ``full`` with naive datetimes.
    """
    path = path or model.__name__
    overrides = overrides or {}
    values: Dict[str, Any] = {}
    for name, info in model.model_fields.items():
        if name in ("id", "revision_id", "created_at", "updated_at") and depth == 0:
            continue
        key = info.alias or name
        if name in overrides:
            values[key] = overrides[name]
            continue
        _, optional = _unwrap(info.annotation)
        required = info.is_required()
        if not required and variant == "minimal" and depth == 0:
            continue
        if not required and variant == "nulls" and optional and depth == 0:
            values[key] = None
            continue
        if not required and optional and depth > 2:
            continue
        values[key] = _value(info.annotation, f"{path}.{name}", variant, depth)
    return values


# Strings tried in turn for a value a pattern, length or custom check refused.
_PLAIN = (
    "plain_1",
    "#1a2b3c",
    "https://example.org/path",
    "person@example.org",
    "en",
    "color",
    "1",
)


def _repair(kwargs: Dict[str, Any], error: Mapping[str, Any]) -> bool:
    """Make one rejected synthetic value acceptable: a string that broke a
    pattern, length or custom check becomes a short plain one; anything else
    that still fails is dropped (when the field allows it). False when stuck."""
    parent: Any = kwargs
    loc = list(error["loc"])
    for step in loc[:-1]:
        try:
            parent = parent[step]
        except (KeyError, IndexError, TypeError):
            return False
    last = loc[-1]
    try:
        current = parent[last]
    except (KeyError, IndexError, TypeError):
        return False
    if isinstance(current, str) and current != _PLAIN[-1]:
        parent[last] = (
            _PLAIN[_PLAIN.index(current) + 1] if current in _PLAIN else _PLAIN[0]
        )
        return True
    if isinstance(parent, dict):
        del parent[last]
        return True
    return False


def build(
    document_cls: type, variant: str, overrides: Optional[Mapping[str, Any]] = None
):
    """A deterministic instance of a Beanie document class."""
    from pydantic import ValidationError

    kwargs = fields_for(document_cls, variant, overrides=overrides)
    naive = variant == "naive"
    timestamps = {
        "created_at": CREATED.replace(tzinfo=None) if naive else CREATED,
        "updated_at": UPDATED.replace(tzinfo=None) if naive else UPDATED,
    }
    for _ in range(100):
        try:
            document = document_cls(**kwargs, **timestamps)
            break
        except ValidationError as error:
            if not all(_repair(kwargs, e) for e in error.errors()):
                raise
    else:  # pragma: no cover - a model the synthesizer cannot satisfy
        raise RuntimeError(
            f"cannot build a valid {document_cls.__name__}; add an override"
        )
    document.id = object_id(document_cls.__name__, variant, "_id")
    return document


def encode(document: Any) -> Dict[str, Any]:
    """The row's ``doc`` and ``_bc_checksum`` exactly as a Postgres twin stores them."""
    doc = canonical_document(to_bson_dict(document))
    values = row_values(document)
    assert values["doc"] == doc and values["bc_checksum"] == checksum(doc)
    return {"doc": doc, "checksum": checksum(doc)}


# -- fixture files --------------------------------------------------------------


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write(path: Path, cases: Mapping[str, Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        {k: cases[k] for k in sorted(cases)},
        indent=1,
        sort_keys=True,
        ensure_ascii=False,
    )
    path.write_text(text + "\n", encoding="utf-8")


def regenerating() -> bool:
    return os.environ.get(WRITE_ENV) == "1"


def mirrored_documents(
    rows: Iterable[type], document_models: Iterable[type]
) -> Dict[str, Optional[type]]:
    """collection -> Beanie document class for every BaseRow table (``None`` if no class)."""
    by_collection = {m.get_settings().name: m for m in document_models}
    return {
        row.mongo_collection(): by_collection.get(row.mongo_collection())
        for row in rows
    }


def build_cases(
    documents: Mapping[str, type],
    overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    extra: Optional[Mapping[str, Callable[[], Any]]] = None,
) -> Dict[str, Any]:
    """case name -> document instance: each class in every variant, plus ``extra`` builders."""
    overrides = overrides or {}
    cases: Dict[str, Any] = {}
    for collection, document_cls in sorted(documents.items()):
        for variant in VARIANTS:
            cases[f"{collection}/{variant}"] = build(
                document_cls, variant, overrides.get(collection)
            )
    for name, builder in (extra or {}).items():
        cases[name] = builder()
    return cases


def check(fixture_path: Path, cases: Mapping[str, Any]) -> List[str]:
    """Compare ``cases`` with the pinned fixture; returns the problems (empty when equal).

    With ``BC_CODEC_GOLDEN_WRITE=1`` the fixture is rewritten instead.
    """
    encoded = {
        name: {"document": type(document).__name__, **encode(document)}
        for name, document in cases.items()
    }
    if regenerating():
        write(fixture_path, encoded)
        return []
    pinned = load(fixture_path)
    problems = []
    for name in sorted(set(pinned) - set(encoded)):
        problems.append(f"{name}: pinned but no longer built (regenerate deliberately)")
    for name, case in sorted(encoded.items()):
        expected = pinned.get(name)
        if expected is None:
            problems.append(f"{name}: not pinned yet (regenerate deliberately)")
            continue
        if expected["document"] != case["document"]:
            problems.append(
                f"{name}: built from {case['document']}, pinned {expected['document']}"
            )
        if canonical_json(case["doc"]) != canonical_json(expected["doc"]):
            problems.append(f"{name}: doc bytes differ from the pinned ones")
        if case["checksum"] != expected["checksum"]:
            problems.append(f"{name}: checksum differs from the pinned one")
        if checksum(expected["doc"]) != expected["checksum"]:
            problems.append(f"{name}: the fixture's checksum does not match its doc")
    return problems


def check_round_trip(fixture_path: Path, classes: Mapping[str, type]) -> List[str]:
    """Decode every pinned ``doc`` into its class and encode it again: same bytes."""
    problems = []
    for name, case in sorted(load(fixture_path).items()):
        document_cls = classes.get(case["document"])
        if document_cls is None:
            problems.append(f"{name}: unknown document class {case['document']}")
            continue
        again = encode(from_row_doc(document_cls, case["doc"]))
        if canonical_json(again["doc"]) != canonical_json(case["doc"]):
            problems.append(f"{name}: decode -> encode changes the doc")
        if again["checksum"] != case["checksum"]:
            problems.append(f"{name}: decode -> encode changes the checksum")
    return problems
