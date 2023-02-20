:tocdepth: 2

API
===

This part of the documentation lists the full API reference of all classes and functions.

WSGI
----

.. autoclass:: backend.wsgi.ApplicationLoader
   :members:
   :show-inheritance:

Config
------

.. automodule:: backend.config

.. autoclass:: backend.config.application.Application
   :members:
   :show-inheritance:

.. autoclass:: backend.config.redis.Redis
   :members:
   :show-inheritance:

.. automodule:: backend.config.gunicorn

CLI
---

.. automodule:: backend.cli

.. autofunction:: backend.cli.cli.cli

.. autofunction:: backend.cli.utils.validate_directory

.. autofunction:: backend.cli.serve.serve

App
---

.. automodule:: backend.app

.. autofunction:: backend.app.asgi.on_startup

.. autofunction:: backend.app.asgi.on_shutdown

.. autofunction:: backend.app.asgi.get_application

.. automodule:: backend.app.router

Controllers
~~~~~~~~~~~

.. automodule:: backend.app.controllers

.. autofunction:: backend.app.controllers.ready.readiness_check

Handlers
~~~~~~~~

.. automodule:: backend.app.handlers

.. autofunction:: backend.app.handlers.init_logging

Middlewares
~~~~~~~~~~~

.. automodule:: backend.app.middlewares

.. autofunction:: backend.app.middlewares.include_middlewares

Models
~~~~~~

.. automodule:: backend.app.models

.. autoclass:: backend.app.models.workspace.Workspace
   :members:
   :show-inheritance:

Views
~~~~~

.. automodule:: backend.app.views

.. autoclass:: backend.app.views.error.ErrorModel
   :members:
   :show-inheritance:

.. autoclass:: backend.app.views.error.ErrorResponse
   :members:
   :show-inheritance:

Exceptions
~~~~~~~~~~

.. automodule:: backend.app.exceptions

.. autoclass:: backend.app.exceptions.http.HTTPException
   :members:
   :show-inheritance:

.. autofunction:: backend.app.exceptions.http.http_exception_handler

Utils
~~~~~

.. automodule:: backend.app.utils

.. autoclass:: backend.app.utils.aiohttp_client.AiohttpClient
   :members:
   :show-inheritance:

.. autoclass:: backend.app.utils.redis.RedisClient
   :members:
   :show-inheritance:
