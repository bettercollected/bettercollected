import datetime as dt
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SettingsPatchDto(BaseModel):
    pinned: Optional[bool]
    customUrl: Optional[str]
    responseDataOwnerField: Optional[str]


class StandardFormSettingDto(SettingsPatchDto):
    embedUrl: Optional[str]
    provider: Optional[str]
    roles: Optional[List[str]]


class StandardQuestionDto(BaseModel):
    type: Optional[str]
    options: Optional[List[Any]]


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


class StandardFormDto(BaseModel):
    formId: Optional[str]
    title: Optional[str]
    description: Optional[str]
    settings: Optional[StandardFormSettingDto]
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
    createdAt: Optional[dt.datetime]
    updatedAt: Optional[dt.datetime]


class StandardFormResponseTransformerDto(StandardFormDto):
    responseId: Optional[str]
    provider: Optional[str]
    dataOwnerIdentifierType: Optional[str]
    dataOwnerIdentifier: Optional[str]
    responseCreatedAt: Optional[dt.datetime]
    responseUpdatedAt: Optional[dt.datetime]
