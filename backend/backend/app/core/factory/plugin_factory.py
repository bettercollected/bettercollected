"""Core implementation - plugin factory."""
from typing import Any, Callable, Dict

from backend.app.core.base.plugin_base import BasePlugin
from common.enums.form_provider import FormProvider

_plugin_creator_funcs: Dict[str, Callable[..., BasePlugin]] = {}


def register_plugin(
    provider: str | FormProvider, creation_func: Callable[..., BasePlugin]
):
    """Register a new form provider plugin."""
    _plugin_creator_funcs[provider] = creation_func


def unregister_plugin(provider: str | FormProvider):
    """Unregister a loaded plugin."""
    _plugin_creator_funcs.pop(provider, None)


def create(args: Dict[str, Any]) -> BasePlugin:
    """Create a plugin of a specific type, give a dictionary or args."""
    provider = args.get("provider")
    try:
        creator_funcs = _plugin_creator_funcs[provider]
        return creator_funcs(**args)
    except KeyError:
        raise ValueError(f"Provider: {provider} is not supported.")
