from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from settings import settings


def init_cors(app: "FastAPI"):
    """
    Initializes CORS handling for the specified FastAPI app.

    This function adds a CORSMiddleware to the app, allowing it to handle CORS requests.
    The allow_origins parameter is set to a list of origins specified in the
    api_settings.allowed_origins attribute, and the allow_credentials, allow_methods,
    and allow_headers parameters are set to allow all values.

    Parameters:
    app (FastAPI): The FastAPI app instance to initialize CORS handling for.
    """
    origins = settings.api_settings.allowed_origins.split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
