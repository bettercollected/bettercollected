"""Application configuration.

The ``config`` submodule defines configuration for your application, router,
gunicorn, and more.

Resources:
    1. `Pydantic documentation`_
    2. `Gunicorn documentation`_

.. _Pydantic documentation:
    https://pydantic-docs.helpmanual.io/

.. _Gunicorn documentation:
    https://docs.gunicorn.org/en/20.1.0/

"""
import os

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.getenv("DOTENV_PATH", ".env"))

from auth.config.application import settings  # noqa: I100

__all__ = ("settings",)
