"""The form promotion switch (``FORM_PROMOTION_ENABLED``).

Off (the default): the promotion routes (copy a form to another workspace, the
form file) answer 422 ``form_promotion_disabled`` before anything is read, no
query is made on their account, and nothing else changes: the public spec API,
the SDK and the CLI are not part of the switch. A ``promotedFrom`` mark already
stored on a form is kept and never shown to respondents, switch or not. On: a
member who may read a form in one workspace and create or edit forms in another
can copy it there, as a draft.

Read from the environment only, deliberately, like ``FORM_ACCESS_ENABLED`` and
``API_KEY_ROLES_ENABLED``: it becomes a stored setting (tier T2) when it is
released.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class FormPromotionSettings(BaseSettings):
    ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="FORM_PROMOTION_")
