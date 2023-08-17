:tocdepth: 2
API
===

This part of the documentation lists the full API reference of all classes and functions.

WSGI
----

.. autoclass:: auth.wsgi.ApplicationLoader
   :members:
   :show-inheritance:

Config
------

.. automodule:: auth.config

.. autoclass:: auth.config.application.Application
   :members:
   :show-inheritance:

.. autoclass:: auth.config.redis.Redis
   :members:
   :show-inheritance:

.. automodule:: auth.config.gunicorn

CLI
---

.. automodule:: auth.cli

.. autofunction:: auth.cli.cli.cli

.. autofunction:: auth.cli.utils.validate_directory

.. autofunction:: auth.cli.serve.serve

App
---

.. automodule:: auth.app

.. autofunction:: auth.app.asgi.on_startup

.. autofunction:: auth.app.asgi.on_shutdown

.. autofunction:: auth.app.asgi.get_application

.. automodule:: auth.app.router

Controllers
~~~~~~~~~~~

.. automodule:: auth.app.controllers

.. autofunction:: auth.app.controllers.ready.readiness_check

Models
~~~~~~

.. automodule:: auth.app.models

Views
~~~~~

.. automodule:: auth.app.views

.. autoclass:: auth.app.views.error.ErrorModel
   :members:
   :show-inheritance:

.. autoclass:: auth.app.views.error.ErrorResponse
   :members:
   :show-inheritance:

Exceptions
~~~~~~~~~~

.. automodule:: auth.app.exceptions

.. autoclass:: auth.app.exceptions.http.HTTPException
   :members:
   :show-inheritance:

.. autofunction:: auth.app.exceptions.http.http_exception_handler

Utils
~~~~~

.. automodule:: auth.app.utils

.. autoclass:: auth.app.utils.aiohttp_client.AiohttpClient
   :members:
   :show-inheritance:

.. autoclass:: auth.app.utils.redis.RedisClient
   :members:
   :show-inheritance:
