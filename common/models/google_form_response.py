from typing import Any, Optional

from pydantic import BaseModel


class GoogleFormResponseDto(BaseModel):
    responseId: Optional[str]
    createTime: Optional[str]
    lastSubmittedTime: Optional[str]
    answers: Optional[Any]
    respondentEmail: Optional[str]
