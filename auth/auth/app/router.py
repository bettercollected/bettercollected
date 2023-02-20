"""Application configuration - root APIRouter.

Defines all FastAPI application endpoints.

Resources:
    1. https://fastapi.tiangolo.com/tutorial/bigger-applications

"""
from typing import Type

from classy_fastapi import Routable
from fastapi import APIRouter

root_api_router = APIRouter(prefix="/api")


# Decorator for automatically inserting routes defined in routable class
def router(*args, prefix=None, **kwargs):
    def decorator(cls: Type[Routable]):
        result = cls(*args, prefix=prefix, **kwargs)
        root_api_router.include_router(result.router)
        return result

    return decorator
