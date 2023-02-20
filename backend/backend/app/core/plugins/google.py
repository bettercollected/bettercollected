from backend.app.core.factory import plugin_factory
from backend.app.core.base.plugin_base import BasePlugin
from common.enums.form_provider import FormProvider


class GooglePlugin(BasePlugin):
    def __init__(self, provider: str | FormProvider):
        super().__init__(provider)
        self.provider = provider

    def connect(self):
        return "Connected to Google"

    # Core as a Proxy handled by plugins
    # Individual services and delegation of below to their services without having to create a new plugin
    # Dynamic router -> /plugins/google -> required path haru add gardini
    # -> services list and oauth -> kk support garxa ta
    # -> form loader -> /GET (importer)  # -> data transformation to standard form and responses
    # -> form response -> /GET
    # -> auto sync


def initialize() -> None:
    """Register the Google Plugin."""
    plugin_factory.register_plugin(FormProvider.GOOGLE, GooglePlugin)
