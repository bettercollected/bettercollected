from datetime import datetime
from typing import Generic, Optional, TypeVar, Any

from pydantic import BaseModel
from pydantic.generics import GenericModel

DataT = TypeVar("DataT")
Content = TypeVar("Content")


class PageableModel(BaseModel):
    page: int = 0
    size: int = 15
    total: int = 0
    # sort


class DataModel(BaseModel):
    content: Optional[DataT]
    pageable: Optional[PageableModel] = None


# class ErrorModel(BaseModel):
#     code: Optional[int]
#     error: Optional[str]
#     detail: Optional[str]

# TODO Remove
class GenericResponseModel(GenericModel, Generic[Content]):
    apiVersion: str = "v1"
    payload: Optional[DataModel | Content] = None
    # error: Optional[ErrorModel] = None
    timestamp: datetime = datetime.now().isoformat()

    # @validator('error', always=True)
    # def check_consistency(cls, v, values):
    #     if v is not None and values['payload'] is not None:
    #         raise ValueError('must not provide both payload and error')
    #     if v is None and values.get('payload') is None:
    #         raise ValueError('must provide payload or error')
    #     return v


def generate_generic_pageable_response(data):
    payload: DataModel = DataModel()
    pageable: PageableModel = PageableModel()
    if isinstance(data, list):
        pageable.total = len(data)

    payload.pageable = pageable
    payload.content = data
    return payload
