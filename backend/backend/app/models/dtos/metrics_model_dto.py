from pydantic import BaseModel, RootModel
from typing import List


class MetricDataModel(BaseModel):
    x: str | None
    y: int


class MetricResponseModel(RootModel):
    root: List[MetricDataModel]
