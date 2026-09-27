"""The isolated transport: a document-sandbox server on a Unix socket gives
the same results as the local child, refuses what the child refuses, caps its
output, survives malformed requests, and is required where configured."""

import asyncio
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

from backend.app.services.pdf_import import sandbox
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.sandbox import (
    SandboxUnavailable,
    run_analysis,
    run_in_sandbox,
    run_text_layer,
)
from tests.app.pdf_import import documents

pytestmark = pytest.mark.asyncio
LIMITS = dict(
    max_pages=30, max_pixels=60_000_000, timeout_s=60, memory_mb=1536, max_parallel=2
)
SERVER = pathlib.Path(sandbox.__file__).parent / "server.py"


@pytest.fixture(scope="module")
def socket_path():
    folder = tempfile.mkdtemp(prefix="bc-sandbox-")
    path = os.path.join(folder, "sandbox.sock")
    process = subprocess.Popen(
        [sys.executable, "-I", str(SERVER), path],
        env={"PATH": os.defpath, "DOC_SANDBOX_PARALLEL": "2"},
        cwd=folder,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(100):
        if os.path.exists(path):
            break
        import time

        time.sleep(0.05)
    yield path
    process.terminate()
    process.wait(timeout=10)


async def test_same_result_as_the_local_child(socket_path):
    over_socket = await run_analysis(
        documents.fillable_pdf(), "application/pdf", socket_path=socket_path, **LIMITS
    )
    local = await run_analysis(documents.fillable_pdf(), "application/pdf", **LIMITS)
    assert over_socket == local and over_socket["pages"][0]["route"] == "widgets"
    words = await run_text_layer(
        documents.text_pdf(), socket_path=socket_path, **LIMITS
    )
    assert [w["text"] for w in words["pages"][0]["words"]][:2] == [
        "Application",
        "form",
    ]


async def test_refusals_and_the_output_cap_cross_the_socket(socket_path):
    with pytest.raises(DocumentRefused) as raised:
        await run_analysis(
            documents.encrypted_pdf(),
            "application/pdf",
            socket_path=socket_path,
            **LIMITS,
        )
    assert raised.value.code == "encrypted"
    with pytest.raises(DocumentRefused) as raised:
        await run_text_layer(
            documents.text_pdf(pages=3),
            socket_path=socket_path,
            max_result_bytes=500,
            **LIMITS,
        )
    assert raised.value.code == "too_complex"


async def test_the_server_survives_malformed_requests(socket_path):
    reader, writer = await asyncio.open_unix_connection(socket_path)
    writer.write(b"\xff\xff\xff\xffgarbage")
    await writer.drain()
    writer.write_eof()
    reply = await reader.read()
    writer.close()
    assert b"unreadable" in reply
    # and keeps serving
    result = await run_analysis(
        documents.text_pdf(), "application/pdf", socket_path=socket_path, **LIMITS
    )
    assert result["page_count"] == 1


async def test_unreachable_or_required_sandbox_is_unavailable_not_a_refusal():
    with pytest.raises(SandboxUnavailable):
        await run_analysis(
            documents.text_pdf(),
            "application/pdf",
            socket_path="/nonexistent/sandbox.sock",
            **LIMITS,
        )
    with pytest.raises(SandboxUnavailable):
        await run_analysis(
            documents.text_pdf(), "application/pdf", require_isolated=True, **LIMITS
        )
    # native rendering never runs in a local child
    with pytest.raises(SandboxUnavailable):
        await run_in_sandbox(
            "render", documents.text_pdf(), "application/pdf", **LIMITS
        )


def test_server_modules_never_import_the_backend_package():
    folder = pathlib.Path(sandbox.__file__).parent
    for name in ("server.py", "runner.py"):
        source = (folder / name).read_text()
        assert "from backend" not in source and "import backend" not in source, name
