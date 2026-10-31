"""What the webhooks switch (``WEBHOOKS_ENABLED``) allows.

On: everything. Off (the default): creating a webhook, switching one on and
sending a test event answer 422 ``webhooks_off``; nothing is queued on submit,
the jobs send nothing and the respondent's privacy panel names no destination.
Everything else still answers: the list, the detail read, edits that do not
switch one on, switching one off, deleting, rotating a secret, the delivery log
and the change history. Saved webhooks and the log stay as they are. Read at call time from
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
