"""The Generic JSON body: ``values``, ``values_schema``, ``metadata`` and
``metadata_schema`` (the format Open Formulieren's Generic JSON registration
sends; docs/open-formulieren-registration.md lists the keys and where our
values differ).

Pure functions over a published form, the decrypted answers and the form's
mapping. Only variables the creator listed are read, so nothing else leaves.
Files are read through a callback (the job's storage reader), base64 encoded.
Nothing here logs, and nothing here keeps what it was given.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
MAX_FILES = 20
MAX_FILE_BYTES = 10 * 1024 * 1024
# all files of one body together, as base64: the job never holds much more
# than this (the client refuses a whole body over 20 MB)
MAX_FILES_BASE64 = 15 * 1024 * 1024

SLIDE = "slide"
GROUP = "group"
TEXT_TYPES = {"short_text", "long_text"}
NUMBER_TYPES = {"number", "rating", "linear_rating", "opinion_scale"}
CHOICE_TYPES = {"multiple_choice", "dropdown"}
SUPPORTED_TYPES = (
    TEXT_TYPES
    | NUMBER_TYPES
    | CHOICE_TYPES
    | {"email", "url", "phone_number", "yes_no", "date", "file_upload", "calculated"}
)

# fixed metadata, always sent; the creator may add more from EXTRA_METADATA
FIXED_METADATA = ("public_reference", "form_version", "registration_timestamp")
EXTRA_METADATA: Tuple[str, ...] = ()
METADATA_TITLES = {
    "public_reference": "Public reference",
    "form_version": "Form version",
    "registration_timestamp": "Registration timestamp",
}


class FileTooLarge(Exception):
    """A file or the number of files is over the limit (permanent)."""


class FileMissing(Exception):
    """A listed file is not in storage."""


def _get(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _type(field: Any) -> Optional[str]:
    value = _get(field, "type")
    return getattr(value, "value", value)


def _children(field: Any) -> List[Any]:
    return list(_get(_get(field, "properties"), "fields") or [])


def _plain(node: Any) -> str:
    if isinstance(node, dict):
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            return node["text"]
        return "".join(_plain(child) for child in node.get("content") or [])
    return ""


def label_of(field: Any) -> str:
    title = _get(field, "title")
    if isinstance(title, str) and title.strip():
        return title.strip()[:200]
    if isinstance(title, dict):
        text = _plain(title).strip()
        if text:
            return text[:200]
    return str(_get(field, "id") or "")


@dataclass(frozen=True)
class Variable:
    """One name of the form's variables namespace the creator may map."""

    source: str
    label: str
    type: str
    kind: str  # question | group_child | hidden
    supported: bool
    reason: Optional[str] = None
    field: Any = None
    group: Any = None


def _page_fields(form: Any) -> List[Any]:
    top = list(_get(form, "fields") or [])
    if not top or any(_type(f) != SLIDE for f in top):
        return []
    return [field for slide in top for field in _children(slide)]


def _unsupported(type_: str) -> str:
    return (
        "not_an_answer"
        if type_
        in {
            "text",
            "statement",
            "page_break",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "p",
            "strong",
            "divider",
            "markdown",
            "VIDEO_CONTENT",
            "IMAGE_CONTENT",
            "conditional",
            "hidden",
            "slide",
        }
        else "type_not_supported"
    )


def variables_of(form: Any) -> Dict[str, Variable]:
    """Every variable of the form by name (supported or not). Internal
    (staff-only) fields are left out entirely: they have no answer at submit."""
    found: Dict[str, Variable] = {}
    for name in _get(form, "hidden_fields") or []:
        found[str(name)] = Variable(str(name), str(name), "hidden", "hidden", True)
    for field in _page_fields(form):
        field_id = _get(field, "id")
        if not field_id or _get(field, "internal"):
            continue
        type_ = _type(field) or ""
        repeat = _get(_get(field, "properties"), "repeat")
        if type_ == GROUP and repeat is not None:
            found[str(field_id)] = Variable(
                str(field_id), label_of(field), "group", "question", True, field=field
            )
            for child in _children(field):
                child_id = _get(child, "id")
                if not child_id or _get(child, "internal"):
                    continue
                child_type = _type(child) or ""
                ok = child_type in SUPPORTED_TYPES and child_type != "file_upload"
                key = f"{field_id}.{child_id}"
                found[key] = Variable(
                    key,
                    f"{label_of(field)} / {label_of(child)}",
                    child_type,
                    "group_child",
                    ok,
                    None if ok else _unsupported(child_type),
                    field=child,
                    group=field,
                )
            continue
        ok = type_ in SUPPORTED_TYPES
        found[str(field_id)] = Variable(
            str(field_id),
            label_of(field),
            type_,
            "question",
            ok,
            (
                None
                if ok
                else (_unsupported(type_) if type_ != GROUP else "type_not_supported")
            ),
            field=field,
        )
    return found


def mappable(form: Any) -> List[Variable]:
    """What the creator can pick: supported answers, in form order. Items of
    a repeating group are reached through the group's own variable."""
    return [
        v
        for v in variables_of(form).values()
        if v.supported and v.kind != "group_child"
    ]


# ---------------------------------------------------------------- answers


def _answer(answers: Dict[str, Any], key: str) -> Optional[dict]:
    value = answers.get(key) if isinstance(answers, dict) else None
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return value if isinstance(value, dict) else None


def _slot(answer: Optional[dict], *names: str) -> Any:
    if not answer:
        return None
    for name in names:
        if answer.get(name) is not None:
            return answer[name]
    return None


def _picked(answer: Optional[dict]) -> Optional[Any]:
    """The option ids picked (a list for a multi-select), or one id, plus an
    "other" text appended as it was written. ``None`` when nothing was picked."""
    if not answer:
        return None
    choices = answer.get("choices")
    if isinstance(choices, dict) and choices.get("values") is not None:
        values = list(choices["values"])
        if choices.get("other"):
            values.append(choices["other"])
        return values
    choice = answer.get("choice")
    if isinstance(choice, dict):
        return choice.get("value") or choice.get("other") or None
    return None


def _choice_list(field: Any) -> List[Any]:
    return list(_get(_get(field, "properties"), "choices") or [])


def option_text(field: Any, chosen: str) -> str:
    """An option as the respondent saw it: its text (``value``, else its
    ``label``, else ``Item n``), like the form page and answer piping show it.
    An id the form does not have is an "other" text, kept as written."""
    for index, choice in enumerate(_choice_list(field)):
        if _get(choice, "id") == chosen:
            for slot in ("value", "label"):
                text = _get(choice, slot)
                if isinstance(text, str) and text.strip():
                    return text
            return f"Item {index + 1}"
    return chosen


def _calculated_value(answer: Optional[dict]) -> Any:
    return _slot(answer, "number", "boolean", "text")


def _option_titles(field: Any) -> List[str]:
    return [option_text(field, _get(choice, "id")) for choice in _choice_list(field)]


def _max_length(field: Any) -> Optional[int]:
    value = _get(_get(field, "validations"), "max_length")
    return value if isinstance(value, int) and value > 0 else None


def _is_multiple(field: Any) -> bool:
    return bool(_get(_get(field, "properties"), "allow_multiple_selection"))


def _string_schema(field: Any, **extra: Any) -> dict:
    schema: Dict[str, Any] = {"title": label_of(field), "type": "string", **extra}
    limit = _max_length(field)
    if limit is not None:
        schema["maxLength"] = limit
    return schema


def _nullable(schema: dict, value: Any) -> dict:
    """An unanswered value is ``null``: say so in its schema (the format Open
    Formulieren sends names the plain type even then; we are exact)."""
    if value is None and isinstance(schema.get("type"), str):
        return {**schema, "type": [schema["type"], "null"]}
    return schema


def scalar(
    field: Any, answer: Optional[dict], *, choices_as_list: bool = True
) -> Tuple[Any, dict]:
    """``(value, schema)`` of one non-file question. Text-like questions that
    were not answered are ``""``, as Open Formulieren sends them; numbers,
    dates and yes/no questions are ``null``."""
    type_ = _type(field) or ""
    title = label_of(field)
    if type_ in TEXT_TYPES:
        return _slot(answer, "text") or "", _string_schema(field)
    if type_ == "email":
        return _slot(answer, "email", "text") or "", _string_schema(
            field, format="email"
        )
    if type_ == "url":
        return _slot(answer, "url", "text") or "", _string_schema(field, format="uri")
    if type_ == "phone_number":
        return _slot(answer, "phone_number", "phoneNumber") or "", _string_schema(field)
    if type_ in NUMBER_TYPES:
        value = _slot(answer, "number")
        return value, _nullable({"title": title, "type": "number"}, value)
    if type_ == "yes_no":
        value = _slot(answer, "boolean")
        value = value if isinstance(value, bool) else None
        return value, _nullable({"title": title, "type": "boolean"}, value)
    if type_ == "date":
        value = _slot(answer, "date")
        return value, _nullable(
            {"title": title, "type": "string", "format": "date"}, value
        )
    if type_ in CHOICE_TYPES:
        options = _option_titles(field)
        picked = _picked(answer)
        if _is_multiple(field) and type_ == "multiple_choice":
            chosen = (
                [option_text(field, p) for p in picked]
                if isinstance(picked, list)
                else [option_text(field, picked)] if picked else []
            )
            if choices_as_list:
                return chosen, {
                    "title": title,
                    "type": "array",
                    "items": {"type": "string", "enum": options},
                }
            selected = set(chosen)
            return {name: name in selected for name in options}, {
                "title": title,
                "type": "object",
                "properties": {name: {"type": "boolean"} for name in options},
                "required": options,
                "additionalProperties": False,
            }
        text = (
            option_text(
                field, picked[0] if isinstance(picked, list) and picked else picked
            )
            if picked
            else ""
        )
        # the empty answer is part of the enum, as in the format we follow
        return text, {"title": title, "type": "string", "enum": [*options, ""]}
    if type_ == "calculated":
        value = _calculated_value(answer)
        kind = (
            "boolean"
            if isinstance(value, bool)
            else "number" if isinstance(value, (int, float)) else "string"
        )
        return ("" if value is None else value), {"title": title, "type": kind}
    return None, {"title": title}


def _file_schema(title: str, present: bool) -> dict:
    if not present:
        return {"title": title, "type": "null"}
    return {
        "title": title,
        "type": "object",
        "properties": {
            "file_name": {"type": "string"},
            "content": {"type": "string", "format": "base64"},
        },
        "required": ["file_name", "content"],
        "additionalProperties": False,
    }


FileReader = Callable[..., bytes]


def base64_size(raw: int) -> int:
    return 4 * ((raw + 2) // 3)


def file_value(
    field: Any,
    answer: Optional[dict],
    read: FileReader,
    limit: int = MAX_FILE_BYTES,
):
    """The ``{file_name, content}`` object of an uploaded file (base64), or
    ``None``. ``read(file_id, limit)`` returns the stored bytes (at most
    ``limit``; the reader refuses a larger object before loading it)."""
    meta = (answer or {}).get("file_metadata") or (answer or {}).get("fileMetadata")
    title = label_of(field)
    if not isinstance(meta, dict) or not meta.get("id"):
        return None, _file_schema(title, False)
    if limit <= 0:
        raise FileTooLarge()
    data = read(str(meta["id"]), limit)
    if len(data) > min(limit, MAX_FILE_BYTES):
        raise FileTooLarge()
    return (
        {
            "file_name": str(meta.get("name") or meta["id"]),
            "content": base64.b64encode(data).decode("ascii"),
        },
        _file_schema(title, True),
    )


def _group_value(
    variable: Variable,
    answer: Optional[dict],
    index: Dict[str, Variable],
    choices_as_list: bool = True,
) -> Tuple[Any, dict]:
    items = (answer or {}).get("items") or []
    children = [v for v in index.values() if v.group is variable.field and v.supported]
    properties: Dict[str, Any] = {}
    rows: List[dict] = []
    for child in children:
        _value, schema = scalar(child.field, None, choices_as_list=choices_as_list)
        # the template of an item: the plain type; an item whose value is
        # missing narrows its own entry below
        kind = schema.get("type")
        if isinstance(kind, list):
            schema = {**schema, "type": next(k for k in kind if k != "null")}
        properties[child.source.split(".", 1)[1]] = schema
    for item in items:
        row = {}
        for child in children:
            child_id = child.source.split(".", 1)[1]
            value, schema = scalar(
                child.field, _answer(item, child_id), choices_as_list=choices_as_list
            )
            row[child_id] = value
            properties[child_id] = {**properties[child_id], **schema}
        rows.append(row)
    schema = {
        "title": variable.label,
        "type": "array",
        "items": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }
    repeat = _get(_get(variable.field, "properties"), "repeat")
    limit = _get(repeat, "max_items")
    if isinstance(limit, int):
        schema["maxItems"] = limit
    return rows, schema


# ------------------------------------------------------------- the document


def _doc(values: Dict[str, Any], schemas: Dict[str, Any]) -> Tuple[dict, dict]:
    return values, {
        "$schema": SCHEMA_DRAFT,
        "type": "object",
        "properties": schemas,
        "required": list(schemas),
        "additionalProperties": False,
    }


def build_values(
    index: Dict[str, Variable],
    mapping: Iterable[Tuple[str, str]],
    answers: Dict[str, Any],
    hidden_fields: Optional[Dict[str, str]],
    transform_to_list: Iterable[str],
    read_file: FileReader,
) -> Tuple[dict, dict]:
    """``(values, values_schema)`` for ``mapping`` (``(source, key)`` pairs).
    A source the form no longer has is left out. A multiple choice question is
    sent as an object of option -> selected unless its source is in
    ``transform_to_list``."""
    as_list = set(transform_to_list)
    values: Dict[str, Any] = {}
    schemas: Dict[str, Any] = {}
    files = 0
    used = 0
    for source, key in mapping:
        variable = index.get(source)
        if variable is None or not variable.supported:
            continue
        as_list_here = source in as_list
        if variable.kind == "hidden":
            value = (hidden_fields or {}).get(source) or ""
            schema = {"title": source, "type": "string"}
        elif variable.type == "group":
            value, schema = _group_value(
                variable, _answer(answers, source), index, as_list_here
            )
        elif variable.type == "file_upload":
            # a running budget: later files get what is left, so no body is
            # ever built from more than MAX_FILES_BASE64 of file content
            left = (MAX_FILES_BASE64 - used) * 3 // 4
            value, schema = file_value(
                variable.field,
                _answer(answers, source),
                read_file,
                min(MAX_FILE_BYTES, left),
            )
            if value is not None:
                used += len(value["content"])
            files += 1 if value is not None else 0
            if files > MAX_FILES:
                raise FileTooLarge()
        else:
            value, schema = scalar(
                variable.field, _answer(answers, source), choices_as_list=as_list_here
            )
        values[key] = value
        schemas[key] = schema
    return _doc(values, schemas)


def build_metadata(
    names: Iterable[str],
    *,
    public_reference: str,
    form_version: str,
    now: dt.datetime,
) -> Tuple[dict, dict]:
    values_by_name = {
        "public_reference": public_reference,
        "form_version": form_version,
        # whole seconds, UTC, "Z": as the format we follow writes it
        "registration_timestamp": now.astimezone(dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }
    schema_by_name = {
        "public_reference": {"title": "Public reference", "type": "string"},
        "form_version": {"title": "Form version", "type": "string"},
        "registration_timestamp": {
            "title": "Registration timestamp",
            "type": "string",
            "format": "date-time",
        },
    }
    chosen = [n for n in dict.fromkeys(names) if n in values_by_name]
    return _doc(
        {n: values_by_name[n] for n in chosen}, {n: schema_by_name[n] for n in chosen}
    )


def serialize(
    values: dict, values_schema: dict, metadata: dict, metadata_schema: dict
) -> bytes:
    return json.dumps(
        {
            "values": values,
            "values_schema": values_schema,
            "metadata": metadata,
            "metadata_schema": metadata_schema,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
