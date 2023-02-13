# flake8: noqa
from abc import abstractmethod
from http import HTTPStatus
from typing import List, Optional, Protocol
from constants.plugin_routes import (
    PLUGIN_ROUTE_AUTHORIZE,
    PLUGIN_ROUTE_CALLBACK,
    PLUGIN_ROUTE_GET_FORM,
    PLUGIN_ROUTE_IMPORT_FORM,
    PLUGIN_ROUTE_LIST_FORMS,
    PLUGIN_ROUTE_REVOKE,
)

from starlette.requests import Request

from enums.http_methods import HTTPMethods
from utils.router import CustomAPIRouter


class BasePluginRoute(Protocol):
    """
    Base Plugin Route Interface

    Defines `abstractmethods` that other form provider implements.
    """

    @abstractmethod
    async def authorize(self, email: str, request: Request):
        raise NotImplementedError

    @abstractmethod
    async def callback(self, request: Request):
        raise NotImplementedError

    @abstractmethod
    async def revoke(self, email: str):
        raise NotImplementedError

    @abstractmethod
    async def list_forms(self, email: str):
        raise NotImplementedError

    @abstractmethod
    async def get_form(self, form_id: str, email: str):
        raise NotImplementedError

    @abstractmethod
    async def import_form(
        self, form_id: str, email: str, data_owner_field: Optional[str] = None
    ):
        raise NotImplementedError


def register_plugin_class(
    router: CustomAPIRouter, route: BasePluginRoute, tags: List[str]
):
    """Registers plugin class with required endpoints and method call.

    When implementing the `BasePluginRoute` interface, add the initialized
    class based router in the `include_router` as:

    ```
    register_plugin_class(
        router=CustomAPIRouter(prefix="/google"),
        route=GoogleRouter,
        tags=["Google API"]
    )
    ```

    Args:
        router (CustomAPIRouter): An instance of `CustomAPIRouter`.
        route (BasePluginRoute): An instance of `BasePluginRoute`.
        tags (List[str]): Route tags.
    """

    # GET: Authorize Endpoint
    router.add_api_route(
        PLUGIN_ROUTE_AUTHORIZE,
        endpoint=route.authorize,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
    )

    # GET: Callback Endpoint
    router.add_api_route(
        PLUGIN_ROUTE_CALLBACK,
        endpoint=route.callback,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
    )

    # POST: Revoke Endpoint
    router.add_api_route(
        PLUGIN_ROUTE_REVOKE,
        endpoint=route.revoke,
        status_code=HTTPStatus.ACCEPTED,
        methods=[HTTPMethods.POST],
        tags=tags,
    )

    # GET: List Forms from the provider
    router.add_api_route(
        PLUGIN_ROUTE_LIST_FORMS,
        endpoint=route.list_forms,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
    )

    # GET: Get Single Form from the provider
    router.add_api_route(
        PLUGIN_ROUTE_GET_FORM,
        endpoint=route.get_form,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
    )

    # POST: Import form from the provider to our platform
    router.add_api_route(
        PLUGIN_ROUTE_IMPORT_FORM,
        endpoint=route.import_form,
        status_code=HTTPStatus.CREATED,
        methods=[HTTPMethods.POST],
        tags=tags,
    )
