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

import json
import uuid
from contextvars import ContextVar
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
)

from common.form_spec.models import (
    MAX_FIELDS,
    MAX_PAGES,
    checked_pattern,
    count_fields,
)
from common.expressions import validate_expression
from common.models.standard_form import (
    DATE_RULES_MAX,
    CalculationFormat,
    DateRule,
    FieldLogic,
    FieldLogicCondition,
    FieldPosition,
    LayoutType,
    LOGO_ALT_MAX_LENGTH,
    PageJump,
    REPEAT_CHILD_FIELD_TYPES,
    RepeatSettings,
    StandardChoice,
    StandardFieldAttachment,
    StandardFieldProperty,
    StandardFieldValidations,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
    Theme,
    WelcomePageField,
    date_rule_problems,
    prune_date_rules,
    SECTION_TITLE_MAX_LENGTH,
    WHY_WE_ASK_MAX_LENGTH,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    WithJsonSchema,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from backend.app.constants.themes import (
    THEME_STYLES,
    preset_name,
    themes as THEME_PRESETS,
)
from backend.app.models.dtos.response_dtos import StandardFormFieldCamelModel
from backend.app.services.calculated_fields import calculated_field_problems
from backend.app.services.image_urls import (
    IMAGE_URL_ERROR,
    checked_image_url,
    first_party_image_url,
)
from backend.app.services.internal_fields import (
    INTERNAL_CAPABLE_TYPES,
    internal_logic_violations,
)
from backend.app.services.policy_url import checked_policy_url
from backend.app.services.rich_text import style_value_problem
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
    StandardFormFieldType.CALCULATED,  # a computed value (expression AST)
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


# Client references: an op that creates a page, field or group may name it
# with ``ref``; later ops of the same batch use ``"$ref:<name>"`` wherever a
# page or field id is expected (REF_ID_KEYS), logic conditions and page
# jumps included. Resolved while the batch is applied (see _resolve_refs).
REF_PREFIX = "$ref:"
REF_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"
REF_ID_KEYS = frozenset(
    {
        "page_id",
        "field_id",
        "group_id",
        "after_field_id",
        "to_page_id",
        "to_group_id",
        "child_field_id",
        "target",
        # a calculated field's expression: {"var": "$ref:<name>"}
        "var",
    }
)
_RefName = Annotated[Optional[str], Field(None, pattern=REF_PATTERN)]

# Most questions one add_page / add_group may create (checked when parsing;
# the form's own size limits, MAX_PAGES / MAX_FIELDS, when applying).
MAX_NEW_PAGE_FIELDS = 200
MAX_NEW_GROUP_FIELDS = 100


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
    # date only: a short label shown with the picker ("Start date")
    label: Optional[str] = Field(None, max_length=120)
    # "Why we ask this", shown under the question; publishing needs one on
    # email, phone and ID-number questions (services/publish_checks.py).
    why_we_ask: Optional[str] = Field(None, max_length=WHY_WE_ASK_MAX_LENGTH)
    # calculated only: the formula as an expressions-v1 AST
    # (docs/spec/expressions-v1.md), its display format, and whether
    # respondents never see the value (computed and stored only).
    expression: Optional[Any] = None
    format: Optional[CalculationFormat] = None
    hidden_from_respondents: Optional[bool] = None
    unanswered_as_zero: Optional[bool] = None
    # Client reference for the new field (see REF_PREFIX).
    ref: _RefName = None


class DateRuleSpec(_CamelModel):
    """A date question's constraint: its answer must be ``comparison`` a
    fixed ``date`` (YYYY-MM-DD), ``today`` or the answer of another date
    question (``fieldId``; inside a repeating group a sibling of the same
    group, outside a group never a group's question)."""

    comparison: Literal["before", "after", "on_or_before", "on_or_after"]
    target: Literal["date", "today", "field"]
    date: Optional[str] = None
    field_id: Optional[str] = None


class FieldPatch(_CamelModel):
    """Partial update of an existing field. Absent = unchanged. The
    ``*_items`` / ``item_*`` / ``export_layout`` keys only apply to
    repeating groups."""

    # Plain text. The form editor may also send a rich-text (TipTap)
    # document (see _check_title); nobody else may.
    title: Optional[Union[str, Dict[str, Any]]] = None
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
    # date questions only: a short label shown with the picker ("" clears),
    # and the date rules (full replacement; [] clears).
    label: Optional[str] = Field(None, max_length=120)
    date_rules: Optional[List[DateRuleSpec]] = None
    # "Why we ask this" line under the question ("" clears).
    why_we_ask: Optional[str] = Field(None, max_length=WHY_WE_ASK_MAX_LENGTH)
    # calculated fields only (see NewFieldSpec)
    expression: Optional[Any] = None
    format: Optional[CalculationFormat] = None
    hidden_from_respondents: Optional[bool] = None
    unanswered_as_zero: Optional[bool] = None

    @field_validator("title", mode="before")
    @classmethod
    def _plain_title_outside_the_editor(cls, value: Any, info: ValidationInfo) -> Any:
        if isinstance(value, dict) and not (info.context or {}).get(EDITOR_CONTEXT):
            raise PydanticCustomError(
                "rich_text_title",
                "A title must be plain text here; rich-text titles come only "
                "from the form editor.",
            )
        return value


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
    ref: _RefName = None


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
    fields: List[NewFieldSpec] = Field(
        default_factory=list, max_length=MAX_NEW_GROUP_FIELDS
    )
    after_field_id: Optional[str] = None
    index: Optional[int] = None
    ref: _RefName = None


class RemoveFieldOp(_CamelModel):
    op: Literal["remove_field"] = "remove_field"
    field_id: str


class MoveFieldOp(_CamelModel):
    """Move a question within its page, to another page (``to_page_id``)
    or into a repeating group (``to_group_id``), at ``index`` (default: the
    end)."""

    op: Literal["move_field"] = "move_field"
    field_id: str
    to_page_id: Optional[str] = None  # default: same page (or group)
    # Move into a repeating group (asked once per item). A child moved with
    # ``to_page_id`` leaves its group.
    to_group_id: Optional[str] = None
    index: Optional[int] = None


class AddPageOp(_CamelModel):
    op: Literal["add_page"] = "add_page"
    index: Optional[int] = None  # default: append
    fields: Optional[List[NewFieldSpec]] = Field(None, max_length=MAX_NEW_PAGE_FIELDS)
    ref: _RefName = None


class MovePageOp(_CamelModel):
    """Move a question page to ``index`` (0-based among the question
    pages; past the end = last)."""

    op: Literal["move_page"] = "move_page"
    page_id: str
    index: int


VALIDATION_PRESETS = {
    "digits": "^[0-9]+$",
    "letters": "^[A-Za-z\u00C0-\u024F' -]+$",
    "alphanumeric": "^[A-Za-z0-9]+$",
}
# PATTERN_MAX_LENGTH and the pattern rule itself: common.form_spec.models


class FieldValidationPatch(_CamelModel):
    """Answer constraints of a question. Absent = unchanged, null = cleared.
    ``preset`` picks a named pattern (VALIDATION_PRESETS); ``pattern`` is
    a regular expression of your own."""

    required: Optional[bool] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_choices: Optional[int] = None
    max_choices: Optional[int] = None
    pattern: Optional[str] = None
    preset: Optional[Literal["digits", "letters", "alphanumeric"]] = None


class SetFieldValidationOp(_CamelModel):
    op: Literal["set_field_validation"] = "set_field_validation"
    field_id: str
    validation: FieldValidationPatch


class SetQuestionNumberingOp(_CamelModel):
    """Number the questions of one page (``page_id``) or of every page."""

    op: Literal["set_question_numbering"] = "set_question_numbering"
    page_id: Optional[str] = None
    show: bool


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
    ref: _RefName = None


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


class SetThemePresetOp(_CamelModel):
    """Dress the form in one of the theme presets (constants/themes.py), by
    name (any case), as the builder's theme picker does: the preset's
    colours, no background, and its own style if it has one (Leaflet), else
    the form's current style. ``style`` sets the style instead
    (constants/themes.py THEME_STYLES). Both are checked when the op is
    applied, so an unknown name fails alone instead of the whole turn."""

    op: Literal["set_theme_preset"] = "set_theme_preset"
    name: str = Field(max_length=60)
    style: Optional[str] = Field(default=None, max_length=30)


class SetSectionTitleOp(_CamelModel):
    """Name a question page's section (``properties.sectionTitle``): what
    the Leaflet section bar and the welcome page's contents list show for
    the page, before its opening heading and its first question. The page is
    given by ``page_id`` or by ``page_index`` (0-based, among the question
    pages, the ``index`` of the form snapshot). ``title`` null or "" clears
    it. The welcome page and the ending have no section title.

    The length is checked when the op is applied, not when it is parsed, so
    one long title fails alone instead of the whole turn."""

    op: Literal["set_section_title"] = "set_section_title"
    page_id: Optional[str] = None
    page_index: Optional[int] = None
    title: Optional[str] = None


# ===========================================================================
# Editor ops: models
#
# Lossless, id-addressed edits for the form editor. The editor sends whole
# questions and pages with the ids it chose, and these ops keep every id and
# every property they are given. They are checked like a whole-form save
# (PATCH .../forms/{form_id}) and refused everywhere else for now: a payload
# is parsed with them only when the caller passes ``allow_editor_ops=True`` to
# parse_ops (EDITOR_ONLY_OPS). Handlers: "Editor ops: handlers" below.
# ===========================================================================

# Validation context key that admits the editor ops (see parse_ops).
EDITOR_CONTEXT = "editor_ops"


class _EditorOp(_CamelModel):
    """An op only the form editor may send."""

    @model_validator(mode="before")
    @classmethod
    def _editor_only(cls, data: Any, info: ValidationInfo) -> Any:
        if not (info.context or {}).get(EDITOR_CONTEXT):
            raise PydanticCustomError(
                "editor_only_op",
                "The operation '{op}' is only available in the form editor; "
                "it cannot be used here.",
                {"op": cls.model_fields["op"].default},
            )
        return data


# A question or page as the editor holds it (the camelCase shape a
# whole-form save takes, StandardFormFieldCamelModel). Read when the op is
# applied, so a refused one fails alone.
EDITOR_FIELD_DEF = "EditorField"
EditorFieldPayload = Annotated[
    Dict[str, Any],
    # ops_schema.py points this at the EditorField definition
    WithJsonSchema({"type": "object", "x-editorField": True}),
]


class _StrictPatch(_CamelModel):
    """A partial update: a key left out stays as it is, null clears it,
    unknown keys are refused."""

    model_config = ConfigDict(
        populate_by_name=True, alias_generator=to_camel, extra="forbid"
    )


class InsertFieldOp(_EditorOp):
    """Insert a complete question, its id kept, on a page at ``index`` (or,
    with ``group_id``, into that repeating group)."""

    op: Literal["insert_field"] = "insert_field"
    page_id: Optional[str] = None
    group_id: Optional[str] = None
    index: int = Field(ge=0)
    field: EditorFieldPayload


class ReplaceFieldOp(_EditorOp):
    """Replace the question with ``field.id`` by ``field``, where it is."""

    op: Literal["replace_field"] = "replace_field"
    field: EditorFieldPayload


class InsertPageOp(_EditorOp):
    """Insert a complete page (type ``slide``, its questions included), ids
    kept, at ``index`` among the question pages."""

    op: Literal["insert_page"] = "insert_page"
    index: int = Field(ge=0)
    page: EditorFieldPayload


class PagePatch(_StrictPatch):
    layout: Optional[LayoutType] = None
    image_url: Optional[str] = None
    theme: Optional[Theme] = None
    position: Optional[FieldPosition] = None
    show_question_numbers: Optional[bool] = None
    section_title: Optional[str] = None


class UpdatePageOp(_EditorOp):
    op: Literal["update_page"] = "update_page"
    page_id: str
    patch: PagePatch


class WelcomePagePatch(_StrictPatch):
    title: Optional[str] = None
    description: Optional[str] = None
    layout: Optional[LayoutType] = None
    image_url: Optional[str] = None
    button_text: Optional[str] = None


class UpdateWelcomePageOp(_EditorOp):
    op: Literal["update_welcome_page"] = "update_welcome_page"
    patch: WelcomePagePatch


class SetHiddenFieldsOp(_EditorOp):
    """The form's hidden fields (URL parameter names), as a whole. Pipes of
    names no longer listed are removed from question titles."""

    op: Literal["set_hidden_fields"] = "set_hidden_fields"
    names: List[str]


class UpdateLogoOp(_EditorOp):
    """The logo's settings. The logo itself only changes by an upload."""

    op: Literal["update_logo"] = "update_logo"
    position: Optional[Literal["auto", "left", "center"]] = None
    alt: Optional[str] = None
    use_workspace_logo: Optional[bool] = None


class EditorChoice(_CamelModel):
    id: str
    value: Optional[str] = None
    ref: Optional[str] = None
    label: Optional[str] = None
    attachment: Optional[StandardFieldAttachment] = None


class SetChoiceOp(_EditorOp):
    op: Literal["set_choice"] = "set_choice"
    field_id: str
    choice_id: str
    value: Optional[str] = None


class AddChoiceOp(_EditorOp):
    """Add a choice, its id kept, at ``index`` (default: the end)."""

    op: Literal["add_choice"] = "add_choice"
    field_id: str
    choice: EditorChoice
    index: Optional[int] = Field(None, ge=0)


class RemoveChoiceOp(_EditorOp):
    op: Literal["remove_choice"] = "remove_choice"
    field_id: str
    choice_id: str


class MoveChoiceOp(_EditorOp):
    op: Literal["move_choice"] = "move_choice"
    field_id: str
    choice_id: str
    index: int = Field(ge=0)


EDITOR_OP_TYPES = (
    InsertFieldOp,
    ReplaceFieldOp,
    InsertPageOp,
    UpdatePageOp,
    UpdateWelcomePageOp,
    SetHiddenFieldsOp,
    UpdateLogoOp,
    SetChoiceOp,
    AddChoiceOp,
    RemoveChoiceOp,
    MoveChoiceOp,
)
# Ops only the form editor may send (refused by parse_ops without allow_editor_ops=True).
EDITOR_ONLY_OPS = frozenset(t.model_fields["op"].default for t in EDITOR_OP_TYPES)

# ===========================================================================
# End of editor ops: models
# ===========================================================================


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
        SetThemePresetOp,
        SetSectionTitleOp,
        MovePageOp,
        SetFieldValidationOp,
        SetQuestionNumberingOp,
        # editor ops (EDITOR_OP_TYPES)
        InsertFieldOp,
        ReplaceFieldOp,
        InsertPageOp,
        UpdatePageOp,
        UpdateWelcomePageOp,
        SetHiddenFieldsOp,
        UpdateLogoOp,
        SetChoiceOp,
        AddChoiceOp,
        RemoveChoiceOp,
        MoveChoiceOp,
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
    # The id of the page, field or group the op created, if any.
    created_id: Optional[str] = None


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


INTERNAL_IN_GROUP_MESSAGE = (
    "Internal fields cannot be placed inside a repeating group — staff fill them "
    "in once per submission, not per item."
)


def _check_child_type(field_type: Any, internal: Optional[bool] = None) -> None:
    value = getattr(field_type, "value", field_type)
    if value == StandardFormFieldType.GROUP.value:
        raise OpError("Repeating groups cannot contain another group.")
    if internal:
        raise OpError(INTERNAL_IN_GROUP_MESSAGE)
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
    if spec.why_we_ask and spec.why_we_ask.strip():
        properties.why_we_ask = spec.why_we_ask.strip()
    if spec.label:
        if spec.type != StandardFormFieldType.DATE:
            raise OpError("A label only applies to date questions.")
        properties.label = spec.label

    _set_calculation(
        spec.type, properties, spec.expression, spec.format, spec.hidden_from_respondents, spec.unanswered_as_zero
    )
    if spec.type == StandardFormFieldType.CALCULATED and spec.required:
        raise OpError("A calculation is computed, never answered, so it cannot be required.")

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


def _set_calculation(
    field_type: Any,
    properties: StandardFieldProperty,
    expression: Any,
    format: Optional[CalculationFormat],
    hidden: Optional[bool],
    as_zero: Optional[bool] = None,
) -> List[str]:
    """Set a calculated field's expression, format and visibility (only the
    ones given); refuses them on any other type and a malformed AST (with the
    path of the bad node). Variables are checked against the form after the
    op (apply_form_ops). Returns change fragments."""
    given = [
        name
        for name, value in (
            ("expression", expression),
            ("format", format),
            ("hiddenFromRespondents", hidden),
            ("unansweredAsZero", as_zero),
        )
        if value is not None
    ]
    if not given:
        return []
    if getattr(field_type, "value", field_type) != StandardFormFieldType.CALCULATED.value:
        raise OpError(f"{', '.join(given)}: only calculated fields have these.")
    if expression is not None:
        problems = validate_expression(expression)
        if problems:
            raise OpError(f"The expression is not valid at '{problems[0].path or '/'}': {problems[0].message}")
        properties.expression = expression
    if format is not None:
        properties.format = format
    if hidden is not None:
        properties.hidden_from_respondents = True if hidden else None
    if as_zero is not None:
        properties.unanswered_as_zero = as_zero
    labels = {
        "expression": "formula",
        "format": "format",
        "hiddenFromRespondents": "visibility",
        "unansweredAsZero": "unanswered as 0",
    }
    return [labels[name] for name in given]


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
    if patch.why_we_ask is not None:
        field.properties.why_we_ask = patch.why_we_ask.strip() or None
        changed.append("why we ask this")
    if patch.internal:
        _ensure_can_be_internal(field.type)
    if patch.internal is not None:
        field.internal = True if patch.internal else None
        changed.append("internal" if patch.internal else "respondent-facing")
    if patch.label is not None:
        if field.type != StandardFormFieldType.DATE:
            raise OpError("A label only applies to date questions.")
        field.properties.label = patch.label.strip() or None
        changed.append("label")
    if patch.date_rules is not None:
        # validated against the form by _apply_update_field beforehand
        field.properties.date_rules = _date_rules(patch.date_rules) or None
        changed.append("date rules")
    changed.extend(
        _set_calculation(
            field.type,
            field.properties,
            patch.expression,
            patch.format,
            patch.hidden_from_respondents,
            patch.unanswered_as_zero,
        )
    )
    if patch.required and field.type == StandardFormFieldType.CALCULATED:
        raise OpError("A calculation is computed, never answered, so it cannot be required.")
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
        _check_child_type(op.field.type, op.field.internal)
        children = _children(group)
        insert_at = _insert_position(children, op.after_field_id, op.index, f"group '{op.group_id}'")
        child = _build_field(op.field, insert_at)
        children.insert(insert_at, child)
        _note_created(child.id)
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
    _note_created(field.id)
    return f"Added '{op.field.title}' ({op.field.type.value}) to page {page.index + 1 if page.index is not None else '?'}"


def _logic_sources(form: StandardForm) -> set:
    """Ids of every field some respondent logic (visibility or jump) reads."""
    sources = set()
    for page in _pages(form):
        for jump in (page.properties.jumps if page.properties else None) or []:
            sources.update(c.field_id for c in jump.conditions or [])
        for field in (page.properties.fields if page.properties else None) or []:
            questions = [field] + (_children(field) if _is_repeating_group(field) else [])
            for question in questions:
                logic = question.properties.logic if question.properties else None
                for c in (logic.conditions if logic else None) or []:
                    sources.add(c.field_id)
                    if c.child_field_id:
                        sources.add(c.child_field_id)
    for page in _pages(form):
        for jump in (page.properties.jumps if page.properties else None) or []:
            sources.update(c.child_field_id for c in jump.conditions or [] if c.child_field_id)
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
        _check_child_type(spec.type, spec.internal)
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
    _note_created(group.id, [child.id for child in children])
    return (
        f"Added the repeating group '{op.title}' ({repeat.effective_min}-{repeat.effective_max} "
        f"x {op.item_label}, {len(children)} question(s)) as '{group.id}'"
    )


def _date_rules(specs: List[DateRuleSpec]) -> List[DateRule]:
    if len(specs) > DATE_RULES_MAX:
        raise OpError(f"A date question can have at most {DATE_RULES_MAX} date rules.")
    try:
        return [DateRule.model_validate(spec.model_dump()) for spec in specs]
    except ValueError as e:
        raise OpError(_validation_message(e))


def _check_date_rules_patch(
    form: StandardForm, field: StandardFormField, specs: List[DateRuleSpec]
) -> None:
    """Date rules go through the same checks as a builder save: an existing
    date question of the same scope, never itself, no circle."""
    if field.type != StandardFormFieldType.DATE:
        raise OpError("Date rules only apply to date questions.")
    rules = _date_rules(specs)
    previous = field.properties.date_rules if field.properties else None
    known = set(date_rule_problems(form.fields))
    if field.properties is None:
        field.properties = StandardFieldProperty(fields=[])
    field.properties.date_rules = rules or None
    try:
        problems = [p for p in date_rule_problems(form.fields) if p not in known]
    finally:
        field.properties.date_rules = previous
    if problems:
        raise OpError(problems[0])


def _date_rule_sources(form: StandardForm) -> set:
    """Ids of every question some date rule compares with."""
    sources = set()
    for page in _pages(form):
        for field in (page.properties.fields if page.properties else None) or []:
            questions = [field] + (
                _children(field) if _is_repeating_group(field) else []
            )
            for question in questions:
                rules = (
                    question.properties.date_rules if question.properties else None
                ) or []
                sources.update(r.field_id for r in rules if r.field_id)
    return sources


def _apply_update_field(form: StandardForm, op: UpdateFieldOp) -> str:
    _, parent, _, field, _ = _locate_field(form, op.field_id)
    _check_title(op.patch.title)
    if op.patch.internal and parent is not None:
        raise OpError(INTERNAL_IN_GROUP_MESSAGE)
    if op.patch.internal and op.field_id in _logic_sources(form):
        raise OpError(
            f"'{_title_text(field)}' is used by conditional logic, so it cannot become "
            "internal — respondents never answer internal fields. Remove the rule first."
        )
    if op.patch.internal and op.field_id in _date_rule_sources(form):
        raise OpError(
            f"'{_title_text(field)}' is used by a date rule, so it cannot become "
            "internal — respondents never answer internal fields. Remove the rule first."
        )
    if op.patch.date_rules is not None:
        _check_date_rules_patch(form, field, op.patch.date_rules)
    changed = _patch_field(field, op.patch)
    return f"Updated '{_title_text(field)}' ({', '.join(changed)})"


def _dropped_rules_note(form: StandardForm) -> str:
    dropped = prune_date_rules(form.fields)
    return f" (and {dropped} date rule(s) that used it)" if dropped else ""


def _apply_remove_field(form: StandardForm, op: RemoveFieldOp) -> str:
    _, _, container, field, position = _locate_field(form, op.field_id)
    container.pop(position)
    gone = {f.id for f in _subtree(field)}
    return (
        f"Removed '{_title_text(field)}'{_dropped_rules_note(form)}"
        f"{_dropped_references_note(form, gone)}"
    )


def _apply_move_field(form: StandardForm, op: MoveFieldOp) -> str:
    page, parent, container, field, position = _locate_field(form, op.field_id)
    if op.to_group_id is not None:
        _, group = _find_group(form, op.to_group_id)
        if group is field:
            raise OpError("A group cannot be moved into itself.")
        _check_child_type(field.type, field.internal)
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
    insert_at = len(target) if op.index is None else max(0, min(op.index, len(target)))
    target.insert(insert_at, field)
    # In or out of a repeating group: rules across the boundary don't apply.
    note = _dropped_rules_note(form)
    if where is None:
        return f"Moved '{_title_text(field)}' to position {insert_at + 1}{note}"
    return f"Moved '{_title_text(field)}' to {where}{note}"


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
    _note_created(page.id, [field.id for field in new_fields])
    return f"Added a page with {len(new_fields)} field(s)"


def _apply_remove_page(form: StandardForm, op: RemovePageOp) -> str:
    page = _find_page(form, op.page_id)
    form.fields.remove(page)
    count = len((page.properties.fields if page.properties else None) or [])
    return (
        f"Removed a page ({count} field(s) with it){_dropped_rules_note(form)}"
        f"{_dropped_references_note(form, {f.id for f in _subtree(page)})}"
    )


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
    if op.patch.privacy_policy_url is not None:
        # Respondents get it as a link: http(s) only.
        try:
            checked_policy_url(op.patch.privacy_policy_url)
        except ValueError as error:
            raise OpError(str(error))
    return "Updated form settings: " + ", ".join(changed)


_SETTINGS_TEXT_KEYS = ("purpose", "retention_text", "privacy_policy_url")
_SETTINGS_SWITCH_KEYS = (
    "require_verified_identity",
    "allow_editing_response",
    "show_submission_number",
)


def apply_settings_ops(settings: Any, ops, results: List["OpResult"]) -> bool:
    """Put the applied update_form_settings ops on ``settings`` (the
    workspace-form association's), in place: text is trimmed and '' clears
    it, switches are set as given. Returns whether any op applied. The one
    place these semantics live: the save (persist_ops_to_form) and the dry
    run both use it."""
    patches = [
        op.patch
        for op, result in zip(ops, results)
        if result.ok and isinstance(op, UpdateFormSettingsOp)
    ]
    for patch in patches:
        for key in _SETTINGS_TEXT_KEYS:
            value = getattr(patch, key)
            if value is not None:
                setattr(settings, key, value.strip() or None)
        for key in _SETTINGS_SWITCH_KEYS:
            value = getattr(patch, key)
            if value is not None:
                setattr(settings, key, value)
    return bool(patches)



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
        for rule in (field.properties.date_rules if field.properties else None) or []:
            if rule.field_id in id_map:
                rule.field_id = id_map[rule.field_id]
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
    _note_created(clone.id)
    field_count = len((clone.properties.fields if clone.properties else None) or [])
    return f"Duplicated page '{op.page_id}' ({field_count} fields) as '{clone.id}'"


def _apply_update_theme(form: StandardForm, op: UpdateThemeOp) -> str:
    theme = op.theme.model_copy(deep=True)
    background = theme.background
    if background is not None and background.imageUrl is not None:
        # Respondent pages load it directly: our storage or Unsplash only
        # (services/image_urls.py).
        try:
            background.imageUrl = checked_image_url(background.imageUrl) or None
        except ValueError as error:
            raise OpError(f"Background image refused: {error}")
    form.theme = theme
    return f"Applied theme '{op.theme.title}'"


def _apply_set_theme_preset(form: StandardForm, op: SetThemePresetOp) -> str:
    # A legacy name (Blue, Green, ...) means the nearest preset (Ocean,
    # Forest, ...), so the builder's picker shows what the model chose.
    name = preset_name(op.name)
    preset = THEME_PRESETS.get(name) if name else None
    if preset is None:
        raise OpError(
            f"There is no theme preset named '{op.name}'. "
            f"Pick one of: {', '.join(THEME_PRESETS)}."
        )
    theme = preset.model_copy(deep=True)
    if op.style is not None:
        style = op.style.strip().lower()
        if style not in THEME_STYLES:
            raise OpError(
                f"There is no style named '{op.style}'. "
                f"Pick one of: {', '.join(THEME_STYLES)}."
            )
        theme.style = style
    elif theme.style is None and form.theme is not None:
        theme.style = form.theme.style
    form.theme = theme
    style = f" in the {theme.style} style" if theme.style else ""
    return f"Applied the '{theme.title}' theme{style}"


# Ids a model may use for the pages that are not question pages.
_WELCOME_PAGE_IDS = {"welcome", "welcome_page", "welcomepage", "start", "intro"}
_ENDING_PAGE_IDS = {
    "ending", "end", "thankyou", "thank_you", "thankyou_page", "thank_you_page",
    "thankyoupage",
}
_NO_SECTION_TITLE = (
    "Only question pages have a section title; the {page} has none. "
    "Change the {instead} instead."
)


def _section_page(form: StandardForm, op: SetSectionTitleOp) -> Tuple[StandardFormField, int]:
    """The question page an op addresses, with its 1-based number."""
    pages = _pages(form)
    if (op.page_id is None) == (op.page_index is None):
        raise OpError("set_section_title needs either a pageId or a pageIndex.")
    if op.page_index is not None:
        if not 0 <= op.page_index < len(pages):
            raise OpError(
                f"There is no page with index {op.page_index}: the form has "
                f"{len(pages)} question page(s), indexed from 0."
            )
        return pages[op.page_index], op.page_index + 1
    key = op.page_id.strip().lower()
    if key in _WELCOME_PAGE_IDS:
        raise OpError(_NO_SECTION_TITLE.format(page="welcome page", instead="form title"))
    if key in _ENDING_PAGE_IDS:
        raise OpError(_NO_SECTION_TITLE.format(page="ending", instead="ending's heading"))
    for number, page in enumerate(pages, start=1):
        if page.id == op.page_id:
            return page, number
    try:
        _, _, _, field, _ = _locate_field(form, op.page_id)
    except OpError:
        raise OpError(f"Page '{op.page_id}' was not found — it may have been removed.")
    raise OpError(
        f"'{_title_text(field)}' is a question, not a page: use the id of the page it is on."
    )


def _apply_set_section_title(form: StandardForm, op: SetSectionTitleOp) -> str:
    if "title" not in op.model_fields_set:
        raise OpError('set_section_title needs a "title" (null or "" clears it).')
    page, number = _section_page(form, op)
    # Plain text on one line: runs of whitespace (newlines too) become a space.
    title = " ".join((op.title or "").split())
    if len(title) > SECTION_TITLE_MAX_LENGTH:
        raise OpError(
            f"A section title can be at most {SECTION_TITLE_MAX_LENGTH} characters "
            f"(this one has {len(title)}). Keep it short and plain."
        )
    if page.properties is None:
        page.properties = StandardFieldProperty(fields=[])
    page.properties.section_title = title or None
    if not title:
        return (
            f"Cleared the section title of page {number} (it shows its opening "
            "heading or first question again)"
        )
    return f"Section title of page {number}: '{title}'"


def _apply_move_page(form: StandardForm, op: MovePageOp) -> str:
    page = _find_page(form, op.page_id)
    if op.index < 0:
        raise OpError("A page's new position (index) must be 0 or more.")
    old = _pages(form).index(page)
    form.fields.remove(page)
    rest = _pages(form)
    target = min(op.index, len(rest))
    if target >= len(rest):
        form.fields.append(page)
    else:
        form.fields.insert(form.fields.index(rest[target]), page)
    if target == old:
        return f"Page {old + 1} stays at position {old + 1}"
    return f"Moved page {old + 1} to position {target + 1}"


# Which questions each kind of answer rule applies to.
_LENGTH_TYPES = {StandardFormFieldType.SHORT_TEXT, StandardFormFieldType.LONG_TEXT}
_PATTERN_TYPES = {StandardFormFieldType.SHORT_TEXT}
_VALUE_TYPES = {StandardFormFieldType.NUMBER}


def _rule_applies(field: StandardFormField, types, rule: str, kinds: str) -> None:
    if field.type not in types:
        kind = field.type.value if field.type else "unknown"
        raise OpError(
            f"{rule} only apply to {kinds} questions; '{_title_text(field)}' is a "
            f"{kind} question."
        )


def _checked_pattern(pattern: str) -> str:
    # The spec's rule (compile only; see checked_pattern on matching).
    try:
        return checked_pattern(pattern)
    except ValueError as error:
        raise OpError(str(error))


def _apply_set_field_validation(form: StandardForm, op: SetFieldValidationOp) -> str:
    _, _, _, field, _ = _locate_field(form, op.field_id)
    patch = op.validation
    given = patch.model_fields_set
    if not given:
        raise OpError(
            "Nothing to change — give at least one of: required, minLength, maxLength, "
            "minValue, maxValue, minChoices, maxChoices, pattern, preset."
        )
    if patch.pattern is not None and patch.preset is not None:
        raise OpError("Give either a pattern or a preset, not both.")
    # Work on a copy: a refused rule leaves the question as it was.
    rules = (field.validations or StandardFieldValidations()).model_copy()
    changed: List[str] = []

    if "required" in given:
        rules.required = patch.required
        changed.append("required" if patch.required else "optional")
    for key, label in (("min_length", "minimum length"), ("max_length", "maximum length")):
        if key in given:
            _rule_applies(field, _LENGTH_TYPES, "Text lengths", "short or long text")
            value = getattr(patch, key)
            if value is not None and value < 0:
                raise OpError(f"The {label} cannot be negative.")
            setattr(rules, key, value)
            changed.append(label)
    for key, label in (("min_value", "minimum"), ("max_value", "maximum")):
        if key in given:
            _rule_applies(field, _VALUE_TYPES, "Minimum and maximum values", "number")
            setattr(rules, key, getattr(patch, key))
            changed.append(label)
    for key, label in (("min_choices", "minimum choices"), ("max_choices", "maximum choices")):
        if key in given:
            value = getattr(patch, key)
            if field.type != StandardFormFieldType.MULTIPLE_CHOICE or not (
                field.properties and field.properties.allow_multiple_selection
            ):
                raise OpError(
                    "A number of choices only applies to a multiple choice question "
                    f"that allows several answers; '{_title_text(field)}' does not."
                )
            if value is not None:
                available = len((field.properties.choices if field.properties else None) or [])
                if value < (1 if key == "max_choices" else 0):
                    raise OpError(f"The {label} must be a positive number.")
                if value > available:
                    raise OpError(
                        f"'{_title_text(field)}' has {available} choice(s), so the {label} "
                        f"cannot be {value}."
                    )
            setattr(rules, key, value)
            changed.append(label)
    if "pattern" in given or "preset" in given:
        _rule_applies(field, _PATTERN_TYPES, "Patterns", "short text")
        if patch.preset is not None:
            rules.regex = VALIDATION_PRESETS[patch.preset]
            changed.append(f"pattern ({patch.preset})")
        elif patch.pattern is not None:
            rules.regex = _checked_pattern(patch.pattern)
            changed.append("pattern")
        else:
            rules.regex = None
            changed.append("no pattern")

    for low, high, what in (
        ("min_length", "max_length", "minimum length"),
        ("min_value", "max_value", "minimum"),
        ("min_choices", "max_choices", "minimum number of choices"),
    ):
        lo, hi = getattr(rules, low), getattr(rules, high)
        if lo is not None and hi is not None and lo > hi:
            raise OpError(f"The {what} ({lo:g}) cannot be more than the maximum ({hi:g}).")
    field.validations = rules
    return f"Updated the answer rules of '{_title_text(field)}' ({', '.join(changed)})"


def _apply_set_question_numbering(form: StandardForm, op: SetQuestionNumberingOp) -> str:
    pages = _pages(form)
    if op.page_id is not None:
        page = _find_page(form, op.page_id)
        targets = [page]
        where = f"page {pages.index(page) + 1}"
    else:
        if not pages:
            raise OpError("The form has no question pages to number.")
        targets = pages
        where = "every page"
    for page in targets:
        if page.properties is None:
            page.properties = StandardFieldProperty(fields=[])
        page.properties.show_question_numbers = op.show
    return f"Turned question numbers {'on' if op.show else 'off'} for {where}"


# ===========================================================================
# Editor ops: handlers (models: "Editor ops: models" above)
# ===========================================================================

# A rich-text title, serialised: at most this many characters, nested at
# most this deep.
TITLE_JSON_MAX_CHARS = 64 * 1024
TITLE_JSON_MAX_DEPTH = 64
# Hidden fields: any names a whole-form save accepts (older forms may hold
# names the builder's editor no longer lets you type), within these limits.
HIDDEN_FIELDS_MAX = 100
HIDDEN_FIELD_NAME_MAX_LENGTH = 200
# The rich-text node that pipes an answer or a hidden field into a title.
ANSWER_PIPE_NODE = "answerPipe"
CHOICE_EDIT_TYPES = {
    StandardFormFieldType.MULTIPLE_CHOICE,
    StandardFormFieldType.DROPDOWN,
    StandardFormFieldType.RANKING,
}


def _json_depth(value: Any) -> int:
    depth, pending = 0, [(value, 1)]
    while pending:
        item, level = pending.pop()
        if isinstance(item, dict):
            depth = max(depth, level)
            pending.extend((v, level + 1) for v in item.values())
        elif isinstance(item, list):
            depth = max(depth, level)
            pending.extend((v, level + 1) for v in item)
    return depth


# What a rich-text title may hold: the node and mark types (with their
# attributes) of the builder's title editor (webapp rich-text-editor
# ``Extenstions``: StarterKit without links, TextStyle, FontSize, Color,
# AnswerPipe). Respondent pages render titles with that schema, which
# refuses any other type or attribute.
_STR = (str, type(None))
TITLE_NODES: Dict[str, Dict[str, Any]] = {
    "doc": {},
    "paragraph": {},
    "text": {},
    "heading": {"level": int},
    "hardBreak": {},
    "blockquote": {},
    "bulletList": {},
    "orderedList": {"start": (int, type(None)), "type": _STR},
    "listItem": {},
    "codeBlock": {"language": _STR},
    "horizontalRule": {},
    ANSWER_PIPE_NODE: {"kind": str, "pipeKey": _STR, "label": _STR, "fallback": _STR},
}
TITLE_MARKS: Dict[str, Dict[str, Any]] = {
    "bold": {},
    "italic": {},
    "underline": {},
    "strike": {},
    "code": {},
    "textStyle": {"fontSize": _STR, "color": _STR},
}
_PIPE_KINDS = {"field", "hidden", "group"}
_NODE_KEYS = {"type", "attrs", "content", "marks", "text"}


def _attrs_problem(what: str, attrs: Any, allowed: Dict[str, Any]) -> Optional[str]:
    if attrs is None:
        return None
    if not isinstance(attrs, dict):
        return f"The attributes of a '{what}' must be an object."
    for key, value in attrs.items():
        if key not in allowed:
            return f"A '{what}' cannot have the attribute '{key}'."
        if isinstance(value, bool) or not isinstance(value, allowed[key]):
            return f"The attribute '{key}' of a '{what}' has the wrong type."
    return None


def _rich_text_problem(title: Dict[str, Any]) -> Optional[str]:
    """Why ``title`` is not a document the title editor can render, if so."""
    if title.get("type") != "doc":
        return "A rich-text title must be a document (type 'doc')."
    pending = [title]
    while pending:
        node = pending.pop()
        if not isinstance(node, dict):
            return "A rich-text title may only hold nodes (objects)."
        kind = node.get("type")
        if kind not in TITLE_NODES:
            return f"A rich-text title cannot hold a '{kind}' node."
        unknown = set(node) - _NODE_KEYS
        if unknown:
            return f"A '{kind}' node cannot have '{sorted(unknown)[0]}'."
        attrs = node.get("attrs")
        problem = _attrs_problem(kind, attrs, TITLE_NODES[kind])
        if problem:
            return problem
        if kind == "heading" and not 1 <= (attrs or {}).get("level", 1) <= 6:
            return "A heading's level must be 1 to 6."
        if kind == ANSWER_PIPE_NODE and (attrs or {}).get("kind", "field") not in _PIPE_KINDS:
            return "An answer pipe's kind must be field, hidden or group."
        if kind == "text":
            if not isinstance(node.get("text"), str) or not node["text"]:
                return "A text node needs some text."
        elif "text" in node:
            return f"A '{kind}' node cannot hold text."
        marks = node.get("marks")
        if marks is not None:
            if not isinstance(marks, list):
                return "Marks must be a list."
            for mark in marks:
                name = mark.get("type") if isinstance(mark, dict) else None
                if name not in TITLE_MARKS:
                    return f"A rich-text title cannot use a '{name}' mark."
                if set(mark) - {"type", "attrs"}:
                    return f"A '{name}' mark can only have attributes."
                problem = _attrs_problem(name, mark.get("attrs"), TITLE_MARKS[name])
                if problem:
                    return problem
                # the font size and colour go into a style attribute
                for key, value in (mark.get("attrs") or {}).items():
                    problem = style_value_problem(key, value)
                    if problem:
                        return problem
        content = node.get("content")
        if content is not None:
            if not isinstance(content, list) or kind == "text":
                return f"The content of a '{kind}' node is not valid."
            pending.extend(content)
    return None


def _check_title(title: Any) -> None:
    """A rich-text title must stay small (TITLE_JSON_MAX_CHARS serialised,
    TITLE_JSON_MAX_DEPTH deep) and hold only what the title editor holds
    (TITLE_NODES, TITLE_MARKS)."""
    if not isinstance(title, dict):
        return
    if _json_depth(title) > TITLE_JSON_MAX_DEPTH:
        raise OpError(
            f"A rich-text title can be nested at most {TITLE_JSON_MAX_DEPTH} levels deep."
        )
    size = len(json.dumps(title, separators=(",", ":"), ensure_ascii=False))
    if size > TITLE_JSON_MAX_CHARS:
        raise OpError(
            f"A rich-text title can be at most {TITLE_JSON_MAX_CHARS} characters "
            f"long as JSON (this one has {size})."
        )
    problem = _rich_text_problem(title)
    if problem:
        raise OpError(problem)


def _subtree(field: StandardFormField) -> List[StandardFormField]:
    """``field`` and every field nested in it."""
    found, pending = [], [field]
    while pending:
        item = pending.pop(0)
        found.append(item)
        pending.extend((item.properties.fields if item.properties else None) or [])
    return found


def _form_ids(form: StandardForm) -> Set[str]:
    ids: Set[str] = set()
    for item in form.fields or []:
        ids.update(f.id for f in _subtree(item) if f.id)
    return ids


def _check_new_ids(form: StandardForm, item: StandardFormField, replaced=()) -> None:
    """Every id of ``item`` (and of its nested fields) is given and unused
    in ``form``, apart from the ids of what ``item`` replaces."""
    taken = _form_ids(form) - set(replaced)
    seen: Set[str] = set()
    for field in _subtree(item):
        if not isinstance(field.id, str) or not field.id.strip():
            raise OpError("Every page and question needs an id.")
        if field.id in taken or field.id in seen:
            raise OpError(f"The id '{field.id}' is already used in this form.")
        seen.add(field.id)
        choice_ids = [
            c.id for c in (field.properties.choices if field.properties else None) or []
        ]
        if len(set(choice_ids)) != len(choice_ids):
            raise OpError(f"The choices of '{_title_text(field)}' need unique ids.")


class _KeptImages:
    """The image addresses ``form`` already holds, collected only when a
    non-first-party address needs them (most ops have none), and without
    copying the form."""

    def __init__(self, form: StandardForm):
        self._form = form
        self._urls: Optional[Set[str]] = None

    def __contains__(self, url: str) -> bool:
        if self._urls is None:
            from backend.app.services.form_images import map_form_images

            found: Set[str] = set()

            def collect(value: Optional[str]) -> Optional[str]:
                if isinstance(value, str) and value.strip():
                    found.add(value.strip())
                return value  # unchanged: only read here

            map_form_images(self._form, collect)
            self._urls = found
        return url in self._urls


def _editor_image(url: Optional[str], keep: "_KeptImages") -> Optional[str]:
    """The address to store for one image, as a whole-form save stores it
    (services/form_images.py): first-party, or already on the form."""
    if url is None or not isinstance(url, str) or not url.strip():
        return url
    stored = first_party_image_url(url)
    if stored is not None:
        return stored
    if url.strip() in keep:
        return url
    raise OpError(IMAGE_URL_ERROR)


def _editor_attachment(attachment: Any, keep: "_KeptImages") -> None:
    if attachment is not None and getattr(attachment.type, "value", attachment.type) == "image":
        attachment.href = _editor_image(attachment.href, keep)


def _editor_theme(theme: Optional[Theme], keep: "_KeptImages") -> None:
    if theme is not None and theme.background is not None:
        theme.background.imageUrl = _editor_image(theme.background.imageUrl, keep)


def _editor_item(raw: Dict[str, Any], form: StandardForm, page: bool) -> StandardFormField:
    """A question or page as the editor sends it, read the way a whole-form
    save reads it and checked like one: the stored model (its group and date
    rule checks included), titles, answer patterns, internal fields and
    images."""
    try:
        model = StandardFormFieldCamelModel.model_validate(raw)
        item = StandardFormField(**model.model_dump(mode="json"))
    except ValidationError as error:
        raise OpError(
            "; ".join(
                ".".join(str(part) for part in e["loc"]) + ": " + e["msg"]
                if e["loc"]
                else str(e["msg"]).removeprefix("Value error, ")
                for e in error.errors(include_input=False, include_url=False)[:5]
            )
        )
    except ValueError as error:
        raise OpError(_validation_message(error))
    is_page = item.type == StandardFormFieldType.SLIDE
    if page and not is_page:
        raise OpError("insert_page needs a page: a field of type 'slide'.")
    if not page and is_page:
        raise OpError("A page is not a question: use insert_page or update_page.")
    keep = _KeptImages(form)
    for field in _subtree(item):
        if field is not item and field.type == StandardFormFieldType.SLIDE:
            raise OpError("A page cannot be placed inside another page or question.")
        if field.type is None:
            raise OpError(f"'{_title_text(field)}' needs a type.")
        _check_title(field.title)
        regex = field.validations.regex if field.validations else None
        if regex is not None and regex.strip():
            _checked_pattern(regex)
        if field.internal:
            _ensure_can_be_internal(field.type)
        field.image_url = _editor_image(field.image_url, keep)
        _editor_attachment(field.attachment, keep)
        if field.properties is not None:
            _editor_theme(field.properties.theme, keep)
            for choice in field.properties.choices or []:
                _editor_attachment(choice.attachment, keep)
    return item


def _calculation_messages(form: StandardForm) -> List[str]:
    return [_calculation_message(p) for p in calculated_field_problems(form)]


def _new_problems(form: StandardForm, before: Tuple[Set[str], Set[str], Set[str]]) -> Optional[str]:
    """The first problem of ``form`` a whole-form save would refuse (logic
    on an internal field, a date rule, a calculation) that was not there
    ``before``."""
    for problem in internal_logic_violations(form):
        if problem not in before[0]:
            return problem
    for problem in date_rule_problems(form.fields):
        if problem not in before[1]:
            return problem
    for problem in _calculation_messages(form):
        if problem not in before[2]:
            return problem
    return None


def _known_problems(form: StandardForm) -> Tuple[Set[str], Set[str], Set[str]]:
    return (
        set(internal_logic_violations(form)),
        set(date_rule_problems(form.fields)),
        set(_calculation_messages(form)),
    )


def _live_question_ids(form: StandardForm) -> Dict[str, StandardFormField]:
    """Questions respondents answer, by id: what logic and pipes may use
    (the builder's getInputFieldsById)."""
    found: Dict[str, StandardFormField] = {}
    for page in _pages(form):
        for field in (page.properties.fields if page.properties else None) or []:
            if field.id and not field.internal:
                found[field.id] = field
            if _is_repeating_group(field):
                for child in _children(field):
                    if child.id and not child.internal:
                        found[child.id] = child
    return found


def _prune_references(
    form: StandardForm,
    gone: Set[str] = frozenset(),
    hidden_names: Optional[Set[str]] = None,
    hidden_gone: Set[str] = frozenset(),
) -> int:
    """Remove what refers to a question that is not there, as the editor
    does after a delete (webapp pruneOrphanedConditions and
    pruneOrphanedPipes): logic and jump conditions on a missing question (a
    rule or jump left without conditions goes too) and answer pipes in
    titles; with ``hidden_names``, also pipes of hidden fields not in it.
    Jumps to a missing page stay, so the editor can show them as broken.

    Returns how many of the removed references were to ``gone`` (the
    questions this op removed) or ``hidden_gone`` (the hidden fields it
    removed); older orphans are removed too but not counted."""
    live = _live_question_ids(form)
    removed = 0

    def is_live(condition: FieldLogicCondition) -> bool:
        if condition.field_id not in live:
            return False
        if not condition.group_mode or condition.group_mode == "COUNT":
            return True
        return bool(condition.child_field_id) and condition.child_field_id in live

    def live_conditions(conditions) -> List[FieldLogicCondition]:
        nonlocal removed
        kept = []
        for condition in conditions or []:
            if is_live(condition):
                kept.append(condition)
            elif condition.field_id in gone or condition.child_field_id in gone:
                removed += 1
        return kept

    def orphan_pipe(node: Any) -> Optional[Set[str]]:
        """None when ``node`` is not an orphaned pipe, else the ids (or the
        hidden field name) it referred to."""
        if not isinstance(node, dict) or node.get("type") != ANSWER_PIPE_NODE:
            return None
        attrs = node.get("attrs") or {}
        key = attrs.get("pipeKey")
        if attrs.get("kind") == "hidden":
            if hidden_names is not None and key not in hidden_names:
                return {f"hidden:{key}"}
            return None
        if attrs.get("kind") == "group":
            parts = str(key or "").split(":")
            group = live.get(parts[0])
            child_id = parts[2] if len(parts) > 2 else None
            children = (group.properties.fields if group and group.properties else None) or []
            if (
                group is None
                or group.type != StandardFormFieldType.GROUP
                or child_id
                and not any(c.id == child_id for c in children)
            ):
                return {parts[0], child_id} - {None}
            return None
        return None if key in live else {key}

    referred_gone = set(gone) | {f"hidden:{name}" for name in hidden_gone}

    def prune_pipes(node: Any) -> None:
        nonlocal removed
        if not isinstance(node, dict) or not isinstance(node.get("content"), list):
            return
        kept = []
        for child in node["content"]:
            refs = orphan_pipe(child)
            if refs is None:
                kept.append(child)
            elif refs & referred_gone:
                removed += 1
        node["content"] = kept
        for child in kept:
            prune_pipes(child)

    def prune_question(field: StandardFormField) -> None:
        if isinstance(field.title, dict):
            prune_pipes(field.title)
        logic = field.properties.logic if field.properties else None
        if logic is not None:
            conditions = live_conditions(logic.conditions)
            if conditions:
                logic.conditions = conditions
            else:
                field.properties.logic = None

    for page in _pages(form):
        properties = page.properties
        if properties is None:
            continue
        if properties.jumps is not None:
            jumps = []
            for jump in properties.jumps:
                conditions = live_conditions(jump.conditions)
                if conditions:
                    jump.conditions = conditions
                    jumps.append(jump)
            properties.jumps = jumps or None
        for field in properties.fields or []:
            prune_question(field)
            if _is_repeating_group(field):
                for child in _children(field):
                    prune_question(child)
    return removed


def _dropped_references_note(form: StandardForm, gone: Set[str]) -> str:
    dropped = _prune_references(form, gone)
    return f" (and {dropped} logic or piping reference(s) to it)" if dropped else ""


def _page_number(form: StandardForm, page: StandardFormField) -> int:
    return _pages(form).index(page) + 1


def _apply_insert_field(form: StandardForm, op: InsertFieldOp) -> str:
    field = _editor_item(op.field, form, page=False)
    _check_new_ids(form, field)
    if op.group_id is not None:
        page, group = _find_group(form, op.group_id)
        if op.page_id is not None and page.id != op.page_id:
            raise OpError(f"The group '{op.group_id}' is not on page '{op.page_id}'.")
        _check_child_type(field.type, field.internal)
        container = _children(group)
        where = f"the group '{_title_text(group)}'"
    elif op.page_id is not None:
        page = _find_page(form, op.page_id)
        container = _children(page)
        where = f"page {_page_number(form, page)}"
    else:
        raise OpError("insert_field needs a pageId (or a groupId).")
    known = _known_problems(form)
    position = min(op.index, len(container))
    container.insert(position, field)
    problem = _new_problems(form, known)
    if problem:
        container.pop(position)
        raise OpError(problem)
    _note_created(field.id)
    return f"Inserted '{_title_text(field)}' ({field.type.value}) into {where}"


def _apply_replace_field(form: StandardForm, op: ReplaceFieldOp) -> str:
    field = _editor_item(op.field, form, page=False)
    if field.id in {page.id for page in _pages(form)}:
        raise OpError(f"'{field.id}' is a page: change it with update_page.")
    _, parent, container, old, position = _locate_field(form, field.id)
    _check_new_ids(form, field, replaced={f.id for f in _subtree(old)})
    if parent is not None:
        _check_child_type(field.type, field.internal)
    known = _known_problems(form)
    container[position] = field
    problem = _new_problems(form, known)
    if problem:
        container[position] = old
        raise OpError(problem)
    gone = {f.id for f in _subtree(old)} - {f.id for f in _subtree(field)}
    return f"Replaced '{_title_text(field)}'{_dropped_references_note(form, gone)}"


def _apply_insert_page(form: StandardForm, op: InsertPageOp) -> str:
    page = _editor_item(op.page, form, page=True)
    _check_new_ids(form, page)
    if form.fields is None:
        form.fields = []
    pages = _pages(form)
    known = _known_problems(form)
    if op.index >= len(pages):
        position = len(form.fields)
    else:
        position = form.fields.index(pages[op.index])
    form.fields.insert(position, page)
    problem = _new_problems(form, known)
    if problem:
        form.fields.pop(position)
        raise OpError(problem)
    _note_created(page.id)
    count = len(_children(page))
    return f"Inserted a page with {count} field(s) at position {_page_number(form, page)}"


_PAGE_PATCH_LABELS = {
    "layout": "layout",
    "image_url": "image",
    "theme": "theme",
    "position": "position",
    "show_question_numbers": "question numbers",
    "section_title": "section title",
}


def _apply_update_page(form: StandardForm, op: UpdatePageOp) -> str:
    page = _find_page(form, op.page_id)
    patch = op.patch
    given = [key for key in _PAGE_PATCH_LABELS if key in patch.model_fields_set]
    if not given:
        raise OpError("The update contained no changes.")
    keep = _KeptImages(form)
    properties = page.properties
    if properties is None:
        properties = page.properties = StandardFieldProperty(fields=[])
    # Checked first: a refused value leaves the page as it was.
    image_url = _editor_image(patch.image_url, keep) if "image_url" in given else None
    theme = patch.theme.model_copy(deep=True) if patch.theme is not None else None
    _editor_theme(theme, keep)
    section_title = None
    if "section_title" in given and patch.section_title is not None:
        section_title = patch.section_title.strip() or None
        if section_title and len(section_title) > SECTION_TITLE_MAX_LENGTH:
            raise OpError(
                f"A section title can be at most {SECTION_TITLE_MAX_LENGTH} characters."
            )
    if "layout" in given:
        properties.layout = patch.layout
    if "image_url" in given:
        page.image_url = image_url or None
    if "theme" in given:
        properties.theme = theme
    if "position" in given:
        properties.position = patch.position
    if "show_question_numbers" in given:
        properties.show_question_numbers = patch.show_question_numbers
    if "section_title" in given:
        properties.section_title = section_title
    labels = ", ".join(_PAGE_PATCH_LABELS[key] for key in given)
    return f"Updated page {_page_number(form, page)} ({labels})"


_WELCOME_PATCH_KEYS = {
    "title": "title",
    "description": "description",
    "layout": "layout",
    "image_url": "imageUrl",
    "button_text": "buttonText",
}


def _apply_update_welcome_page(form: StandardForm, op: UpdateWelcomePageOp) -> str:
    patch = op.patch
    given = [key for key in _WELCOME_PATCH_KEYS if key in patch.model_fields_set]
    if not given:
        raise OpError("The update contained no changes.")
    image_url = None
    if "image_url" in given:
        image_url = _editor_image(patch.image_url, _KeptImages(form)) or None
    if form.welcome_page is None:
        form.welcome_page = WelcomePageField()
    for key in given:
        value = image_url if key == "image_url" else getattr(patch, key)
        setattr(form.welcome_page, _WELCOME_PATCH_KEYS[key], value)
    return "Updated the welcome page (" + ", ".join(given).replace("_", " ") + ")"


def _apply_set_hidden_fields(form: StandardForm, op: SetHiddenFieldsOp) -> str:
    """Names as a whole-form save takes them (the builder's editor only lets
    a creator type URL-safe ones, but an older form may hold others and
    stays editable), within HIDDEN_FIELDS_MAX and
    HIDDEN_FIELD_NAME_MAX_LENGTH."""
    if len(op.names) > HIDDEN_FIELDS_MAX:
        raise OpError(f"A form can have at most {HIDDEN_FIELDS_MAX} hidden fields.")
    for name in op.names:
        if len(name) > HIDDEN_FIELD_NAME_MAX_LENGTH:
            raise OpError(
                f"A hidden field name can be at most {HIDDEN_FIELD_NAME_MAX_LENGTH} "
                "characters."
            )
    before = set(form.hidden_fields or [])
    form.hidden_fields = list(op.names)
    dropped = _prune_references(
        form, hidden_names=set(op.names), hidden_gone=before - set(op.names)
    )
    note = f" (and {dropped} piping reference(s) to removed ones)" if dropped else ""
    return f"Set {len(op.names)} hidden field(s){note}"


def _apply_update_logo(form: StandardForm, op: UpdateLogoOp) -> str:
    given = op.model_fields_set & {"position", "alt", "use_workspace_logo"}
    if not given:
        raise OpError("The update contained no changes.")
    if op.alt is not None and len(op.alt) > LOGO_ALT_MAX_LENGTH:
        raise OpError(f"The logo's alt text can be at most {LOGO_ALT_MAX_LENGTH} characters.")
    if "position" in given:
        form.logo_position = op.position
    if "alt" in given:
        form.logo_alt = op.alt
    if "use_workspace_logo" in given:
        form.use_workspace_logo = op.use_workspace_logo
    labels = {"position": "position", "alt": "alt text", "use_workspace_logo": "workspace logo"}
    return "Updated the logo settings (" + ", ".join(labels[k] for k in sorted(given)) + ")"


def _choice_field(form: StandardForm, field_id: str, change: bool) -> Tuple[StandardFormField, List[StandardChoice]]:
    _, _, _, field, _ = _locate_field(form, field_id)
    if field.type == StandardFormFieldType.YES_NO and change:
        raise OpError("Yes/No choices are fixed.")
    if field.type not in CHOICE_EDIT_TYPES and field.type != StandardFormFieldType.YES_NO:
        kind = field.type.value if field.type else "unknown"
        raise OpError(f"'{_title_text(field)}' is a {kind} question: it has no choices.")
    if field.properties is None:
        field.properties = StandardFieldProperty(fields=[])
    if field.properties.choices is None:
        field.properties.choices = []
    return field, field.properties.choices


def _choice_position(field: StandardFormField, choices: List[StandardChoice], choice_id: str) -> int:
    for position, choice in enumerate(choices):
        if choice.id == choice_id:
            return position
    raise OpError(f"'{_title_text(field)}' has no choice '{choice_id}'.")


def _apply_set_choice(form: StandardForm, op: SetChoiceOp) -> str:
    field, choices = _choice_field(form, op.field_id, change=True)
    choice = choices[_choice_position(field, choices, op.choice_id)]
    choice.value = op.value
    return f"Changed a choice of '{_title_text(field)}'"


def _apply_add_choice(form: StandardForm, op: AddChoiceOp) -> str:
    field, choices = _choice_field(form, op.field_id, change=True)
    if not op.choice.id.strip():
        raise OpError("A choice needs an id.")
    if any(c.id == op.choice.id for c in choices):
        raise OpError(f"'{_title_text(field)}' already has a choice '{op.choice.id}'.")
    choice = StandardChoice(**op.choice.model_dump())
    _editor_attachment(choice.attachment, _KeptImages(form))
    position = len(choices) if op.index is None else min(op.index, len(choices))
    choices.insert(position, choice)
    return f"Added a choice to '{_title_text(field)}'"


def _apply_remove_choice(form: StandardForm, op: RemoveChoiceOp) -> str:
    field, choices = _choice_field(form, op.field_id, change=True)
    choices.pop(_choice_position(field, choices, op.choice_id))
    return f"Removed a choice of '{_title_text(field)}'"


def _apply_move_choice(form: StandardForm, op: MoveChoiceOp) -> str:
    field, choices = _choice_field(form, op.field_id, change=False)
    choice = choices.pop(_choice_position(field, choices, op.choice_id))
    position = min(op.index, len(choices))
    choices.insert(position, choice)
    return f"Moved a choice of '{_title_text(field)}' to position {position + 1}"


def _payload_count(raw: Any) -> int:
    """Fields in an editor payload, nested ones included (count_fields of
    what it will be)."""
    total, pending = 0, [raw]
    while pending:
        item = pending.pop()
        if not isinstance(item, dict):
            continue
        total += 1
        properties = item.get("properties")
        if isinstance(properties, dict) and isinstance(properties.get("fields"), list):
            pending.extend(properties["fields"])
    return total


def _editor_growth(form: StandardForm, op) -> Tuple[int, int]:
    """Pages and fields an editor op adds (see _growth)."""
    if isinstance(op, InsertFieldOp):
        return 0, _payload_count(op.field)
    if isinstance(op, InsertPageOp):
        return 1, max(0, _payload_count(op.page) - 1)
    if isinstance(op, ReplaceFieldOp):
        field_id = op.field.get("id")
        try:
            _, _, _, old, _ = _locate_field(form, field_id)
        except OpError:
            return 0, 0
        return 0, max(0, _payload_count(op.field) - count_fields([old]))
    return 0, 0


_EDITOR_HANDLERS = {
    "insert_field": _apply_insert_field,
    "replace_field": _apply_replace_field,
    "insert_page": _apply_insert_page,
    "update_page": _apply_update_page,
    "update_welcome_page": _apply_update_welcome_page,
    "set_hidden_fields": _apply_set_hidden_fields,
    "update_logo": _apply_update_logo,
    "set_choice": _apply_set_choice,
    "add_choice": _apply_add_choice,
    "remove_choice": _apply_remove_choice,
    "move_choice": _apply_move_choice,
}
assert set(_EDITOR_HANDLERS) == EDITOR_ONLY_OPS

# ===========================================================================
# End of editor ops: handlers
# ===========================================================================


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
    "set_theme_preset": _apply_set_theme_preset,
    "set_section_title": _apply_set_section_title,
    "move_page": _apply_move_page,
    "set_field_validation": _apply_set_field_validation,
    "set_question_numbering": _apply_set_question_numbering,
}
_HANDLERS.update(_EDITOR_HANDLERS)
OP_NAMES = frozenset(_HANDLERS)

# Most ops one MCP update_form call or one dry run may carry.
MAX_OPS_PER_BATCH = 200


def too_many_ops(count: int) -> Optional[str]:
    """The plain refusal for a batch over MAX_OPS_PER_BATCH, or None."""
    if count <= MAX_OPS_PER_BATCH:
        return None
    return (
        f"At most {MAX_OPS_PER_BATCH} operations can be sent at once (this batch "
        f"has {count}); split them into several batches."
    )


# ---------------------------------------------------------------------------
# Client references (``ref`` / ``"$ref:<name>"``)
# ---------------------------------------------------------------------------

# What the running handler created: (its id, ids of the fields it created
# with it, in the order of the op's ``fields``).
_CREATED: ContextVar[Optional[Tuple[str, Tuple[str, ...]]]] = ContextVar(
    "form_ops_created", default=None
)


def _note_created(created_id: str, nested=()) -> None:
    _CREATED.set((created_id, tuple(nested)))


def _refs_defined(op) -> List[Tuple[str, Optional[int]]]:
    """``(name, position)`` of each ref an op defines: the op's own
    (position None) and those of the fields it creates with it."""
    defined: List[Tuple[str, Optional[int]]] = []
    if isinstance(op, AddFieldOp):
        if op.ref and op.field.ref and op.ref != op.field.ref:
            raise OpError("add_field has two different refs: give one, on the op or on its field.")
        name = op.ref or op.field.ref
        if name:
            defined.append((name, None))
        return defined
    if getattr(op, "ref", None):
        defined.append((op.ref, None))
    if isinstance(op, (AddPageOp, AddGroupOp)):
        defined.extend((spec.ref, i) for i, spec in enumerate(op.fields or []) if spec.ref)
    return defined


def _ref_target(name: str, refs: Dict[str, Tuple[int, Optional[str]]]) -> str:
    entry = refs.get(name)
    if entry is None:
        raise OpError(
            f"Unknown reference '{REF_PREFIX}{name}': no earlier operation in this batch "
            f"defines the ref '{name}' (refs are set with \"ref\" on add_page, add_field, "
            "add_group or duplicate_page, or on a field inside add_page or add_group)."
        )
    index, created = entry
    if created is None:
        raise OpError(
            f"'{REF_PREFIX}{name}' names what operation #{index} would have created, "
            "but that operation failed."
        )
    return created


def _resolve_refs(op, refs: Dict[str, Tuple[int, Optional[str]]]):
    """``op`` with every ``"$ref:<name>"`` under an id key (REF_ID_KEYS)
    replaced by the id that name was given to. Other values are left as
    they are."""
    found = False

    def walk(value, key=None):
        nonlocal found
        if isinstance(value, dict):
            return {k: walk(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        if key in REF_ID_KEYS and isinstance(value, str) and value.startswith(REF_PREFIX):
            found = True
            return _ref_target(value[len(REF_PREFIX):], refs)
        return value

    resolved = walk(op.model_dump(exclude_unset=True))
    if not found:
        return op
    try:
        # an editor op got here through parse_ops(allow_editor_ops=True)
        return type(op).model_validate(resolved, context={EDITOR_CONTEXT: True})
    except ValueError as error:
        raise OpError(_validation_message(error))


def ref_dependencies(ops: List[FormOp]) -> List[Set[int]]:
    """For each op, the indexes of the earlier ops whose refs it uses
    (``"$ref:<name>"`` under an id key): accepting the op without them
    cannot work. A ref nobody defines is left to apply_form_ops to report."""
    definers: Dict[str, int] = {}
    needs: List[Set[int]] = []

    def used(value, key=None):
        if isinstance(value, dict):
            for k, v in value.items():
                yield from used(v, k)
        elif isinstance(value, list):
            for v in value:
                yield from used(v)
        elif (
            key in REF_ID_KEYS
            and isinstance(value, str)
            and value.startswith(REF_PREFIX)
        ):
            yield value[len(REF_PREFIX) :]

    for i, op in enumerate(ops):
        needs.append(
            {
                definers[name]
                for name in used(op.model_dump(exclude_unset=True))
                if name in definers
            }
        )
        try:
            defined = _refs_defined(op)
        except OpError:
            defined = []
        for name, _ in defined:
            definers.setdefault(name, i)
    return needs


def _calculation_problems(form: StandardForm) -> Optional[List[Any]]:
    """The form's calculation problems, or None when it has no calculated
    field (nothing to keep valid)."""
    if not any(
        field.type == StandardFormFieldType.CALCULATED
        for page in _pages(form)
        for field in (page.properties.fields if page.properties else None) or []
    ):
        return None
    return calculated_field_problems(form)


def _carries_calculation(op) -> bool:
    """Does the op bring a calculated field or an expression?"""
    # typed specs and the editor ops' raw questions and pages alike
    pending = [op.model_dump(exclude_none=True)]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            kind = value.get("type")
            if getattr(kind, "value", kind) == StandardFormFieldType.CALCULATED.value or "expression" in value:
                return True
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return False


def _calculation_message(problem: Any) -> str:
    where = f" (expression node '{problem.path}')" if problem.path else ""
    return f"{problem.message}{where}"


def finished_form(working: StandardForm) -> StandardForm:
    """``working`` as a batch leaves it: renumbered, date rules no save
    would accept pruned, and validated as a whole (on a copy)."""
    working = working.model_copy(deep=True)
    _renumber(working)
    # Nothing may leave with a date rule the save path would refuse.
    prune_date_rules(working.fields)
    # The schema is the final arbiter — a structurally invalid result must
    # never leave this function.
    return StandardForm.model_validate(working.model_dump())


class _SizeLimitReached(OpError):
    """An op would take the form past MAX_PAGES / MAX_FIELDS: it fails and
    the rest of the batch is not applied (later ops can only add more)."""


SIZE_LIMIT_SKIPPED = (
    "Not applied: an earlier operation reached the form's size limit."
)


def _form_size(form: StandardForm) -> Tuple[int, int]:
    """(question pages, fields on them, group questions included)."""
    pages = _pages(form)
    return len(pages), sum(
        count_fields(page.properties.fields if page.properties else None)
        for page in pages
    )


def _growth(form: StandardForm, op) -> Tuple[int, int]:
    """Pages and fields an op adds, known before it runs — so an op that
    would be too big is refused before anything is copied."""
    if isinstance(op, AddPageOp):
        return 1, len(op.fields or [])
    if isinstance(op, AddFieldOp):
        return 0, 1
    if isinstance(op, AddGroupOp):
        return 0, 1 + len(op.fields)
    if isinstance(op, DuplicatePageOp):
        page = _find_page(form, op.page_id)
        return 1, count_fields(page.properties.fields if page.properties else None)
    if isinstance(op, EDITOR_OP_TYPES):
        return _editor_growth(form, op)
    return 0, 0


def _size_problem(pages: int, fields: int, before: Tuple[int, int]) -> Optional[str]:
    """Why ``(pages, fields)`` is too big, unless it did not grow (a form
    already over a limit can still be edited and shrunk)."""
    if pages > MAX_PAGES and pages > before[0]:
        return f"A form can have at most {MAX_PAGES} pages; this would make {pages}."
    if fields > MAX_FIELDS and fields > before[1]:
        return (
            f"A form can have at most {MAX_FIELDS} fields in all; this would make "
            f"{fields}."
        )
    return None


def apply_form_ops(
    form: StandardForm,
    ops: List[FormOp],
    *,
    atomic: bool = False,
    on_step: Optional[Callable[[int, StandardForm, "OpResult"], None]] = None,
) -> Tuple[StandardForm, List[OpResult]]:
    """Apply operations to a deep copy of ``form``; the original is untouched.

    Partial (default): per-op failures are recorded and skipped (the chat
    turn survives a bad op). Atomic: all or nothing — when any op fails,
    the returned form is an unchanged copy of ``form``; every op is still
    tried so that all errors come back, each with its op index.
    The returned form is renumbered and re-validated as a whole.
    ``on_step(index, working, result)`` runs after each op that was tried
    with the form as the ops so far left it (not renumbered; see
    finished_form) — to see what each op changed. It must not modify
    ``working``.

    Size: an op that would take the form past MAX_PAGES or MAX_FIELDS
    fails before it runs, and the rest of the batch is not applied.
    """
    working = form.model_copy(deep=True)
    results: List[OpResult] = []
    size = _form_size(working)
    stopped = False
    # ref name -> (index of the op that defines it, the created id or None
    # when that op failed)
    refs: Dict[str, Tuple[int, Optional[str]]] = {}

    for i, op in enumerate(ops):
        if stopped:
            results.append(
                OpResult(index=i, op=op.op, ok=False, message=SIZE_LIMIT_SKIPPED)
            )
            continue
        handler = _HANDLERS.get(op.op)
        token = _CREATED.set(None)
        defined: List[Tuple[str, Optional[int]]] = []
        try:
            if handler is None:
                raise OpError(f"Unknown operation '{op.op}'.")
            defined = _refs_defined(op)
            names = [name for name, _ in defined]
            for name in names:
                if names.count(name) > 1:
                    raise OpError(f"The ref '{name}' is defined twice in this operation.")
                if name in refs:
                    raise OpError(
                        f"The ref '{name}' is already defined by operation #{refs[name][0]}; "
                        "each ref names one new item."
                    )
            op = _resolve_refs(op, refs)
            # Calculations must stay valid after every op: an op that leaves
            # one with an unknown field, an internal field or a circle is
            # refused and undone (the builder save would refuse the form).
            calc_before = _calculation_problems(working)
            snapshot = (
                working.model_copy(deep=True)
                if calc_before is not None or _carries_calculation(op)
                else None
            )
            add_pages, add_fields = _growth(working, op)
            if add_pages or add_fields:
                problem = _size_problem(
                    size[0] + add_pages, size[1] + add_fields, size
                )
                if problem:
                    raise _SizeLimitReached(problem)
            message = handler(working, op)
            if snapshot is not None:
                new_problems = [
                    p for p in (_calculation_problems(working) or []) if p not in (calc_before or [])
                ]
                if new_problems:
                    working = snapshot
                    raise OpError(_calculation_message(new_problems[0]))
            after = _form_size(working)
            problem = _size_problem(*after, size)
            if problem:
                # Not foreseen by _growth: the change is already made, so
                # nothing of this batch may be applied.
                raise _SizeLimitReached(problem)
            size = after
            created = _CREATED.get()
            for name, position in defined:
                if created is None:
                    continue
                refs[name] = (i, created[0] if position is None else created[1][position])
            results.append(
                OpResult(
                    index=i, op=op.op, ok=True, message=message,
                    created_id=created[0] if created else None,
                )
            )
        except OpError as e:
            # Later uses of this op's refs then say that it failed.
            for name, _ in defined:
                refs.setdefault(name, (i, None))
            results.append(OpResult(index=i, op=op.op, ok=False, message=str(e)))
            if isinstance(e, _SizeLimitReached):
                stopped = True
                if _form_size(working) != size:
                    # changed past the limit: drop the whole batch
                    return form.model_copy(deep=True), results + [
                        OpResult(index=j, op=o.op, ok=False, message=SIZE_LIMIT_SKIPPED)
                        for j, o in enumerate(ops[i + 1 :], start=i + 1)
                    ]
        finally:
            _CREATED.reset(token)
        if on_step is not None:
            on_step(i, working, results[-1])

    if atomic and not all(r.ok for r in results):
        return form.model_copy(deep=True), results

    return finished_form(working), results


def applied(results: List[OpResult], atomic: bool) -> bool:
    """Did a batch change the form? Partial: when any op applied. Atomic:
    only when every op did."""
    if atomic:
        return bool(results) and all(r.ok for r in results)
    return any(r.ok for r in results)


def parse_ops(
    payload: List[Dict[str, Any]], *, allow_editor_ops: bool = False
) -> List[FormOp]:
    """Parse a raw ops payload (AI/MCP JSON) into typed operations.

    The editor ops (EDITOR_ONLY_OPS) are refused, each with its own error
    at its index, unless ``allow_editor_ops`` is true: only the form editor
    may send them."""
    context = {EDITOR_CONTEXT: True} if allow_editor_ops else None
    return FormOps.model_validate({"ops": payload}, context=context).ops
