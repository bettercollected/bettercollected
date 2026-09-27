"""Open untrusted documents in a resource-limited subprocess.

``run_in_sandbox`` starts ``_child.py`` as a script in Python's isolated mode,
with a scrubbed environment and a throwaway working directory: the child
never sees the API's secrets (database URIs, storage and AI keys) and never
loads the backend's settings or .env. The child applies its own address-space,
CPU-time and core-dump limits; the parent adds a wall-clock timeout. At most
``max_parallel`` children run at once in a process, whatever the number of
workspaces importing, so a burst of heavy documents cannot exhaust the host.

Modes: ``analyze`` (page signals and routes) and ``text`` (the text layer).
Not yet enough for native page rendering (#703: separate user, no network and
a syscall filter come first).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from typing import Dict, Iterable, Optional

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
    content_type: str,
    max_pages: int,
    max_pixels: int,
    memory_mb: int,
    cpu_s: int,
    mode: str = "analyze",
    skip_pages: str = "",
):
    return [
        sys.executable,
        "-I",  # isolated: ignore PYTHON* variables, user site and the working directory
        CHILD,
        mode,
        content_type,
        str(max_pages),
        str(max_pixels),
        str(memory_mb),
        str(cpu_s),
        skip_pages,
    ]


async def run_in_sandbox(
    mode: str,
    data: bytes,
    content_type: str,
    *,
    max_pages: int,
    max_pixels: int,
    timeout_s: int,
    memory_mb: int,
    max_parallel: int = 2,
    skip_pages: str = "",
) -> dict:
    """The child's JSON result, or raises DocumentRefused (including for
    crashes and timeouts)."""
    async with _semaphore(max_parallel):
        with tempfile.TemporaryDirectory(prefix="bc-import-") as scratch:
            process = await asyncio.create_subprocess_exec(
                *child_command(
                    content_type,
                    max_pages,
                    max_pixels,
                    memory_mb,
                    timeout_s,
                    mode,
                    skip_pages,
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
    if process.returncode != 0 or not result:
        raise DocumentRefused("unreadable", "This document could not be read.")
    return result


async def run_analysis(data: bytes, content_type: str, **limits) -> dict:
    """Page signals and routes."""
    result = await run_in_sandbox("analyze", data, content_type, **limits)
    if "pages" not in result:
        raise DocumentRefused("unreadable", "This document could not be read.")
    return result


async def run_text_layer(data: bytes, skip_pages: Iterable[int] = (), **limits) -> dict:
    """Words of every page not in ``skip_pages``, legacy fonts decoded."""
    return await run_in_sandbox(
        "text",
        data,
        "application/pdf",
        skip_pages=",".join(str(n) for n in skip_pages),
        **limits,
    )
