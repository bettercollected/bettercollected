from typing import Any, List, Optional

from pydantic import BaseModel


class GoogleChoiceQuestionDto(BaseModel):
    """Data transfer object for Google Forms choice questions."""

    type: Optional[str] = None
    options: Optional[List[Any]] = None


class GoogleQuestionDto(BaseModel):
    """Data transfer object for Google Forms questions."""

    questionId: Optional[str] = None
    required: Optional[bool] = None
    textQuestion: Optional[Any] = None
    choiceQuestion: Optional[GoogleChoiceQuestionDto] = None
    fileUploadQuestion: Optional[Any] = None
    scaleQuestion: Optional[Any] = None
    dateQuestion: Optional[Any] = None
    timeQuestion: Optional[Any] = None


class GoogleMediaProperties(BaseModel):
    width: Optional[int] = None


class GoogleImage(BaseModel):
    contentUri: Optional[str] = None
    properties: Optional[GoogleMediaProperties] = GoogleMediaProperties()


class GoogleFormItemQuestionDto(BaseModel):
    """Data transfer object for Google Forms question items."""

    question: Optional[GoogleQuestionDto] = None
    image: Optional[GoogleImage] = None


class GoogleOptionValue(BaseModel):
    value: str


class GoogleColumns(BaseModel):
    type: Optional[str] = None
    options: Optional[List[GoogleOptionValue]] = []


class GoogleGrid(BaseModel):
    columns: Optional[GoogleColumns] = GoogleColumns()


class GoogleRowQuestion(BaseModel):
    title: Optional[str] = None


class GoogleGroupQuestion(BaseModel):
    questionId: Optional[str] = None
    required: Optional[bool] = None
    rowQuestion: Optional[GoogleRowQuestion] = GoogleRowQuestion()


class GoogleFormQuestionGroupItem(BaseModel):
    """Data transfer object for Google Forms question group items."""

    questions: List[GoogleGroupQuestion] = []
    grid: Optional[GoogleGrid] = GoogleGrid()
    image: Optional[GoogleImage] = None


class GoogleInfoDto(BaseModel):
    """Data transfer object for general information about a Google Form."""

    title: Optional[str] = None
    description: Optional[str] = None
    documentTitle: Optional[str] = None


class GoogleImageItem(BaseModel):
    image: Optional[GoogleImage] = GoogleImage()


class GoogleVideo(BaseModel):
    youtubeUri: Optional[str] = None
    properties: Optional[GoogleMediaProperties] = GoogleMediaProperties()


class GoogleVideoItem(BaseModel):
    video: Optional[GoogleVideo] = GoogleVideo()


class GoogleFormItemsDto(BaseModel):
    """Data transfer object for items in a Google Form."""

    itemId: Optional[str] = None
    title: Optional[str] = None
    imageItem: Optional[GoogleImageItem] = None
    videoItem: Optional[GoogleVideoItem] = None
    description: Optional[str] = None
    pageBreakItem: Optional[Any] = None
    questionItem: Optional[GoogleFormItemQuestionDto] = None
    questionGroupItem: Optional[GoogleFormQuestionGroupItem] = None
    textItem: Optional[Any] = None


class GoogleFormDto(BaseModel):
    """Data transfer object for a Google Form."""

    formId: Optional[str] = None
    info: Optional[GoogleInfoDto] = None
    revisionId: Optional[str] = None
    responderUri: Optional[str] = None
    items: Optional[List[GoogleFormItemsDto]] = []
    provider: Optional[str] = None
