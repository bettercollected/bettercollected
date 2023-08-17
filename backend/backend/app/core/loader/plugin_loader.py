"""Core implementation - plugin loaders."""

import importlib
from typing import List


class PluginInterface:
    """A plugin has a single function called initialize."""

    @staticmethod
    def initialize() -> None:
        """Initializes the form plugins."""


def import_module(plugin_name: str) -> PluginInterface:
    return importlib.import_module(plugin_name)  # type: ignore


def load_plugins(plugins: List[str]) -> None:
    """Loads the plugins defined in the plugins list."""
    for plugin_name in plugins:
        plugin_module = import_module(plugin_name)
        plugin_module.initialize()
