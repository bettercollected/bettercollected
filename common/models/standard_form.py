import datetime as dt
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SettingsPatchDto(BaseModel):
    """
    Data transfer object for patching form settings.
    """

    pinned: Optional[bool]
    customUrl: Optional[str]
    responseDataOwnerField: Optional[str]


class StandardFormSettingDto(SettingsPatchDto):
    """
    Data transfer object for standard form settings.
    """

    embedUrl: Optional[str]
    provider: Optional[str]
    roles: Optional[List[str]]


class StandardQuestionDto(BaseModel):
    """
    Data transfer object for standard questions.
    """

    type: Optional[str]
    options: Optional[List[Any]]


class StandardFormQuestionDto(BaseModel):
    """
    Data transfer object for questions in a standard form.
    """

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


class StandardFormDto(BaseModel):
    """
    Data transfer object for a standard form.
    """

    formId: Optional[str]
    title: Optional[str]
    description: Optional[str]
    settings: Optional[StandardFormSettingDto]
    questions: Optional[List[StandardFormQuestionDto]]
    createdTime: Optional[str]
    modifiedTime: Optional[str]


class StandardFormResponseAnswerDto(BaseModel):
    """
    Data transfer object for an answer in a standard form response.
    """

    questionId: Optional[str]
    answer: Optional[Any]


class StandardFormResponseDto(BaseModel):
    """
    Data transfer object for a standard form response.
    """

    responseId: Optional[str]
    formId: Optional[str]
    formTitle: Optional[str]
    formCustomUrl: Optional[str]
    provider: Optional[str]
    dataOwnerIdentifierType: Optional[str]
    dataOwnerIdentifier: Optional[str]
    responses: Optional[Dict[str, StandardFormResponseAnswerDto]]
    createdAt: Optional[dt.datetime]
    updatedAt: Optional[dt.datetime]


class StandardFormResponseTransformerDto(StandardFormDto):
    """
    Data transfer object for transforming a standard form response into a standard form.
    """

    responseId: Optional[str]
    provider: Optional[str]
    dataOwnerIdentifierType: Optional[str]
    dataOwnerIdentifier: Optional[str]
    responseCreatedAt: Optional[dt.datetime]
    responseUpdatedAt: Optional[dt.datetime]
