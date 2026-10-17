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
from typing import Any, Dict, List, Literal, Optional, Union

from common.models.standard_form import (
    DATE_RULES_MAX,
    LOGO_ALT_MAX_LENGTH,
    REPEAT_MAX_ITEMS_LIMIT,
    SECTION_TITLE_MAX_LENGTH,
    WHY_WE_ASK_MAX_LENGTH,
    LayoutType,
    StandardFormFieldType,
)
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

SPEC_VERSION = "1"
SCHEMA_ID = (
    "https://raw.githubusercontent.com/bettercollected/bettercollected/"
    "develop/docs/spec/form-spec-v1.schema.json"
)
JUMP_TARGET_SUBMIT = "__SUBMIT__"

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
    no match goes to the next page."""

    operator: Optional[Literal["AND", "OR"]] = None
    conditions: Optional[List[Condition]] = None
    target: Optional[str] = None


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
        None, description="A regular expression the text answer must match."
    )
    min_choices: Optional[int] = Field(None, ge=0)
    max_choices: Optional[int] = Field(None, ge=0)


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
    """A page shown after submitting."""

    title: Optional[str] = None
    message: Optional[str] = None
    button_text: Optional[str] = None
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
    pages: List[Page] = Field(default_factory=list)
    endings: Optional[List[Ending]] = None
    theme: Optional[Theme] = None
    hidden_fields: Optional[List[str]] = Field(
        None,
        description="URL parameter names captured with each response "
        "(names only, never values).",
    )
    logo: Optional[Logo] = None
    trust: Optional[Trust] = None


FormField.model_rebuild()
