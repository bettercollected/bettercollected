import enum
from enum import Enum
from typing import Optional, List, Any, Dict

from pydantic import BaseModel


class TypeFormLink(BaseModel):
    display: Optional[str] = None


class TypeFormSelfHref(BaseModel):
    href: Optional[str] = None


class TypeFormSettings(BaseModel):
    is_public: Optional[bool]


JsonObject = Dict[str, Any]


class FieldType(str, Enum):
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
    attachment: Optional[Attachment] = Attachment()


# TypeFormField = ForwardRef('TypeFormField')


class FieldProperties(BaseModel):
    description: Optional[str]
    choices: Optional[List[Choice]] = []
    fields: Optional[List['TypeFormField']] = []
    allow_multiple_selection: Optional[bool]
    randomize: Optional[bool]
    allow_other_choice: Optional[bool]
    vertical_alignment: Optional[bool]
    supersized: Optional[bool]
    show_labels: Optional[bool]
    alphabetical_order: Optional[bool]
    hide_marks: Optional[bool]
    button_text: Optional[str]
    steps: Optional[int]
    shape: Optional[str]
    labels: Optional[Dict[str, str]]
    start_at_one: Optional[bool]
    structure: Optional[str]
    separator: Optional[str]


class Validation(BaseModel):
    required: Optional[bool]
    max_length: Optional[int]
    min_value: Optional[float]
    max_value: Optional[float]


class TypeFormField(BaseModel):
    id: Optional[str]
    ref: Optional[str]
    title: Optional[str]
    type: Optional[FieldType]
    properties: Optional[FieldProperties] = FieldProperties()
    validations: Optional[Validation] = Validation()
    attachment: Optional[Attachment] = Attachment()


FieldProperties.update_forward_refs()


class TypeFormDto(BaseModel):
    id: str
    type: Optional[str]
    title: str
    last_updated_at: Optional[str]
    created_at: Optional[str]
    settings: Optional[TypeFormSettings] = TypeFormSettings()
    _links: Optional[TypeFormLink]
    theme: Optional[JsonObject]
    self: Optional[TypeFormSelfHref] = TypeFormSelfHref()
    fields: Optional[List[TypeFormField]]
    hidden: Optional[List[str]]
    language: Optional[str]
    variables: Optional[JsonObject]


class ResponseType(str, enum.Enum):
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


class AnswerField(BaseModel):
    id: str
    ref: Optional[str]
    type: Optional[FieldType]


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


class Answer(BaseModel):
    field: AnswerField
    type: Optional[ResponseType]
    text: Optional[str]
    choice: Optional[ChoiceAnswer] = ChoiceAnswer()
    choices: Optional[ChoicesAnswer] = ChoicesAnswer()
    number: Optional[int]
    boolean: Optional[bool]
    email: Optional[str]
    date: Optional[str]
    url: Optional[str]
    file_url: Optional[str]
    payment: Optional[PaymentAnswer] = PaymentAnswer()
    phone_number: Optional[str]


class TypeFormResponse(BaseModel):
    response_id: str
    landed_at: Optional[str]
    submitted_at: Optional[str]
    hidden: Optional[JsonObject]
    calculated: Optional[JsonObject]
    answers: Optional[List[Answer]]
