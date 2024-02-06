from typing import Any, Optional, Dict


class HTTPException(Exception):

    def __str__(self):
        return self.content

    def __init__(
            self,
            status_code: int,
            content: Any = None,
            headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize HTTPException class object instance.

        Args:
            status_code (int): HTTP error status code.
            content (Any): Response body.
            headers (Optional[Dict[str, Any]]): Additional response headers.

        """
        self.status_code = status_code
        self.content = content
        self.headers = headers
