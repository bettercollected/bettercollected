"""Errors of an AI call, as the HTTP answers the client gets.

They are ``HTTPException``s, so a service's ``except HTTPException: raise``
passes them through unchanged. Messages are plain and never quote the
prompt or the model's reply.
"""

from http import HTTPStatus
from typing import Optional

from backend.app.exceptions import HTTPException


class AIError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        retry_after: Optional[int] = None,
    ):
        super().__init__(
            status_code=status_code,
            content={"code": code, "message": message},
            headers={"Retry-After": str(retry_after)} if retry_after else None,
        )
        self.code = code
        self.message = message


def ai_timeout() -> AIError:
    return AIError(
        HTTPStatus.GATEWAY_TIMEOUT,
        "ai_timeout",
        "The AI took too long to answer. Nothing was changed. Please try again.",
    )


def ai_unavailable() -> AIError:
    return AIError(
        HTTPStatus.BAD_GATEWAY,
        "ai_unavailable",
        "The AI service could not be reached or refused the request. "
        "Nothing was changed. Please try again later.",
    )


def ai_unusable(message: Optional[str] = None) -> AIError:
    return AIError(
        HTTPStatus.BAD_GATEWAY,
        "ai_unusable_reply",
        message
        or "The AI returned an unusable answer. Nothing was changed. Please try again.",
    )


def ai_rate_limited(retry_after: int) -> AIError:
    return AIError(
        HTTPStatus.TOO_MANY_REQUESTS,
        "ai_rate_limited",
        "Too many AI requests. Please wait a minute and try again.",
        retry_after=retry_after,
    )


def ai_daily_limit(retry_after: int) -> AIError:
    return AIError(
        HTTPStatus.TOO_MANY_REQUESTS,
        "ai_daily_limit",
        "This workspace has used its AI allowance for today. "
        "It resets at midnight UTC.",
        retry_after=retry_after,
    )
