import datetime as dt
import enum
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from beanie import PydanticObjectId
from common.models.consent import Consent, ConsentResponse, ResponseRetentionType
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class ThemeBackground(BaseModel):
    """Optional page-ground decoration. Field names are camelCase on purpose:
    the webapp sends the theme verbatim inside the form JSON (no camel<->snake
    conversion happens for this nested object), and the same shape round-trips
    back out. Lenient here — strict validation lives on the workspace
    theme-presets endpoint where themes are authored."""

    type: Optional[str] = None
    gradientFrom: Optional[str] = None
    gradientTo: Optional[str] = None
    gradientAngle: Optional[int] = None
    pattern: Optional[str] = None
    imageUrl: Optional[str] = None


class Theme(BaseModel):
    title: str
    primary: str
    secondary: str
    tertiary: str
    accent: str
    background: Optional[ThemeBackground] = None
    # How the form is dressed (classic/sheet/studio; open for future styles).
    # Lenient here — strict validation lives on the workspace theme endpoint.
    style: Optional[str] = None


class EmbedProvider(str, enum.Enum):
    YOUTUBE = "youtube"
    VIEMO = "vimeo"
    NO_EMBED = "no_embed"


class LayoutType(str, enum.Enum):
    TWO_COLUMN_IMAGE_LEFT = ("TWO_COLUMN_IMAGE_LEFT",)
    TWO_COLUMN_IMAGE_RIGHT = ("TWO_COLUMN_IMAGE_RIGHT",)
    SINGLE_COLUMN_IMAGE_BACKGROUND = ("SINGLE_COLUMN_IMAGE_BACKGROUND",)
    SINGLE_COLUMN_NO_BACKGROUND = ("SINGLE_COLUMN_NO_BACKGROUND",)
    SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN = "SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN"


class FormBuilderTagTypes(str, enum.Enum):
    LAYOUT_HEADER1 = "h1"
    LAYOUT_HEADER2 = "h2"
    LAYOUT_HEADER3 = "h3"
    LAYOUT_HEADER4 = "h4"
    LAYOUT_HEADER5 = "h5"
    LAYOUT_SHORT_TEXT = "p"
    LAYOUT_LABEL = "strong"
    LAYOUT_DIVIDER = "divider"

    INPUT_SHORT_TEXT = "input_short_text"
    INPUT_MARKDOWN = "input_markdown"
    INPUT_LONG_TEXT = "input_long_text"
    INPUT_MULTIPLE_CHOICE = "input_multiple_choice"
    INPUT_MULTISELECT = "input_multiselect"
    INPUT_CHECKBOXES = "input_checkboxes"
    INPUT_EMAIL = "input_email"
    INPUT_NUMBER = "input_number"
    INPUT_PHONE_NUMBER = "input_phone_number"
    INPUT_LINK = "input_link"
    INPUT_DATE = "input_date"
    INPUT_TIME = "input_time"
    INPUT_DATE_RANGE = "input_date_range"
    INPUT_TIME_RANGE = "input_time_range"
    INPUT_DATETIME_RANGE = "input_datetime_range"
    INPUT_DROPDOWN = "input_dropdown"
    INPUT_RATING = "input_rating"
    INPUT_LINEAR_SCALE = "input_linear_scale"
    INPUT_TEMPLATE_BUTTON = "input_template_button"
    INPUT_FILE_UPLOAD = "input_file_upload"
    INPUT_RANKING = "input_ranking"
    INPUT_MATRIX = "input_matrix"


class StandardFormFieldType(str, Enum):
    SLIDE = "slide"
    DATE = "date"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    MULTIPLE_CHOICE = "multiple_choice"
    OPINION_SCALE = "opinion_scale"
    RANKING = "ranking"
    RATING = "rating"
    DROPDOWN = "dropdown"
    MATRIX = "matrix"
    TABULAR_INPUT = "tabular_input"
    FILE_UPLOAD = "file_upload"
    GROUP = "group"
    EMAIL = "email"
    PAYMENT = "payment"
    STATEMENT = "statement"
    PAGE_BREAK = "page_break"
    CALCULATED = "calculated"
    HIDDEN = "hidden"
    CONDITIONAL = "conditional"

    LAYOUT_HEADER1 = "h1"
    LAYOUT_HEADER2 = "h2"
    LAYOUT_HEADER3 = "h3"
    LAYOUT_HEADER4 = "h4"
    LAYOUT_HEADER5 = "h5"
    LAYOUT_SHORT_TEXT = "p"
    LAYOUT_LABEL = "strong"
    LAYOUT_DIVIDER = "divider"
    LAYOUT_MARKDOWN = "markdown"

    INPUT_SHORT_TEXT = "input_short_text"
    INPUT_LONG_TEXT = "input_long_text"
    INPUT_MARKDOWN = "input_markdown"
    INPUT_MULTIPLE_CHOICE = "input_multiple_choice"
    INPUT_MULTISELECT = "input_multiselect"
    INPUT_CHECKBOXES = "input_checkboxes"
    INPUT_EMAIL = "input_email"
    INPUT_NUMBER = "input_number"
    INPUT_PHONE_NUMBER = "input_phone_number"
    INPUT_LINK = "input_link"
    INPUT_DATE = "input_date"
    INPUT_TIME = "input_time"
    INPUT_DATE_RANGE = "input_date_range"
    INPUT_TIME_RANGE = "input_time_range"
    INPUT_DATETIME_RANGE = "input_datetime_range"
    INPUT_DROPDOWN = "input_dropdown"
    INPUT_RATING = "input_rating"
    INPUT_LINEAR_SCALE = "input_linear_scale"
    INPUT_TEMPLATE_BUTTON = "input_template_button"
    INPUT_FILE_UPLOAD = "input_file_upload"
    INPUT_RANKING = "input_ranking"
    INPUT_MATRIX = "input_matrix"

    TEXT = "text"
    YES_NO = "yes_no"
    LINK = "url"
    LINEAR_RATING = "linear_rating"
    PHONE_NUMBER = "phone_number"
    NUMBER = "number"
    VIDEO_CONTENT = "VIDEO_CONTENT"
    IMAGE_CONTENT = "IMAGE_CONTENT"
    DATE_INPUT = "date_input"
    EMAIL_INPUT = "email_input"
    NUMBER_INPUT = "number_input"
    SHORT_TEXT_INPUT = "short_text_input"
    LONG_TEXT_INPUT = "long_text_input"
    MULTIPLE_CHOICE_INPUT = "multiple_choice_input"
    RANKING_INPUT = "ranking_input"
    RATING_INPUT = "rating_input"
    DROP_DOWN_INPUT = "drop_down_input"
    MEDIA_INPUT = "media_input"
    MATRIX_ROW_INPUT = "matrix_row_input"


class StandardResponseType(str, Enum):
    TEXT = "text"
    CHOICE = "choice"
    CHOICES = "choices"
    NUMBER = "number"
    BOOLEAN = "boolean"
    MATRIX = "matrix"
    EMAIL = "email"
    DATE = "date"
    URL = "url"
    PHONE_NUMBER = "phone_number"
    FILE_URL = "file_url"
    PAYMENT = "payment"
    TABULAR_INPUT = "tabular_input"
    # A repeating group: the answer carries one answers-dict per item in
    # ``StandardFormResponseAnswer.items``.
    GROUP = "group"


class StandardAttachmentProperties(BaseModel):
    description: Optional[str] = None


class StandardAttachmentType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


class StandardFieldAttachment(BaseModel):
    type: Optional[StandardAttachmentType] = None
    href: Optional[str] = None
    scale: Optional[float] = None
    properties: Optional[StandardAttachmentProperties] = StandardAttachmentProperties()
    embed_provider: Optional[EmbedProvider] = None


class StandardChoice(BaseModel):
    id: Optional[str] = None
    ref: Optional[str] = None
    value: Optional[str] = None
    label: Optional[str] = None
    attachment: Optional[StandardFieldAttachment] = None


class StandardAnswerField(BaseModel):
    id: str
    ref: Optional[str] = None


class StandardPaymentAnswer(BaseModel):
    amount: Optional[str] = None
    last4: Optional[str] = None
    name: Optional[str] = None


class FileMetadata(BaseModel):
    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    size: Optional[float] = None
    url: Optional[str] = None


class StandardChoiceAnswer(BaseModel):
    value: Optional[str] = None
    other: Optional[str] = None


class StandardChoicesAnswer(BaseModel):
    values: Optional[List[str]] = None
    other: Optional[str] = None


class Comparison(str, enum.Enum):
    CONTAINS = "contains"
    DOES_NOT_CONTAIN = "does_not_contain"
    IS_EQUAL = "is_equal"
    IS_NOT_EQUAL = "is_not_equal"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THEN_EQUAL = "greater_than_equal"
    LESS_THAN_EQUAL = "less_than_equal"


class FieldType(str, enum.Enum):
    SINGLE = "single"
    MATRIX = "matrix"


class ConditionalType(str, enum.Enum):
    SINGLE = "single"
    NESTED = "nested"


class LogicalOperator(str, enum.Enum):
    AND = "and"
    OR = "or"


class Condition(BaseModel):
    type: Optional[ConditionalType] = None
    comparison: Optional[Comparison] = None
    field: Optional["StandardFormField"] = None
    conditions: Optional[List["Condition"]] = None
    logical_operator: Optional[LogicalOperator] = None
    field_type: Optional[FieldType] = None
    value: Optional[Any] = None


class ConditionalPayload(BaseModel):
    field: Optional[Any] = None
    operator: Optional[str] = None
    value: Optional[Any] = None


class ActionType(str, enum.Enum):
    JUMP_TO_PAGE = "jump_to_page"
    CALCULATE = "calculate"
    REQUIRE_ANSWERS = "require_answer"
    SHOW_FIELDS = "show_fields"
    HIDE_FIELDS = "hide_fields"


class ConditionalActions(BaseModel):
    type: Optional[ActionType] = None
    payload: Optional[List[str] | str] = None


class StandardFormSettings(BaseModel):
    """
    Data transfer object for standard form settings.
    """

    embed_url: Optional[str] = None
    custom_url: Optional[str] = None
    provider: Optional[str] = None
    language: Optional[str] = None
    is_public: Optional[bool] = None
    is_trial: Optional[bool] = None
    response_data_owner_field: Optional[str] = None
    response_data_owner_fields: Optional[List[str]] = None
    screens: Optional[Dict[str, List[Dict[str, Any]]]] = None
    privacy_policy_url: Optional[str] = None
    response_expiration: Optional[str] = None
    response_expiration_type: Optional[ResponseRetentionType] = None
    # If responses are set to editable then it can be used for tracking responses
    is_response_editable: Optional[bool] = None
    # State whether the form is accepting new responses
    is_closed: Optional[bool] = None


class FieldLogicCondition(BaseModel):
    """A single condition in a v2 field conditional-visibility rule."""

    field_id: Optional[str] = None
    field_type: Optional[str] = None
    comparison: Optional[str] = None
    value: Optional[Any] = None
    # Group-level conditions (``field_id`` is a repeating group): ``COUNT``
    # compares the number of items with ``value``; ``ANY`` / ``ALL`` apply
    # ``comparison``/``value`` to ``child_field_id`` in each item. There is
    # deliberately no condition on a specific item position.
    group_mode: Optional[str] = None
    child_field_id: Optional[str] = None
    child_field_type: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class FieldLogic(BaseModel):
    """
    v2 conditional-visibility rule stored on a field at ``properties.logic``.
    Kept as plain strings (action ``SHOW``/``HIDE``, operator ``AND``/``OR``,
    comparison enum values) so it round-trips the webapp shape verbatim without
    enum-casing coupling. See webapp ``utils/conditional-logic.ts``.
    """

    action: Optional[str] = None
    operator: Optional[str] = None
    conditions: Optional[List[FieldLogicCondition]] = None

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class PageJump(BaseModel):
    """
    v2 page-jump / branching rule stored on a slide at ``properties.jumps``.
    ``target`` is a slide id or the sentinel ``__SUBMIT__``. Plain strings, same
    rationale as :class:`FieldLogic`.
    """

    operator: Optional[str] = None
    conditions: Optional[List[FieldLogicCondition]] = None
    target: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class FieldPosition(BaseModel):
    """Flow-view canvas coordinates of a page node. Cosmetic only."""

    x: Optional[float] = None
    y: Optional[float] = None


# Hard ceiling on items per repeating group, whatever the creator asks for.
REPEAT_MAX_ITEMS_LIMIT = 50
# Up to this many items a group exports as columns per item by default;
# above it, as a separate table with one row per item.
REPEAT_COLUMNS_EXPORT_MAX = 5

# Child question types a repeating group may contain (v1). Nested groups,
# internal fields (hidden/calculated) and fields whose answers live outside
# the answers dict (uploads) or span several answers (matrix, table) are not
# supported inside a group.
REPEAT_CHILD_FIELD_TYPES = {
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
    "text",
}


class RepeatSettings(BaseModel):
    """Makes a ``group`` field repeatable: respondents fill its child questions
    once per item (one block per applicant, employer, ...), between
    ``min_items`` and ``max_items`` times. ``item_label`` names one item
    ("Applicant") and labels the add button; ``item_title`` is an optional
    header template that may pipe a sibling answer (``{{field:<child id>}}``).
    ``export_layout`` overrides the default export shape (columns per item
    when ``max_items <= 5``, else a separate table of rows)."""

    min_items: Optional[int] = Field(1, ge=0, le=REPEAT_MAX_ITEMS_LIMIT)
    max_items: Optional[int] = Field(3, ge=1, le=REPEAT_MAX_ITEMS_LIMIT)
    item_label: Optional[str] = Field(None, max_length=80)
    item_title: Optional[str] = Field(None, max_length=300)
    export_layout: Optional[Literal["columns", "rows"]] = None

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    @model_validator(mode="after")
    def _check_bounds(self):
        if (
            self.min_items is not None
            and self.max_items is not None
            and self.min_items > self.max_items
        ):
            raise ValueError(
                "A repeating group's minimum number of items cannot exceed its maximum."
            )
        return self

    @property
    def effective_min(self) -> int:
        return self.min_items if self.min_items is not None else 1

    @property
    def effective_max(self) -> int:
        return self.max_items if self.max_items is not None else 3

    @property
    def effective_export_layout(self) -> str:
        if self.export_layout:
            return self.export_layout
        return "columns" if self.effective_max <= REPEAT_COLUMNS_EXPORT_MAX else "rows"


class StandardFieldProperty(BaseModel):
    hidden: Optional[bool] = None
    logic: Optional[FieldLogic] = None
    jumps: Optional[List[PageJump]] = None
    position: Optional[FieldPosition] = None
    description: Optional[str] = None
    choices: Optional[List[StandardChoice]] = None
    fields: Optional[List["StandardFormField"]] = None
    allow_multiple_selection: Optional[bool] = None
    allow_other_choice: Optional[bool] = None
    hide_marks: Optional[bool] = None
    button_text: Optional[str] = None
    placeholder: Optional[str] = None
    steps: Optional[int] = None
    start_from: Optional[int] = None
    rating_shape: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    date_format: Optional[str] = None
    actions: Optional[List[ConditionalActions]] = None
    conditions: Optional[List[Condition]] = None
    logical_operator: Optional[LogicalOperator] = None
    update_id: Optional[str] = None
    mentions: Optional[Dict[str, str]] = None
    theme: Optional[Theme] = None
    layout: Optional[LayoutType] = None
    row_titles: Optional[List[str]] = None
    column_titles: Optional[List[str]] = None
    tabular_value: Optional[List[List[str]]] = None
    # 12-grid width of the field on desktop (12 = full row, 6 = half…); the
    # webapp sends camelCase colSpan via the alias generator.
    col_span: Optional[int] = Field(None, ge=1, le=12)
    # Present only on a repeating ``group`` field (see RepeatSettings).
    repeat: Optional[RepeatSettings] = None

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class StandardFieldValidations(BaseModel):
    required: Optional[bool] = None
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    regex: Optional[str] = None
    min_choices: Optional[int] = None
    max_choices: Optional[int] = None


class StandardFormField(BaseModel):
    """
    Data transfer object for Fields in a standard form.
    """

    id: Optional[str] = None
    index: Optional[int] = None
    ref: Optional[str] = None
    title: Optional[str | Dict[str, Any]] = None
    description: Optional[str] = None
    value: Optional[str] = None
    type: Optional[StandardFormFieldType] = None
    tag: Optional[FormBuilderTagTypes] = None
    properties: Optional[StandardFieldProperty] = Field(
        default_factory=StandardFieldProperty
    )
    validations: Optional[StandardFieldValidations] = Field(
        default_factory=StandardFieldValidations
    )
    attachment: Optional[StandardFieldAttachment] = None
    image_url: Optional[str] = None
    # Internal ("for office use only") field: never served to respondents,
    # filled in by workspace members on each submission afterwards. Its values
    # live in ``StandardFormResponse.internal_answers``, never in ``answers``.
    internal: Optional[bool] = None

    @model_validator(mode="after")
    def _check_repeating_group(self):
        check_repeating_group_structure(self)
        return self


def _type_value(field_type: Any) -> Optional[str]:
    return getattr(field_type, "value", field_type)


def check_repeating_group_structure(field: Any) -> None:
    """Validate a repeating group's children (v1 rules). Only fields that
    carry ``properties.repeat`` are checked, so legacy/imported ``group``
    fields are untouched. Raises ``ValueError`` with a readable message."""
    properties = getattr(field, "properties", None)
    repeat = getattr(properties, "repeat", None) if properties else None
    if repeat is None:
        return
    if _type_value(getattr(field, "type", None)) != StandardFormFieldType.GROUP.value:
        raise ValueError("Only a group field can repeat.")
    children = getattr(properties, "fields", None) or []
    seen = set()
    for child in children:
        child_type = _type_value(getattr(child, "type", None))
        if child_type == StandardFormFieldType.GROUP.value:
            raise ValueError("Repeating groups cannot contain another group.")
        if child_type not in REPEAT_CHILD_FIELD_TYPES:
            raise ValueError(
                f"A '{child_type}' question cannot be placed inside a repeating group."
            )
        child_id = getattr(child, "id", None)
        if child_id and child_id in seen:
            raise ValueError("Questions inside a repeating group need unique ids.")
        seen.add(child_id)


StandardFieldProperty.model_rebuild()
Condition.model_rebuild()
StandardFormField.model_rebuild()


class State(BaseModel):
    global_state: Optional[Dict[str, Any]] = Field(None)
    processor_state: Optional[Dict[str, Any]] = Field(None)
    # Is form response locked at submission by default can be set otherwise
    # by default it will be in locked state
    is_locked: Optional[bool] = Field(None)


class Trigger(str, Enum):
    # This trigger is run when form response is submitted
    on_submit = "on_submit"
    # This trigger is run when form is opened
    on_open = "on_open"

    def __str__(self):
        return self.value


class ParameterValue(BaseModel):
    name: str = Field(None)
    value: str = Field(None)
    required: Optional[bool] = Field(False)


class ActionState(BaseModel):
    id: PydanticObjectId
    enabled: Optional[bool] = True


class WelcomePageField(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    layout: Optional[LayoutType] = None
    imageUrl: Optional[str] = None
    buttonText: Optional[str] = None


class ThankYouPageField(BaseModel):
    # Heading shown above the message; the responder falls back to the classic
    # "Thank You!" greeting when unset.
    title: Optional[str] = None
    message: Optional[str] = None
    buttonText: Optional[str] = None
    buttonLink: Optional[str] = None
    layout: Optional[LayoutType] = None
    imageUrl: Optional[str] = None


class StandardForm(BaseModel):
    builder_version: Optional[str] = None
    form_id: Optional[str] = None
    imported_form_id: Optional[str] = None
    type: Optional[str] = None
    title: Optional[str] = None
    logo: Optional[str] = None
    cover_image: Optional[str] = None
    description: Optional[str] = None
    button_text: Optional[str] = None
    is_multi_page: Optional[bool] = None
    fields: Optional[List[StandardFormField]] = None
    # Creator-declared URL parameter names ("hidden fields"): captured from the
    # share link's query string at fill time (e.g. utm_source), stored with the
    # response, and available to answer piping in question text. Names only —
    # values never live on the form.
    hidden_fields: Optional[List[str]] = None
    consent: Optional[List[Consent]] = None
    state: Optional[State] = Field(default_factory=State)
    settings: Optional[StandardFormSettings] = Field(
        default_factory=StandardFormSettings
    )
    published_at: Optional[dt.datetime] = None
    actions: Optional[Dict[str, List[ActionState]]] = None
    parameters: Optional[Dict[str, List[ParameterValue]]] = Field(None)
    secrets: Optional[Dict[str, List[ParameterValue]]] = Field(None)
    theme: Optional[Theme] = None
    welcome_page: Optional[WelcomePageField] = None
    thankyou_page: Optional[List[ThankYouPageField]] = None
    row_titles: Optional[List[str]] = None
    column_titles: Optional[List[str]] = None

class StandardFormResponseAnswer(BaseModel):
    field: Optional[StandardAnswerField] = None
    type: Optional[StandardResponseType] = None
    text: Optional[str] = None
    choice: Optional[StandardChoiceAnswer] = None
    choices: Optional[StandardChoicesAnswer] = None
    number: Optional[int] = None
    boolean: Optional[bool] = None
    email: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    file_url: Optional[str] = None
    payment: Optional[StandardPaymentAnswer] = None
    phone_number: Optional[str] = None
    file_metadata: Optional[FileMetadata] = None
    tabular_value: Optional[List[List[str]]] = None
    # Repeating group answer (type ``group``): one answers-dict per item, keyed
    # by child field id, each value validated like a top-level answer. Only
    # valid on a repeating group's key (enforced against the form on submit).
    items: Optional[List[Dict[str, "StandardFormResponseAnswer"]]] = Field(
        None, max_length=REPEAT_MAX_ITEMS_LIMIT
    )


StandardFormResponseAnswer.model_rebuild()


class InternalAnswerMeta(BaseModel):
    """Who last changed one internal answer on a submission, and when."""

    updated_by: Optional[str] = None
    updated_by_email: Optional[str] = None
    updated_at: Optional[dt.datetime] = None


class ResponseState(BaseModel):
    global_state: Optional[Dict[str, Any]] = Field({})
    processor_state: Optional[Dict[PydanticObjectId, Dict[str, Any]]] = Field({})
    is_locked: Optional[bool] = Field(True)
    choices_total_point: Optional[float] = Field(None)


class StandardFormResponse(BaseModel):
    """
    Data transfer object for a standard form response.
    """

    response_id: Optional[str] = None
    form_id: Optional[str] = None
    provider: Optional[str] = None
    respondent_email: Optional[str] = None
    answers: (
        Optional[Dict[str, StandardFormResponseAnswer | Dict[str, Any]]] | bytes | str
    ) = None
    # Captured hidden-field (URL parameter) values for this submission, keyed by
    # the declared name. Encrypted at rest alongside `answers` (bytes/str once
    # persisted), decrypted on the same read path.
    hidden_fields: Optional[Dict[str, str] | bytes | str] = None
    # Staff-entered values of the form's internal fields, keyed by field id.
    # Encrypted at rest like `answers`; never returned to respondents.
    internal_answers: (
        Optional[Dict[str, StandardFormResponseAnswer | Dict[str, Any]]] | bytes | str
    ) = None
    # field id -> who last changed that internal answer and when (plaintext).
    internal_answers_meta: Optional[Dict[str, InternalAnswerMeta]] = None
    # Optimistic-concurrency counter for staff edits of internal answers:
    # bumped on every save, which only succeeds against the version the
    # editor read (None = never edited = 0).
    internal_answers_version: Optional[int] = None
    form_version: Optional[int] = None
    created_at: Optional[dt.datetime] = None
    updated_at: Optional[dt.datetime] = None
    published_at: Optional[dt.datetime] = None
    consent: Optional[List[ConsentResponse]] = None
    expiration: Optional[str] = None
    expiration_type: Optional[ResponseRetentionType] = None
    state: Optional[ResponseState] = Field(None)
    dataOwnerIdentifierType: Optional[str] = None
    dataOwnerIdentifier: Optional[str] = None
    anonymous_identity: Optional[str] = None
    submission_uuid: Optional[str] = None

