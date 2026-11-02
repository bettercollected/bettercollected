"""The API key roles switch (``API_KEY_ROLES_ENABLED``).

Off (the default): a key cannot be given a role or a list of forms (setting one
answers 422 ``api_key_roles_off``), and every key without either behaves
exactly as it always has. A limit already stored on a key is still enforced:
switching this off never widens a key. On: an admin can limit a key to a role
(Editor, Reviewer, Viewer, Privacy officer) and to a list of forms.

Read from the environment only, deliberately, like ``FORM_ACCESS_ENABLED``:
until every entry point enforces it, the switch must not be reachable from the
admin portal's stored settings. It becomes a stored setting (tier T2) when it is
released.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiKeyRolesSettings(BaseSettings):
    ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="API_KEY_ROLES_")
