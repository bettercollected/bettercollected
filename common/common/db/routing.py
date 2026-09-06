"""The seam between the application and its stores (plans/postgres-consolidation.md §6).

Every repository the container hands out is a :class:`RoutingRepository`: a
proxy over the Mongo implementation and, once it exists, the Postgres one.
Method calls are dispatched by the flags for the repository's group:

* **writes** (methods marked with :func:`write_op`) go to the primary store;
  the same call is then replayed on the mirror store, bounded by a timeout
  and never allowed to fail the request — a failure is counted, logged
  (redacted) and handed to ``on_mirror_failure`` for the outbox;
* **reads** go to the read source; with ``DB_SHADOW_READ_SAMPLE`` > 0 a
  sample is also issued to the other store and the results compared.

With only a Mongo implementation registered and the default flags this is a
transparent pass-through, which is how R1 ships before the first Postgres
repository lands.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel

from common.db.flags import DbFlags, ReadSource

logger = logging.getLogger(__name__)

WRITE_MARKER = "__bc_write__"


def write_op(fn):
    """Mark a repository method as a write. Unmarked methods are reads."""
    setattr(fn, WRITE_MARKER, True)
    return fn


def is_write_op(fn) -> bool:
    return bool(getattr(fn, WRITE_MARKER, False))


class RoutingError(RuntimeError):
    """The flags ask for a store this repository has no implementation of."""


@dataclass
class MirrorFailure:
    group: str
    repository: str
    method: str
    store: ReadSource
    args: tuple
    kwargs: dict
    error: BaseException


@dataclass
class ShadowDiff:
    group: str
    repository: str
    method: str
    source: ReadSource
    other: ReadSource
    args: tuple
    kwargs: dict


@dataclass
class RoutingMetrics:
    calls: Counter = field(default_factory=Counter)
    mirror_failures: Counter = field(default_factory=Counter)
    shadow_reads: Counter = field(default_factory=Counter)
    shadow_diffs: Counter = field(default_factory=Counter)
    shadow_errors: Counter = field(default_factory=Counter)


def normalise_result(value: Any) -> Any:
    """Shape a repository result for comparison: models to plain JSON data."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): normalise_result(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalise_result(v) for v in value]
    return value


def results_equal(a: Any, b: Any) -> bool:
    return normalise_result(a) == normalise_result(b)


class RoutingRepository:
    def __init__(
        self,
        *,
        group: str,
        flags: DbFlags,
        mongo: Any = None,
        postgres: Any = None,
        mirror_timeout_s: float = 2.0,
        on_mirror_failure: Optional[Callable[[MirrorFailure], Any]] = None,
        on_shadow_diff: Optional[Callable[[ShadowDiff], Any]] = None,
        comparator: Callable[[Any, Any], bool] = results_equal,
        metrics: Optional[RoutingMetrics] = None,
    ):
        if mongo is None and postgres is None:
            raise RoutingError(f"{group}: no store implementation given")
        self._group = group
        self._flags = flags
        self._stores = {ReadSource.MONGO: mongo, ReadSource.POSTGRES: postgres}
        self._mirror_timeout_s = mirror_timeout_s
        self._on_mirror_failure = on_mirror_failure
        self._on_shadow_diff = on_shadow_diff
        self._comparator = comparator
        self._metrics = metrics or RoutingMetrics()
        self._surface = mongo if mongo is not None else postgres
        self._repository = type(self._surface).__name__
        self._check_configuration()

    # -- configuration ---------------------------------------------------
    def _check_configuration(self) -> None:
        needed = set()
        needed.add(self._flags.read_source(self._group))
        needed.add(self._flags.primary_store(self._group))
        mirror = self._flags.mirror_store(self._group)
        if mirror is not None:
            needed.add(mirror)
        missing = [s.value for s in needed if self._stores[s] is None]
        if missing:
            raise RoutingError(
                f"group {self._group!r} ({self._repository}): flags require the "
                f"{', '.join(missing)} store but no implementation is registered"
            )

    @property
    def group(self) -> str:
        return self._group

    @property
    def metrics(self) -> RoutingMetrics:
        return self._metrics

    def store(self, source: ReadSource) -> Any:
        return self._stores[source]

    # -- dispatch ----------------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        attr = getattr(self._surface, name)
        if not callable(attr):
            return attr
        if inspect.iscoroutinefunction(attr):
            return self._write(name) if is_write_op(attr) else self._read(name)
        return self._sync(name)

    def _impl(self, source: ReadSource, name: str):
        return getattr(self._stores[source], name)

    def _sync(self, name: str):
        def method(*args, **kwargs):
            self._metrics.calls[(self._group, name)] += 1
            return self._impl(self._flags.read_source(self._group), name)(
                *args, **kwargs
            )

        return method

    def _read(self, name: str):
        async def method(*args, **kwargs):
            self._metrics.calls[(self._group, name)] += 1
            source = self._flags.read_source(self._group)
            result = await self._impl(source, name)(*args, **kwargs)
            other = (
                ReadSource.POSTGRES if source is ReadSource.MONGO else ReadSource.MONGO
            )
            if self._stores[other] is not None and self._flags.should_shadow_read():
                await self._shadow(name, source, other, result, args, kwargs)
            return result

        return method

    def _write(self, name: str):
        async def method(*args, **kwargs):
            self._metrics.calls[(self._group, name)] += 1
            primary = self._flags.primary_store(self._group)
            result = await self._impl(primary, name)(*args, **kwargs)
            mirror = self._flags.mirror_store(self._group)
            if mirror is not None and self._stores[mirror] is not None:
                await self._mirror(name, mirror, args, kwargs)
            return result

        return method

    async def _mirror(self, name: str, store: ReadSource, args, kwargs) -> None:
        try:
            await asyncio.wait_for(
                self._impl(store, name)(*args, **kwargs), timeout=self._mirror_timeout_s
            )
        except (
            BaseException
        ) as exc:  # noqa: BLE001 — the mirror must never fail the request
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            self._metrics.mirror_failures[(self._group, name)] += 1
            logger.warning(
                "mirror write failed: group=%s repository=%s method=%s store=%s error=%s",
                self._group,
                self._repository,
                name,
                store.value,
                type(exc).__name__,
            )
            if self._on_mirror_failure is not None:
                try:
                    maybe = self._on_mirror_failure(
                        MirrorFailure(
                            self._group,
                            self._repository,
                            name,
                            store,
                            args,
                            kwargs,
                            exc,
                        )
                    )
                    if inspect.isawaitable(maybe):
                        await maybe
                except Exception as hook_exc:  # noqa: BLE001
                    logger.warning(
                        "mirror failure hook raised: {}", type(hook_exc).__name__
                    )

    async def _shadow(self, name, source, other, result, args, kwargs) -> None:
        self._metrics.shadow_reads[(self._group, name)] += 1
        try:
            other_result = await asyncio.wait_for(
                self._impl(other, name)(*args, **kwargs), timeout=self._mirror_timeout_s
            )
        except Exception as exc:  # noqa: BLE001
            self._metrics.shadow_errors[(self._group, name)] += 1
            logger.warning(
                "shadow read failed: group=%s repository=%s method=%s store=%s error=%s",
                self._group,
                self._repository,
                name,
                other.value,
                type(exc).__name__,
            )
            return
        try:
            equal = self._comparator(result, other_result)
        except Exception:  # noqa: BLE001 — an uncomparable result counts as a diff
            equal = False
        if not equal:
            self._metrics.shadow_diffs[(self._group, name)] += 1
            logger.warning(
                "shadow read differs: group=%s repository=%s method=%s source=%s other=%s",
                self._group,
                self._repository,
                name,
                source.value,
                other.value,
            )
            if self._on_shadow_diff is not None:
                try:
                    maybe = self._on_shadow_diff(
                        ShadowDiff(
                            self._group,
                            self._repository,
                            name,
                            source,
                            other,
                            args,
                            kwargs,
                        )
                    )
                    if inspect.isawaitable(maybe):
                        await maybe
                except Exception as hook_exc:  # noqa: BLE001
                    logger.warning(
                        "shadow diff hook raised: {}", type(hook_exc).__name__
                    )
