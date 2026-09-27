"""Typed form-edit operations — the spine of AI form editing.

Every AI mutation of a form (builder chat, MCP ``update_form``, future
compliance fixes) is expressed as a list of small typed operations against
stable field/page IDs and applied here — never as a wholesale regenerated
form. Patching preserves IDs (logic references, existing responses, piping),
keeps diffs reviewable, and lets one bad op fail gracefully without
discarding the rest of the turn.

Contract:
    new_form, results = apply_form_ops(form, ops)

- ``form`` is never mutated; a deep copy is edited and returned.
- Each op yields an ``OpResult`` (ok/error + human-readable message — the
  messages double as the chat panel's per-turn change list).
- After all ops, indexes are renumbered and the whole form is re-validated
  through ``StandardForm`` — the model proposes, the schema disposes.
"""

import uuid
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union

from common.models.standard_form import (
    FieldLogic,
    FieldLogicCondition,
    LayoutType,
    PageJump,
    REPEAT_CHILD_FIELD_TYPES,
    RepeatSettings,
    StandardChoice,
    StandardFieldProperty,
    StandardFieldValidations,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
    Theme,
)
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.internal_fields import INTERNAL_CAPABLE_TYPES
from pydantic.alias_generators import to_camel


class OpError(Exception):
    """A single operation failed; the turn continues with the next op."""


# Field types the AI may CREATE. Deliberately the simple v2 set — matrix and
# tabular need nested row/column specs and get their own ops later.
ADDABLE_FIELD_TYPES = {
    StandardFormFieldType.SHORT_TEXT,
    StandardFormFieldType.LONG_TEXT,
    StandardFormFieldType.EMAIL,
    StandardFormFieldType.NUMBER,
    StandardFormFieldType.LINK,
    StandardFormFieldType.PHONE_NUMBER,
    StandardFormFieldType.DATE,
    StandardFormFieldType.YES_NO,
    StandardFormFieldType.MULTIPLE_CHOICE,
    StandardFormFieldType.DROPDOWN,
    StandardFormFieldType.RATING,
    StandardFormFieldType.LINEAR_RATING,
    StandardFormFieldType.FILE_UPLOAD,
    StandardFormFieldType.TEXT,  # statement / display-only
}

CHOICE_FIELD_TYPES = {
    StandardFormFieldType.MULTIPLE_CHOICE,
    StandardFormFieldType.DROPDOWN,
}

RATING_FIELD_TYPES = {
    StandardFormFieldType.RATING,
    StandardFormFieldType.LINEAR_RATING,
}


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class NewFieldSpec(_CamelModel):
    """What the AI supplies to create a field."""

    title: str
    type: StandardFormFieldType
    description: Optional[str] = None
    required: Optional[bool] = None
    placeholder: Optional[str] = None
    choices: Optional[List[str]] = None
    steps: Optional[int] = None
    start_from: Optional[int] = None
    col_span: Optional[int] = Field(None, ge=1, le=12)
    # Internal ("for office use only"): hidden from respondents, filled in by
    # staff on each submission afterwards.
    internal: Optional[bool] = None
    # multiple_choice only: respondents may pick several choices
    allow_multiple: Optional[bool] = None


class FieldPatch(_CamelModel):
    """Partial update of an existing field. Absent = unchanged. The
    ``*_items`` / ``item_*`` / ``export_layout`` keys only apply to
    repeating groups."""

    title: Optional[str] = None
    description: Optional[str] = None
    required: Optional[bool] = None
    placeholder: Optional[str] = None
    choices: Optional[List[str]] = None  # full replacement when present
    steps: Optional[int] = None
    start_from: Optional[int] = None
    col_span: Optional[int] = Field(None, ge=1, le=12)
    internal: Optional[bool] = None
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    item_label: Optional[str] = None
    item_title: Optional[str] = None
    export_layout: Optional[Literal["columns", "rows"]] = None


class AddFieldOp(_CamelModel):
    """Add a question to a page, or (with ``group_id``) into a repeating
    group, where it is asked once per item."""

    op: Literal["add_field"] = "add_field"
    page_id: Optional[str] = None
    group_id: Optional[str] = None
    field: NewFieldSpec
    # Placement: after a specific sibling, at an index, or appended (default).
    after_field_id: Optional[str] = None
    index: Optional[int] = None


class UpdateFieldOp(_CamelModel):
    op: Literal["update_field"] = "update_field"
    field_id: str
    patch: FieldPatch


class AddGroupOp(_CamelModel):
    """Create a repeating group on a page: child questions respondents fill
    once per item ("Applicant 1", "Applicant 2", ...), between ``min_items``
    and ``max_items`` times."""

    op: Literal["add_group"] = "add_group"
    page_id: str
    title: str
    description: Optional[str] = None
    item_label: str = "Item"
    min_items: int = 1
    max_items: int = 3
    item_title: Optional[str] = None
    export_layout: Optional[Literal["columns", "rows"]] = None
    fields: List[NewFieldSpec] = Field(default_factory=list)
    after_field_id: Optional[str] = None
    index: Optional[int] = None


class RemoveFieldOp(_CamelModel):
    op: Literal["remove_field"] = "remove_field"
    field_id: str


class MoveFieldOp(_CamelModel):
    op: Literal["move_field"] = "move_field"
    field_id: str
    to_page_id: Optional[str] = None  # default: same page (or group)
    # Move into a repeating group (asked once per item). A child moved with
    # ``to_page_id`` leaves its group.
    to_group_id: Optional[str] = None
    index: int


class AddPageOp(_CamelModel):
    op: Literal["add_page"] = "add_page"
    index: Optional[int] = None  # default: append
    fields: Optional[List[NewFieldSpec]] = None


class RemovePageOp(_CamelModel):
    op: Literal["remove_page"] = "remove_page"
    page_id: str


class UpdateFormInfoOp(_CamelModel):
    op: Literal["update_form_info"] = "update_form_info"
    title: Optional[str] = None
    description: Optional[str] = None


COMPARISONS = (
    "IS_EMPTY", "IS_NOT_EMPTY", "IS_EQUAL", "IS_NOT_EQUAL", "CONTAINS",
    "DOES_NOT_CONTAIN", "LESS_THAN", "LESS_THAN_EQUAL", "GREATER_THAN",
    "GREATER_THAN_EQUAL", "STARTS_WITH", "ENDS_WITH",
)
VALUELESS_COMPARISONS = {"IS_EMPTY", "IS_NOT_EMPTY"}
JUMP_TARGET_SUBMIT = "__SUBMIT__"


class LogicConditionSpec(_CamelModel):
    """One condition of a visibility rule / page jump. Mirrors the builder's
    logic editor exactly: choice conditions carry the choice LABEL, yes/no
    carries "Yes"/"No" (see webapp condition-editor-shared.tsx)."""

    field_id: str
    comparison: Literal[
        "IS_EMPTY", "IS_NOT_EMPTY", "IS_EQUAL", "IS_NOT_EQUAL", "CONTAINS",
        "DOES_NOT_CONTAIN", "LESS_THAN", "LESS_THAN_EQUAL", "GREATER_THAN",
        "GREATER_THAN_EQUAL", "STARTS_WITH", "ENDS_WITH",
    ]
    value: Optional[Any] = None
    # When ``field_id`` is a repeating group: COUNT compares the number of
    # items; ANY / ALL test ``child_field_id`` in the items.
    group_mode: Optional[Literal["COUNT", "ANY", "ALL"]] = None
    child_field_id: Optional[str] = None


class FieldLogicSpec(_CamelModel):
    action: Literal["SHOW", "HIDE"]
    operator: Literal["AND", "OR"] = "AND"
    conditions: List[LogicConditionSpec] = Field(..., min_length=1)


class SetFieldLogicOp(_CamelModel):
    """Conditional visibility on a field ("show X only when Y = ..."). The
    rule lives on the TARGET field; conditions reference earlier answers.
    ``logic: null`` clears the rule."""

    op: Literal["set_field_logic"] = "set_field_logic"
    field_id: str
    logic: Optional[FieldLogicSpec] = None


class PageJumpSpec(_CamelModel):
    operator: Literal["AND", "OR"] = "AND"
    conditions: List[LogicConditionSpec] = Field(..., min_length=1)
    target: str  # a page id, or JUMP_TARGET_SUBMIT


class SetPageJumpsOp(_CamelModel):
    """Branching: after this page, jump to a target page (or submit) when the
    conditions match; first matching jump wins, no match = next page.
    ``jumps: null`` clears."""

    op: Literal["set_page_jumps"] = "set_page_jumps"
    page_id: str
    jumps: Optional[List[PageJumpSpec]] = None


class DuplicatePageOp(_CamelModel):
    """Clone a page with all its fields (fresh ids everywhere). In-page logic
    references are remapped to the cloned fields."""

    op: Literal["duplicate_page"] = "duplicate_page"
    page_id: str
    index: Optional[int] = None  # default: right after the original


class FormSettingsPatch(_CamelModel):
    """AI-editable form settings — the Form tab's metadata.

    Deliberately a SUBSET of SettingsPatchDto: trust-layer text and
    response-behaviour toggles. Distribution/visibility (hidden, private,
    pinned, custom URL, close date) stays human-only — an ambiguous chat
    instruction must never unpublish or hide a form.
    """

    purpose: Optional[str] = None  # empty string clears
    retention_text: Optional[str] = None  # empty string clears
    privacy_policy_url: Optional[str] = None  # empty string clears
    require_verified_identity: Optional[bool] = None
    allow_editing_response: Optional[bool] = None
    show_submission_number: Optional[bool] = None


class UpdateFormSettingsOp(_CamelModel):
    op: Literal["update_form_settings"] = "update_form_settings"
    patch: FormSettingsPatch


class UpdateThemeOp(_CamelModel):
    op: Literal["update_theme"] = "update_theme"
    theme: Theme


FormOp = Annotated[
    Union[
        AddFieldOp,
        AddGroupOp,
        UpdateFieldOp,
        RemoveFieldOp,
        MoveFieldOp,
        AddPageOp,
        RemovePageOp,
        UpdateFormInfoOp,
        UpdateFormSettingsOp,
        SetFieldLogicOp,
        SetPageJumpsOp,
        DuplicatePageOp,
        UpdateThemeOp,
    ],
    Field(discriminator="op"),
]


class FormOps(_CamelModel):
    """Envelope for parsing an AI/MCP payload of operations."""

    ops: List[FormOp]


class OpResult(_CamelModel):
    index: int
    op: str
    ok: bool
    message: str


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def _pages(form: StandardForm) -> List[StandardFormField]:
    return [f for f in (form.fields or []) if f.type == StandardFormFieldType.SLIDE]


def _find_page(form: StandardForm, page_id: str) -> StandardFormField:
    for page in _pages(form):
        if page.id == page_id:
            return page
    raise OpError(f"Page '{page_id}' was not found — it may have been removed.")


def _is_repeating_group(field: Optional[StandardFormField]) -> bool:
    return bool(
        field is not None
        and field.type == StandardFormFieldType.GROUP
        and field.properties is not None
        and field.properties.repeat is not None
    )


def _children(field: StandardFormField) -> List[StandardFormField]:
    if field.properties is None:
        field.properties = StandardFieldProperty(fields=[])
    if field.properties.fields is None:
        field.properties.fields = []
    return field.properties.fields


def _locate_field(
    form: StandardForm, field_id: str
) -> Tuple[StandardFormField, Optional[StandardFormField], List[StandardFormField], StandardFormField, int]:
    """Return (page, parent group or None, containing list, field, position)
    for a non-page field id — page questions and repeating-group children."""
    for page in _pages(form):
        fields = (page.properties.fields if page.properties else None) or []
        for position, field in enumerate(fields):
            if field.id == field_id:
                return page, None, fields, field, position
            if _is_repeating_group(field):
                children = _children(field)
                for child_position, child in enumerate(children):
                    if child.id == field_id:
                        return page, field, children, child, child_position
    raise OpError(f"Field '{field_id}' was not found — it may have been removed.")


def _find_field(form: StandardForm, field_id: str) -> Tuple[StandardFormField, StandardFormField, int]:
    """Return (page, field, position-in-container) for a non-page field id."""
    page, _, _, field, position = _locate_field(form, field_id)
    return page, field, position


def _find_group(form: StandardForm, group_id: str) -> Tuple[StandardFormField, StandardFormField]:
    page, parent, _, field, _ = _locate_field(form, group_id)
    if parent is not None or not _is_repeating_group(field):
        raise OpError(f"'{_title_text(field)}' is not a repeating group.")
    return page, field


def _check_child_type(field_type: Any) -> None:
    value = getattr(field_type, "value", field_type)
    if value == StandardFormFieldType.GROUP.value:
        raise OpError("Repeating groups cannot contain another group.")
    if value not in REPEAT_CHILD_FIELD_TYPES:
        raise OpError(
            f"A '{value}' question cannot be placed inside a repeating group (allowed: "
            + ", ".join(sorted(REPEAT_CHILD_FIELD_TYPES))
            + ")."
        )


def _title_text(field: StandardFormField) -> str:
    if isinstance(field.title, str) and field.title.strip():
        return field.title.strip()
    return field.id or "untitled"


def _renumber(form: StandardForm) -> None:
    for slide_index, page in enumerate(_pages(form)):
        page.index = slide_index
        for field_index, field in enumerate((page.properties.fields if page.properties else None) or []):
            field.index = field_index
            if _is_repeating_group(field):
                for child_index, child in enumerate(_children(field)):
                    child.index = child_index


# ---------------------------------------------------------------------------
# Field construction / patching
# ---------------------------------------------------------------------------


def _build_field(spec: NewFieldSpec, index: int) -> StandardFormField:
    if spec.type not in ADDABLE_FIELD_TYPES:
        raise OpError(
            f"Field type '{spec.type.value}' cannot be created by AI ops (allowed: "
            + ", ".join(sorted(t.value for t in ADDABLE_FIELD_TYPES))
            + ")."
        )

    properties = StandardFieldProperty(fields=[])

    if spec.type == StandardFormFieldType.YES_NO:
        # Creation parity with the builder: yes/no is always exactly Yes/No.
        properties.choices = [
            StandardChoice(id=str(uuid.uuid4()), value="Yes"),
            StandardChoice(id=str(uuid.uuid4()), value="No"),
        ]
    elif spec.type in CHOICE_FIELD_TYPES:
        if not spec.choices or len(spec.choices) < 2:
            raise OpError(f"'{spec.type.value}' needs at least 2 choices.")
        properties.choices = [StandardChoice(id=str(uuid.uuid4()), value=v) for v in spec.choices]
        if spec.allow_multiple and spec.type == StandardFormFieldType.MULTIPLE_CHOICE:
            properties.allow_multiple_selection = True
    elif spec.type in RATING_FIELD_TYPES:
        properties.steps = spec.steps or (5 if spec.type == StandardFormFieldType.RATING else 10)
        if spec.start_from is not None:
            properties.start_from = spec.start_from

    if spec.placeholder is not None:
        properties.placeholder = spec.placeholder
    if spec.description is not None:
        properties.description = spec.description
    if spec.col_span is not None:
        properties.col_span = spec.col_span

    validations = StandardFieldValidations(required=spec.required) if spec.required is not None else StandardFieldValidations()
    if spec.internal:
        _ensure_can_be_internal(spec.type)

    return StandardFormField(
        id=str(uuid.uuid4()),
        index=index,
        type=spec.type,
        title=spec.title,
        description=spec.description,
        properties=properties,
        validations=validations,
        internal=True if spec.internal else None,
    )


def _ensure_can_be_internal(field_type) -> None:
    value = getattr(field_type, "value", field_type)
    if value not in INTERNAL_CAPABLE_TYPES:
        raise OpError(
            f"'{value}' fields can't be internal — staff fill internal fields in "
            "from the dashboard (text, number, date, email, link, phone, yes/no, "
            "choice and dropdown)."
        )


def _patch_field(field: StandardFormField, patch: FieldPatch) -> List[str]:
    """Apply a partial update; returns human-readable change fragments."""
    changed: List[str] = []
    if field.properties is None:
        field.properties = StandardFieldProperty(fields=[])
    if field.validations is None:
        field.validations = StandardFieldValidations()

    if patch.title is not None:
        field.title = patch.title
        changed.append("title")
    if patch.description is not None:
        field.description = patch.description
        field.properties.description = patch.description
        changed.append("description")
    if patch.required is not None:
        field.validations.required = patch.required
        changed.append("required" if patch.required else "optional")
    if patch.placeholder is not None:
        field.properties.placeholder = patch.placeholder
        changed.append("placeholder")
    if patch.choices is not None:
        if field.type == StandardFormFieldType.YES_NO:
            raise OpError("Yes/No choices are fixed — convert the field instead.")
        if field.type not in CHOICE_FIELD_TYPES:
            raise OpError(f"'{field.type.value if field.type else 'unknown'}' has no choices to update.")
        if len(patch.choices) < 2:
            raise OpError("A choice field needs at least 2 choices.")
        # Preserve IDs for unchanged values so existing logic rules survive.
        existing = {c.value: c for c in (field.properties.choices or []) if c.value}
        field.properties.choices = [
            existing.get(v) or StandardChoice(id=str(uuid.uuid4()), value=v) for v in patch.choices
        ]
        changed.append("choices")
    if patch.steps is not None:
        if field.type not in RATING_FIELD_TYPES:
            raise OpError("'steps' only applies to rating fields.")
        if patch.steps < 1:
            raise OpError("'steps' must be a positive integer.")
        field.properties.steps = patch.steps
        changed.append("steps")
    if patch.start_from is not None:
        field.properties.start_from = patch.start_from
        changed.append("startFrom")
    if patch.col_span is not None:
        field.properties.col_span = patch.col_span
        changed.append("width")
    if patch.internal:
        _ensure_can_be_internal(field.type)
    if patch.internal is not None:
        field.internal = True if patch.internal else None
        changed.append("internal" if patch.internal else "respondent-facing")
    group_keys = ("min_items", "max_items", "item_label", "item_title", "export_layout")
    group_patch = {k: getattr(patch, k) for k in group_keys if getattr(patch, k) is not None}
    if group_patch:
        if not _is_repeating_group(field):
            raise OpError("Item limits and labels only apply to repeating groups.")
        merged = {**field.properties.repeat.model_dump(), **group_patch}
        try:
            field.properties.repeat = RepeatSettings(**merged)
        except ValueError as e:
            raise OpError(_validation_message(e))
        changed.extend(k.replace("_", " ") for k in group_patch)
    if not changed:
        raise OpError("The update contained no changes.")
    return changed


# ---------------------------------------------------------------------------
# Op handlers
# ---------------------------------------------------------------------------


def _validation_message(error: Exception) -> str:
    errors = getattr(error, "errors", None)
    if callable(errors):
        return "; ".join(str(e.get("msg", "")).removeprefix("Value error, ") for e in errors())
    return str(error)


def _insert_position(fields: List[StandardFormField], after_field_id: Optional[str], index: Optional[int], where: str) -> int:
    if after_field_id is not None:
        positions = [i for i, f in enumerate(fields) if f.id == after_field_id]
        if not positions:
            raise OpError(f"Field '{after_field_id}' is not in {where}.")
        return positions[0] + 1
    if index is not None:
        return max(0, min(index, len(fields)))
    return len(fields)


def _apply_add_field(form: StandardForm, op: AddFieldOp) -> str:
    if op.group_id is not None:
        _, group = _find_group(form, op.group_id)
        _check_child_type(op.field.type)
        children = _children(group)
        insert_at = _insert_position(children, op.after_field_id, op.index, f"group '{op.group_id}'")
        children.insert(insert_at, _build_field(op.field, insert_at))
        return f"Added '{op.field.title}' ({op.field.type.value}) to the group '{_title_text(group)}'"
    if op.page_id is None:
        raise OpError("add_field needs a pageId (or a groupId to add into a repeating group).")
    page = _find_page(form, op.page_id)
    if page.properties is None:
        page.properties = StandardFieldProperty(fields=[])
    if page.properties.fields is None:
        page.properties.fields = []
    fields = page.properties.fields
    insert_at = _insert_position(fields, op.after_field_id, op.index, f"page '{op.page_id}'")

    field = _build_field(op.field, insert_at)
    fields.insert(insert_at, field)
    return f"Added '{op.field.title}' ({op.field.type.value}) to page {page.index + 1 if page.index is not None else '?'}"


def _logic_sources(form: StandardForm) -> set:
    """Ids of every field some respondent logic (visibility or jump) reads."""
    sources = set()
    for page in _pages(form):
        for jump in (page.properties.jumps if page.properties else None) or []:
            sources.update(c.field_id for c in jump.conditions or [])
        for field in (page.properties.fields if page.properties else None) or []:
            logic = field.properties.logic if field.properties else None
            sources.update(c.field_id for c in (logic.conditions if logic else None) or [])
    return sources


def _apply_add_group(form: StandardForm, op: AddGroupOp) -> str:
    page = _find_page(form, op.page_id)
    if page.properties is None:
        page.properties = StandardFieldProperty(fields=[])
    if page.properties.fields is None:
        page.properties.fields = []
    fields = page.properties.fields
    try:
        repeat = RepeatSettings(
            min_items=op.min_items,
            max_items=op.max_items,
            item_label=op.item_label,
            item_title=op.item_title,
            export_layout=op.export_layout,
        )
    except ValueError as e:
        raise OpError(_validation_message(e))
    children = []
    for i, spec in enumerate(op.fields):
        _check_child_type(spec.type)
        children.append(_build_field(spec, i))
    insert_at = _insert_position(fields, op.after_field_id, op.index, f"page '{op.page_id}'")
    group = StandardFormField(
        id=str(uuid.uuid4()),
        index=insert_at,
        type=StandardFormFieldType.GROUP,
        title=op.title,
        description=op.description,
        properties=StandardFieldProperty(fields=children, repeat=repeat, description=op.description),
        validations=StandardFieldValidations(),
    )
    fields.insert(insert_at, group)
    return (
        f"Added the repeating group '{op.title}' ({repeat.effective_min}-{repeat.effective_max} "
        f"x {op.item_label}, {len(children)} question(s)) as '{group.id}'"
    )


def _apply_update_field(form: StandardForm, op: UpdateFieldOp) -> str:
    _, field, _ = _find_field(form, op.field_id)
    if op.patch.internal and op.field_id in _logic_sources(form):
        raise OpError(
            f"'{_title_text(field)}' is used by conditional logic, so it cannot become "
            "internal — respondents never answer internal fields. Remove the rule first."
        )
    changed = _patch_field(field, op.patch)
    return f"Updated '{_title_text(field)}' ({', '.join(changed)})"


def _apply_remove_field(form: StandardForm, op: RemoveFieldOp) -> str:
    _, _, container, field, position = _locate_field(form, op.field_id)
    container.pop(position)
    return f"Removed '{_title_text(field)}'"


def _apply_move_field(form: StandardForm, op: MoveFieldOp) -> str:
    page, parent, container, field, position = _locate_field(form, op.field_id)
    if op.to_group_id is not None:
        _, group = _find_group(form, op.to_group_id)
        if group is field:
            raise OpError("A group cannot be moved into itself.")
        _check_child_type(field.type)
        target = _children(group)
        where = f"the group '{_title_text(group)}'"
    elif op.to_page_id is not None or parent is None:
        target_page = _find_page(form, op.to_page_id) if op.to_page_id else page
        if target_page.properties is None:
            target_page.properties = StandardFieldProperty(fields=[])
        if target_page.properties.fields is None:
            target_page.properties.fields = []
        target = target_page.properties.fields
        where = (
            f"page {target_page.index + 1 if target_page.index is not None else '?'}"
            if target_page is not page or parent is not None
            else None
        )
    else:
        target = container  # reorder within its group
        where = None

    container.pop(position)
    insert_at = max(0, min(op.index, len(target)))
    target.insert(insert_at, field)
    if where is None:
        return f"Moved '{_title_text(field)}' to position {insert_at + 1}"
    return f"Moved '{_title_text(field)}' to {where}"


def _apply_add_page(form: StandardForm, op: AddPageOp) -> str:
    if form.fields is None:
        form.fields = []
    new_fields = [_build_field(spec, i) for i, spec in enumerate(op.fields or [])]
    page = StandardFormField(
        id=str(uuid.uuid4()),
        index=0,  # renumbered afterwards
        type=StandardFormFieldType.SLIDE,
        properties=StandardFieldProperty(fields=new_fields, layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND),
    )
    pages = _pages(form)
    if op.index is None or op.index >= len(pages):
        form.fields.append(page)
    else:
        anchor = pages[max(0, op.index)]
        form.fields.insert(form.fields.index(anchor), page)
    return f"Added a page with {len(new_fields)} field(s)"


def _apply_remove_page(form: StandardForm, op: RemovePageOp) -> str:
    page = _find_page(form, op.page_id)
    form.fields.remove(page)
    count = len((page.properties.fields if page.properties else None) or [])
    return f"Removed a page ({count} field(s) with it)"


def _apply_update_form_info(form: StandardForm, op: UpdateFormInfoOp) -> str:
    changed = []
    if op.title is not None:
        form.title = op.title
        if form.welcome_page is not None:
            form.welcome_page.title = op.title
        changed.append("title")
    if op.description is not None:
        form.description = op.description
        changed.append("description")
    if not changed:
        raise OpError("The update contained no changes.")
    return f"Updated form {', '.join(changed)}"


_SETTINGS_LABELS = {
    "purpose": "purpose",
    "retention_text": "retention",
    "privacy_policy_url": "privacy policy link",
    "require_verified_identity": "verified-identity requirement",
    "allow_editing_response": "response editing",
    "show_submission_number": "submission numbers",
}


def _apply_update_form_settings(form: StandardForm, op: UpdateFormSettingsOp) -> str:
    """Settings live on the workspace-form association, not the form body —
    the engine validates and reports; ``persist_ops_to_form`` writes them."""
    changed = [
        _SETTINGS_LABELS[key]
        for key, value in op.patch.model_dump().items()
        if value is not None
    ]
    if not changed:
        raise OpError(
            "Nothing to change — provide at least one of: purpose, retentionText, "
            "privacyPolicyUrl, requireVerifiedIdentity, allowEditingResponse, showSubmissionNumber."
        )
    return "Updated form settings: " + ", ".join(changed)



CHOICE_TYPES = {StandardFormFieldType.MULTIPLE_CHOICE, StandardFormFieldType.DROPDOWN}


COUNT_COMPARISONS = {"IS_EQUAL", "IS_NOT_EQUAL", "GREATER_THAN", "GREATER_THAN_EQUAL", "LESS_THAN", "LESS_THAN_EQUAL"}


def _validated_value(source: StandardFormField, comparison: str, raw: Any) -> Any:
    if comparison in VALUELESS_COMPARISONS:
        return None
    if raw in (None, ""):
        raise OpError(f"Comparison '{comparison}' needs a value.")
    if source.type in CHOICE_TYPES:
        labels = [c.value for c in ((source.properties.choices if source.properties else None) or [])]
        if str(raw) not in labels:
            raise OpError(f"'{raw}' is not a choice of '{_title_text(source)}'. Choices: {', '.join(labels)}")
    if source.type == StandardFormFieldType.YES_NO and str(raw) not in ("Yes", "No"):
        raise OpError("Yes/No conditions take the value 'Yes' or 'No'.")
    return raw


def _validated_conditions(
    form: StandardForm, specs: List[LogicConditionSpec], scope_group_id: Optional[str] = None
) -> List[FieldLogicCondition]:
    """Resolve and validate condition sources against the actual form.

    Mirrors the builder's logic editor: fieldType is stamped from the source
    field; choice values must be one of the source's labels; yes/no values
    must be "Yes"/"No"; IS_EMPTY/IS_NOT_EMPTY take no value.

    Repeating groups: a question of a group can only be referenced by a
    sibling in the same group (``scope_group_id``) — it then means "this
    item's answer". Elsewhere the group is referenced as a whole
    (``groupMode`` COUNT / ANY / ALL), never by item position."""
    conditions: List[FieldLogicCondition] = []
    for spec in specs:
        _, parent, _, source, _ = _locate_field(form, spec.field_id)
        if source.internal:
            raise OpError(
                f"'{_title_text(source)}' is an internal field — respondents never "
                "answer it, so logic cannot depend on it."
            )
        source_type = getattr(source.type, "value", source.type)
        if parent is not None and parent.id != scope_group_id:
            raise OpError(
                f"'{_title_text(source)}' is asked once per item of '{_title_text(parent)}'. Outside the group, "
                "refer to the group itself with groupMode COUNT, ANY or ALL."
            )
        if _is_repeating_group(source):
            if spec.group_mode is None:
                raise OpError(
                    f"'{_title_text(source)}' is a repeating group: set groupMode to COUNT (number of items), "
                    "ANY or ALL (with childFieldId)."
                )
            if spec.group_mode == "COUNT":
                if spec.comparison not in COUNT_COMPARISONS:
                    raise OpError("Item-count conditions compare a number (e.g. IS_EQUAL, GREATER_THAN_EQUAL).")
                try:
                    count = int(spec.value)
                except (TypeError, ValueError):
                    raise OpError("Item-count conditions need a whole number as value.")
                conditions.append(
                    FieldLogicCondition(
                        field_id=spec.field_id, field_type=source_type, comparison=spec.comparison, value=count,
                        group_mode="COUNT",
                    )
                )
                continue
            child = next((c for c in _children(source) if c.id == spec.child_field_id), None)
            if child is None:
                raise OpError(f"ANY/ALL conditions need childFieldId: a question of '{_title_text(source)}'.")
            conditions.append(
                FieldLogicCondition(
                    field_id=spec.field_id, field_type=source_type, comparison=spec.comparison,
                    value=_validated_value(child, spec.comparison, spec.value),
                    group_mode=spec.group_mode, child_field_id=child.id,
                    child_field_type=getattr(child.type, "value", child.type),
                )
            )
            continue
        if spec.group_mode is not None:
            raise OpError(f"groupMode only applies to repeating groups, not '{_title_text(source)}'.")
        conditions.append(
            FieldLogicCondition(
                field_id=spec.field_id, field_type=source_type, comparison=spec.comparison,
                value=_validated_value(source, spec.comparison, spec.value),
            )
        )
    return conditions


def _apply_set_field_logic(form: StandardForm, op: SetFieldLogicOp) -> str:
    _, parent, _, field, _ = _locate_field(form, op.field_id)
    if field.properties is None:
        field.properties = StandardFieldProperty()
    if op.logic is None:
        field.properties.logic = None
        return f"Cleared the visibility rule on '{_title_text(field)}'"
    for spec in op.logic.conditions:
        if spec.field_id == op.field_id:
            raise OpError("A field's visibility cannot depend on its own answer.")
    conditions = _validated_conditions(form, op.logic.conditions, parent.id if parent is not None else None)
    field.properties.logic = FieldLogic(action=op.logic.action, operator=op.logic.operator, conditions=conditions)
    verb = "Show" if op.logic.action == "SHOW" else "Hide"
    return f"{verb} '{_title_text(field)}' when {len(conditions)} condition(s) match"


def _apply_set_page_jumps(form: StandardForm, op: SetPageJumpsOp) -> str:
    page = _find_page(form, op.page_id)
    if page.properties is None:
        page.properties = StandardFieldProperty()
    if op.jumps is None:
        page.properties.jumps = None
        return f"Cleared page jumps on page '{op.page_id}'"
    jumps: List[PageJump] = []
    for spec in op.jumps:
        if spec.target != JUMP_TARGET_SUBMIT:
            target_page = _find_page(form, spec.target)  # raises if unknown
            if target_page.id == op.page_id:
                raise OpError("A page cannot jump to itself.")
        jumps.append(
            PageJump(operator=spec.operator, conditions=_validated_conditions(form, spec.conditions), target=spec.target)
        )
    page.properties.jumps = jumps
    return f"Set {len(jumps)} jump rule(s) on page '{op.page_id}'"


def _apply_duplicate_page(form: StandardForm, op: DuplicatePageOp) -> str:
    original = _find_page(form, op.page_id)
    clone = original.model_copy(deep=True)
    clone.id = str(uuid.uuid4())
    id_map: Dict[str, str] = {}
    page_fields = (clone.properties.fields if clone.properties else None) or []
    all_fields = list(page_fields) + [c for f in page_fields if _is_repeating_group(f) for c in _children(f)]
    for field in all_fields:
        new_id = str(uuid.uuid4())
        id_map[field.id] = new_id
        field.id = new_id
        if field.properties and field.properties.choices:
            for choice in field.properties.choices:
                choice.id = str(uuid.uuid4())
    # Remap in-page logic references onto the cloned fields; references to
    # fields outside the page stay as they are.
    for field in all_fields:
        logic = field.properties.logic if field.properties else None
        for condition in (logic.conditions if logic else None) or []:
            if condition.field_id in id_map:
                condition.field_id = id_map[condition.field_id]
            if condition.child_field_id in id_map:
                condition.child_field_id = id_map[condition.child_field_id]
        repeat = field.properties.repeat if field.properties else None
        if repeat is not None and repeat.item_title:
            for old_id, new_id in id_map.items():
                repeat.item_title = repeat.item_title.replace(old_id, new_id)
    # Cloned jumps would re-branch from the copy in surprising ways — drop them.
    if clone.properties:
        clone.properties.jumps = None
        clone.properties.position = None
    pages = form.fields or []
    original_position = next(i for i, f in enumerate(pages) if f.id == op.page_id)
    insert_at = op.index if op.index is not None else original_position + 1
    insert_at = max(0, min(insert_at, len(pages)))
    pages.insert(insert_at, clone)
    field_count = len((clone.properties.fields if clone.properties else None) or [])
    return f"Duplicated page '{op.page_id}' ({field_count} fields) as '{clone.id}'"


def _apply_update_theme(form: StandardForm, op: UpdateThemeOp) -> str:
    form.theme = op.theme
    return f"Applied theme '{op.theme.title}'"


_HANDLERS = {
    "add_field": _apply_add_field,
    "add_group": _apply_add_group,
    "update_field": _apply_update_field,
    "remove_field": _apply_remove_field,
    "move_field": _apply_move_field,
    "add_page": _apply_add_page,
    "remove_page": _apply_remove_page,
    "update_form_info": _apply_update_form_info,
    "update_form_settings": _apply_update_form_settings,
    "set_field_logic": _apply_set_field_logic,
    "set_page_jumps": _apply_set_page_jumps,
    "duplicate_page": _apply_duplicate_page,
    "update_theme": _apply_update_theme,
}


def apply_form_ops(form: StandardForm, ops: List[FormOp]) -> Tuple[StandardForm, List[OpResult]]:
    """Apply operations to a deep copy of ``form``; the original is untouched.

    Per-op failures are recorded and skipped (the chat turn survives a bad
    op); the returned form is renumbered and re-validated as a whole.
    """
    working = form.model_copy(deep=True)
    results: List[OpResult] = []

    for i, op in enumerate(ops):
        handler = _HANDLERS.get(op.op)
        try:
            if handler is None:
                raise OpError(f"Unknown operation '{op.op}'.")
            message = handler(working, op)
            results.append(OpResult(index=i, op=op.op, ok=True, message=message))
        except OpError as e:
            results.append(OpResult(index=i, op=op.op, ok=False, message=str(e)))

    _renumber(working)
    # The schema is the final arbiter — a structurally invalid result must
    # never leave this function.
    validated = StandardForm.model_validate(working.model_dump())
    return validated, results


def parse_ops(payload: List[Dict[str, Any]]) -> List[FormOp]:
    """Parse a raw ops payload (AI/MCP JSON) into typed operations."""
    return FormOps.model_validate({"ops": payload}).ops
