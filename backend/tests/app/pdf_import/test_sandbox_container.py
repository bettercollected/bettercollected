"""The document-sandbox container with its seccomp profile (#703), for real.

Starts the backend image the way the compose files run ``document-sandbox``
(no network, read-only, no capabilities, no-new-privileges, the profile in
deploy/seccomp/document-sandbox.json), reads the synthetic documents in every
mode over the socket, and checks from inside the container that what the
profile denies fails with EPERM.

Skipped unless docker and the image are available. Build the image first:

    docker build -f backend/Dockerfile -t bettercollected/backend:sandbox-test .

(``DOC_SANDBOX_IMAGE`` selects another tag.)
"""

import base64
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import uuid

import pytest

from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.sandbox import (
    run_analysis,
    run_layout,
    run_render,
    run_text_layer,
)
from tests.app.pdf_import import documents

IMAGE = os.environ.get("DOC_SANDBOX_IMAGE", "bettercollected/backend:sandbox-test")
PROFILE = (
    pathlib.Path(__file__).resolve().parents[4]
    / "deploy"
    / "seccomp"
    / "document-sandbox.json"
)
PYTHON = "/api/backend/.venv/bin/python"
SERVER = "/api/backend/backend/app/services/pdf_import/server.py"
LIMITS = dict(
    max_pages=30, max_pixels=60_000_000, timeout_s=60, memory_mb=1536, max_parallel=2
)


def _image_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return (
        subprocess.run(
            ["docker", "image", "inspect", IMAGE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


pytestmark = pytest.mark.skipif(
    not _image_available(), reason=f"needs docker and the {IMAGE} image"
)


def _hardened(name: str, *extra: str) -> list:
    return [
        "docker",
        "run",
        "--name",
        name,
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:size=256m,noexec,nosuid,nodev",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--pids-limit",
        "64",
        *extra,
    ]


@pytest.fixture(scope="module")
def container():
    # short path (AF_UNIX paths are limited to 108 bytes); the container runs
    # as this user, so it can create the socket and this test can open it
    folder = tempfile.mkdtemp(prefix="bcsbx-")
    name = f"bc-doc-sandbox-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        _hardened(
            name,
            "-d",
            "--security-opt",
            f"seccomp={PROFILE}",
            "-e",
            "DOC_SANDBOX_PARALLEL=2",
            "-v",
            f"{folder}:/run/doc-sandbox",
            IMAGE,
            PYTHON,
            "-I",
            SERVER,
            "/run/doc-sandbox/sandbox.sock",
        ),
        check=True,
        stdout=subprocess.DEVNULL,
    )
    path = os.path.join(folder, "sandbox.sock")
    try:
        for _ in range(200):
            if os.path.exists(path):
                break
            time.sleep(0.05)
        assert os.path.exists(path), "the sandbox server did not start"
        yield name, path
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.rmtree(folder, ignore_errors=True)


@pytest.mark.asyncio
async def test_every_mode_works_under_the_profile(container):
    _, path = container
    kw = dict(socket_path=path, **LIMITS)
    for data, content_type in [
        (documents.text_pdf(pages=2), "application/pdf"),
        (documents.fillable_pdf(), "application/pdf"),
        (documents.scan_pdf(), "application/pdf"),
        (documents.form_pdf(filled=True), "application/pdf"),
        (documents.photo_png(), "image/png"),
    ]:
        analysis = await run_analysis(data, content_type, **kw)
        assert analysis["page_count"] >= 1
        if content_type == "application/pdf":
            text = await run_text_layer(data, **kw)
            layout = await run_layout(data, **kw)
            assert len(text["pages"]) == len(layout["pages"]) == analysis["page_count"]
        rendered = await run_render(data, content_type, [1], **kw)
        png = base64.b64decode(rendered["pages"][0]["png"])
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
    words = await run_text_layer(documents.text_pdf(), **kw)
    assert [w["text"] for w in words["pages"][0]["words"]][:2] == [
        "Application",
        "form",
    ]
    with pytest.raises(DocumentRefused) as raised:
        await run_analysis(documents.encrypted_pdf(), "application/pdf", **kw)
    assert raised.value.code == "encrypted"


PROBE = r"""
import ctypes, errno, json, platform, socket

def attempt(family, kind):
    try:
        socket.socket(family, kind).close()
        return "allowed"
    except OSError as error:
        return errno.errorcode.get(error.errno, str(error.errno))

out = {
    "AF_UNIX": attempt(socket.AF_UNIX, socket.SOCK_STREAM),
    "AF_INET": attempt(socket.AF_INET, socket.SOCK_STREAM),
    "AF_INET6": attempt(socket.AF_INET6, socket.SOCK_DGRAM),
    "AF_NETLINK": attempt(socket.AF_NETLINK, socket.SOCK_RAW),
}
if platform.machine() == "x86_64":
    libc = ctypes.CDLL(None, use_errno=True)
    for name, number, arg in [
        ("ptrace", 101, 0),            # PTRACE_TRACEME
        ("mount", 165, 0),
        ("unshare", 272, 0x10000000),  # CLONE_NEWUSER
        ("keyctl", 250, 0),
        ("bpf", 321, 0),
        ("io_uring_setup", 425, 1),
        ("personality", 135, 0xFFFFFFFF),
    ]:
        ctypes.set_errno(0)
        result = libc.syscall(number, ctypes.c_long(arg), 0, 0, 0, 0)
        out[name] = "allowed" if result >= 0 else errno.errorcode.get(ctypes.get_errno())
print(json.dumps(out))
"""


def _probe(*docker_run_or_exec: str) -> dict:
    result = subprocess.run(
        [*docker_run_or_exec, PYTHON, "-I", "-"],
        input=PROBE.encode(),
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_the_profile_denies_network_sockets_and_dangerous_syscalls(container):
    name, _ = container
    inside = _probe("docker", "exec", "-i", name)
    assert inside.pop("AF_UNIX") == "allowed"
    assert inside and set(inside.values()) == {"EPERM"}, inside


def test_without_the_profile_the_same_probe_gets_further(container):
    """The contrast that shows the profile, not the other options, denies them:
    under Docker's default profile a network-less container can still open an
    AF_INET socket."""
    default = _probe(
        *_hardened(f"bc-doc-sandbox-probe-{uuid.uuid4().hex[:8]}", "--rm", "-i"),
        IMAGE,
    )
    assert default["AF_INET"] == "allowed"


def test_the_healthcheck_connects_under_the_profile(container):
    name, _ = container
    subprocess.run(
        [
            "docker",
            "exec",
            name,
            PYTHON,
            "-I",
            "-c",
            "import socket; s = socket.socket(socket.AF_UNIX);"
            " s.connect('/run/doc-sandbox/sandbox.sock')",
        ],
        check=True,
    )
