# flake8: noqa
from abc import abstractmethod
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Protocol

from fastapi import Body
from starlette.requests import Request

from common.constants.plugin_routes import (
    PLUGIN_ROUTE_FORM,
    PLUGIN_ROUTE_FORMS,
    PLUGIN_ROUTE_FORM_RESPONSE,
    PLUGIN_ROUTE_FORM_RESPONSES,
    PLUGIN_ROUTE_IMPORT_FORM,
    PLUGIN_ROUTE_IMPORT_FORMS,
    PLUGIN_ROUTE_VERIFY
)
from common.enums.form_provider import FormProvider
from common.enums.http_methods import HTTPMethods
from common.models.user import User
from common.utils.router import CustomAPIRouter


class BasePluginRoute(Protocol):
    """
    Base Plugin Route Interface

    Defines `abstractmethods` that other form provider implements.
    """

    @abstractmethod
    async def list_forms(self, provider: str, request: Request):
        raise NotImplementedError

    @abstractmethod
    async def get_form(
            self, form_id: str, email: str, provider: str | FormProvider, request: Request
    ):
        raise NotImplementedError

    # TODO : Refactor this import form as single form get
    @abstractmethod
    async def import_form(
            self, form_id: str, provider: str | FormProvider, request: Request
    ):
        raise NotImplementedError

    # TODO : Refactor this import form as all forms

    @abstractmethod
    async def import_forms(self, provider: str | FormProvider, request: Request):
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

    @abstractmethod
    async def verify_oauth_token(self, provider: str | FormProvider, request: Request):
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

    # GET: List Forms from the provider
    router.add_api_route(
        PLUGIN_ROUTE_FORMS,
        endpoint=route.list_forms,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
        responses={400: {"message": "Bad Request"}, 401: {"message": "Authorization token is missing."}}
    )

    # GET: Get Single Form from the provider
    router.add_api_route(
        PLUGIN_ROUTE_FORM,
        endpoint=route.get_form,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
        responses={400: {"message": "Bad Request"}, 401: {"message": "Authorization token is missing."},
                   404: {"message": "Not found"},
                   405: {"description": "Method not allowed"}
                   }
    )
    # TODO : Refactor this import form as all forms

    # POST: Import form from the provider to our platform
    router.add_api_route(
        PLUGIN_ROUTE_IMPORT_FORM,
        endpoint=route.import_form,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
        responses={400: {"message": "Bad Request"},
                   404: {"message": "Not found: The resource you are requesting is not available."},
                   401: {"message": "Authorization token is missing."}}
    )
    # TODO : Refactor this import form as all forms

    router.add_api_route(
        PLUGIN_ROUTE_IMPORT_FORMS,
        endpoint=route.import_forms,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
        responses={400: {"message": "Bad Request"},
                   404: {"message": "Not found: The resource you are requesting is not available."},
                   401: {"message": "Authorization token is missing."},
                   405: {"description": "Method not allowed"}
                   }

    )

    # POST: Creates form in the provider and our platform
    router.add_api_route(
        PLUGIN_ROUTE_FORMS,
        endpoint=route.create_form,
        status_code=HTTPStatus.CREATED,
        methods=[HTTPMethods.POST],
        tags=tags,
        responses={400: {"message": "Bad Request"}, 401: {"message": "Authorization token is missing."},
                   404: {"message": "Not found"},
                   405: {"description": "Method not allowed"}
                   }
    )

    # PATCH: Updates form in the provider and our platform
    router.add_api_route(
        PLUGIN_ROUTE_FORM,
        endpoint=route.update_form,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.PATCH],
        tags=tags,
        responses={400: {"message": "Bad Request"}, 401: {"message": "Authorization token is missing."},
                   404: {"message": "Not found"},
                   405: {"description": "Method not allowed"}
                   }
    )

    # DELETE: Delete form from the provider and our platform
    router.add_api_route(
        PLUGIN_ROUTE_FORM,
        endpoint=route.delete_form,
        status_code=HTTPStatus.NO_CONTENT,
        methods=[HTTPMethods.DELETE],
        tags=tags,
        responses={400: {"message": "Bad Request"}, 401: {"message": "Authorization token is missing."},
                   404: {"message": "Not found"},
                   405: {"description": "Method not allowed"}
                   }
    )

    # GET: List form responses from the provider
    router.add_api_route(
        PLUGIN_ROUTE_FORM_RESPONSES,
        endpoint=route.list_form_responses,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
        responses={400: {"message": "Bad Request"}, 401: {"message": "Authorization token is missing."},
                   404: {"message": "Not found"},
                   405: {"description": "Method not allowed"}
                   }
    )

    # GET: Get Single Form Response from the provider
    router.add_api_route(
        PLUGIN_ROUTE_FORM_RESPONSE,
        endpoint=route.get_form_response,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
        responses={400: {"message": "Bad Request"}, 401: {"message": "Authorization token is missing."},
                   404: {"message": "Not found"},
                   405: {"description": "Method not allowed"}
                   }
    )

    # DELETE: Delete form response from the provider and our platform
    router.add_api_route(
        PLUGIN_ROUTE_FORM_RESPONSE,
        endpoint=route.delete_form_response,
        status_code=HTTPStatus.NO_CONTENT,
        methods=[HTTPMethods.DELETE],
        tags=tags,
        responses={400: {"message": "Bad Request"}, 401: {"message": "Authorization token is missing."},
                   404: {"message": "Not found"},
                   405: {"description": "Method not allowed"}
                   }
    )

    # GET: Verify oauth access token
    router.add_api_route(
        PLUGIN_ROUTE_VERIFY,
        endpoint=route.verify_oauth_token,
        status_code=HTTPStatus.OK,
        methods=[HTTPMethods.GET],
        tags=tags,
        responses={400: {"message": "Bad Request"}, 401: {"message": "Authorization token is missing."},
                   404: {"message": "Not found"},
                   405: {"description": "Method not allowed"}
                   }
    )
