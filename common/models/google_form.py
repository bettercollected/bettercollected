from typing import Any, List, Optional

from pydantic import BaseModel


class GoogleChoiceQuestionDto(BaseModel):
    """
    Data transfer object for Google Forms choice questions.
    """

    type: Optional[str]
    options: Optional[List[Any]]


class GoogleQuestionDto(BaseModel):
    """
    Data transfer object for Google Forms questions.
    """

    questionId: Optional[str]
    required: Optional[bool]
    textQuestion: Optional[Any]
    choiceQuestion: Optional[GoogleChoiceQuestionDto]
    fileUploadQuestion: Optional[Any]
    scaleQuestion: Optional[Any]
    dateQuestion: Optional[Any]
    timeQuestion: Optional[Any]


class GoogleFormItemQuestionDto(BaseModel):
    """
    Data transfer object for Google Forms question items.
    """

    question: Optional[GoogleQuestionDto]


class GoogleFormQuestionGroupItem(BaseModel):
    """
    Data transfer object for Google Forms question group items.
    """

    questions: List[Any]
    grid: Any


class GoogleInfoDto(BaseModel):
    """
    Data transfer object for general information about a Google Form.
    """

    title: Optional[str]
    description: Optional[str]
    documentTitle: Optional[str]


class GoogleFormItemsDto(BaseModel):
    """
    Data transfer object for items in a Google Form.
    """

    itemId: Optional[str]
    title: Optional[str]
    imageItem: Optional[Any]
    videoItem: Optional[Any]
    description: Optional[str]
    pageBreakItem: Optional[Any]
    questionItem: Optional[GoogleFormItemQuestionDto]
    questionGroupItem: Optional[GoogleFormQuestionGroupItem]


class GoogleFormDto(BaseModel):
    """
    Data transfer object for a Google Form.
    """

    formId: Optional[str]
    info: Optional[GoogleInfoDto]
    revisionId: Optional[str]
    responderUri: Optional[str]
    items: Optional[List[GoogleFormItemsDto]]
    provider: Optional[str]
