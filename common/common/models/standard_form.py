import datetime as dt
import enum
from enum import Enum
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from common.models.consent import Consent, ConsentResponse, ResponseRetentionType
from pydantic import BaseModel, Field


class EmbedProvider(str, enum.Enum):
    YOUTUBE = "youtube"
    VIEMO = "vimeo"
    NO_EMBED = "no_embed"


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
    DATE = "date"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    MULTIPLE_CHOICE = "multiple_choice"
    OPINION_SCALE = "opinion_scale"
    RANKING = "ranking"
    RATING = "rating"
    DROPDOWN = "dropdown"
    MATRIX = "matrix"
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


class StandardAttachmentProperties(BaseModel):
    description: Optional[str]


class StandardAttachmentType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


class StandardFieldAttachment(BaseModel):
    type: Optional[StandardAttachmentType]
    href: Optional[str]
    scale: Optional[float]
    properties: Optional[StandardAttachmentProperties] = StandardAttachmentProperties()
    embed_provider: Optional[EmbedProvider]


class StandardChoice(BaseModel):
    id: Optional[str]
    ref: Optional[str]
    value: Optional[str]
    label: Optional[str]
    attachment: Optional[StandardFieldAttachment]


class StandardAnswerField(BaseModel):
    id: str
    ref: Optional[str]


class StandardPaymentAnswer(BaseModel):
    amount: Optional[str]
    last4: Optional[str]
    name: Optional[str]


class FileMetadata(BaseModel):
    id: str
    name: Optional[str]
    type: Optional[str]
    size: Optional[float]
    url: Optional[str]


class StandardChoiceAnswer(BaseModel):
    value: Optional[str]
    other: Optional[str]


class StandardChoicesAnswer(BaseModel):
    values: Optional[List[str]]
    other: Optional[str]


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
    type: Optional[ConditionalType]
    comparison: Optional[Comparison]
    field: Optional["StandardFormField"]
    conditions: Optional[List["Condition"]]
    logical_operator: Optional[LogicalOperator]
    field_type: Optional[FieldType]
    value: Optional[Any]


class ConditionalPayload(BaseModel):
    field: Optional[Any]
    operator: Optional[str]
    value: Optional[Any]


class ActionType(str, enum.Enum):
    JUMP_TO_PAGE = "jump_to_page"
    CALCULATE = "calculate"
    REQUIRE_ANSWERS = "require_answer"
    SHOW_FIELDS = "show_fields"
    HIDE_FIELDS = "hide_fields"


class ConditionalActions(BaseModel):
    type: Optional[ActionType]
    payload: Optional[List[str] | str]


class StandardFormSettings(BaseModel):
    """
    Data transfer object for standard form settings.
    """

    embed_url: Optional[str]
    custom_url: Optional[str]
    provider: Optional[str]
    language: Optional[str]
    is_public: Optional[bool]
    is_trial: Optional[bool]
    response_data_owner_field: Optional[str]
    response_data_owner_fields: Optional[List[str]]
    screens: Optional[Dict[str, List[Dict[str, Any]]]]
    privacy_policy_url: Optional[str]
    response_expiration: Optional[str]
    response_expiration_type: Optional[ResponseRetentionType]
    # If responses are set to editable then it can be used for tracking responses
    is_response_editable: Optional[bool]
    # State whether the form is accepting new responses
    is_closed: Optional[bool]


class StandardFieldProperty(BaseModel):
    hidden: Optional[bool]
    description: Optional[str]
    choices: Optional[List[StandardChoice]]
    fields: Optional[List["StandardFormField"]]
    allow_multiple_selection: Optional[bool]
    allow_other_choice: Optional[bool]
    hide_marks: Optional[bool]
    button_text: Optional[str]
    placeholder: Optional[str]
    steps: Optional[int]
    start_form: Optional[int]
    rating_shape: Optional[str]
    labels: Optional[Dict[str, str]]
    date_format: Optional[str]
    actions: Optional[List[ConditionalActions]]
    conditions: Optional[List[Condition]]
    logical_operator: Optional[LogicalOperator]
    update_id: Optional[str]
    mentions: Optional[Dict[str, str]]


class StandardFieldValidations(BaseModel):
    required: Optional[bool]
    max_length: Optional[int]
    min_length: Optional[int]
    min_value: Optional[float]
    max_value: Optional[float]
    regex: Optional[str]
    min_choices: Optional[int]
    max_choices: Optional[int]


class StandardFormField(BaseModel):
    """
    Data transfer object for Fields in a standard form.
    """

    id: Optional[str]
    ref: Optional[str]
    title: Optional[str]
    description: Optional[str]
    value: Optional[str]
    type: Optional[StandardFormFieldType]
    tag: Optional[FormBuilderTagTypes]
    properties: Optional[StandardFieldProperty] = StandardFieldProperty()
    validations: Optional[StandardFieldValidations] = StandardFieldValidations()
    attachment: Optional[StandardFieldAttachment] = None


StandardFieldProperty.update_forward_refs()
Condition.update_forward_refs()
StandardFormField.update_forward_refs()


class State(BaseModel):
    global_state: Optional[Dict[str, Any]] = Field(
        None,
        example={
            "global_var1": "default value",
            "global_var2": 0,
            "global_var3": True,
        })
    processor_state: Optional[Dict[str, Any]] = Field(
        None,
        example={
            "processor_var1": "default value",
            "processor_var2": 0,
            "processor_var3": True,
        })
    # Is form response locked at submission by default can be set otherwise
    # by default it will be in locked state
    is_locked: Optional[bool] = Field(None)


class StandardForm(BaseModel):
    form_id: Optional[str]
    type: Optional[str]
    title: Optional[str]
    logo: Optional[str]
    cover_image: Optional[str]
    description: Optional[str]
    button_text: Optional[str]
    fields: Optional[List[StandardFormField]]
    consent: Optional[List[Consent]]
    state: Optional[State] = Field(State())
    settings: Optional[StandardFormSettings] = StandardFormSettings()
    published_at: Optional[dt.datetime]


class StandardFormResponseAnswer(BaseModel):
    field: Optional[StandardAnswerField]
    type: Optional[StandardResponseType]
    text: Optional[str]
    choice: Optional[StandardChoiceAnswer]
    choices: Optional[StandardChoicesAnswer]
    number: Optional[int]
    boolean: Optional[bool]
    email: Optional[str]
    date: Optional[str]
    url: Optional[str]
    file_url: Optional[str]
    payment: Optional[StandardPaymentAnswer]
    phone_number: Optional[str]
    file_metadata: Optional[FileMetadata]


class ResponseState(BaseModel):
    global_state: Optional[Dict[str, Any]] = Field({})
    processor_state: Optional[Dict[PydanticObjectId, Dict[str, Any]]] = Field({})
    is_locked: Optional[bool] = Field(True)
    choices_total_point: Optional[float] = Field(None)


class StandardFormResponse(BaseModel):
    """
    Data transfer object for a standard form response.
    """
    response_id: Optional[str]
    form_id: Optional[str]
    provider: Optional[str]
    respondent_email: Optional[str] = None
    answers: Optional[
                 Dict[str, StandardFormResponseAnswer | Dict[str, Any]]
             ] | bytes | str
    form_version: Optional[int]
    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]
    published_at: Optional[dt.datetime]
    consent: Optional[List[ConsentResponse]]
    expiration: Optional[str]
    expiration_type: Optional[ResponseRetentionType]
    state: Optional[ResponseState] = Field(None)
    dataOwnerIdentifierType: Optional[str]
    dataOwnerIdentifier: Optional[str]
