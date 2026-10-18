"""Metadata contracts for data tasks.

Importable by the admin web process: nothing here (or in ``catalog/``) imports a
task implementation, the runner, a database driver or the public application.
A task is split in two on purpose:

* ``catalog/<task>.py`` declares a :class:`TaskMeta` (name, version, parameter
  and result models, declared event codes, ...). The portal lists, validates
  and signs requests from this alone.
* ``impl/<task>.py`` implements :class:`TaskSpec` (``precheck`` and ``run``) and
  is imported only by the runner.

The models are deliberately narrow so a task cannot leak by construction:
parameters never carry secrets (a registry test rejects field names the audit
mask would blank), and results hold only integers, booleans, ids and enums, never
free text.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import (
    Annotated,
    Any,
    Awaitable,
    Callable,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    runtime_checkable,
)

from pydantic import BaseModel, ConfigDict, StringConstraints

TASK_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}(\.[a-z][a-z0-9_]{0,31})?$")
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"
ID_RE = re.compile(ID_PATTERN)
CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
COUNTER_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
RESOURCE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
MAX_EVENT_IDS = 20
MAX_EVENT_COUNTERS = 16
MAX_RESULT_BYTES = 8 * 1024

# A string field of a Result is an id, never prose.
Id = Annotated[str, StringConstraints(pattern=ID_PATTERN)]

# Field names no task parameter may use. Mirrors the audit mask's deny-list
# (services/audit.py ``_DENY``; a test keeps them in step) so a parameter can
# never be a secret that the audit trail would have to blank.
DENY_FIELD_NAME = re.compile(
    r"secret|token|password|passwd|pass(?!ed|ing|port|age|through)|pwd|key|code|otp|hash"
    r"|authorization|auth(?!or)|cookie|seed|private|dsn|url|credential|bearer|jwt"
    r"|session(?!_?id)|signature|salt",
    re.IGNORECASE,
)


class Params(BaseModel):
    """Base for task parameters: unknown fields are refused, instances are
    immutable. Subclass with plain typed fields (no secrets)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Result(BaseModel):
    """Base for task results: ``int``, ``bool``, ids (:data:`Id`) and enums only."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RunState(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    refused = "refused"
    cancelled = "cancelled"
    interrupted = "interrupted"


TERMINAL_STATES = frozenset(
    {
        RunState.succeeded,
        RunState.failed,
        RunState.refused,
        RunState.cancelled,
        RunState.interrupted,
    }
)


class Refusal(Exception):
    """Raised by ``precheck`` (or ``run``) to decline: the run ends ``refused``
    with ``code`` recorded. The code is a short snake_case token, never prose."""

    def __init__(self, code: str):
        if not CODE_RE.match(code or ""):
            raise ValueError("a refusal code is a short snake_case token")
        super().__init__(code)
        self.code = code


class TaskError(Exception):
    """Raised by a task to fail with a declared ``code`` (recorded, with the
    class name; the message is never stored)."""

    def __init__(self, code: str):
        if not CODE_RE.match(code or ""):
            raise ValueError("a task error code is a short snake_case token")
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TaskMeta:
    """Everything the portal needs to know about a task."""

    name: str
    version: int
    params: type[Params]
    result: type[Result]
    events: type[enum.Enum]  # the only codes ``emit`` accepts (str-valued)
    mutating: bool
    resources: tuple[str, ...] = ()  # extra locks, besides ``task:<name>``
    resumable: bool = False
    requires_prior_dry_run: bool = False
    title: str = ""
    refusals: Optional[type[enum.Enum]] = None  # documented ``Refusal`` codes
    internal: bool = field(default=False, compare=False)  # test-only task


@runtime_checkable
class TaskContext(Protocol):
    """What a running task may do. Implemented by the runner."""

    run_id: str
    task: str
    dry_run: bool
    params_hash: str
    requested_by: str
    resumes_run_id: Optional[str]

    async def progress(self, done: int, total: Optional[int] = None) -> None:
        """Report progress; written at most every 2 seconds."""

    async def emit(
        self,
        code: Any,
        counts: Optional[Mapping[str, int]] = None,
        ids: Optional[Sequence[str]] = None,
    ) -> None:
        """Record an event: a declared code, integer counters, at most 20 ids."""

    async def checkpoint(self, cursor: Mapping[str, Any]) -> None:
        """Persist a small resume cursor (at most 2 KB)."""

    async def load_checkpoint(self) -> Optional[dict]:
        """The latest cursor of this run, or of the run it resumes."""

    async def cancelled(self) -> bool:
        """True once cancel was requested or the lease was lost; check between batches."""

    def read_setting(self, name: str) -> Any:
        """Read a setting. Not available until the settings store lands."""

    async def audit(
        self,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        before: Any = None,
        after: Any = None,
        outcome: str = "success",
        detail: Any = None,
    ) -> None:
        """Append an audit row (``actor_kind='system'``, run and requester in detail)."""

    # hook for keyset-fingerprint matching on resume; ``None`` means "none"
    fingerprint: Optional[Callable[[], Awaitable[Optional[str]]]]


@runtime_checkable
class TaskSpec(Protocol):
    """An implementation. ``META`` is its catalog entry."""

    META: TaskMeta

    async def precheck(self, ctx: TaskContext, params: Params) -> None:
        """Raise :class:`Refusal` to decline before anything is locked or changed."""

    async def run(self, ctx: TaskContext, params: Params) -> Result: ...
