"""Server Initializer."""
import logging

from backend.version import __version__
from backend.wsgi import ApplicationLoader

# initialize logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

__all__ = ("ApplicationLoader", "__version__")
