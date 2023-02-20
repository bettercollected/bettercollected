"""Application configuration - root APIRouter.

Defines all FastAPI application endpoints.

Resources:
    1. https://fastapi.tiangolo.com/tutorial/bigger-applications

"""
from typing import Type

from classy_fastapi import Routable
from fastapi import APIRouter

from common.utils.router import CustomAPIRouter
from typeform.app.controllers import form_router
from typeform.app.controllers.auth_router import AuthRoutes

root_api_router = CustomAPIRouter(prefix="")
root_api_router.include_router(AuthRoutes().router, prefix="/typeform")
root_api_router.include_router(form_router.router)


# Decorator for automatically inserting routes defined in routable class
def router(*args, prefix=None, **kwargs):
    def decorator(cls: Type[Routable]):
        result = cls(*args, prefix=prefix, **kwargs)
        root_api_router.include_router(result.router)
        return result

    return decorator
