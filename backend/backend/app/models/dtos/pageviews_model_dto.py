from pydantic import BaseModel
from typing import List


class PageDataModel(BaseModel):
    x: str
    y: int


class PageViewModel(BaseModel):
    pageviews: List[PageDataModel]
    sessions: List[PageDataModel]
