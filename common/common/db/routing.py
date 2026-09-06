"""The seam between the application and its stores (plans/postgres-consolidation.md §6).

Every repository the container hands out is a :class:`RoutingRepository`: a
proxy over the Mongo implementation and, once it exists, the Postgres one.
Method calls are dispatched by the flags for the repository's group:

* **writes** (methods marked with :func:`write_op`) go to the primary store;
  the mirror store is then brought in line, bounded by a timeout and never
  allowed to fail the request — a failure is counted, logged (redacted) and
  handed to ``on_mirror_failure`` for the outbox. By default the mirror
  re-executes the call with the same arguments, which is only correct when
  the call is deterministic in them; a write that mints state the caller did
  not pass in (a new document's id, an invitation token) must be marked
  ``@write_op(replay=True)`` and return the persisted document(s) — the
  mirror then stores *those*, so both stores hold the same document;
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
REPLAY_MARKER = "__bc_replay__"


def write_op(fn=None, *, replay: bool = False):
    """Mark a repository method as a write. Unmarked methods are reads.

    ``replay=True`` declares that the method returns the document(s) it
    persisted and that the mirror must store that result rather than re-run
    the method (see the module docstring). Usable bare or with arguments.
    """

    def mark(f):
        setattr(f, WRITE_MARKER, True)
        setattr(f, REPLAY_MARKER, replay)
        return f

    return mark if fn is None else mark(fn)


def is_write_op(fn) -> bool:
    return bool(getattr(fn, WRITE_MARKER, False))


def is_replayed(fn) -> bool:
    return bool(getattr(fn, REPLAY_MARKER, False))


@dataclass
class WriteResult:
    """Returned by a ``replay=True`` write whose return value is not what it
    persisted — e.g. a document handed back decrypted while the stored copy is
    encrypted. The mirror stores ``documents``; the caller receives ``value``."""

    value: Any
    documents: list


def persisted_documents(result: Any) -> list:
    """The persisted document(s) in a replayed write's result: a document with
    an id, a list/tuple of them, or a :class:`WriteResult`. Anything else
    yields ``[]`` and the mirror falls back to re-executing the call."""
    if isinstance(result, WriteResult):
        return list(result.documents)

    def is_doc(v: Any) -> bool:
        return getattr(v, "id", None) is not None and callable(getattr(v, "save", None))

    if is_doc(result):
        return [result]
    if isinstance(result, (list, tuple)) and result and all(is_doc(v) for v in result):
        return list(result)
    return []


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
    documents: tuple = ()  # what a replayed write tried to store on the mirror


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
    if isinstance(value, WriteResult):
        return normalise_result(value.value)
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
            if is_write_op(attr):
                return self._write(name, replay=is_replayed(attr))
            return self._read(name)
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

    def _write(self, name: str, *, replay: bool):
        async def method(*args, **kwargs):
            self._metrics.calls[(self._group, name)] += 1
            primary = self._flags.primary_store(self._group)
            result = await self._impl(primary, name)(*args, **kwargs)
            mirror = self._flags.mirror_store(self._group)
            if mirror is not None and self._stores[mirror] is not None:
                documents = persisted_documents(result) if replay else []
                await self._mirror(name, mirror, args, kwargs, documents)
            return result.value if isinstance(result, WriteResult) else result

        return method

    async def _replay(self, store: ReadSource, documents: list) -> None:
        impl = self._stores[store]
        hook = getattr(impl, "replay_write", None)
        if hook is not None:
            await hook(documents)
            return
        for document in documents:  # a Beanie repository: save() is an upsert by id
            await document.save()

    async def _mirror(
        self, name: str, store: ReadSource, args, kwargs, documents: list = ()
    ) -> None:
        try:
            if documents:
                coro = self._replay(store, documents)
            else:
                coro = self._impl(store, name)(*args, **kwargs)
            await asyncio.wait_for(coro, timeout=self._mirror_timeout_s)
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
                            tuple(documents),
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
