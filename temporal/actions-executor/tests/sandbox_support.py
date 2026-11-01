"""Shared helpers of the sandbox tests: run code through the real child, and
skip when this machine's kernel cannot confine one (no Landlock, not root)."""

import asyncio

import pytest

from sandbox import broker, confine


def run(code, data=None, handlers=None, unvalidated=False, **limits):
    limits.setdefault("timeout_seconds", 20)
    return asyncio.run(
        broker.run_code(
            code,
            data or {},
            handlers or {},
            _unvalidated_for_tests=unvalidated,
            **limits,
        )
    )


def can_confine() -> bool:
    try:
        asyncio.run(broker.probe())
    except broker.SandboxUnavailable:
        return False
    return True


needs_confinement = pytest.mark.skipif(
    not can_confine(),
    reason="this kernel cannot confine the sandbox child (no Landlock, not root)",
)
