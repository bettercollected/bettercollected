"""Open untrusted documents only inside a sandbox.

Two transports, same result:

``socket`` (production)  the isolated ``document-sandbox`` container, reached
    over a Unix socket (``PDF_IMPORT_SANDBOX_SOCKET``): unprivileged user, no
    network, read-only filesystem, no capabilities, no secrets (#703).
``local`` (development, tests)  a child process of this one: isolated Python,
    scrubbed environment, temporary working directory, resource limits.

With ``require_isolated`` the local transport is refused, and modes that run
native code on the document (``render``) only ever use the socket. The result
is capped by size on both transports: the API and worker processes have no
memory limit of their own. At most ``max_parallel`` documents are in flight
per process.
"""

from __future__ import annotations

import asyncio
from typing import Iterable, Optional

from .analysis import DocumentRefused
from .runner import (
    TooMuchOutput,
    child_command,  # noqa: F401 — re-exported for tests
    child_env,  # noqa: F401 — re-exported for tests
    encode_request,
    read_response,
    run_child,
    too_complex,
)

NATIVE_MODES = ("render",)

_slots: Optional[asyncio.Semaphore] = None
_slots_size = 0


class SandboxUnavailable(Exception):
    """The isolated sandbox could not be reached: retry later, the document is not at fault."""


def _semaphore(size: int) -> asyncio.Semaphore:
    global _slots, _slots_size
    if _slots is None or _slots_size != size:
        _slots, _slots_size = asyncio.Semaphore(max(1, size)), size
    return _slots


async def _over_socket(
    path: str, mode: str, data: bytes, content_type: str, limits: dict
) -> dict:
    header = {"mode": mode, "content_type": content_type, **limits}
    cap = limits["max_result_bytes"]
    try:
        reader, writer = await asyncio.open_unix_connection(path)
    except (
        FileNotFoundError,
        ConnectionRefusedError,
        PermissionError,
        OSError,
    ) as error:
        raise SandboxUnavailable(type(error).__name__) from error
    try:
        writer.write(encode_request(header, data))
        await writer.drain()
        result = await asyncio.wait_for(
            read_response(reader, cap), limits["timeout_s"] + 15
        )
    except TooMuchOutput:
        raise too_complex()
    except asyncio.TimeoutError:
        raise DocumentRefused("timeout", "This document took too long to read.")
    except (
        asyncio.IncompleteReadError,
        ConnectionResetError,
        BrokenPipeError,
        ValueError,
    ) as error:
        raise SandboxUnavailable(type(error).__name__) from error
    finally:
        writer.close()
    if "refused" in result:
        raise DocumentRefused(result["refused"]["code"], result["refused"]["message"])
    return result


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
    max_result_bytes: int = 16 * 1024 * 1024,
    socket_path: str = "",
    require_isolated: bool = False,
) -> dict:
    """The sandbox's result, or raises DocumentRefused (the document) or
    SandboxUnavailable (the sandbox)."""
    limits = dict(
        max_pages=max_pages,
        max_pixels=max_pixels,
        timeout_s=timeout_s,
        memory_mb=memory_mb,
        skip_pages=skip_pages,
        max_result_bytes=max_result_bytes,
    )
    async with _semaphore(max_parallel):
        if socket_path:
            return await _over_socket(socket_path, mode, data, content_type, limits)
        if require_isolated or mode in NATIVE_MODES:
            raise SandboxUnavailable(
                "the isolated document sandbox is required but not configured"
            )
        return await run_child(mode, data, content_type, **limits)


def isolated(socket_path: str) -> bool:
    return bool(socket_path)


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


async def run_layout(data: bytes, skip_pages: Iterable[int] = (), **limits) -> dict:
    """Layout primitives of every page not in ``skip_pages``."""
    return await run_in_sandbox(
        "layout",
        data,
        "application/pdf",
        skip_pages=",".join(str(n) for n in skip_pages),
        **limits,
    )
