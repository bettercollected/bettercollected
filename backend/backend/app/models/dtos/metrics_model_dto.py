from pydantic import BaseModel
from typing import List


class MetricDataModel(BaseModel):
    x: str | None
    y: int


class MetricResponseModel(BaseModel):
    __root__: List[MetricDataModel]
