"""The second app theme's switch (``APP_THEME_PIGMENT_ENABLED``).

Off (the default): a workspace cannot choose the Pigment theme (the change
answers 422 ``app_theme_disabled``) and every workspace is served the default
theme, ``daybreak``, whatever it has stored; a stored choice is kept, neither
enforced nor shown. On: a workspace's owners and admins can choose between the
two themes.

The switch also covers the form side of the same theme: while it is off the
``Pigment`` theme preset is not offered, and a new form theme that names the
``pigment`` background artwork or sets the ``choiceKeys`` key is refused (a form
that already stores them is unchanged). On, the preset, its artwork and the
choice keys are offered (``constants/themes.py``, ``docs/pigment-preset.md``).

A stored setting (tier T2, class R, like ``CAPTCHA_ENABLED`` and
``DAYBREAK_PRESET_ENABLED``): an instance admin turns it on in the admin
portal's settings, or the environment sets it. The order is the loader's: a
non-empty environment value, then the stored value, then the default (off). It
is read when the backend starts, so a change in the portal is picked up by the
next restart of the backend.
"""

from common.settings.loader.pydantic_source import StoreBackedSettings
from pydantic_settings import SettingsConfigDict


class AppThemeSettings(StoreBackedSettings):
    ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="APP_THEME_PIGMENT_")
