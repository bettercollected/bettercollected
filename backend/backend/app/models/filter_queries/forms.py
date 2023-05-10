from typing import Optional

from fastapi import Depends
from pydantic import BaseModel

from backend.app.models.filter_queries.sort import SortRequest


class FormsFilterQuery(BaseModel):
    form_id: Optional[str]


def add_sort_query_params(default_value=None):
    def decorator(func):
        async def wrapper(*args, sort: SortRequest = Depends(), **kwargs):
            return await func(*args, sort=sort, **kwargs)

        return wrapper

    return decorator
