import datetime as dt
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class QuestionFieldType(str, Enum):
    ADDRESS = "address"
    CONTACT_INFO = "contact_info"
    DATE = "date"
    DROPDOWN = "dropdown"
    EMAIL = "email"
    MATRIX = "matrix"
    FILE_UPLOAD = "file_upload"
    GROUP = "group"
    GRID = "grid"
    LEGAL = "legal"
    LONG_TEXT = "long_text"
    MULTIPLE_CHOICE = "multiple_choice"
    NUMBER = "number"
    OPINION_SCALE = "opinion_scale"
    PAYMENT = "payment"
    PHONE_NUMBER = "phone_number"
    NPS = "nps"
    PICTURE_CHOICE = "picture_choice"
    RATING = "rating"
    SHORT_TEXT = "short_text"
    STATEMENT = "statement"
    WEBSITE = "website"
    YES_NO = "yes_no"
    RANKING = "ranking"


class ResponseType(str, Enum):
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


class AttachmentProperties(BaseModel):
    description: Optional[str]


class Attachment(BaseModel):
    type: Optional[str]
    href: Optional[str]
    scale: Optional[float]
    properties: Optional[AttachmentProperties] = AttachmentProperties()


class Choice(BaseModel):
    ref: Optional[str]
    label: Optional[str]
    attachment: Optional[Attachment]


class AnswerField(BaseModel):
    id: str
    ref: Optional[str]
    type: Optional[QuestionFieldType]


class PaymentAnswer(BaseModel):
    amount: Optional[str]
    last4: Optional[str]
    name: Optional[str]


class ChoiceAnswer(BaseModel):
    label: Optional[str]
    other: Optional[str]


class ChoicesAnswer(BaseModel):
    labels: Optional[List[str]]
    other: Optional[str]


class StandardFormSettingsDto(BaseModel):
    """
    Data transfer object for standard form settings.
    """

    embed_url: Optional[str]
    provider: Optional[str]
    language: Optional[str]
    is_public: Optional[bool]
    is_trial: Optional[bool]
    response_data_owner_fields: Optional[List[str]]
    screens: Optional[Dict[str, List[Dict[str, Any]]]]


class StandardQuestionPropertyDto(BaseModel):
    description: Optional[str]
    choices: Optional[List[Choice]]
    questions: Optional[List["StandardFormQuestionDto"]]
    allow_multiple_selection: Optional[bool]
    allow_other_choice: Optional[bool]
    hide_marks: Optional[bool]
    button_text: Optional[str]
    steps: Optional[int]
    shape: Optional[str]
    labels: Optional[Dict[str, str]]
    start_at_one: Optional[bool]
    structure: Optional[str]
    separator: Optional[str]


class StandardQuestionValidationDto(BaseModel):
    required: Optional[bool]
    max_length: Optional[int]
    min_value: Optional[float]
    max_value: Optional[float]


class StandardFormAnswerDto(BaseModel):
    field: AnswerField
    type: Optional[ResponseType]
    text: Optional[str]
    choice: Optional[ChoiceAnswer]
    choices: Optional[ChoicesAnswer]
    number: Optional[int]
    boolean: Optional[bool]
    email: Optional[str]
    date: Optional[str]
    url: Optional[str]
    file_url: Optional[str]
    payment: Optional[PaymentAnswer]
    phone_number: Optional[str]


class StandardFormQuestionDto(BaseModel):
    """
    Data transfer object for questions in a standard form.
    """

    id: Optional[str]
    ref: Optional[str]
    title: Optional[str]
    description: Optional[str]
    type: Optional[QuestionFieldType]
    properties: Optional[StandardQuestionPropertyDto] = StandardQuestionPropertyDto()
    validations: Optional[StandardQuestionValidationDto]
    attachment: Optional[Attachment] = None


StandardQuestionPropertyDto.update_forward_refs()


class StandardFormDto(BaseModel):
    form_id: Optional[str]
    type: Optional[str]
    title: Optional[str]
    description: Optional[str]
    questions: Optional[List[StandardFormQuestionDto]]
    settings: Optional[StandardFormSettingsDto]
    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]
    published_at: Optional[dt.datetime]


class StandardFormResponseDto(BaseModel):
    """
    Data transfer object for a standard form response.
    """

    response_id: Optional[str]
    form_id: Optional[str]
    provider: Optional[str]
    respondent_email: Optional[str]
    answers: Optional[List[StandardFormAnswerDto]]
    created_at: Optional[dt.datetime]
    updated_at: Optional[dt.datetime]
    published_at: Optional[dt.datetime]
