"""Registry of task implementations, with the invariants every task must meet."""

from __future__ import annotations

import enum
import inspect
import types
import typing
from dataclasses import dataclass
from typing import Any, Callable, Optional

from backend.admin.tasks.spec import (
    CODE_RE,
    DENY_FIELD_NAME,
    ID_PATTERN,
    RESOURCE_RE,
    TASK_NAME,
    Params,
    Result,
    TaskMeta,
    TaskSpec,
)

RESERVED_EVENT_CODES = ("truncated", "failed", "cancelled")


class RegistryError(ValueError):
    """A task definition breaks a registry rule."""


def _unwrap(annotation: Any) -> list[Any]:
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        return _unwrap(typing.get_args(annotation)[0])
    if origin in (typing.Union, types.UnionType):
        out: list[Any] = []
        for arg in typing.get_args(annotation):
            if arg is not type(None):
                out.extend(_unwrap(arg))
        return out
    return [annotation]


def _annotated_id(annotation: Any) -> bool:
    """``Id`` anywhere inside the annotation (``Optional[Id]`` keeps it nested)."""
    if typing.get_origin(annotation) is typing.Annotated:
        meta = getattr(annotation, "__metadata__", ())
        if any(getattr(m, "pattern", None) == ID_PATTERN for m in meta):
            return True
    return any(_annotated_id(arg) for arg in typing.get_args(annotation))


def _has_id_pattern(field) -> bool:
    return any(
        getattr(m, "pattern", None) == ID_PATTERN for m in field.metadata
    ) or _annotated_id(field.annotation)


def check_params(params: type[Params]) -> None:
    if not (isinstance(params, type) and issubclass(params, Params)):
        raise RegistryError("params must subclass Params")
    if params.model_config.get("extra") != "forbid":
        raise RegistryError("params must forbid extra fields")
    for name in params.model_fields:
        if DENY_FIELD_NAME.search(name):
            raise RegistryError(
                f"parameter name {name!r} looks like a secret; parameters never carry secrets"
            )


def check_result(result: type[Result]) -> None:
    if not (isinstance(result, type) and issubclass(result, Result)):
        raise RegistryError("result must subclass Result")
    for name, field in result.model_fields.items():
        for ann in _unwrap(field.annotation):
            if ann is bool or ann is int:
                continue
            if isinstance(ann, type) and issubclass(ann, Result):
                check_result(ann)  # a nested group of counters obeys the same rules
                continue
            if isinstance(ann, type) and issubclass(ann, enum.Enum):
                continue
            if ann is str and _has_id_pattern(field):
                continue
            raise RegistryError(
                f"result field {name!r} must be int, bool, an enum or an Id (no free text)"
            )


def check_meta(meta: TaskMeta) -> None:
    if not TASK_NAME.match(meta.name):
        raise RegistryError("task name must be lowercase snake_case, optionally dotted once")
    if not isinstance(meta.version, int) or isinstance(meta.version, bool) or meta.version < 1:
        raise RegistryError("task version must be a positive integer")
    if not (isinstance(meta.events, type) and issubclass(meta.events, enum.Enum)):
        raise RegistryError("events must be an Enum of declared event codes")
    for member in meta.events:
        if not isinstance(member.value, str) or not CODE_RE.match(member.value):
            raise RegistryError("event codes are short snake_case strings")
        if member.value in RESERVED_EVENT_CODES:
            raise RegistryError("event code is reserved by the runner")
    for res in meta.resources:
        if not RESOURCE_RE.match(res) or res.startswith(("task:", "mutating:")):
            raise RegistryError(
                "resource names are plain tokens (task: and mutating: are reserved)"
            )
    if meta.requires_prior_dry_run and not meta.mutating:
        raise RegistryError("only a mutating task needs a prior dry run")
    check_params(meta.params)
    check_result(meta.result)


@dataclass(frozen=True)
class Registered:
    meta: TaskMeta
    impl: TaskSpec


class Registry:
    def __init__(self) -> None:
        self._tasks: dict[str, Registered] = {}

    def register(self, meta: TaskMeta, impl: TaskSpec) -> None:
        check_meta(meta)
        if meta.name in self._tasks:
            raise RegistryError(f"task {meta.name!r} is already registered")
        for method in ("precheck", "run"):
            if not inspect.iscoroutinefunction(getattr(impl, method, None)):
                raise RegistryError(f"{method} must be an async method")
        self._tasks[meta.name] = Registered(meta, impl)

    def task(self, meta: TaskMeta) -> Callable[[type], type]:
        """Class decorator: ``@registry.task(META)`` registers an instance."""

        def decorate(cls: type) -> type:
            self.register(meta, cls())
            return cls

        return decorate

    def get(self, name: str) -> Optional[Registered]:
        return self._tasks.get(name)

    def names(self) -> list[str]:
        return sorted(self._tasks)

    def __contains__(self, name: str) -> bool:
        return name in self._tasks

    def __len__(self) -> int:
        return len(self._tasks)
