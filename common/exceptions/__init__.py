import warnings
from typing import Optional

from constants import (
    MESSAGE_CONVERSION_WARNING,
    MESSAGE_DATA_TO_ITEM_ERROR,
    MESSAGE_FORBIDDEN,
    MESSAGE_ITEM_TO_DATA_ERROR,
    MESSAGE_KEY_FOUND,
    MESSAGE_NOT_FOUND,
)


class ForbiddenError(Exception):
    """
    Exception class for representing a forbidden request error.
    This exception is raised when a client makes a request that is not allowed by the server.
    """

    def __init__(self, message: Optional[str]):
        """
        Initializes a ForbiddenError instance.

        Args:
            message (str, optional): The error message to be displayed. If not provided, a default message is used.
        """
        self.message = message if message is not None else MESSAGE_FORBIDDEN

    def __str__(self):
        """
        Returns the string representation of the ForbiddenError instance.
        """
        return self.message


class NotFoundError(Exception):
    """
    Exception class for representing a resource not found error.
    This exception is raised when a client makes a request for a resource that is not available on the server.
    """

    def __init__(self, message: Optional[str]):
        """
        Initializes a NotFoundError instance.

        Args:
            message (str, optional): The error message to be displayed. If not provided, a default message is used.
        """
        self.message = message if message is not None else MESSAGE_NOT_FOUND

    def __str__(self):
        """
        Returns the string representation of the NotFoundError instance.
        """
        return self.message


class KeyFoundError(Exception):
    """
    Exception class for representing a key found error.
    This exception is typically raised during insertion when an item with the given key/ID field is found,
    but it was not expected to be present.
    """

    def __init__(self, message: Optional[str]):
        """
        Initializes a KeyFoundError instance.

        Args:
            message (str, optional): The error message to be displayed. If not provided, a default message is used.
        """
        self.message = message if message is not None else MESSAGE_KEY_FOUND

    def __str__(self):
        """
        Returns the string representation of the KeyFoundError instance.
        """
        return self.message


class ItemToDataError(ValueError):
    """
    Exception class for representing an error when converting an item to data.
    This exception is raised when an error occurs while attempting to convert an item to a data representation.
    """

    def __init__(self, message: Optional[str]):
        """
        Initializes an ItemToDataError instance.

        Args:
            message (str, optional): The error message to be displayed. If not provided, a default message is used.
        """
        self.message = message if message is not None else MESSAGE_ITEM_TO_DATA_ERROR

    def __str__(self):
        """
        Returns the string representation of the ItemToDataError instance.
        """
        return self.message


class DataToItemError(ValueError):
    """
    Exception class for representing an error when converting data to an item.
    This exception is raised when an error occurs while attempting to convert data to an item representation.
    """

    def __init__(self, message: Optional[str]):
        """
        Initializes a DataToItemError instance.

        Args:
            message (str, optional): The error message to be displayed. If not provided, a default message is used.
        """
        self.message = message if message is not None else MESSAGE_DATA_TO_ITEM_ERROR

    def __str__(self):
        """
        Returns the string representation of the DataToItemError instance.
        """
        return self.message


class ConversionWarning(UserWarning):
    """
    Warning class for representing a non-fatal error when converting data to an item or an item to data.
    This warning is raised when an error occurs while attempting to convert data to an item or an item to data,
    but the conversion can still proceed with potentially degraded results.
    """

    def __init__(self, message: Optional[str]):
        """
        Initializes a ConversionWarning instance.

        Args:
            message (str, optional): The warning message to be displayed. If not provided, a default message is used.
        """
        self.message = message if message is not None else MESSAGE_CONVERSION_WARNING

    def __str__(self):
        """
        Returns the string representation of the ConversionWarning instance.
        """
        return self.message


def _handle_conversion_error(repo, data):
    """
    Handles an error that occurred while attempting to convert data to an item or an item to data.

    Args:
        repo: The repository object where the error occurred.
        data: The data that was being converted.
    Raises:
        ConversionWarning: If the errors_query attribute of the repository is set to "warn".
        Any other exception: If the errors_query attribute of the repository is set to "raise".
    """
    errors_query = repo.errors_query
    if errors_query == "raise":
        raise
    if errors_query == "warn":
        warnings.warn(
            f"Converting a data to an item failed:\n{data}", ConversionWarning
        )
