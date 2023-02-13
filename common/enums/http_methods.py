import enum


class HTTPMethods(str, enum.Enum):
    """
    Enum representing the different HTTP Methods.
    """

    GET: str = "GET"
    POST: str = "POST"
    PATCH: str = "PATCH"
    PUT: str = "PUT"
    DELETE: str = "DELETE"
