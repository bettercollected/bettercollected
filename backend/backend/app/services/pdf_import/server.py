"""The isolated document sandbox: ``python -I server.py <socket path>``.

Runs in its own container (see docker-compose.deployment.yml,
``document-sandbox``): an unprivileged user, no network, a read-only
filesystem, all capabilities dropped, a seccomp syscall allowlist
(deploy/seccomp/document-sandbox.json), no environment file. It listens on a
Unix socket on a volume shared with the backend and the jobs worker, and runs
each request in the usual child (isolated Python, scrubbed environment,
resource limits, timeout). It never imports the backend package, so it holds
no settings and no secrets.

Environment (all optional): DOC_SANDBOX_PARALLEL (children at once, 2),
DOC_SANDBOX_MAX_DOCUMENT_BYTES (largest accepted document, 32 MB).
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdf_import.analysis import DocumentRefused  # noqa: E402
from pdf_import.runner import (  # noqa: E402
    encode_response,
    read_request,
    run_child,
)

PARALLEL = int(os.environ.get("DOC_SANDBOX_PARALLEL", "2"))
MAX_DOCUMENT = int(
    os.environ.get("DOC_SANDBOX_MAX_DOCUMENT_BYTES", str(32 * 1024 * 1024))
)
# the server's own ceilings: a request cannot ask for more than these
CEILING = {
    "max_pages": 50,
    "max_pixels": 100_000_000,
    "timeout_s": 300,
    "memory_mb": 2048,
    "max_result_bytes": 64 * 1024 * 1024,
    "render_max_side": 2400,
}
_slots = asyncio.Semaphore(max(1, PARALLEL))


def _limits(header: dict) -> dict:
    limits = {}
    for key, ceiling in CEILING.items():
        value = int(header.get(key, ceiling))
        limits[key] = max(1, min(value, ceiling))
    return limits


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        try:
            header, data = await asyncio.wait_for(
                read_request(reader, MAX_DOCUMENT), 60
            )
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ValueError):
            result = {
                "refused": {
                    "code": "unreadable",
                    "message": "This document could not be read.",
                }
            }
        else:
            async with _slots:
                try:
                    result = await run_child(
                        str(header.get("mode", "")),
                        data,
                        str(header.get("content_type", "")),
                        skip_pages=str(header.get("skip_pages", "")),
                        **_limits(header),
                    )
                except DocumentRefused as refused:
                    result = {
                        "refused": {"code": refused.code, "message": refused.message}
                    }
        writer.write(encode_response(result))
        await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        writer.close()


async def main(path: str) -> None:
    if os.path.exists(path):
        os.unlink(path)
    server = await asyncio.start_unix_server(handle, path=path)
    os.chmod(path, 0o660)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
