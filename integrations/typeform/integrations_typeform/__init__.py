"""This project was generated with fastapi-mvc."""
import logging

from integrations_typeform.wsgi import ApplicationLoader
from integrations_typeform.version import __version__

# initialize logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

__all__ = ("ApplicationLoader", "__version__")
