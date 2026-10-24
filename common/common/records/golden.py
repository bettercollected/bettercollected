"""Test support: prove the record codec against the pinned golden fixtures.

The golden fixtures (:mod:`common.db.codec_golden`) pin the ``doc`` and
checksum every mirrored document class encodes to today. The checks here run
the same cases through the record layer instead:

* :func:`check_encoding` — :func:`common.records.codec.encode` /
  :func:`~common.records.codec.row_values` of the (Beanie) case instances give
  the pinned bytes: the record codec is the current codec, rule for rule;
* :func:`twin` — the class a document class becomes once its base is
  :class:`~common.records.base.Record` (same fields, validators, serializers
  and ``Settings``; Beanie's own pieces dropped). Building the cases from the
  twins (``codec_golden.build_cases``) and decoding the pinned ``doc`` into
  them (:func:`check_round_trip`) must give the pinned bytes as well;
* :func:`check_wire` — a twin has the JSON schema (OpenAPI) of its document
  class, and an instance decoded from a pinned ``doc`` dumps to the same JSON
  as the Beanie one: moving a class onto ``Record`` changes nothing a client
  sees.

The fixtures are never regenerated from here: a difference is a codec bug.
This module imports Beanie (through ``common.db``) and is used by tests only;
the record layer itself does not.
"""

from __future__ import annotations

import types
from copy import copy
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping

from pydantic import BaseModel

from common.db.canonical import canonical_json
from common.db.codec_golden import load
from common.records.base import Record
from common.records.codec import decode, encode, row_values

# Config keys Beanie sets on Document; Record sets the same ones itself.
_BASE_CONFIG = {"populate_by_name", "alias_generator", "json_schema_extra"}
_DECORATOR_KINDS = (
    "validators",
    "field_validators",
    "root_validators",
    "field_serializers",
    "model_serializers",
    "model_validators",
    "computed_fields",
)

_twins: Dict[type, type] = {}


def _is_document(cls: type) -> bool:
    from beanie import Document

    return isinstance(cls, type) and issubclass(cls, Document)


def _is_document_base(cls: type) -> bool:
    """Beanie's ``Document`` and ``MongoDocument``: what ``Record`` replaces.
    Other abstract bases (``BaseDocument``) are rebased like any class, so
    whatever they redeclare (its timestamp defaults) carries over."""
    from common.configs.mongo_document import MongoDocument

    return cls is MongoDocument or (
        _is_document(cls) and cls.__module__.split(".")[0] == "beanie"
    )


def twin(document_cls: type) -> type:
    """``document_cls`` rebased onto :class:`Record` (memoised)."""
    if issubclass(document_cls, Record):
        return document_cls
    if document_cls in _twins:
        return _twins[document_cls]
    from pydantic._internal._decorators import PydanticDescriptorProxy

    bases: List[type] = []
    for base in document_cls.__bases__:
        if _is_document_base(base):
            replacement = Record
        elif _is_document(base):
            replacement = twin(base)
        else:
            replacement = base
        if replacement not in bases:
            bases.append(replacement)
    if not any(issubclass(b, Record) for b in bases):
        bases.append(Record)

    own_annotations = document_cls.__dict__.get("__annotations__", {})
    fields = {
        name: info
        for name, info in document_cls.model_fields.items()
        if name in own_annotations and name != "revision_id"
    }
    namespace: Dict[str, Any] = {
        "__module__": document_cls.__module__,
        "__qualname__": document_cls.__qualname__,
        "__doc__": document_cls.__doc__,
        "__annotations__": {name: info.annotation for name, info in fields.items()},
    }
    for name, info in fields.items():
        namespace[name] = copy(info)
    for kind in _DECORATOR_KINDS:
        for name, decorator in getattr(
            document_cls.__pydantic_decorators__, kind
        ).items():
            if name in document_cls.__dict__:
                namespace[name] = PydanticDescriptorProxy(
                    document_cls.__dict__[name], decorator.info, decorator.shim
                )
    config = {
        key: value
        for key, value in document_cls.__dict__.get("model_config", {}).items()
        if key not in _BASE_CONFIG
    }
    if config:
        namespace["model_config"] = config
    if "Settings" in document_cls.__dict__:
        # an inherited one comes with the (rebased) base class
        namespace["Settings"] = document_cls.__dict__["Settings"]

    def body(ns: Dict[str, Any]) -> None:
        ns.update(namespace)

    made = types.new_class(document_cls.__name__, tuple(bases), {}, body)
    _twins[document_cls] = made
    return made


def twins(classes: Mapping[str, type]) -> Dict[str, type]:
    return {key: twin(cls) for key, cls in classes.items()}


# -- checks ---------------------------------------------------------------------


def check_encoding(fixture_path: Path, cases: Mapping[str, Any]) -> List[str]:
    """The record codec on ``cases`` (any document instances) gives the pinned
    ``doc``, checksum and row id."""
    pinned = load(fixture_path)
    problems = []
    if not pinned:
        return [f"{fixture_path}: no pinned cases"]
    for name in sorted(set(pinned) - set(cases)):
        problems.append(f"{name}: pinned but not built")
    for name, document in sorted(cases.items()):
        expected = pinned.get(name)
        if expected is None:
            problems.append(f"{name}: not pinned")
            continue
        if type(document).__name__ != expected["document"]:
            problems.append(f"{name}: built from {type(document).__name__}")
        doc = encode(document)
        values = row_values(document)
        if canonical_json(doc) != canonical_json(expected["doc"]):
            problems.append(f"{name}: record codec doc differs from the pinned one")
        if values["doc"] != doc or values["bc_checksum"] != expected["checksum"]:
            problems.append(f"{name}: record codec checksum differs")
        if values["id"] != expected["doc"]["_id"]["$oid"]:
            problems.append(f"{name}: row id differs from doc._id")
    return problems


def check_round_trip(fixture_path: Path, classes: Mapping[str, type]) -> List[str]:
    """Every pinned ``doc`` decodes into ``classes[document]`` (e.g. the twins)
    with the record codec and encodes back to the same bytes."""
    problems = []
    for name, case in sorted(load(fixture_path).items()):
        cls = classes.get(case["document"])
        if cls is None:
            problems.append(f"{name}: no class {case['document']}")
            continue
        again = row_values(decode(cls, case["doc"]))
        if canonical_json(again["doc"]) != canonical_json(case["doc"]):
            problems.append(f"{name}: decode -> encode changes the doc")
        if again["bc_checksum"] != case["checksum"]:
            problems.append(f"{name}: decode -> encode changes the checksum")
    return problems


def _dump(model: BaseModel, **options: Any) -> str:
    """A JSON dump, or the error it raises (synthetic cases hold binary data
    that no JSON dump accepts: both classes must refuse it alike)."""
    try:
        return canonical_json(model.model_dump(mode="json", **options))
    except Exception as error:  # noqa: BLE001 - compared, not handled
        return f"error: {type(error).__name__}"


def _dumps(model: BaseModel) -> List[str]:
    """How the API can serialise a model: by name, by alias (FastAPI's
    default), without ``None`` values."""
    return [
        _dump(model),
        _dump(model, by_alias=True),
        _dump(model, by_alias=True, exclude_none=True),
    ]


def check_wire(
    fixture_path: Path,
    classes: Mapping[str, type],
    decode_document: Callable[[type, Mapping[str, Any]], Any],
) -> List[str]:
    """For each document class in ``classes`` (name -> Beanie class): its twin
    has the same JSON schema in both modes, and every pinned ``doc`` decoded
    into the twin dumps (JSON, by name and by alias) exactly like the Beanie
    instance ``decode_document`` returns."""
    problems = []
    for name, cls in sorted(classes.items()):
        made = twin(cls)
        for mode in ("validation", "serialization"):
            if made.model_json_schema(mode=mode) != cls.model_json_schema(mode=mode):
                problems.append(f"{name}: JSON schema ({mode}) differs")
    for name, case in sorted(load(fixture_path).items()):
        cls = classes.get(case["document"])
        if cls is None:
            continue
        record = decode(twin(cls), case["doc"])
        document = decode_document(cls, case["doc"])
        if _dumps(record) != _dumps(document):
            problems.append(f"{name}: the API would serialise it differently")
        if record.model_dump() != document.model_dump():
            problems.append(f"{name}: python dump differs")
    return problems
