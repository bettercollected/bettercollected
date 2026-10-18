"""pydantic-settings glue: ``StoreBackedSettings`` and ``StoreSource``.

A class that extends ``StoreBackedSettings`` instead of ``BaseSettings`` gets
the store between the environment and the defaults, so the existing nested
pattern (``x: Cls = Cls()``) keeps working and every class reads the same one
snapshot (``load_snapshot``). With the store off (no runtime) the source list
is exactly pydantic-settings' default, so nothing changes.

Order with the store on: init arguments, environment, dotenv, store, secrets
directory. An empty environment value counts as unset only for a setting that
has a store row (it is dropped, so the store row applies); everywhere else an
empty value behaves as before.

This module imports pydantic-settings, which the pure loader does not need,
so import it only from a service that depends on pydantic-settings.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Type

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from ..registry import normalize_value
from .runtime import current_runtime

__all__ = ["StoreBackedSettings", "StoreSource"]


def _env_name(settings_cls: Type[BaseSettings], name: str, field: FieldInfo) -> Optional[Tuple[str, str]]:
    """``(data key, store key)`` for a field, or None when it has no single name."""
    alias = field.validation_alias
    if isinstance(alias, str):
        return alias, alias.upper()
    if alias is not None:
        return None
    prefix = str(settings_cls.model_config.get("env_prefix", "") or "")
    return name, (prefix + name).upper()


def _plain(value: Any) -> Any:
    """Scalars as text, as an environment variable would carry them."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return value


class StoreSource(PydanticBaseSettingsSource):
    def get_field_value(self, field: FieldInfo, field_name: str):  # pragma: no cover
        return None, field_name, False

    def __call__(self) -> Dict[str, Any]:
        runtime = current_runtime()
        found: Dict[str, Any] = {}
        if runtime is None:
            return found
        for name, field in self.settings_cls.model_fields.items():
            names = _env_name(self.settings_cls, name, field)
            if names is None:
                continue
            data_key, key = names
            resolved = runtime.resolve_key(key)
            if resolved is not None:
                found[data_key] = _plain(resolved.value)
        return found


class _DropEmptyWhenStored(PydanticBaseSettingsSource):
    """An empty value from ``inner`` does not shadow a verified store row."""

    def __init__(self, settings_cls: Type[BaseSettings], inner: PydanticBaseSettingsSource):
        super().__init__(settings_cls)
        self._inner = inner

    def get_field_value(self, field: FieldInfo, field_name: str):  # pragma: no cover
        return self._inner.get_field_value(field, field_name)

    def __call__(self) -> Dict[str, Any]:
        data = dict(self._inner())
        runtime = current_runtime()
        if runtime is None:
            return data
        for name, field in self.settings_cls.model_fields.items():
            names = _env_name(self.settings_cls, name, field)
            if names is None or names[0] not in data:
                continue
            value = data[names[0]]
            if (
                isinstance(value, str)
                and not normalize_value(value)
                and runtime.current.get(names[1]) is not None
            ):
                del data[names[0]]
        return data


class StoreBackedSettings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        if current_runtime() is None:
            return (init_settings, env_settings, dotenv_settings, file_secret_settings)
        return (
            init_settings,
            _DropEmptyWhenStored(settings_cls, env_settings),
            _DropEmptyWhenStored(settings_cls, dotenv_settings),
            StoreSource(settings_cls),
            file_secret_settings,
        )
