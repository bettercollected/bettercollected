from typing import Any, List, Optional

from pydantic import BaseModel


class GoogleChoiceQuestionDto(BaseModel):
    type: Optional[str]
    options: Optional[List[Any]]


class GoogleQuestionDto(BaseModel):
    questionId: Optional[str]
    required: Optional[bool]
    textQuestion: Optional[Any]
    choiceQuestion: Optional[GoogleChoiceQuestionDto]
    fileUploadQuestion: Optional[Any]
    scaleQuestion: Optional[Any]
    dateQuestion: Optional[Any]
    timeQuestion: Optional[Any]


class GoogleFormItemQuestionDto(BaseModel):
    question: Optional[GoogleQuestionDto]


class GoogleFormQuestionGroupItem(BaseModel):
    questions: List[Any]
    grid: Any


class GoogleInfoDto(BaseModel):
    title: Optional[str]
    description: Optional[str]
    documentTitle: Optional[str]


class GoogleFormItemsDto(BaseModel):
    itemId: Optional[str]
    title: Optional[str]
    imageItem: Optional[Any]
    videoItem: Optional[Any]
    description: Optional[str]
    pageBreakItem: Optional[Any]
    questionItem: Optional[GoogleFormItemQuestionDto]
    questionGroupItem: Optional[GoogleFormQuestionGroupItem]


class GoogleFormDto(BaseModel):
    formId: Optional[str]
    info: Optional[GoogleInfoDto]
    revisionId: Optional[str]
    responderUri: Optional[str]
    items: Optional[List[GoogleFormItemsDto]]
    provider: Optional[str]
