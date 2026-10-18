"""The typed parameter form of a task, generated from its ``Params`` JSON schema.

Pure functions: no database, no request object. Supported shapes (everything the
registry allows a task to declare today):

* ``str`` with length limits and an optional pattern (ids are strings with the id
  pattern), ``int`` with a range, an enum (a select), ``bool`` (a checkbox);
* a list of strings, one per line in a textarea, with a maximum count;
* any of those wrapped in ``Optional``.

Any other shape is *unsupported*: no input is rendered for it and the page says
so. A required unsupported parameter also removes the start buttons, since the
form could not produce valid params.

Validation is always ``meta.params.model_validate``; the form only turns text into
the types the model expects. Error reporting names fields (taken from the schema,
never from the submission) and never echoes a submitted value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from pydantic import ValidationError

from backend.admin.tasks.spec import TaskMeta

PREFIX = "p_"
MAX_TEXT = 2000
MAX_LINES_TEXT = 20_000
KINDS = ("text", "int", "enum", "bool", "lines", "multi")
UNSUPPORTED = "unsupported"
MAX_INT_DIGITS = 12


@dataclass(frozen=True)
class FormField:
    name: str
    kind: str  # one of KINDS or UNSUPPORTED
    required: bool
    optional: bool = False
    default: Any = None
    label: str = ""
    description: str = ""
    choices: tuple[str, ...] = ()
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    min_items: Optional[int] = None
    max_items: Optional[int] = None

    @property
    def input_name(self) -> str:
        return PREFIX + self.name

    @property
    def supported(self) -> bool:
        return self.kind != UNSUPPORTED

    def choice_name(self, choice: str) -> str:
        """The checkbox name of one choice of a ``multi`` field."""
        return f"{PREFIX}{self.name}__{choice}"

    @property
    def default_text(self) -> str:
        return field_text(self, self.default)


def _label(name: str) -> str:
    return name.replace("_", " ").capitalize()


def _resolve(schema: Mapping, defs: Mapping) -> Mapping:
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        return {**defs.get(ref[len("#/$defs/"):], {}), **{k: v for k, v in schema.items() if k != "$ref"}}
    return schema


def _strip_optional(schema: Mapping, defs: Mapping) -> tuple[Optional[Mapping], bool]:
    """``(inner, optional)``; ``inner`` is None for shapes with several non-null variants."""
    schema = _resolve(schema, defs)
    variants = schema.get("anyOf")
    if variants is None:
        return schema, False
    non_null = [v for v in variants if _resolve(v, defs).get("type") != "null"]
    optional = len(non_null) != len(variants)
    if len(non_null) != 1:
        return None, optional
    inner = {**{k: v for k, v in schema.items() if k != "anyOf"}, **_resolve(non_null[0], defs)}
    return inner, optional


def _int_or_none(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _build(name: str, spec: Mapping, defs: Mapping, required: bool) -> FormField:
    base = dict(
        name=name,
        required=required,
        label=_label(name),
        description=str(spec.get("description", ""))[:300],
        default=spec.get("default"),
    )
    inner, optional = _strip_optional(spec, defs)
    if inner is None:
        return FormField(kind=UNSUPPORTED, **base)
    base["optional"] = optional
    kind = inner.get("type")
    if "enum" in inner and kind in (None, "string") and all(isinstance(c, str) for c in inner["enum"]):
        return FormField(kind="enum", choices=tuple(inner["enum"]), **base)
    if kind == "boolean":
        return FormField(kind="bool", **base)
    if kind == "integer":
        return FormField(
            kind="int", minimum=_int_or_none(inner.get("minimum")),
            maximum=_int_or_none(inner.get("maximum")), **base,
        )
    if kind == "string":
        return FormField(
            kind="text", min_length=_int_or_none(inner.get("minLength")),
            max_length=_int_or_none(inner.get("maxLength")),
            pattern=inner.get("pattern") if isinstance(inner.get("pattern"), str) else None, **base,
        )
    if kind == "array":
        items = _resolve(inner.get("items") or {}, defs)
        if "enum" in items and all(isinstance(c, str) for c in items["enum"]):
            return FormField(
                kind="multi", choices=tuple(items["enum"]),
                max_items=_int_or_none(inner.get("maxItems")), **base,
            )
        if items.get("type") == "string" and "enum" not in items:
            return FormField(
                kind="lines", min_items=_int_or_none(inner.get("minItems")),
                max_items=_int_or_none(inner.get("maxItems")),
                pattern=items.get("pattern") if isinstance(items.get("pattern"), str) else None,
                max_length=_int_or_none(items.get("maxLength")), **base,
            )
    return FormField(kind=UNSUPPORTED, **base)


def fields_for(meta: TaskMeta) -> list[FormField]:
    schema = meta.params.model_json_schema()
    defs = schema.get("$defs", {})
    required = set(schema.get("required", []))
    return [
        _build(name, spec, defs, name in required)
        for name, spec in schema.get("properties", {}).items()
    ]


def can_submit(fields: list[FormField]) -> bool:
    """False when a required parameter has a shape the form cannot express."""
    return not any(f.required and not f.supported for f in fields)


# -- values <-> text ---------------------------------------------------------------
def field_text(f: FormField, value: Any) -> str:
    if value is None:
        return ""
    if f.kind == "lines" and isinstance(value, (list, tuple)):
        return "\n".join(str(v) for v in value)
    if f.kind == "enum" and hasattr(value, "value"):
        return str(value.value)
    return str(value)


def form_values(fields: list[FormField], params: Mapping[str, Any]) -> dict[str, Any]:
    """Input name -> text (or bool for checkboxes) that reproduces ``params``."""
    out: dict[str, Any] = {}
    for f in fields:
        if not f.supported:
            continue
        value = params.get(f.name, f.default)
        if f.kind == "multi":
            chosen = {getattr(v, "value", v) for v in (value or [])}
            for c in f.choices:
                out[f.choice_name(c)] = c in chosen
            continue
        out[f.input_name] = bool(value) if f.kind == "bool" else field_text(f, value)
    return out


def _form_get(form: Mapping[str, Any], key: str, limit: int) -> Optional[str]:
    value = form.get(key)
    return value[:limit] if isinstance(value, str) else None


def read_form(fields: list[FormField], form: Mapping[str, Any]) -> tuple[dict, set]:
    """``(raw, unreadable)``: values for ``model_validate`` and the names of fields
    whose text could not even be turned into the right type."""
    raw: dict[str, Any] = {}
    unreadable: set[str] = set()
    for f in fields:
        if not f.supported:
            continue
        if f.kind == "bool":
            raw[f.name] = _form_get(form, f.input_name, 8) is not None
            continue
        if f.kind == "multi":
            chosen = [c for c in f.choices if form.get(f.choice_name(c)) is not None]
            if chosen:
                raw[f.name] = chosen
            continue
        if f.kind == "lines":
            text = _form_get(form, f.input_name, MAX_LINES_TEXT + 1)
            if text is not None and len(text) > MAX_LINES_TEXT:
                unreadable.add(f.name)
                continue
            lines = [line.strip() for line in (text or "").replace("\r", "").split("\n")]
            lines = [line for line in lines if line]
            if lines:
                raw[f.name] = lines
            elif f.required:
                raw[f.name] = []
            continue
        text = _form_get(form, f.input_name, MAX_TEXT + 1)
        if text is not None and len(text) > MAX_TEXT:
            unreadable.add(f.name)
            continue
        text = (text or "").strip()
        if text == "":
            if f.required and f.kind == "text":
                raw[f.name] = ""
            continue  # blank: the default applies (or "missing" is reported)
        if f.kind == "int":
            body = text[1:] if text[:1] in "+-" else text
            if not (body.isascii() and body.isdigit() and len(body) <= MAX_INT_DIGITS):
                unreadable.add(f.name)
                continue
            raw[f.name] = int(text)
        else:
            raw[f.name] = text
    return raw, unreadable


@dataclass(frozen=True)
class Parsed:
    params: Optional[dict]  # canonical (``model_dump(mode="json")``), None when invalid
    bad: frozenset = field(default_factory=frozenset)  # field names that failed


def parse(meta: TaskMeta, fields: list[FormField], form: Mapping[str, Any]) -> Parsed:
    raw, unreadable = read_form(fields, form)
    if unreadable:
        return Parsed(None, frozenset(unreadable))
    try:
        model = meta.params.model_validate(raw)
    except ValidationError as exc:
        names = {f.name for f in fields}
        bad = {str(e["loc"][0]) for e in exc.errors() if e["loc"] and str(e["loc"][0]) in names}
        return Parsed(None, frozenset(bad or {"?"}))
    return Parsed(model.model_dump(mode="json"))


def validate_stored(meta: TaskMeta, params: Mapping[str, Any]) -> Optional[dict]:
    """Canonical params for stored ones (a run being resumed), or None."""
    try:
        return meta.params.model_validate(dict(params)).model_dump(mode="json")
    except ValidationError:
        return None


def summary(fields: list[FormField], params: Mapping[str, Any]) -> list[tuple[str, Any]]:
    """``(label, value)`` rows for a confirmation page (a bool stays a bool so the
    template can translate it); values are already validated."""
    rows = []
    for f in fields:
        if not f.supported:
            continue
        value = params.get(f.name)
        if f.kind == "bool":
            text = bool(value)
        elif f.kind in ("lines", "multi"):
            text = ", ".join(getattr(v, "value", v) for v in value) if value else "-"
        else:
            text = field_text(f, value) or "-"
        rows.append((f.label, text))
    return rows
