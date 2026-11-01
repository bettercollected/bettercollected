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

from common.countries import COUNTRIES_MAX
from common.currencies import CURRENCIES_MAX, is_currency_code
from common.models.standard_form import (
    check_countries,
    check_tags_settings,
    CALCULATION_MAX_DECIMALS,
    DATE_RULES_MAX,
    ENDING_BUTTON_TEXT_MAX_LENGTH,
    ENDING_ID_PATTERN,
    ENDING_MESSAGE_MAX_LENGTH,
    ENDING_NAME_MAX_LENGTH,
    ENDING_TITLE_MAX_LENGTH,
    FIELD_RULES_MAX,
    FORM_FIELD_RULES_MAX,
    OPTION_CONDITIONS_MAX,
    OPTION_FILTER_PAIRS_MAX,
    OPTION_ID_MAX_LENGTH,
    OPTION_SOURCE_ID_MAX_LENGTH,
    FORM_LANGUAGES,
    MAX_ENDINGS,
    LOGO_ALT_MAX_LENGTH,
    REPEAT_MAX_ITEMS_LIMIT,
    RULE_CONDITIONS_MAX,
    RULE_CONST_MAX_LENGTH,
    RULE_DESCRIPTION_MAX_LENGTH,
    RULE_ID_PATTERN,
    RULE_TITLE_MAX_LENGTH,
    SECTION_TITLE_MAX_LENGTH,
    WHY_WE_ASK_MAX_LENGTH,
    LayoutType,
    StandardFormFieldType,
)
from common.form_spec.re2_patterns import re2_problem
from common.models.standard_form import _rule_expression_problem
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
    PATTERN_MAX_LENGTH characters, and one RE2 can use (the engine the server
    matches answers with, in linear time: backend services/answer_validation.
    py). So lookarounds and backreferences are refused here, not silently left
    unchecked later. Raises ValueError with a plain message. The one rule for
    the spec, the set_field_validation op and the importer.

    Only compiled here, never matched, and RE2 compiles in time linear in the
    pattern's size within a fixed memory budget. The respondent's browser
    never runs a creator's pattern."""
    pattern = pattern.strip()
    if not pattern:
        raise ValueError("The pattern is empty: give a regular expression, or none.")
    if len(pattern) > PATTERN_MAX_LENGTH:
        raise ValueError(f"A pattern can be at most {PATTERN_MAX_LENGTH} characters.")
    problem = re2_problem(pattern)
    if problem is not None:
        raise ValueError(
            f"'{pattern}' is not a valid pattern ({problem}). Answer patterns use "
            "RE2 syntax: there are no lookarounds and no backreferences."
        )
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
        "day",
        "time",
        "currency",
        "date_range",
        "tags",
        "address",
        "signature",
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
    artwork: Optional[Literal["marble"]] = Field(
        None,
        description=(
            "Built-in artwork served by the app (marble: a marbled endpaper). It "
            "fills the picture half of a welcome or ending page whose layout has "
            "one and no image of its own. Absent: none."
        ),
    )


ThemeFont = Literal[
    "public-sans", "atkinson-next", "archivo", "besley", "rubik", "atkinson-mono"
]


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
    # Type and shape (common.models.standard_form THEME_FONTS and the lists
    # beside it). Absent means the form's look before these keys existed.
    title_font: Optional[ThemeFont] = Field(
        None,
        description=(
            "Face of titles and question labels. Absent: the text face "
            "(or the style's own title face)."
        ),
    )
    body_font: Optional[ThemeFont] = Field(
        None,
        description="Face of everything else respondents read. Absent: public-sans.",
    )
    data_font: Optional[ThemeFont] = Field(
        None,
        description="Face of data such as the submission number. Absent: the app's mono face.",
    )
    title_width: Optional[Literal["normal", "expanded"]] = Field(
        None,
        description="Width of display titles: expanded is 125% on a face with a width axis (archivo).",
    )
    radius: Optional[Literal["sharp", "soft", "round"]] = Field(
        None,
        description="Corners of fields, option cards and buttons: sharp 0, soft 6px, round 16px. Absent: the style's own.",
    )
    button_style: Optional[Literal["filled", "outlined", "pill"]] = Field(
        None, description="Absent: filled."
    )
    highlight: Optional[str] = Field(
        None,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="The chosen answer, the 'why we ask' and 'optional' notes and, where it reads, the focus ring. Absent: secondary.",
    )
    selection: Optional[str] = Field(
        None,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="The chosen answer alone, when it should differ from the highlight. Absent: the highlight, else secondary.",
    )
    input_text: Optional[str] = Field(
        None,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="The colour of the answers typed in the white input boxes (4.5:1 on white). Absent: primary.",
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
    logic: Optional["Logic"] = Field(
        None,
        description="Offer this option only (SHOW) or unless (HIDE) its "
        f"conditions hold, at most {OPTION_CONDITIONS_MAX}. The conditions read "
        "earlier questions of the form. An answer that selects an option that "
        "is not offered is refused.",
    )


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


Choice.model_rebuild()


class OptionFilterEntry(_Spec):
    """While the earlier question's option ``when`` (its id) is chosen, the
    question offers the options in ``show`` (their ids)."""

    when: str = Field(..., min_length=1, max_length=OPTION_ID_MAX_LENGTH)
    show: List[str] = Field(default_factory=list, max_length=OPTION_FILTER_PAIRS_MAX)


class OptionFilter(_Spec):
    """Filter a choice question's options by an earlier choice question's
    answer: the options offered are those the chosen options of ``fieldId``
    map to (the union over a multiple choice's selection). Without an answer
    to it (or with only "Other" text) nothing is filtered; a chosen option
    with no entry offers nothing."""

    field_id: str = Field(..., min_length=1)
    mapping: List[OptionFilterEntry] = Field(
        default_factory=list, max_length=OPTION_FILTER_PAIRS_MAX
    )


class OptionSource(_Spec):
    """Where a dropdown or multiple choice question's options come from
    instead of ``choices``: ``kind`` ``list`` (a workspace's option list,
    ``listId``; ``parentFieldId`` names an earlier choice question whose
    answer narrows the list by each item's group) or ``form_answers`` (the
    answers to question ``questionId`` of another form ``formId`` of the same
    workspace; the saver needs permission to read that form's responses).
    A question has either a source or ``choices``, never both. Checked by
    the server on every save and again on every submission."""

    kind: Literal["list", "form_answers"]
    list_id: Optional[str] = Field(None, max_length=OPTION_SOURCE_ID_MAX_LENGTH)
    parent_field_id: Optional[str] = Field(
        None, max_length=OPTION_SOURCE_ID_MAX_LENGTH
    )
    form_id: Optional[str] = Field(None, max_length=OPTION_SOURCE_ID_MAX_LENGTH)
    question_id: Optional[str] = Field(None, max_length=OPTION_SOURCE_ID_MAX_LENGTH)

    @model_validator(mode="after")
    def _shape(self):
        if self.kind == "list":
            if not self.list_id or self.form_id or self.question_id:
                raise ValueError("A list source names a list (listId) and nothing else.")
        else:
            if not self.form_id or not self.question_id:
                raise ValueError("A form-answers source names formId and questionId.")
            if self.list_id or self.parent_field_id:
                raise ValueError(
                    "A form-answers source takes no listId or parentFieldId."
                )
        return self


class RuleWhen(_Spec):
    """When a rule is active: ``conditions`` (as in ``logic``; operator AND
    when absent) or an expressions-v1 ``expression`` (active when its value
    is truthy), never both."""

    operator: Optional[Literal["AND", "OR"]] = None
    conditions: Optional[List[Condition]] = Field(
        None, min_length=1, max_length=RULE_CONDITIONS_MAX
    )
    expression: Optional[Any] = Field(
        None,
        description="An expressions-v1 syntax tree (docs/spec/expressions-v1.md) "
        "over the form's variables; inside a repeating group a sibling "
        "question's id reads that item's answer.",
    )

    @model_validator(mode="after")
    def _one_kind(self):
        if (self.conditions is None) == (self.expression is None):
            raise ValueError(
                "A rule's 'when' needs either conditions or an expression (not both)."
            )
        if self.expression is not None:
            if self.operator is not None:
                raise ValueError(
                    "A rule's 'operator' only combines conditions, not an expression."
                )
            problem = _rule_expression_problem(self.expression)
            if problem:
                raise ValueError(f"A rule's 'when' expression: {problem}")
        return self


class RuleSetValue(_Spec):
    """The value a rule gives the question: a fixed ``const`` (a text, a
    number, true/false for yes/no, a YYYY-MM-DD date, or the ``id`` of one of
    a choice question's options) or an ``expression``, never both."""

    const: Optional[Union[bool, int, float, str]] = Field(
        None, description="A choice question is set by the id of one of its options."
    )
    expression: Optional[Any] = None

    @model_validator(mode="after")
    def _one_kind(self):
        if (self.const is None) == (self.expression is None):
            raise ValueError("'setValue' needs either 'const' or 'expression'.")
        if isinstance(self.const, float) and (
            self.const != self.const or self.const in (float("inf"), float("-inf"))
        ):
            raise ValueError("'setValue' must be a finite number.")
        if isinstance(self.const, str) and len(self.const) > RULE_CONST_MAX_LENGTH:
            raise ValueError(
                f"A 'setValue' text can be at most {RULE_CONST_MAX_LENGTH} characters."
            )
        if self.expression is not None:
            problem = _rule_expression_problem(self.expression)
            if problem:
                raise ValueError(f"A 'setValue' expression: {problem}")
        return self


class RuleThen(_Spec):
    """What a rule does while it is active (at least one key). The server
    enforces ``required``, ``readOnly`` and ``setValue``; ``title`` and
    ``description`` only change what respondents read."""

    required: Optional[bool] = Field(
        None,
        description="true: the question must be answered; false: it is optional.",
    )
    read_only: Optional[Literal[True]] = Field(
        None,
        description="Respondents cannot change the value: a submitted value is "
        "discarded (replaced by an active setValue, else removed).",
    )
    title: Optional[str] = Field(
        None,
        max_length=RULE_TITLE_MAX_LENGTH,
        description="Plain text; may pipe answers ({{field:<id>}}).",
    )
    description: Optional[str] = Field(None, max_length=RULE_DESCRIPTION_MAX_LENGTH)
    set_value: Optional[RuleSetValue] = Field(
        None,
        description="The server computes the value and stores it, whatever a "
        "client sent; an empty result leaves the question unanswered. Implies "
        "readOnly.",
    )

    @model_validator(mode="after")
    def _something(self):
        if all(
            getattr(self, key) is None
            for key in ("required", "read_only", "title", "description", "set_value")
        ):
            raise ValueError(
                "A rule's 'then' needs at least one of: required, readOnly, "
                "title, description, setValue."
            )
        if self.title is not None and not self.title.strip():
            raise ValueError("A rule's title cannot be empty.")
        return self


class Rule(_Spec):
    """A field rule: while ``when`` holds, ``then`` applies. A field's rules
    apply in order; for each property the last active rule wins
    (``required`` starts from ``validations.required``). Rules never show or
    hide a question (that is ``logic``)."""

    id: str = Field(
        ...,
        pattern=RULE_ID_PATTERN,
        description="Unique within the form.",
    )
    when: RuleWhen
    then: RuleThen


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
    date_rules: Optional[List[DateRule]] = Field(
        None,
        max_length=DATE_RULES_MAX,
        description="Constraints on a date or day question's answer.",
    )
    min_time: Optional[str] = Field(
        None,
        pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$",
        description="A time question: the earliest time that can be answered (HH:MM, 24-hour).",
    )
    max_time: Optional[str] = Field(
        None,
        pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$",
        description="A time question: the latest time that can be answered (HH:MM, 24-hour).",
    )
    currencies: Optional[List[str]] = Field(
        None,
        min_length=1,
        max_length=CURRENCIES_MAX,
        description="A currency question: the ISO 4217 codes respondents may pick "
        "(the first is the default). Amounts are answered with min/max in validations.",
    )
    countries: Optional[List[str]] = Field(
        None,
        min_length=1,
        max_length=COUNTRIES_MAX,
        description="An address question: the ISO 3166-1 alpha-2 codes of the countries "
        "respondents may give (default: NL only).",
    )
    address_lookup: Optional[bool] = Field(
        None,
        description="An address question: fill in street and city from a Dutch "
        "postcode and house number while the server offers it (default: yes).",
    )
    why_we_ask: Optional[str] = Field(None, max_length=WHY_WE_ASK_MAX_LENGTH)
    logic: Optional[Logic] = None
    option_filter: Optional[OptionFilter] = Field(
        None,
        description="A choice question's options filtered by an earlier "
        "choice question's answer (see OptionFilter).",
    )
    option_source: Optional[OptionSource] = Field(
        None,
        description="A dropdown or multiple choice question's options taken from "
        "a workspace list or from another form's answers instead of choices "
        "(see OptionSource).",
    )
    share_as_choices: Optional[bool] = Field(
        None,
        description="A short text, dropdown or multiple choice question: its answers "
        "may be shown as choices in other forms of the same workspace (an "
        "optionSource of kind form_answers). Off unless true. Respondents are told "
        "next to the question; only answers given while a version with it on was "
        "filled are ever offered.",
    )
    rules: Optional[List[Rule]] = Field(
        None,
        max_length=FIELD_RULES_MAX,
        description=f"At most {FIELD_RULES_MAX} rules per question and "
        f"{FORM_FIELD_RULES_MAX} per form (see Rule).",
    )
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

    @model_validator(mode="after")
    def _check_type_settings(self):
        if (
            self.min_time is not None
            and self.max_time is not None
            and self.min_time > self.max_time
        ):
            raise ValueError("minTime is after maxTime.")
        if self.currencies is not None:
            for code in self.currencies:
                if not is_currency_code(code):
                    raise ValueError(f"'{code}' is not a currency the form offers.")
            if len(set(self.currencies)) != len(self.currencies):
                raise ValueError("A currency is listed twice.")
        check_countries(self.countries)
        check_tags_settings(self)
        return self


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
    # The order of the alternatives is pinned: ``typing`` caches a Union by its
    # members, not their order, so whichever module built an equal Union first
    # (psycopg's ``Union[str, int, None]``) decided it, and with it the
    # generated schemas, depending on the import order.
    value: Optional[Union[int, str]] = Field(
        None,
        json_schema_extra={
            "anyOf": [{"type": "integer"}, {"type": "string"}, {"type": "null"}]
        },
    )


class Trust(_Spec):
    """What respondents are told about their data, and how answers are
    handled."""

    purpose: Optional[str] = None
    retention_text: Optional[str] = Field(
        None,
        description=(
            "An internal note stored with the form. It is not shown to "
            "respondents: they see only the retention period the form "
            'enforces (see "retention").'
        ),
    )
    privacy_policy_url: Optional[str] = Field(None, description="An http(s) URL.")
    retention: Optional[Retention] = None
    require_verified_identity: Optional[bool] = None
    allow_editing_response: Optional[bool] = None
    show_submission_number: Optional[bool] = None
    allow_save_draft: Optional[bool] = Field(
        None,
        description="Let respondents save a draft and continue later (off by "
        "default). Drafts are encrypted, kept apart from the responses and "
        "deleted after draftRetentionDays.",
    )
    draft_retention_days: Optional[int] = Field(
        None,
        ge=1,
        le=90,
        description="How many days after the last save a draft is kept, 1 to "
        "90; left out, 30.",
    )
    show_review_page: Optional[bool] = Field(
        None,
        description=(
            "Respondents see their answers on a page of their own, with a link "
            "back to each page, before they send them."
        ),
    )


class FormSpec(_Spec):
    """A form, as its creator controls it."""

    model_config = ConfigDict(title="BetterCollected form spec v1")

    spec_version: Literal["1"]
    title: Optional[str] = None
    description: Optional[str] = None
    language: Optional[Literal[tuple(FORM_LANGUAGES)]] = Field(
        None,
        description="The language the form's own text (title, questions, "
        "choices) is written in, as a short BCP 47 tag. Respondent pages mark "
        "that text with it for screen readers and browsers. When a document "
        "that replaces a form leaves it out, the form keeps its language; "
        "null clears it.",
    )
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

    @model_validator(mode="before")
    @classmethod
    def _count_rules_first(cls, data):
        # far too many rules: refused before each one is validated
        if isinstance(data, dict) and isinstance(data.get("pages"), list):
            total = sum(
                _raw_spec_rules(page.get("fields"))
                for page in data["pages"]
                if isinstance(page, dict)
            )
            if total > FORM_FIELD_RULES_MAX:
                raise ValueError(
                    f"A form can have at most {FORM_FIELD_RULES_MAX} rules; this "
                    f"one has {total}."
                )
        return data

    @model_validator(mode="after")
    def _check_field_count(self):
        count = sum(count_fields(page.fields) for page in self.pages)
        if count > MAX_FIELDS:
            raise ValueError(
                f"A form can have at most {MAX_FIELDS} fields in all; this one "
                f"has {count}."
            )
        rules = sum(
            len(field.rules or [])
            for page in self.pages
            for field in _all_fields(page.fields)
        )
        if rules > FORM_FIELD_RULES_MAX:
            raise ValueError(
                f"A form can have at most {FORM_FIELD_RULES_MAX} rules; this one "
                f"has {rules}."
            )
        return self


def _raw_spec_rules(fields) -> int:
    """Rules of raw spec fields (``rules`` beside ``fields``), unparsed."""
    total, pending = 0, list(fields) if isinstance(fields, list) else []
    while pending:
        field = pending.pop()
        if not isinstance(field, dict):
            continue
        if isinstance(field.get("rules"), list):
            total += len(field["rules"])
        if isinstance(field.get("fields"), list):
            pending.extend(field["fields"])
    return total


def _all_fields(fields):
    pending = list(fields or [])
    while pending:
        field = pending.pop()
        yield field
        pending.extend(field.fields or [])


FormField.model_rebuild()
