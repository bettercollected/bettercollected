"""The second app theme's switch (``APP_THEME_PIGMENT_ENABLED``).

Off (the default): a workspace cannot choose the Pigment theme (the change
answers 422 ``app_theme_disabled``) and every workspace is served the default
theme, ``daybreak``, whatever it has stored; a stored choice is kept, neither
enforced nor shown. On: a workspace's owners and admins can choose between the
two themes.

Read from the environment only, deliberately, like ``FORM_PROMOTION_ENABLED``
and ``REPORTING_ENABLED``: the switch must not be flipped from the admin portal
while the theme is built up. It may become a stored setting (tier T2) when it
is released.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppThemeSettings(BaseSettings):
    ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="APP_THEME_PIGMENT_")
