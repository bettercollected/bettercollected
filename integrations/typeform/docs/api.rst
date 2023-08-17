:tocdepth: 2

API
===

This part of the documentation lists the full API reference of all classes and functions.

WSGI
----

.. autoclass:: typeform.wsgi.ApplicationLoader
   :members:
   :show-inheritance:

Config
------

.. automodule:: typeform.config

.. autoclass:: typeform.config.application.Application
   :members:
   :show-inheritance:

.. automodule:: typeform.config.gunicorn

CLI
---

.. automodule:: typeform.cli

.. autofunction:: typeform.cli.cli.cli

.. autofunction:: typeform.cli.utils.validate_directory

.. autofunction:: typeform.cli.serve.serve

App
---

.. automodule:: typeform.app

.. autofunction:: typeform.app.asgi.on_startup

.. autofunction:: typeform.app.asgi.on_shutdown

.. autofunction:: typeform.app.asgi.get_application

.. automodule:: typeform.app.router

Controllers
~~~~~~~~~~~

.. automodule:: typeform.app.controllers

.. autofunction:: typeform.app.controllers.auth_router.AuthRoutes

.. autofunction:: typeform.app.controllers.form_router._get_forms
.. autofunction:: typeform.app.controllers.form_router._get_single_form
.. autofunction:: typeform.app.controllers.form_router._convert_form

Models
~~~~~~

.. automodule:: typeform.app.models

Views
~~~~~

.. automodule:: typeform.app.views

.. autoclass:: typeform.app.views.error.ErrorModel
   :members:
   :show-inheritance:

.. autoclass:: typeform.app.views.error.ErrorResponse
   :members:
   :show-inheritance:

Exceptions
~~~~~~~~~~

.. automodule:: typeform.app.exceptions

.. autoclass:: typeform.app.exceptions.http.HTTPException
   :members:
   :show-inheritance:

.. autofunction:: typeform.app.exceptions.http.http_exception_handler

Utils
~~~~~

.. automodule:: typeform.app.utils
