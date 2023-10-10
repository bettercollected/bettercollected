import logging
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Type,
    Union,
)

from fastapi import APIRouter, params, routing
from fastapi.datastructures import Default, DefaultPlaceholder
from fastapi.encoders import DictIntStrAny, SetIntStr
from fastapi.openapi.models import Response
from fastapi.routing import APIRoute
from fastapi.utils import generate_unique_id

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import BaseRoute
from starlette.types import ASGIApp

_response_class = Default(JSONResponse)
_generate_unique_id_function = Default(generate_unique_id)


class RequestWithLogger(Request):
    """
    A subclass of Request with a logged request body.

    This class defines an async method body that asynchronously
    streams and concatenates the request body, and logs it if the
    app is in development mode. The _body attribute is used to
    cache the concatenated body so that it is only read from the
    stream once.

    Returns:
    bytes: The request body.
    """

    async def body(self) -> bytes:
        """
        Asynchronously streams and concatenates the request body,
        and logs it if the app is in development mode.

        This method asynchronously streams the request body,
        concatenates the chunks, and stores the result in the `_body`
        attribute. If the app is in development mode, it logs the
        `_body` value. The `_body` attribute is used to cache the
        concatenated body so that it is only read from the stream once.

        Parameters:
            self (RequestWithLogger): The `RequestWithLogger` instance.

        Returns:
            bytes: The request body.
        """
        if not hasattr(self, "_body"):
            chunks = []
            async for chunk in self.stream():
                chunks.append(chunk)
            self._body = b"".join(chunks)

        logging.info(f"Request body : {self._body}")

        return self._body


class CustomAPIRoute(APIRoute):
    """
    A subclass of APIRoute with a logged request and response body.

    This class extends `APIRoute` by defining a `get_route_handler`
    method that wraps the original route handler with a custom handler
    that logs the request and response bodies in development mode. The
    custom handler creates a `RequestWithLogger` instance from the
    request and passes it to the original route handler, and then logs
    the response body before returning it.

    Parameters:
        path (str): The URL path for the route.
        endpoint (Callable): The function that handles the route.
        response_model (Type[Any], optional): The response model for the
            route. Defaults to None.
        status_code (int, optional): The HTTP status code for the route.
            Defaults to None.
        tags (List[Union[str, Enum]], optional): The tags for the route.
            Defaults to None.
        dependencies (Sequence[params.Depends], optional): The dependencies
            for the route. Defaults to None.
        summary (str, optional): The summary for the route. Defaults to None.
        description (str, optional): The description for the route.
            Defaults to None.
        response_description (str, optional): The response description for
            the route. Defaults to "Successful Response".
        responses (Dict[Union[int, str],Dict[str, Any]], optional): The
            responses for the route. Defaults to None.
        deprecated (bool, optional): Whether the route is deprecated.
            Defaults to None.
        name (str, optional): The name for the route. Defaults to None.
        methods (Union[Set[str], List[str]], optional): The HTTP methods
            allowed for the route. Defaults to None.
        operation_id (str, optional): The operation ID for the route.
            Defaults to None.
        response_model_include (Union[SetIntStr, DictIntStrAny], optional):
            The fields to include in the response model. Defaults to None.
        response_model_exclude (Union[SetIntStr, DictIntStrAny], optional):
            The fields to exclude from the response model. Defaults to None.
        response_model_by_alias (bool, optional): Whether to use field aliases
            in the response model. Defaults to True.
        response_model_exclude_unset (bool, optional): Whether to exclude unset
            fields in the response model. Defaults to False.
        response_model_exclude_defaults (bool, optional): Whether to exclude
            fields with default values in the response model. Defaults to False.
        response_model_exclude_none (bool, optional): Whether to exclude fields
            with None values in the response model. Defaults to
            settings.exclude_none_in_all_response_models.
        include_in_schema (bool, optional): Whether to include the route in
            the OpenAPI schema. Defaults to True.
        response_class (Type[Response], optional): The response class for the
            route. Defaults to _response_class.
        dependency_overrides_provider (Any, optional): The dependency overrides
            provider for the route. Defaults to None.
        callbacks (List[BaseRoute], optional): The callbacks for the route.
            Defaults to None.
        openapi_extra (Dict[str, Any], optional): Extra fields to include in
            the OpenAPI schema for the route. Defaults to None.
        generate_unique_id_function (Callable[[APIRoute], str]): A function to
            generate a unique ID for the route. Defaults to _generate_unique_id_function.
    """

    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        response_model: Optional[Type[Any]] = None,
        status_code: Optional[int] = None,
        tags: Optional[List[Union[str, Enum]]] = None,
        dependencies: Optional[Sequence[params.Depends]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "Successful Response",
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        name: Optional[str] = None,
        methods: Optional[Union[Set[str], List[str]]] = None,
        operation_id: Optional[str] = None,
        response_model_include: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_exclude: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none=True,
        include_in_schema: bool = True,
        response_class: Union[Type[Response], DefaultPlaceholder] = _response_class,
        dependency_overrides_provider: Optional[Any] = None,
        callbacks: Optional[List[BaseRoute]] = None,
        openapi_extra: Optional[Dict[str, Any]] = None,
        generate_unique_id_function: Callable[
            [APIRoute], str
        ] = _generate_unique_id_function,
    ):
        super().__init__(
            path,
            endpoint,
            response_model=response_model,
            status_code=status_code,
            tags=tags,
            dependencies=dependencies,
            summary=summary,
            description=description,
            response_description=response_description,
            responses=responses,
            deprecated=deprecated,
            name=name,
            methods=methods,
            operation_id=operation_id,
            response_model_include=response_model_include,
            response_model_exclude=response_model_exclude,
            response_model_by_alias=response_model_by_alias,
            response_model_exclude_unset=response_model_exclude_unset,
            response_model_exclude_defaults=response_model_exclude_defaults,
            response_model_exclude_none=response_model_exclude_none,
            include_in_schema=include_in_schema,
            response_class=response_class,
            dependency_overrides_provider=dependency_overrides_provider,
            callbacks=callbacks,
            openapi_extra=openapi_extra,
            generate_unique_id_function=generate_unique_id_function,
        )

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """
        A wrapper function that wraps the original route handler to
        log request and response bodies.

        Args:
        request (Request): The request object.

        Returns:
        Coroutine[Any, Any, Response]: The response for the request.
        """
        original_route_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            """
            A wrapper function that wraps the original route handler to
            log request and response bodies.

            This function is intended to be used as a route handler for
            FastAPI routes. It wraps the original route handler to log
            request and response bodies. This can be useful for debugging
            and development purposes.

            Args:
            request (Request): The request object.

            Returns:
            Coroutine[Any, Any, Response]: The response for the request.
            """
            request = RequestWithLogger(request.scope, request.receive)
            response = await original_route_handler(request)

            logging.info(
                f"Response body : {response.body if response.__dict__.get('body') else ''}"
            )
            return response

        return handler


# Extend API Router to include custom API Route show that own customization
# can be done that applies to all routes
class CustomAPIRouter(APIRouter):
    """
    A custom router that inherits from FastAPI's APIRouter class.

    This router is a custom implementation of FastAPI's APIRouter
    class that allows the user to specify a prefix that will be
    prepended to the path of all the routes in the router. This can
    be useful for organizing routes in a logical hierarchy and for
    making it easy to change the base URL of all routes in a router.
    """

    def __init__(
        self,
        *,
        prefix: str,
        tags: Optional[List[Union[str, Enum]]] = None,
        dependencies: Optional[Sequence[params.Depends]] = None,
        default_response_class: Type[Response] = _response_class,
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        callbacks: Optional[List[BaseRoute]] = None,
        routes: Optional[List[routing.BaseRoute]] = None,
        redirect_slashes: bool = True,
        default: Optional[ASGIApp] = None,
        dependency_overrides_provider: Optional[Any] = None,
        route_class: Type[APIRoute] = CustomAPIRoute,
        on_startup: Optional[Sequence[Callable[[], Any]]] = None,
        on_shutdown: Optional[Sequence[Callable[[], Any]]] = None,
        deprecated: Optional[bool] = None,
        include_in_schema: bool = True,
        generate_unique_id_function: Callable[
            [APIRoute], str
        ] = _generate_unique_id_function,
    ):
        super().__init__(
            tags=tags,
            dependencies=dependencies,
            default_response_class=default_response_class,
            responses=responses,
            callbacks=callbacks,
            routes=routes,
            redirect_slashes=redirect_slashes,
            default=default,
            dependency_overrides_provider=dependency_overrides_provider,
            route_class=route_class,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            deprecated=deprecated,
            include_in_schema=include_in_schema,
            generate_unique_id_function=generate_unique_id_function,
            prefix=prefix,
        )
