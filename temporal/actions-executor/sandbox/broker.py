"""The broker: the executor's side of a sandboxed run.

For each run of custom action code it starts one child (``child.py``) with an
empty environment, an empty working directory and only a pipe pair, waits for
the child to report that it confined itself, sends it the code and the data of
this run, and answers its calls. Every effect the code has on the world (an
HTTP request, a mail, a spreadsheet row) is a call the broker's handler table
performs, after its own checks; the child holds no secret, no key and no
network. The broker never trusts the child's words: a line that is not the
protocol, a call to a name that is not in the table, more calls than the quota,
a child that does not confine itself, or one that outlives its time, ends the
run and the child.

The confinement is the kernel's (``confine.py``); it needs no container flag.
With a filesystem the child cannot cut away (neither root for ``chroot`` nor
Landlock), the broker refuses to send it any code.
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from sandbox.confine import _libc, PR_SET_DUMPABLE

logger = logging.getLogger(__name__)

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "child.py")
MAX_LINE = 8 * 1024 * 1024
READY_TIMEOUT_SECONDS = 15

Handler = Callable[..., Union[Any, Awaitable[Any]]]


class SandboxUnavailable(Exception):
    """The child could not be started or did not confine itself as required.
    Nothing was run. The message names facts (steps), never data."""


class CallRefused(Exception):
    """A handler's refusal: ``status`` and a message the code may read."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Outcome:
    """What a run came to."""

    log: List[str] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None
    calls: int = 0
    facts: Dict[str, Any] = field(default_factory=dict)


def harden_parent() -> None:
    """Make this process non-dumpable: its ``/proc`` entries (environment,
    memory) are no longer readable by another process of the same user."""
    try:
        _libc().prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)
    except Exception:  # noqa: BLE001 - best effort, the child has no file access
        logger.warning("could not make the executor process non-dumpable")


def child_env() -> Dict[str, str]:
    """Everything the child gets from this process's environment: nothing."""
    return {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "random",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def required_confinement(facts: Dict[str, Any], require_filesystem: bool) -> List[str]:
    """The confinement steps the child did not report (empty when all held)."""
    missing = []
    if facts.get("error"):
        missing.append("confinement")
    for step in ("rlimits", "no_new_privs", "seccomp", "unprivileged"):
        if facts.get(step) is not True:
            missing.append(step)
    if require_filesystem and facts.get("filesystem") in (None, "none"):
        missing.append("filesystem")
    return missing


async def _readline(process, timeout: float) -> Optional[dict]:
    try:
        line = await asyncio.wait_for(process.stdout.readline(), timeout)
    except (asyncio.LimitOverrunError, ValueError):
        return None
    if not line:
        return None
    try:
        message = json.loads(line)
    except ValueError:
        return None
    return message if isinstance(message, dict) else None


async def _write(process, message: dict) -> None:
    process.stdin.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
    await process.stdin.drain()


async def _kill(process) -> None:
    if process.returncode is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                process.kill()
            except ProcessLookupError:
                pass
    try:
        await asyncio.wait_for(process.wait(), 5)
    except asyncio.TimeoutError:
        logger.error("a sandbox child did not end after SIGKILL")


def _ended(process) -> Dict[str, Any]:
    """The error of a child that ended without reporting."""
    code = process.returncode
    if code is not None and code < 0:
        name = (
            signal.Signals(-code).name if -code in set(signal.Signals) else str(-code)
        )
        kind = "cpu_limit" if name == "SIGXCPU" else "killed"
        return {"kind": kind, "message": f"the code was stopped ({name})"}
    return {"kind": "killed", "message": "the code ended without a result"}


async def run_code(
    code: str,
    data: Dict[str, Any],
    handlers: Dict[str, Handler],
    *,
    memory_mb: int = 256,
    cpu_seconds: int = 10,
    timeout_seconds: float = 30,
    max_calls: int = 20,
    max_log_bytes: int = 64 * 1024,
    require_filesystem: bool = True,
    _unvalidated_for_tests: bool = False,
) -> Outcome:
    """Run ``code`` with ``data`` in a fresh confined child; ``handlers`` are the
    only calls it can make (each takes the call's arguments as keywords and
    returns JSON data, or raises :class:`CallRefused`). Raises
    :class:`SandboxUnavailable` when nothing could be run."""
    scratch = tempfile.mkdtemp(prefix="bc-action-")
    os.chmod(scratch, 0o700)
    process = None
    outcome = Outcome()
    try:
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                CHILD,
                str(int(memory_mb)),
                str(int(cpu_seconds)),
                scratch,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=child_env(),
                cwd=scratch,
                start_new_session=True,
                limit=MAX_LINE + 1,
            )
        except OSError as error:
            raise SandboxUnavailable(
                f"the child did not start ({type(error).__name__})"
            )

        ready = await _readline(process, READY_TIMEOUT_SECONDS)
        if ready is None or ready.get("t") != "ready":
            raise SandboxUnavailable("the child did not report that it is confined")
        outcome.facts = ready.get("facts") or {}
        missing = required_confinement(outcome.facts, require_filesystem)
        if missing:
            raise SandboxUnavailable("not confined: " + ", ".join(missing))

        await _write(
            process,
            {
                "t": "run",
                "code": code,
                "data": data,
                "max_log_bytes": max_log_bytes,
                "validate": not _unvalidated_for_tests,
            },
        )

        async def serve() -> None:
            while True:
                message = await _readline(process, timeout_seconds)
                if message is None:
                    try:
                        await asyncio.wait_for(process.wait(), 2)
                    except asyncio.TimeoutError:
                        pass
                    outcome.error = _ended(process)
                    return
                kind = message.get("t")
                if kind == "done":
                    outcome.log = [str(line) for line in message.get("log") or []]
                    outcome.error = message.get("error")
                    return
                if kind != "call":
                    outcome.error = {"kind": "killed", "message": "protocol violation"}
                    return
                outcome.calls += 1
                if outcome.calls > max_calls:
                    outcome.error = {
                        "kind": "quota",
                        "message": "the code made too many outside calls",
                    }
                    return
                await _write(process, await _answer(message, handlers))

        try:
            await asyncio.wait_for(serve(), timeout_seconds)
        except asyncio.TimeoutError:
            outcome.error = {"kind": "timeout", "message": "the code took too long"}
        return outcome
    finally:
        if process is not None:
            await _kill(process)
        shutil.rmtree(scratch, ignore_errors=True)


async def _answer(message: dict, handlers: Dict[str, Handler]) -> dict:
    call_id = message.get("id")
    name = message.get("m")
    arguments = message.get("a")
    handler = handlers.get(name) if isinstance(name, str) else None
    if handler is None or not isinstance(arguments, dict):
        return {
            "t": "ret",
            "id": call_id,
            "ok": False,
            "status": 400,
            "e": "unknown call",
        }
    try:
        result = handler(**arguments)
        if asyncio.iscoroutine(result):
            result = await result
        return {"t": "ret", "id": call_id, "ok": True, "v": result}
    except CallRefused as refused:
        return {
            "t": "ret",
            "id": call_id,
            "ok": False,
            "status": refused.status,
            "e": refused.message,
        }
    except TypeError:
        return {
            "t": "ret",
            "id": call_id,
            "ok": False,
            "status": 400,
            "e": "bad arguments",
        }
    except Exception as error:  # noqa: BLE001 - the class only, never a message
        logger.warning(
            "an outside call of action code failed: %s", type(error).__name__
        )
        return {
            "t": "ret",
            "id": call_id,
            "ok": False,
            "status": 502,
            "e": "the call failed",
        }


async def probe(require_filesystem: bool = True) -> Dict[str, Any]:
    """Start a child that does nothing and report how it confined itself (for the
    start-up log). Raises :class:`SandboxUnavailable` when it could not."""
    outcome = await run_code(
        "", {}, {}, timeout_seconds=20, require_filesystem=require_filesystem
    )
    return outcome.facts
