"""Entry point of the sandbox child. Run as a script in isolated mode
(``python -I _child.py``), so it imports only the analysis modules and never
the backend package, its settings or its .env file.

Resource limits are applied here, first thing, rather than via ``preexec_fn``
in the parent (which is unsafe once the parent has threads).
"""

import json
import os
import sys


def _apply_limits(memory_mb: int, cpu_s: int) -> None:
    import resource

    memory = memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 5))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        os.setsid()
    except OSError:
        pass


def main(argv) -> int:
    content_type, max_pages, max_pixels, memory_mb, cpu_s = (
        argv[0],
        int(argv[1]),
        int(argv[2]),
        int(argv[3]),
        int(argv[4]),
    )
    _apply_limits(memory_mb, cpu_s)
    # the package directory's parent, so "pdf_import" imports as a top-level package
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from pdf_import.analysis import DocumentRefused, analyze_image, analyze_pdf

        data = sys.stdin.buffer.read()
        try:
            if content_type == "application/pdf":
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
    sys.exit(main(sys.argv[1:]))
