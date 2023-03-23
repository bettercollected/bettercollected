from backend.app.core.base.plugin_base import BasePlugin
from backend.app.core.factory import plugin_factory

from common.enums.form_provider import FormProvider


class TypeformPlugin(BasePlugin):
    def __init__(self, provider: str | FormProvider):
        super().__init__(provider)
        self.provider = provider

    def connect(self):
        return "Connected to Typeform"


def initialize() -> None:
    """Register the Typeform Plugin."""
    plugin_factory.register_plugin(FormProvider.TYPEFORM, TypeformPlugin)
