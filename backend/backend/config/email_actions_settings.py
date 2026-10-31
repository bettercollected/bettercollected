"""The email actions switch (``EMAIL_ACTIONS_ENABLED``).

Off (the default): creating or enabling an email action and sending a test mail
answer 422 ``email_actions_off``, no submission queues a mail, the jobs send
nothing and the respondent's privacy panel names no recipient; saved actions
and the delivery log stay as they are. On: a form's admins can mail the team,
and the respondent a copy of their own submission (docs/email-actions.md). The
mails go through the instance's mail server (``MAIL_*``).
"""

from pydantic_settings import SettingsConfigDict

from common.settings.loader.pydantic_source import StoreBackedSettings


class EmailActionsSettings(StoreBackedSettings):
    ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="EMAIL_ACTIONS_")
