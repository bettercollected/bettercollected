from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class GoogleTextAnswerValue(BaseModel):
    value: Optional[str]


class GoogleTextAnswer(BaseModel):
    answers: List[GoogleTextAnswerValue] = []


class GoogleAnswer(BaseModel):
    textAnswers: Optional[GoogleTextAnswer] = GoogleTextAnswer()


class GoogleFormResponseDto(BaseModel):
    """
    Data transfer object for a response to a Google Form.
    """

    responseId: Optional[str]
    createTime: Optional[str]
    lastSubmittedTime: Optional[str]
    answers: Optional[Dict[str, GoogleAnswer]]
    respondentEmail: Optional[str] = None
