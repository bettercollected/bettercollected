:tocdepth: 2

API
===

This part of the documentation lists the full API reference of all classes and functions.

WSGI
----

.. autoclass:: googleform.wsgi.ApplicationLoader
   :members:
   :show-inheritance:

Config
------

.. automodule:: googleform.config

.. autoclass:: googleform.config.application.Application
   :members:
   :show-inheritance:

.. autoclass:: googleform.config.redis.Redis
   :members:
   :show-inheritance:

.. automodule:: googleform.config.gunicorn

CLI
---

.. automodule:: googleform.cli

.. autofunction:: googleform.cli.cli.cli

.. autofunction:: googleform.cli.utils.validate_directory

.. autofunction:: googleform.cli.serve.serve

App
---

.. automodule:: googleform.app

.. autofunction:: googleform.app.asgi.on_startup

.. autofunction:: googleform.app.asgi.on_shutdown

.. autofunction:: googleform.app.asgi.get_application

.. automodule:: googleform.app.router

Controllers
~~~~~~~~~~~

.. automodule:: googleform.app.controllers

.. autofunction:: googleform.app.controllers.ready.readiness_check

Models
~~~~~~

.. automodule:: googleform.app.models

Views
~~~~~

.. automodule:: googleform.app.views

.. autoclass:: googleform.app.views.error.ErrorModel
   :members:
   :show-inheritance:

.. autoclass:: googleform.app.views.error.ErrorResponse
   :members:
   :show-inheritance:

Exceptions
~~~~~~~~~~

.. automodule:: googleform.app.exceptions

.. autoclass:: googleform.app.exceptions.http.HTTPException
   :members:
   :show-inheritance:

.. autofunction:: googleform.app.exceptions.http.http_exception_handler

Utils
~~~~~

.. automodule:: googleform.app.utils

.. autoclass:: googleform.app.utils.aiohttp_client.AiohttpClient
   :members:
   :show-inheritance:

.. autoclass:: googleform.app.utils.redis.RedisClient
   :members:
   :show-inheritance:
