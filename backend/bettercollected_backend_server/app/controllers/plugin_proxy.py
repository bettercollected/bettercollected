"""Plugin proxy controller implementation."""
import logging
from http import HTTPStatus

from common.constants.plugin_routes import (
    PLUGIN_ROUTE_AUTHORIZE,
    PLUGIN_ROUTE_CALLBACK,
    PLUGIN_ROUTE_GET_FORM,
    PLUGIN_ROUTE_IMPORT_FORM,
    PLUGIN_ROUTE_LIST_FORMS,
    PLUGIN_ROUTE_REVOKE,
)
from common.utils.cbv import cbv
from common.utils.router import CustomAPIRouter

router = CustomAPIRouter(prefix="")
log = logging.getLogger(__name__)


@cbv(router=router)
class PluginProxy:
    @router.get(
        PLUGIN_ROUTE_AUTHORIZE,
        status_code=HTTPStatus.OK,
        # Decorator options:
        # https://fastapi.tiangolo.com/tutorial/path-operation-configuration/
    )
    async def authorize(self):
        """Define plugin proxy authorize endpoint."""
        # Implement endpoint logic here.
        return {"hello": "world"}

    @router.get(
        PLUGIN_ROUTE_CALLBACK,
        status_code=HTTPStatus.OK,
        # Decorator options:
        # https://fastapi.tiangolo.com/tutorial/path-operation-configuration/
    )
    async def callback(self):
        """Define plugin proxy callback endpoint."""
        # Implement endpoint logic here.
        return {"hello": "world"}

    @router.post(
        PLUGIN_ROUTE_REVOKE,
        status_code=HTTPStatus.ACCEPTED,
        # Decorator options:
        # https://fastapi.tiangolo.com/tutorial/path-operation-configuration/
    )
    async def revoke(self):
        """Define plugin proxy revoke endpoint."""
        # Implement endpoint logic here.
        return {"hello": "world"}

    @router.get(
        PLUGIN_ROUTE_LIST_FORMS,
        status_code=HTTPStatus.OK,
        # Decorator options:
        # https://fastapi.tiangolo.com/tutorial/path-operation-configuration/
    )
    async def list_forms(self):
        """Define plugin proxy list_forms endpoint."""
        # Implement endpoint logic here.
        return {"hello": "world"}

    @router.get(
        PLUGIN_ROUTE_GET_FORM,
        status_code=HTTPStatus.OK,
        # Decorator options:
        # https://fastapi.tiangolo.com/tutorial/path-operation-configuration/
    )
    async def get_form(self):
        """Define plugin proxy get_form endpoint."""
        # Implement endpoint logic here.
        return {"hello": "world"}

    @router.post(
        PLUGIN_ROUTE_IMPORT_FORM,
        status_code=HTTPStatus.CREATED,
        # Decorator options:
        # https://fastapi.tiangolo.com/tutorial/path-operation-configuration/
    )
    async def import_form(self):
        """Define plugin proxy import_form endpoint."""
        # Implement endpoint logic here.
        return {"hello": "world"}
