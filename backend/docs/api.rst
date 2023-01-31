:tocdepth: 2

API
===

This part of the documentation lists the full API reference of all classes and functions.

WSGI
----

.. autoclass:: bettercollected_backend_server.wsgi.ApplicationLoader
   :members:
   :show-inheritance:

Config
------

.. automodule:: bettercollected_backend_server.config

.. autoclass:: bettercollected_backend_server.config.application.Application
   :members:
   :show-inheritance:

.. autoclass:: bettercollected_backend_server.config.redis.Redis
   :members:
   :show-inheritance:

.. automodule:: bettercollected_backend_server.config.gunicorn

CLI
---

.. automodule:: bettercollected_backend_server.cli

.. autofunction:: bettercollected_backend_server.cli.cli.cli

.. autofunction:: bettercollected_backend_server.cli.utils.validate_directory

.. autofunction:: bettercollected_backend_server.cli.serve.serve

App
---

.. automodule:: bettercollected_backend_server.app

.. autofunction:: bettercollected_backend_server.app.asgi.on_startup

.. autofunction:: bettercollected_backend_server.app.asgi.on_shutdown

.. autofunction:: bettercollected_backend_server.app.asgi.get_application

.. automodule:: bettercollected_backend_server.app.router

Controllers
~~~~~~~~~~~

.. automodule:: bettercollected_backend_server.app.controllers

.. autofunction:: bettercollected_backend_server.app.controllers.ready.readiness_check

Models
~~~~~~

.. automodule:: bettercollected_backend_server.app.models

Views
~~~~~

.. automodule:: bettercollected_backend_server.app.views

.. autoclass:: bettercollected_backend_server.app.views.error.ErrorModel
   :members:
   :show-inheritance:

.. autoclass:: bettercollected_backend_server.app.views.error.ErrorResponse
   :members:
   :show-inheritance:

Exceptions
~~~~~~~~~~

.. automodule:: bettercollected_backend_server.app.exceptions

.. autoclass:: bettercollected_backend_server.app.exceptions.http.HTTPException
   :members:
   :show-inheritance:

.. autofunction:: bettercollected_backend_server.app.exceptions.http.http_exception_handler

Utils
~~~~~

.. automodule:: bettercollected_backend_server.app.utils

.. autoclass:: bettercollected_backend_server.app.utils.aiohttp_client.AiohttpClient
   :members:
   :show-inheritance:

.. autoclass:: bettercollected_backend_server.app.utils.redis.RedisClient
   :members:
   :show-inheritance:
