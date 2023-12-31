import logging

from googleform.version import __version__
from googleform.wsgi import ApplicationLoader

# initialize logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

__all__ = ("ApplicationLoader", "__version__")
