import warnings
from typing import Optional

from constants import MESSAGE_FORBIDDEN, MESSAGE_NOT_FOUND


class ForbiddenError(Exception):
    """Raised when someone requests for those resources that are
    not public or unauthorized.
    """

    def __init__(self, message: Optional[str]):
        self.message = message if message is not None else MESSAGE_FORBIDDEN

    def __str__(self):
        return self.message


class NotFoundError(Exception):
    """Raised when someone requests for those resources that are
    not available..
    """

    def __init__(self, message: Optional[str]):
        self.message = message if message is not None else MESSAGE_NOT_FOUND

    def __str__(self):
        return self.message


class KeyFoundError(Exception):
    """Typically raised in insertion.

    Raised when an item for given key/id field
    is found when it was not expected.
    """


class ItemToDataError(ValueError):
    """Raised when converting an item to a data fails."""


class DataToItemError(ValueError):
    """Raised when converting a data to an item fails."""


class ConversionWarning(UserWarning):
    """Converting a data to an item or an item to a data failed non-fatally."""


def _handle_conversion_error(repo, data):
    errors_query = repo.errors_query
    if errors_query == "raise":
        raise
    if errors_query == "warn":
        warnings.warn(
            f"Converting a data to an item failed:\n{data}", ConversionWarning
        )
