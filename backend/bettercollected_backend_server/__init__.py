"""Server Initializer."""
import logging

from bettercollected_backend_server.wsgi import ApplicationLoader
from bettercollected_backend_server.version import __version__

# initialize logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

__all__ = ("ApplicationLoader", "__version__")
