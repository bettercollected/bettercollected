"""The form-level access switch (``FORM_ACCESS_ENABLED``).

Off (the default): nothing about form-level access is enforced. A member's
permissions on a form are those of their workspace role (as before), a stored
grant, team or restricted mode is ignored, and no decision reads the tables
behind them. Stored data stays as it is. On: a form can be restricted to chosen
people and teams, and a grant can raise a member's role on one form
(docs/enterprise-access-model.md, "Form-level scope").
"""

from pydantic_settings import SettingsConfigDict

from common.settings.loader.pydantic_source import StoreBackedSettings


class FormAccessSettings(StoreBackedSettings):
    ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="FORM_ACCESS_")
