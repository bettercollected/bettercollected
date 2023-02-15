# flake8: noqa
from abc import abstractmethod
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Protocol

from fastapi import Body

from constants.plugin_routes import (
    PLUGIN_ROUTE_AUTHORIZE,
    PLUGIN_ROUTE_CALLBACK,
    PLUGIN_ROUTE_FORM,
    PLUGIN_ROUTE_FORMS,
    PLUGIN_ROUTE_FORM_RESPONSE,
    PLUGIN_ROUTE_FORM_RESPONSES,
    PLUGIN_ROUTE_IMPORT_FORM,
    PLUGIN_ROUTE_REVOKE,
)

from starlette.requests import Request

from enums.http_methods import HTTPMethods
from utils.router import CustomAPIRouter

from enums.form_provider import FormProvider


class BasePluginRoute(Protocol):
    """
    Base Plugin Route Interface

    Defines `abstractmethods` that other form provider implements.
    """

    @abstractmethod
    async def authorize(
        self, request: Request, email: str, provider: str | FormProvider
    ):
        raise NotImplementedError

    @abstractmethod
    async def callback(self, request: Request, provider: str | FormProvider):
        raise NotImplementedError

    @abstractmethod
    async def revoke(self, email: str, provider: str | FormProvider):
        raise NotImplementedError

    @abstractmethod
    async def list_forms(self, email: str, provider: str | FormProvider):
        raise NotImplementedError

    @abstractmethod
    async def get_form(self, form_id: str, email: str, provider: str | FormProvider):
        raise NotImplementedError

    @abstractmethod
    async def import_form(
        self,
        form_id: str,
        email: str,
        provider: str | FormProvider,
        data_owner_field: Optional[str] = None,
    ):
        raise NotImplementedError

    @abstractmethod
    async def create_form(
        self,
        email: str,
        provider: str | FormProvider,
        request_body: Dict[str, Any] = Body(...),
    ):
        raise NotImplementedError

    @abstractmethod
    async def update_form(
        self,
        form_id: str,
        email: str,
        provider: str | FormProvider,
        request_body: Dict[str, Any] = Body(...),
    ):
        raise NotImplementedError

    @abstractmethod
    async def delete_form(self, form_id: str, email: str, provider: str | FormProvider):
        raise NotImplementedError

    @abstractmethod
    async def list_form_responses(
        self, form_id: str, email: str, provider: str | FormProvider
    ):
        raise NotImplementedError

    @abstractmethod
    async def get_form_response(
        self, form_id: str, email: str, response_id: str, provider: str | FormProvider
    ):
        raise NotImplementedError

    @abstractmethod
    async def delete_form_response(
        self, form_id: str, email: str, response_id: str, provider: str | FormProvider
    ):
        raise NotImplementedError


def register_plugin_class(
    router: CustomAPIRouter, route: BasePluginRoute, tags: List[str]
):
    """Registers plugin class with required endpoints and method call.

    When implementing the `BasePluginRoute` interface, add the initialized
    class based router in the `include_router` as:

    ```
    google_router = CustomAPIRouter(prefix=settings.api_settings.root_path + "")
    google_tags = ["Google API"]
    register_plugin_class(
        router=google_router,
        route=GoogleRouter(),
        tags=google_tags,
    )

    server.include_router(google_router, tags=google_tags)
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
        PLUGIN_ROUTE_FORMS,
        endpoint=route.list_forms,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
    )

    # GET: Get Single Form from the provider
    router.add_api_route(
        PLUGIN_ROUTE_FORM,
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

    # POST: Creates form in the provider and our platform
    router.add_api_route(
        PLUGIN_ROUTE_FORMS,
        endpoint=route.create_form,
        status_code=HTTPStatus.CREATED,
        methods=[HTTPMethods.POST],
        tags=tags,
    )

    # PATCH: Updates form in the provider and our platform
    router.add_api_route(
        PLUGIN_ROUTE_FORM,
        endpoint=route.update_form,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.PATCH],
        tags=tags,
    )

    # DELETE: Delete form from the provider and our platform
    router.add_api_route(
        PLUGIN_ROUTE_FORM,
        endpoint=route.delete_form,
        status_code=HTTPStatus.NO_CONTENT,
        methods=[HTTPMethods.DELETE],
        tags=tags,
    )

    # GET: List form responses from the provider
    router.add_api_route(
        PLUGIN_ROUTE_FORM_RESPONSES,
        endpoint=route.list_form_responses,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
    )

    # GET: Get Single Form Response from the provider
    router.add_api_route(
        PLUGIN_ROUTE_FORM_RESPONSE,
        endpoint=route.get_form_response,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
    )

    # DELETE: Delete form response from the provider and our platform
    router.add_api_route(
        PLUGIN_ROUTE_FORM_RESPONSE,
        endpoint=route.delete_form_response,
        status_code=HTTPStatus.NO_CONTENT,
        methods=[HTTPMethods.DELETE],
        tags=tags,
    )
