"""What the submissions switch (``SUBMISSIONS_API_ENABLED``) allows.

On: API keys with the ``submissions:write`` scope create and update responses
(docs/submissions-api.md). Off (the default): both endpoints answer 404 before
the key is even looked at, an API key can't be created with the scope (422
``submissions_api_off``), and a key that already has it is refused (404 at the
endpoints). Responses that were made through the API stay as they are and are
read like any other. Read at call time from ``settings.SUBMISSIONS_API_ENABLED``.
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException

OFF_CODE = "submissions_api_off"
OFF_MESSAGE = "Creating responses through the API is turned off on this instance."
SCOPE = "submissions:write"


def submissions_api_enabled() -> bool:
    from backend.config import settings

    return bool(getattr(settings, "SUBMISSIONS_API_ENABLED", False))


def refuse_scope_when_off() -> None:
    """Granting the scope while the switch is off: 422."""
    if not submissions_api_enabled():
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": OFF_CODE, "message": OFF_MESSAGE},
        )


def hide_when_off() -> None:
    """The endpoints while the switch is off: 404, as if they did not exist."""
    if not submissions_api_enabled():
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Not found")
