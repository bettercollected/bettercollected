""""""
import logging

from googleform.wsgi import ApplicationLoader
from googleform.version import __version__

# initialize logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

__all__ = ("ApplicationLoader", "__version__")
