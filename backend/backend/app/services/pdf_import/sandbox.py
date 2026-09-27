"""Open untrusted documents in a resource-limited subprocess.

``run_analysis`` starts ``python -m backend.app.services.pdf_import.sandbox``
with an address-space and CPU-time limit and a wall-clock timeout; the child
reads the document from stdin and prints JSON. A malicious or broken file can
exhaust the child, never the API or worker process that asked.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from backend.app.services.pdf_import.analysis import (
    DocumentRefused,
    analyze_image,
    analyze_pdf,
)

PDF_TYPES = {"application/pdf"}


def _limits(memory_mb: int, cpu_s: int):
    def apply():
        import resource

        memory = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 5))
        os.setsid()

    return apply


async def run_analysis(
    data: bytes,
    content_type: str,
    *,
    max_pages: int,
    max_pixels: int,
    timeout_s: int,
    memory_mb: int,
) -> dict:
    """Analysis result, or raises DocumentRefused (including for crashes and timeouts)."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "backend.app.services.pdf_import.sandbox",
        content_type,
        str(max_pages),
        str(max_pixels),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=_limits(memory_mb, timeout_s),
    )
    try:
        stdout, _stderr = await asyncio.wait_for(process.communicate(data), timeout_s)
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


def _main(argv) -> int:
    content_type, max_pages, max_pixels = argv[0], int(argv[1]), int(argv[2])
    data = sys.stdin.buffer.read()
    try:
        if content_type in PDF_TYPES:
            result = analyze_pdf(data, max_pages)
        else:
            result = analyze_image(data, max_pixels)
    except DocumentRefused as refused:
        result = {"refused": {"code": refused.code, "message": refused.message}}
    except MemoryError:
        result = {
            "refused": {
                "code": "too_large",
                "message": "This document is too large to read.",
            }
        }
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
