"""Application configuration - root APIRouter.

Defines all FastAPI application endpoints.

Resources:
    1. https://fastapi.tiangolo.com/tutorial/bigger-applications

"""

from fastapi import APIRouter
from typing import Type

from classy_fastapi import Routable

from backend.app.controllers.plugin_proxy import PluginProxy
from backend.config import settings
from common.base.plugin import register_plugin_class

root_api_router = APIRouter(prefix=settings.api_settings.ROOT_PATH)

plugin_proxy_router_tags = ["Form Provider Plugin Proxy"]
register_plugin_class(
    router=root_api_router, route=PluginProxy(), tags=plugin_proxy_router_tags
)


# Decorator for automatically inserting routes defined in routable class
def router(prefix=None, tags=None, **kwargs):
    def decorator(cls: Type[Routable]):
        result = cls(prefix=prefix, tags=tags, **kwargs)
        root_api_router.include_router(result.router)
        return result

    return decorator
