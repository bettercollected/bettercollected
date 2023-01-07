from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from settings import settings


def init_swagger(app: "FastAPI"):
    """
    Initializes Swagger UI and ReDoc for the specified FastAPI app.

    This function adds two routes to the app: one for the Swagger UI
    HTML page, and one for the ReDoc HTML page. Both routes return the
    respective HTML page with the app's title and the URL of the OpenAPI
    specification as parameters. The Swagger UI route also includes an
    oauth2_redirect_url parameter.

    Parameters:
    app (FastAPI): The FastAPI app instance to initialize Swagger UI and ReDoc for.

    Returns:
    None
    """

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui_html():
        """
        Returns the Swagger UI HTML page for the app.

        This function returns the Swagger UI HTML page with the app's title,
        the URL of the OpenAPI specification, and the `oauth2_redirect_url`
        as parameters.

        Returns:
            str: The Swagger UI HTML page.
        """
        return get_swagger_ui_html(
            openapi_url=f"{settings.api_settings.host}/openapi.json",
            title=app.title + " - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        """
        Returns the ReDoc HTML page for the app.

        This function returns the ReDoc HTML page with the app's title and
        the URL of the OpenAPI specification as parameters.

        Returns:
            str: The ReDoc HTML page.
        """
        return get_redoc_html(
            openapi_url=f"{settings.api_settings.host}/openapi.json",
            title=app.title + " - Swagger UI",
        )
