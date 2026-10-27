"""Refusals of an import: a stable code, an HTTP status and a message."""

from http import HTTPStatus
from typing import Any, Dict, Optional


class ImportRefused(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}

    def content(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.extra}


def refuse(code: str, message: str, status: int = HTTPStatus.BAD_REQUEST, **extra):
    return ImportRefused(int(status), code, message, extra)
