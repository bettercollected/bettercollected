"""Open untrusted documents in a resource-limited subprocess.

``run_analysis`` starts ``_child.py`` as a script in Python's isolated mode,
with a scrubbed environment and a throwaway working directory: the child
never sees the API's secrets (database URIs, storage and AI keys) and never
loads the backend's settings or .env. The child applies its own address-space,
CPU-time and core-dump limits; the parent adds a wall-clock timeout. At most
``max_parallel`` children run at once in a process, whatever the number of
workspaces importing, so a burst of heavy documents cannot exhaust the host.

Not yet enough for native page rendering (the rendering stage adds a
separate user, no network and a syscall filter first).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from typing import Dict, Optional

from .analysis import DocumentRefused

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_child.py")

_slots: Optional[asyncio.Semaphore] = None
_slots_size = 0


def _semaphore(size: int) -> asyncio.Semaphore:
    global _slots, _slots_size
    if _slots is None or _slots_size != size:
        _slots, _slots_size = asyncio.Semaphore(max(1, size)), size
    return _slots


def child_env(home: str) -> Dict[str, str]:
    """Everything the child gets from its parent's environment: nothing secret."""
    return {
        "PATH": os.defpath,
        "HOME": home,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }


def child_command(
    content_type: str, max_pages: int, max_pixels: int, memory_mb: int, cpu_s: int
):
    return [
        sys.executable,
        "-I",  # isolated: ignore PYTHON* variables, user site and the working directory
        CHILD,
        content_type,
        str(max_pages),
        str(max_pixels),
        str(memory_mb),
        str(cpu_s),
    ]


async def run_analysis(
    data: bytes,
    content_type: str,
    *,
    max_pages: int,
    max_pixels: int,
    timeout_s: int,
    memory_mb: int,
    max_parallel: int = 2,
) -> dict:
    """Analysis result, or raises DocumentRefused (including for crashes and timeouts)."""
    async with _semaphore(max_parallel):
        with tempfile.TemporaryDirectory(prefix="bc-import-") as scratch:
            process = await asyncio.create_subprocess_exec(
                *child_command(
                    content_type, max_pages, max_pixels, memory_mb, timeout_s
                ),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=child_env(scratch),
                cwd=scratch,
            )
            try:
                stdout, _ = await asyncio.wait_for(process.communicate(data), timeout_s)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise DocumentRefused("timeout", "This document took too long to read.")
    try:
        result = json.loads(stdout.decode("utf-8") or "{}")
    except ValueError:
        result = {}
    if "refused" in result:
        raise DocumentRefused(result["refused"]["code"], result["refused"]["message"])
    if process.returncode != 0 or "pages" not in result:
        raise DocumentRefused("unreadable", "This document could not be read.")
    return result
