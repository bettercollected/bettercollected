from typing import Dict, List, Optional

from pydantic import BaseModel


class GoogleTextAnswerValue(BaseModel):
    value: Optional[str] = None


class GoogleTextAnswer(BaseModel):
    answers: List[GoogleTextAnswerValue] = []


class GoogleAnswer(BaseModel):
    textAnswers: Optional[GoogleTextAnswer] = GoogleTextAnswer()


class GoogleFormResponseDto(BaseModel):
    """Data transfer object for a response to a Google Form."""

    responseId: Optional[str] = None
    createTime: Optional[str] = None
    lastSubmittedTime: Optional[str] = None
    answers: Optional[Dict[str, GoogleAnswer]] = None
    respondentEmail: Optional[str] = None
