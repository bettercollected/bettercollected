"""This project was generated with fastapi-mvc."""

import logging

from auth.version import __version__

# initialize logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

__all__ = "__version__"
