import enum


class HTTPMethods(str, enum.Enum):
    """
    Enum representing the different HTTP Methods.
    """

    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    PUT = "PUT"
    DELETE = "DELETE"
