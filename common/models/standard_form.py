import datetime as dt
import enum
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EmbedProvider(str, enum.Enum):
    YOUTUBE = "youtube"
    VIEMO = "vimeo"
    NO_EMBED = "no_embed"


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
    PAYMENT = "payment"
    STATEMENT = "statement"


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
    ref: Optional[str]
    label: Optional[str]
    attachment: Optional[StandardFieldAttachment]


class StandardAnswerField(BaseModel):
    id: str
    ref: Optional[str]


class StandardPaymentAnswer(BaseModel):
    amount: Optional[str]
    last4: Optional[str]
    name: Optional[str]


class StandardChoiceAnswer(BaseModel):
    value: Optional[str]
    other: Optional[str]


class StandardChoicesAnswer(BaseModel):
    values: Optional[List[str]]
    other: Optional[str]


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
    response_data_owner_fields: Optional[List[str]]
    screens: Optional[Dict[str, List[Dict[str, Any]]]]
    # If responses are set to editable then it can be used for tracking responses
    is_response_editable: Optional[bool]
    # State whether the form is accepting new responses
    is_closed: Optional[bool]


class StandardFieldProperty(BaseModel):
    description: Optional[str]
    choices: Optional[List[StandardChoice]]
    fields: Optional[List["StandardFormField"]]
    allow_multiple_selection: Optional[bool]
    allow_other_choice: Optional[bool]
    hide_marks: Optional[bool]
    button_text: Optional[str]
    steps: Optional[int]
    start_form: Optional[int]
    rating_shape: Optional[str]
    labels: Optional[Dict[str, str]]
    date_format: Optional[str]


class StandardFieldValidations(BaseModel):
    required: Optional[bool]
    max_length: Optional[int]
    min_value: Optional[float]
    max_value: Optional[float]


class StandardFormField(BaseModel):
    """
    Data transfer object for Fields in a standard form.
    """

    id: Optional[str]
    ref: Optional[str]
    title: Optional[str]
    description: Optional[str]
    type: Optional[StandardFormFieldType]
    properties: Optional[StandardFieldProperty] = StandardFieldProperty()
    validations: Optional[StandardFieldValidations] = StandardFieldValidations()
    attachment: Optional[StandardFieldAttachment] = None


StandardFieldProperty.update_forward_refs()


class StandardForm(BaseModel):
    form_id: Optional[str]
    type: Optional[str]
    title: Optional[str]
    description: Optional[str]
    fields: Optional[List[StandardFormField]]
    settings: Optional[StandardFormSettings] = StandardFormSettings()
    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]
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


class StandardFormResponse(BaseModel):
    """
    Data transfer object for a standard form response.
    """

    response_id: Optional[str]
    form_id: Optional[str]
    provider: Optional[str]
    respondent_email: Optional[str] = None
    answers: Optional[Dict[str, StandardFormResponseAnswer]]
    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]
    published_at: Optional[dt.datetime]

    # TODO : Get data owner from workspace form settings from this response
    dataOwnerIdentifierType: Optional[str]
    dataOwnerIdentifier: Optional[str]
