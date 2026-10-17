"""Form spec v1: the public, versioned document shape of a form.

These models are a public contract, generated into
``docs/spec/form-spec-v1.schema.json`` (``python -m common.form_spec.schema``)
and kept apart from the internal ``StandardForm`` on purpose: the stored
model may change, the spec only by a new version. ``adapters.py`` converts
between the two.

What a creator controls is in the document; what the server owns is not
(workspace and owner ids, timestamps, publish state, response counts,
provider and import metadata, action secrets). Names are camelCase, unknown
keys are refused, so a typo is reported instead of silently dropped.
"""

import enum
import re
from typing import Any, Dict, List, Literal, Optional, Union

from common.models.standard_form import (
    CALCULATION_MAX_DECIMALS,
    DATE_RULES_MAX,
    ENDING_BUTTON_TEXT_MAX_LENGTH,
    ENDING_ID_PATTERN,
    ENDING_MESSAGE_MAX_LENGTH,
    ENDING_NAME_MAX_LENGTH,
    ENDING_TITLE_MAX_LENGTH,
    MAX_ENDINGS,
    LOGO_ALT_MAX_LENGTH,
    REPEAT_MAX_ITEMS_LIMIT,
    SECTION_TITLE_MAX_LENGTH,
    WHY_WE_ASK_MAX_LENGTH,
    LayoutType,
    StandardFormFieldType,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

SPEC_VERSION = "1"
SCHEMA_ID = (
    "https://raw.githubusercontent.com/bettercollected/bettercollected/"
    "develop/docs/spec/form-spec-v1.schema.json"
)
JUMP_TARGET_SUBMIT = "__SUBMIT__"
# Size limits of one document (far above any real form).
MAX_PAGES = 200
MAX_FIELDS = 2000  # questions and content blocks, group questions included
# Longest answer pattern (regular expression) a question may have.
PATTERN_MAX_LENGTH = 200


def checked_pattern(pattern: str) -> str:
    """An answer pattern as it may be stored: trimmed, at most
    PATTERN_MAX_LENGTH characters, a regular expression that compiles.
    Raises ValueError with a plain message. The one rule for the spec and
    the set_field_validation op.

    Only compiled here, never matched: submitted answers are matched with
    re2 (linear time) on a capped input in the backend's
    services/answer_validation.py. A creator's pattern is untrusted and
    Python's re can backtrack for a very long time."""
    pattern = pattern.strip()
    if not pattern:
        raise ValueError("The pattern is empty: give a regular expression, or none.")
    if len(pattern) > PATTERN_MAX_LENGTH:
        raise ValueError(f"A pattern can be at most {PATTERN_MAX_LENGTH} characters.")
    try:
        re.compile(pattern)
    except re.error as error:
        raise ValueError(f"'{pattern}' is not a valid pattern ({error}).")
    return pattern


def count_fields(fields) -> int:
    """Fields of a list, nested ones (group questions) included. Works on
    spec fields and stored fields alike."""
    total = 0
    pending = list(fields or [])
    while pending:
        field = pending.pop()
        total += 1
        children = getattr(field, "fields", None)
        if children is None:
            properties = getattr(field, "properties", None)
            children = getattr(properties, "fields", None) if properties else None
        pending.extend(children or [])
    return total


# Every question type a page may hold: all stored types except the page
# itself. Built from the stored enum, so a new type shows up as a change of
# the committed schema (and its staleness test) rather than silently.
FieldType = enum.Enum(
    "FieldType",
    {
        member.name: member.value
        for member in StandardFormFieldType
        if member is not StandardFormFieldType.SLIDE
    },
    type=str,
)
FieldType.__doc__ = "A question or content block type."

# The types the page-based builder offers today. Every other FieldType is
# legacy (first-generation builder, imports): still accepted, so stored
# forms keep reading, but marked deprecated in the schema and warned about
# by validation.
CURRENT_FIELD_TYPES = frozenset(
    {
        "short_text",
        "long_text",
        "email",
        "number",
        "url",
        "phone_number",
        "date",
        "yes_no",
        "multiple_choice",
        "dropdown",
        "rating",
        "linear_rating",
        "file_upload",
        "matrix",
        "tabular_input",
        "group",
        "calculated",
        "text",
        "IMAGE_CONTENT",
        "VIDEO_CONTENT",
    }
)
LEGACY_FIELD_TYPES = frozenset(m.value for m in FieldType) - CURRENT_FIELD_TYPES


def _field_type_json_schema(cls, core_schema, handler):
    """Current and legacy types as two branches, the legacy one
    ``deprecated`` (JSON Schema can't mark single enum values)."""
    values = [m.value for m in cls]
    return {
        "title": "FieldType",
        "description": cls.__doc__,
        "anyOf": [
            {
                "type": "string",
                "enum": [v for v in values if v in CURRENT_FIELD_TYPES],
            },
            {
                "type": "string",
                "enum": [v for v in values if v in LEGACY_FIELD_TYPES],
                "deprecated": True,
                "description": "Legacy types the builder no longer offers: "
                "still accepted so that stored forms can be read; do not use "
                "them for new questions.",
            },
        ],
    }


FieldType.__get_pydantic_json_schema__ = classmethod(_field_type_json_schema)

Layout = enum.Enum(
    "Layout", {member.name: member.value for member in LayoutType}, type=str
)
Layout.__doc__ = "How a page, the welcome page or an ending is laid out."

Comparison = Literal[
    "IS_EMPTY",
    "IS_NOT_EMPTY",
    "IS_EQUAL",
    "IS_NOT_EQUAL",
    "CONTAINS",
    "DOES_NOT_CONTAIN",
    "LESS_THAN",
    "LESS_THAN_EQUAL",
    "GREATER_THAN",
    "GREATER_THAN_EQUAL",
    "STARTS_WITH",
    "ENDS_WITH",
]


class _Spec(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        use_enum_values=True,
    )


class ThemeBackground(_Spec):
    """Optional decoration of the page ground."""

    type: Optional[str] = None
    gradient_from: Optional[str] = None
    gradient_to: Optional[str] = None
    gradient_angle: Optional[int] = None
    pattern: Optional[str] = None
    image_url: Optional[str] = Field(
        None, description="Only images from our own storage or Unsplash are shown."
    )


class Theme(_Spec):
    """Colours and style of the form (or of one page, as an override)."""

    title: str
    primary: str
    secondary: str
    tertiary: str
    accent: str
    background: Optional[ThemeBackground] = None
    style: Optional[str] = Field(
        None, description="e.g. classic, sheet, studio, leaflet"
    )


class Attachment(_Spec):
    """An image or video shown with a question or a choice."""

    type: Optional[Literal["image", "video"]] = None
    href: Optional[str] = None
    scale: Optional[float] = None
    description: Optional[str] = None
    embed_provider: Optional[Literal["youtube", "vimeo", "no_embed"]] = None


class Choice(_Spec):
    """One option of a choice question. Logic conditions compare with
    ``value``."""

    id: Optional[str] = None
    value: Optional[str] = None
    label: Optional[str] = None
    attachment: Optional[Attachment] = None


class Condition(_Spec):
    """One condition of a visibility rule or a page jump: the answer of
    ``fieldId`` compared with ``value`` (a choice's value, "Yes"/"No" for a
    yes/no question). On a repeating group, ``groupMode`` COUNT compares
    the number of items; ANY / ALL test ``childFieldId`` in the items."""

    field_id: Optional[str] = None
    field_type: Optional[str] = Field(
        None, description="Type of the source question (filled in by the editor)."
    )
    comparison: Optional[Comparison] = None
    value: Optional[Any] = None
    group_mode: Optional[Literal["COUNT", "ANY", "ALL"]] = None
    child_field_id: Optional[str] = None
    child_field_type: Optional[str] = None


class Logic(_Spec):
    """Show or hide this question when its conditions match (operator:
    AND = all, OR = any; AND when absent)."""

    action: Optional[Literal["SHOW", "HIDE"]] = None
    operator: Optional[Literal["AND", "OR"]] = None
    conditions: Optional[List[Condition]] = None


class PageJump(_Spec):
    """After this page, go to ``target`` (a page id, or "__SUBMIT__" to
    end the form) when the conditions match. The first matching jump wins;
    no match goes to the next page. With "__SUBMIT__", ``endingId`` names
    the ending shown after submitting (default: the form's default
    ending)."""

    operator: Optional[Literal["AND", "OR"]] = None
    conditions: Optional[List[Condition]] = None
    target: Optional[str] = None
    ending_id: Optional[str] = Field(
        None,
        pattern=ENDING_ID_PATTERN,
        description='The id of an ending of this form; only with target "__SUBMIT__".',
    )


class DateRule(_Spec):
    """The chosen date must be ``comparison`` a fixed ``date`` (YYYY-MM-DD),
    today, or the answer of another date question (``fieldId``)."""

    comparison: Literal["before", "after", "on_or_before", "on_or_after"]
    target: Literal["date", "today", "field"]
    date: Optional[str] = None
    field_id: Optional[str] = None


class Repeat(_Spec):
    """Makes a group repeatable: its questions are answered once per item."""

    min_items: Optional[int] = Field(None, ge=0, le=REPEAT_MAX_ITEMS_LIMIT)
    max_items: Optional[int] = Field(None, ge=1, le=REPEAT_MAX_ITEMS_LIMIT)
    item_label: Optional[str] = Field(None, max_length=80)
    item_title: Optional[str] = Field(None, max_length=300)
    export_layout: Optional[Literal["columns", "rows"]] = None


class Validations(_Spec):
    """Answer constraints. Lengths apply to text answers, values to numbers,
    choices to multiple-selection questions."""

    required: Optional[bool] = None
    min_length: Optional[int] = Field(None, ge=0)
    max_length: Optional[int] = Field(None, ge=0)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = Field(
        None,
        max_length=PATTERN_MAX_LENGTH,
        description="A regular expression the text answer must match.",
    )
    min_choices: Optional[int] = Field(None, ge=0)
    max_choices: Optional[int] = Field(None, ge=0)

    @field_validator("pattern")
    @classmethod
    def _check_pattern(cls, value):
        # "" is no pattern; anything else follows the op's rule (checked,
        # kept as written)
        if value and value.strip():
            checked_pattern(value)
        return value


class CalculationFormat(_Spec):
    """How a calculated field shows its value (display only; the stored
    value is the computed one)."""

    style: Optional[Literal["number", "currency", "percent", "text"]] = Field(
        None,
        description="number (default), currency, percent (0.25 shows as 25%) "
        "or text.",
    )
    decimals: Optional[int] = Field(None, ge=0, le=CALCULATION_MAX_DECIMALS)
    currency: Optional[str] = Field(
        None, pattern=r"^[A-Z]{3}$", description="ISO 4217 code; EUR by default."
    )


class Position(_Spec):
    """Where a page sits on the flow view's canvas (cosmetic)."""

    x: Optional[float] = None
    y: Optional[float] = None


class FormField(_Spec):
    """A question or content block on a page (or inside a group)."""

    id: str = Field(..., min_length=1)
    type: FieldType
    title: Optional[Union[str, Dict[str, Any]]] = Field(
        None,
        description="Plain text, or a rich-text document (which may pipe "
        "answers and hidden fields).",
    )
    description: Optional[str] = None
    value: Optional[str] = None
    image_url: Optional[str] = None
    attachment: Optional[Attachment] = None
    internal: Optional[bool] = Field(
        None,
        description="For office use only: never shown to respondents, filled "
        "in by staff on each submission.",
    )
    validations: Optional[Validations] = None
    placeholder: Optional[str] = None
    choices: Optional[List[Choice]] = None
    allow_multiple_selection: Optional[bool] = None
    allow_other_choice: Optional[bool] = None
    steps: Optional[int] = None
    start_from: Optional[int] = None
    rating_shape: Optional[str] = None
    hide_marks: Optional[bool] = None
    labels: Optional[Dict[str, str]] = None
    date_format: Optional[str] = None
    row_titles: Optional[List[str]] = None
    column_titles: Optional[List[str]] = None
    tabular_value: Optional[List[List[str]]] = None
    col_span: Optional[int] = Field(
        None, ge=1, le=12, description="Width on a 12-column grid (12 = full row)."
    )
    label: Optional[str] = Field(
        None, max_length=120, description="Short label shown with a date picker."
    )
    date_rules: Optional[List[DateRule]] = Field(None, max_length=DATE_RULES_MAX)
    why_we_ask: Optional[str] = Field(None, max_length=WHY_WE_ASK_MAX_LENGTH)
    logic: Optional[Logic] = None
    expression: Optional[Any] = Field(
        None,
        description="A calculated field's formula as an expressions-v1 syntax "
        'tree (docs/spec/expressions-v1.md), e.g. {"+": [{"var": "<field id>"}, '
        "1]}. Variables are question ids, '<group id>.<question id>' for a "
        "repeating group's question, and hidden-field names.",
    )
    format: Optional[CalculationFormat] = None
    hidden_from_respondents: Optional[bool] = Field(
        None,
        description="A calculated field that is computed and stored but never "
        "shown to respondents.",
    )
    unanswered_as_zero: Optional[bool] = Field(
        None,
        description="A calculated field: unanswered questions it uses count as 0 "
        "(default: on, unless the format is text).",
    )
    repeat: Optional[Repeat] = None
    fields: Optional[List["FormField"]] = Field(
        None, description="The questions of a group."
    )


class Page(_Spec):
    """A page of questions, in the order respondents see them."""

    id: str = Field(..., min_length=1)
    section_title: Optional[str] = Field(None, max_length=SECTION_TITLE_MAX_LENGTH)
    layout: Optional[Layout] = None
    image_url: Optional[str] = None
    theme: Optional[Theme] = None
    show_question_numbers: Optional[bool] = None
    position: Optional[Position] = None
    jumps: Optional[List[PageJump]] = None
    fields: List[FormField] = Field(default_factory=list)


class WelcomePage(_Spec):
    title: Optional[str] = None
    description: Optional[str] = None
    layout: Optional[Layout] = None
    image_url: Optional[str] = None
    button_text: Optional[str] = None


class Ending(_Spec):
    """A page shown after submitting. A page jump may choose one by its
    ``id``; a plain submit shows the default ending (the one with
    ``isDefault``, else the first)."""

    id: Optional[str] = Field(
        None,
        pattern=ENDING_ID_PATTERN,
        description="Stable id that page jumps name. Given when left out.",
    )
    name: Optional[str] = Field(
        None,
        max_length=ENDING_NAME_MAX_LENGTH,
        description="Short internal name, e.g. Eligible. Respondents never see it.",
    )
    is_default: Optional[bool] = Field(
        None, description="Shown after a plain submit. At most one ending."
    )
    title: Optional[str] = Field(None, max_length=ENDING_TITLE_MAX_LENGTH)
    message: Optional[str] = Field(None, max_length=ENDING_MESSAGE_MAX_LENGTH)
    button_text: Optional[str] = Field(None, max_length=ENDING_BUTTON_TEXT_MAX_LENGTH)
    button_link: Optional[str] = Field(None, description="An http(s) URL.")
    layout: Optional[Layout] = None
    image_url: Optional[str] = None


class Logo(_Spec):
    """The organisation logo at the top of every respondent page."""

    url: Optional[str] = Field(
        None,
        json_schema_extra={"readOnly": True},
        description="Set by uploading a logo; ignored when a document is written.",
    )
    position: Optional[Literal["auto", "left", "center"]] = None
    alt: Optional[str] = Field(None, max_length=LOGO_ALT_MAX_LENGTH)
    use_workspace_logo: Optional[bool] = None


class Retention(_Spec):
    """How long answers are kept: a number of days, until a date
    (YYYY-MM-DD), or forever."""

    type: Literal["days", "date", "forever"]
    value: Optional[Union[int, str]] = None


class Trust(_Spec):
    """What respondents are told about their data, and how answers are
    handled."""

    purpose: Optional[str] = None
    retention_text: Optional[str] = None
    privacy_policy_url: Optional[str] = Field(None, description="An http(s) URL.")
    retention: Optional[Retention] = None
    require_verified_identity: Optional[bool] = None
    allow_editing_response: Optional[bool] = None
    show_submission_number: Optional[bool] = None


class FormSpec(_Spec):
    """A form, as its creator controls it."""

    model_config = ConfigDict(title="BetterCollected form spec v1")

    spec_version: Literal["1"]
    title: Optional[str] = None
    description: Optional[str] = None
    welcome_page: Optional[WelcomePage] = None
    pages: List[Page] = Field(
        default_factory=list,
        max_length=MAX_PAGES,
        description=f"At most {MAX_PAGES} pages, with at most {MAX_FIELDS} "
        "fields in all (group questions included).",
    )
    endings: Optional[List[Ending]] = Field(
        None, max_length=MAX_ENDINGS, description=f"At most {MAX_ENDINGS} endings."
    )
    theme: Optional[Theme] = None
    hidden_fields: Optional[List[str]] = Field(
        None,
        description="URL parameter names captured with each response "
        "(names only, never values).",
    )
    logo: Optional[Logo] = None
    trust: Optional[Trust] = None

    @model_validator(mode="after")
    def _check_field_count(self):
        count = sum(count_fields(page.fields) for page in self.pages)
        if count > MAX_FIELDS:
            raise ValueError(
                f"A form can have at most {MAX_FIELDS} fields in all; this one "
                f"has {count}."
            )
        return self


FormField.model_rebuild()
