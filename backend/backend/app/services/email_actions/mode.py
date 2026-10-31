"""What the email actions switch (``EMAIL_ACTIONS_ENABLED``) allows.

On: everything. Off (the default): creating an email action, switching one on
and sending a test mail answer 422 ``email_actions_off``; nothing is queued on
submit, the jobs send nothing and the respondent's privacy panel names no
recipient. Everything else still answers: the list, edits that do not switch
one on, switching one off, deleting and the delivery log. Saved actions and the
log stay as they are. Read at call time from ``settings.email_actions.ENABLED``.
Mail needs the instance's mail server (``MAIL_SMTP_SERVER`` and
``MAIL_SENDER``): without them an action cannot be switched on
(422 ``mail_not_configured``) and a run fails with that code.
"""

from http import HTTPStatus

from backend.app.exceptions import HTTPException
from backend.config import settings

OFF_CODE = "email_actions_off"
OFF_MESSAGE = "Email actions are turned off on this instance."
NOT_CONFIGURED_CODE = "mail_not_configured"
NOT_CONFIGURED_MESSAGE = "This instance has no mail server configured."


def email_actions_enabled() -> bool:
    return bool(settings.email_actions.ENABLED)


def mail_configured() -> bool:
    mail = settings.mail_settings
    return bool((mail.smtp_server or "").strip() and (mail.sender or "").strip())


def refuse_when_off() -> None:
    if not email_actions_enabled():
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": OFF_CODE, "message": OFF_MESSAGE},
        )


def refuse_when_not_configured() -> None:
    if not mail_configured():
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": NOT_CONFIGURED_CODE, "message": NOT_CONFIGURED_MESSAGE},
        )
