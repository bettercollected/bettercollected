from pydantic import BaseSettings


class ProviderPluginSettings(BaseSettings):
    GOOGLE_SERVICE: str = ""
    TYPEFORM_SERVICE: str = ""

    # All your additional application configuration should go either here or in
    # separate file in this submodule.

    class Config:
        """Config sub-class needed to customize BaseSettings settings.

        Attributes:
            case_sensitive (bool): When case_sensitive is True, the environment
                variable names must match field names (optionally with a prefix)
            env_prefix (str): The prefix for environment variable.

        Resources:
            https://pydantic-docs.helpmanual.io/usage/settings/

        """

        case_sensitive = True
        env_prefix = "PROVIDER_PLUGIN_"
