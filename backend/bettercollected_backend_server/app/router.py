"""Application configuration - root APIRouter.

Defines all FastAPI application endpoints.

Resources:
    1. https://fastapi.tiangolo.com/tutorial/bigger-applications

"""

from bettercollected_backend_server.app.controllers import plugin_proxy
from bettercollected_backend_server.app.controllers import ready
from common.utils.router import CustomAPIRouter

root_api_router = CustomAPIRouter(prefix="")

root_api_router.include_router(ready.router, tags=["Ready"])
root_api_router.include_router(plugin_proxy.router, tags=["Plugin Proxy"])
