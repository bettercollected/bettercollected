:tocdepth: 2
API
===

This part of the documentation lists the full API reference of all classes and functions.

WSGI
----

.. autoclass:: integrations_typeform.wsgi.ApplicationLoader
   :members:
   :show-inheritance:

Config
------

.. automodule:: integrations_typeform.config

.. autoclass:: integrations_typeform.config.application.Application
   :members:
   :show-inheritance:

.. autoclass:: integrations_typeform.config.redis.Redis
   :members:
   :show-inheritance:

.. automodule:: integrations_typeform.config.gunicorn

CLI
---

.. automodule:: integrations_typeform.cli

.. autofunction:: integrations_typeform.cli.cli.cli

.. autofunction:: integrations_typeform.cli.utils.validate_directory

.. autofunction:: integrations_typeform.cli.serve.serve

App
---

.. automodule:: integrations_typeform.app

.. autofunction:: integrations_typeform.app.asgi.on_startup

.. autofunction:: integrations_typeform.app.asgi.on_shutdown

.. autofunction:: integrations_typeform.app.asgi.get_application

.. automodule:: integrations_typeform.app.router

Controllers
~~~~~~~~~~~

.. automodule:: integrations_typeform.app.controllers

.. autofunction:: integrations_typeform.app.controllers.ready.readiness_check

Models
~~~~~~

.. automodule:: integrations_typeform.app.models

Views
~~~~~

.. automodule:: integrations_typeform.app.views

.. autoclass:: integrations_typeform.app.views.error.ErrorModel
   :members:
   :show-inheritance:

.. autoclass:: integrations_typeform.app.views.error.ErrorResponse
   :members:
   :show-inheritance:

Exceptions
~~~~~~~~~~

.. automodule:: integrations_typeform.app.exceptions

.. autoclass:: integrations_typeform.app.exceptions.http.HTTPException
   :members:
   :show-inheritance:

.. autofunction:: integrations_typeform.app.exceptions.http.http_exception_handler

Utils
~~~~~

.. automodule:: integrations_typeform.app.utils

.. autoclass:: integrations_typeform.app.utils.aiohttp_client.AiohttpClient
   :members:
   :show-inheritance:

.. autoclass:: integrations_typeform.app.utils.redis.RedisClient
   :members:
   :show-inheritance:
