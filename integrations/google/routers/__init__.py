from fastapi import FastAPI

from common.base.plugin import register_plugin_class
from common.enums.form_provider import FormProvider
from common.utils.router import CustomAPIRouter
from routers import form, form_response
from routers.google import GoogleRouter
from settings import settings


def include_routers(server: "FastAPI"):
    """
    Includes all the routers in the given FastAPI server instance.

    Parameters:
        server (FastAPI): FastAPI server instance to include routers in.
    """

    google_router = CustomAPIRouter(
        prefix=settings.api_settings.root_path + "/" + FormProvider.GOOGLE
    )
    google_tags = ["Google API"]
    register_plugin_class(
        router=google_router,
        route=GoogleRouter(),
        tags=google_tags,
    )

    server.include_router(google_router, tags=google_tags)
    server.include_router(form.router, tags=["Google Forms"])
    server.include_router(form_response.router, tags=["Google Form Submissions"])
