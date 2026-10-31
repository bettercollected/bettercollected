"""What the webhooks switch (``WEBHOOKS_ENABLED``) allows.

On: everything. Off (the default): creating or enabling a webhook, rotating
nothing and sending a test all answer 422 ``webhooks_off``; nothing is queued
on submit, the jobs do nothing and the respondent's privacy panel names no
destination. Saved webhooks and the delivery log stay as they are, and a
webhook can still be disabled or deleted. Read at call time from
``settings.webhooks.ENABLED``.
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException
from backend.config import settings

OFF_CODE = "webhooks_off"
OFF_MESSAGE = "Webhooks are turned off on this instance."


def webhooks_enabled() -> bool:
    return bool(settings.webhooks.ENABLED)


def refuse_when_off() -> None:
    if not webhooks_enabled():
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": OFF_CODE, "message": OFF_MESSAGE},
        )
