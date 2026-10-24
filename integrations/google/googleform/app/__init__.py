"""Application implementation.

The ``app`` submodule defines application controllers, models, views, utils,
exceptions, and all other implementations for the need of your application.

Resources:
    1. `FastAPI documentation`_
    2. `Pydantic documentation`_

.. _FastAPI documentation:
    https://fastapi.tiangolo.com

.. _Pydantic documentation:
    https://pydantic-docs.helpmanual.io/

"""
# Configuration first: it loads the settings snapshot everything below reads.
import googleform.config  # noqa: F401
from googleform.app.asgi import get_application


__all__ = ("get_application",)
