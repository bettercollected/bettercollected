# import datetime as dt
# import enum
# from enum import Enum
# from typing import Any, Dict, List, Optional
#
# from pydantic import BaseModel
#
#
# class EmbedProvider(str, enum.Enum):
#     YOUTUBE = 'youtube'
#     VIEMO = 'vimeo'
#     NO_EMBED = 'no_embed'
#
#
# class StandardFormFieldType(str, Enum):
#     ADDRESS = "address"
#     CONTACT_INFO = "contact_info"
#     DATE = "date"
#     DROPDOWN = "dropdown"
#     EMAIL = "email"
#     MATRIX = "matrix"
#     FILE_UPLOAD = "file_upload"
#     GROUP = "group"
#     GRID = "grid"
#     LEGAL = "legal"
#     LONG_TEXT = "long_text"
#     MULTIPLE_CHOICE = "multiple_choice"
#     NUMBER = "number"
#     OPINION_SCALE = "opinion_scale"
#     PAYMENT = "payment"
#     PHONE_NUMBER = "phone_number"
#     NPS = "nps"
#     PICTURE_CHOICE = "picture_choice"
#     RATING = "rating"
#     SHORT_TEXT = "short_text"
#     STATEMENT = "statement"
#     WEBSITE = "website"
#     YES_NO = "yes_no"
#     RANKING = "ranking"
#
#
# class StandardResponseType(str, Enum):
#     TEXT = "text"
#     CHOICE = "choice"
#     CHOICES = "choices"
#     NUMBER = "number"
#     BOOLEAN = "boolean"
#     MATRIX = "matrix"
#     EMAIL = "email"
#     DATE = "date"
#     URL = "url"
#     PHONE_NUMBER = "phone_number"
#     FILE_URL = "file_url"
#     PAYMENT = "payment"
#
#
# class StandardAttachmentProperties(BaseModel):
#     description: Optional[str]
#
#
# class StandardFieldAttachment(BaseModel):
#     type: Optional[str]
#     href: Optional[str]
#     scale: Optional[float]
#     properties: Optional[StandardAttachmentProperties] = StandardAttachmentProperties()
#
#
# class StandardChoice(BaseModel):
#     ref: Optional[str]
#     label: Optional[str]
#     attachment: Optional[StandardFieldAttachment]
#
#
# class StandardAnswerField(BaseModel):
#     id: str
#     ref: Optional[str]
#     type: Optional[StandardFormFieldType]
#
#
# class StandardPaymentAnswer(BaseModel):
#     amount: Optional[str]
#     last4: Optional[str]
#     name: Optional[str]
#
#
# class StandardChoiceAnswer(BaseModel):
#     label: Optional[str]
#     other: Optional[str]
#
#
# class StandardChoicesAnswer(BaseModel):
#     labels: Optional[List[str]]
#     other: Optional[str]
#
#
# class StandardFormSettings(BaseModel):
#     """
#     Data transfer object for standard form settings.
#     """
#
#     embed_url: Optional[str]
#     provider: Optional[str]
#     language: Optional[str]
#     is_public: Optional[bool]
#     is_trial: Optional[bool]
#     response_data_owner_fields: Optional[List[str]]
#     screens: Optional[Dict[str, List[Dict[str, Any]]]]
#
#
# class StandardFieldPropertyDto(BaseModel):
#     description: Optional[str]
#     choices: Optional[List[StandardChoice]]
#     fields: Optional[List["StandardFormField"]]
#     allow_multiple_selection: Optional[bool]
#     allow_other_choice: Optional[bool]
#     hide_marks: Optional[bool]
#     button_text: Optional[str]
#     steps: Optional[int]
#     shape: Optional[str]
#     labels: Optional[Dict[str, str]]
#     start_at_one: Optional[bool]
#     structure: Optional[str]
#     separator: Optional[str]
#
#
# class StandardFieldValidations(BaseModel):
#     required: Optional[bool]
#     max_length: Optional[int]
#     min_value: Optional[float]
#     max_value: Optional[float]
#
#
# class StandardFormAnswerDto(BaseModel):
#     field: StandardAnswerField
#     type: Optional[StandardResponseType]
#     text: Optional[str]
#     choice: Optional[StandardChoiceAnswer]
#     choices: Optional[StandardChoicesAnswer]
#     number: Optional[int]
#     boolean: Optional[bool]
#     email: Optional[str]
#     date: Optional[str]
#     url: Optional[str]
#     file_url: Optional[str]
#     payment: Optional[StandardPaymentAnswer]
#     phone_number: Optional[str]
#
#
# class StandardFormField(BaseModel):
#     """
#     Data transfer object for Fields in a standard form.
#     """
#
#     id: Optional[str]
#     ref: Optional[str]
#     title: Optional[str]
#     description: Optional[str]
#     type: Optional[StandardFormFieldType]
#     properties: Optional[StandardFieldPropertyDto] = StandardFieldPropertyDto()
#     validations: Optional[StandardFieldValidations]
#     attachment: Optional[StandardFieldAttachment] = None
#
#
# StandardFieldPropertyDto.update_forward_refs()
#
#
# class StandardForm(BaseModel):
#     form_id: Optional[str]
#     type: Optional[str]
#     title: Optional[str]
#     description: Optional[str]
#     fields: Optional[List[StandardFormField]]
#     settings: Optional[StandardFormSettings]
#     created_at: Optional[dt.datetime]
#     updated_at: Optional[dt.datetime]
#     published_at: Optional[dt.datetime]
#
#
# class StandardFormResponseDto(BaseModel):
#     """
#     Data transfer object for a standard form response.
#     """
#
#     response_id: Optional[str]
#     form_id: Optional[str]
#     provider: Optional[str]
#     respondent_email: Optional[str]
#     answers: Optional[List[StandardFormAnswerDto]]
#     created_at: Optional[dt.datetime]
#     updated_at: Optional[dt.datetime]
#     published_at: Optional[dt.datetime]

import enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SettingsPatchDto(BaseModel):
    pinned: Optional[bool]
    customUrl: Optional[str]
    private: Optional[bool] = False
    responseDataOwnerField: Optional[str]


class StandardFormSettingDto(SettingsPatchDto):
    embedUrl: Optional[str]
    provider: Optional[str]
    private: Optional[bool] = False
    roles: Optional[List[str]]
    # If responses are set to editable then it can be used for tracking responses
    is_response_editable: Optional[bool]
    # State whether the form is accepting new responses
    is_closed: Optional[bool]


class StandardQuestionDto(BaseModel):
    type: Optional[str]
    options: Optional[List[Any]]


class StandardProperties(BaseModel):
    description: Optional[str]


class EmbedProvider(str, enum.Enum):
    YOUTUBE = 'youtube'
    VIEMO = 'vimeo'
    NO_EMBED = 'no_embed'


class StandardAttachment(BaseModel):
    href: Optional[str]
    type: Optional[str]
    embed_provider: Optional[EmbedProvider]
    properties: Optional[StandardProperties]


class StandardFormQuestionDto(BaseModel):
    questionId: Optional[str]
    formId: Optional[str]
    title: Optional[str]
    description: Optional[str]
    type: Optional[Any]
    required: Optional[bool]
    isMediaContent: Optional[bool]
    mediaContent: Optional[bool]
    isGroupQuestion: Optional[bool]
    groupQuestion: Optional[Any]
    answer: Optional[Any]

    attachment: Optional[StandardAttachment]


class StandardFormDto(BaseModel):
    formId: Optional[str]
    title: Optional[str]
    description: Optional[str]
    settings: Optional[StandardFormSettingDto] = StandardFormSettingDto()
    questions: Optional[List[StandardFormQuestionDto]]
    createdTime: Optional[str]
    modifiedTime: Optional[str]


class StandardFormResponseAnswerDto(BaseModel):
    questionId: Optional[str]
    answer: Optional[Any]


class StandardFormResponseDto(BaseModel):
    responseId: Optional[str]
    formId: Optional[str]
    formTitle: Optional[str]
    formCustomUrl: Optional[str]
    provider: Optional[str]
    dataOwnerIdentifierType: Optional[str]
    dataOwnerIdentifier: Optional[str]
    responses: Optional[Dict[str, StandardFormResponseAnswerDto]]
    createdAt: Optional[str]
    updatedAt: Optional[str]


class StandardFormResponseTransformerDto(StandardFormDto):
    responseId: Optional[str]
    provider: Optional[str]
    dataOwnerIdentifierType: Optional[str]
    dataOwnerIdentifier: Optional[str]
    responseCreatedAt: Optional[str]
    responseUpdatedAt: Optional[str]
