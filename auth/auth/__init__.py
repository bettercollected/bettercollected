"""This project was generated with fastapi-mvc."""
import logging

from auth.version import __version__
from auth.wsgi import ApplicationLoader

# initialize logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

__all__ = ("ApplicationLoader", "__version__")
