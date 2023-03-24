import json
from typing import List

from backend.app.core.base.plugin_base import BasePlugin
from backend.app.core.factory import plugin_factory
from backend.app.core.loader import plugin_loader


class FormPluginClient:
    def __init__(self):
        self.plugins: List[BasePlugin] = []

    def load_plugins(self):
        with open("./plugin.json") as file:
            data = json.load(file)

            # load plugins
            plugin_loader.load_plugins(data.get("plugins", []))

            self.plugins.extend(
                [plugin_factory.create(item) for item in data.get("providers", [])]
            )
        return self.plugins


if __name__ == "__main__":
    plugins = FormPluginClient().load_plugins()
    print(f"Plugin List: {plugins}")

    for plugin in plugins:
        print(plugin, end="\t")
        print(plugin.connect())
