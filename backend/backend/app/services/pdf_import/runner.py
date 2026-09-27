"""Run one sandbox child and exchange a document for its result.

Import-safe (no imports from the backend package): used by the backend's
local transport and by the isolated sandbox server (``server.py``), which runs
from the same image in a separate, network-less container.

Also defines the framing both sides of the socket transport speak:

    request   u32 header length | header JSON | u64 document length | document
    response  u64 result length | result JSON
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import sys
import tempfile
from typing import Dict

from .analysis import DocumentRefused

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_child.py")
MODES = ("analyze", "text", "layout", "render")
MAX_HEADER_BYTES = 64 * 1024


def child_env(home: str, render_max_side: int = 1600) -> Dict[str, str]:
    """Everything the child gets from its parent's environment: nothing secret."""
    return {
        "BC_RENDER_MAX_SIDE": str(int(render_max_side)),
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


class TooMuchOutput(Exception):
    pass


async def kill(process) -> None:
    if process.returncode is None:
        process.kill()
    await process.wait()


async def exchange(process, data: bytes, cap: int) -> bytes:
    """Feed the document to the child and read its result, never holding more
    than ``cap`` bytes of it."""

    async def feed():
        try:
            process.stdin.write(data)
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the child stopped reading (refused, or crashed): its output says why
        finally:
            process.stdin.close()

    feeder = asyncio.create_task(feed())
    chunks, total = [], 0
    try:
        while True:
            chunk = await process.stdout.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise TooMuchOutput()
            chunks.append(chunk)
        await process.wait()
    finally:
        await asyncio.gather(feeder, return_exceptions=True)
    return b"".join(chunks)


def too_complex() -> DocumentRefused:
    return DocumentRefused(
        "too_complex", "This document holds more content than a form import can handle."
    )


async def run_child(
    mode: str,
    data: bytes,
    content_type: str,
    *,
    max_pages: int,
    max_pixels: int,
    timeout_s: int,
    memory_mb: int,
    skip_pages: str = "",
    max_result_bytes: int = 16 * 1024 * 1024,
    render_max_side: int = 1600,
) -> dict:
    """The child's JSON result, or raises DocumentRefused (including for
    crashes, timeouts and results larger than ``max_result_bytes``)."""
    if mode not in MODES:
        raise DocumentRefused("unreadable", "Unknown reading mode.")
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
            env=child_env(scratch, render_max_side),
            cwd=scratch,
        )
        try:
            stdout = await asyncio.wait_for(
                exchange(process, data, max_result_bytes), timeout_s
            )
        except asyncio.TimeoutError:
            await kill(process)
            raise DocumentRefused("timeout", "This document took too long to read.")
        except TooMuchOutput:
            await kill(process)
            raise too_complex()
    try:
        result = json.loads(stdout.decode("utf-8") or "{}")
    except ValueError:
        result = {}
    if "refused" in result:
        raise DocumentRefused(result["refused"]["code"], result["refused"]["message"])
    if process.returncode != 0 or not result:
        raise DocumentRefused("unreadable", "This document could not be read.")
    return result


# --- framing -------------------------------------------------------------------


def encode_request(header: dict, data: bytes) -> bytes:
    head = json.dumps(header).encode("utf-8")
    return struct.pack(">I", len(head)) + head + struct.pack(">Q", len(data)) + data


async def read_request(reader: asyncio.StreamReader, max_document: int):
    (head_len,) = struct.unpack(">I", await reader.readexactly(4))
    if head_len > MAX_HEADER_BYTES:
        raise ValueError("header too large")
    header = json.loads((await reader.readexactly(head_len)).decode("utf-8"))
    (doc_len,) = struct.unpack(">Q", await reader.readexactly(8))
    if doc_len > max_document:
        raise ValueError("document too large")
    return header, await reader.readexactly(doc_len)


def encode_response(result: dict) -> bytes:
    body = json.dumps(result, ensure_ascii=False).encode("utf-8")
    return struct.pack(">Q", len(body)) + body


async def read_response(reader: asyncio.StreamReader, cap: int) -> dict:
    (length,) = struct.unpack(">Q", await reader.readexactly(8))
    if length > cap:
        raise TooMuchOutput()
    return json.loads((await reader.readexactly(length)).decode("utf-8"))
