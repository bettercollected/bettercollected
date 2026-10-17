"""The document sandbox's ``logo`` mode (pdf_import/logo_image.py): which
uploads it takes, that it re-encodes them without their metadata, and that it
runs over the isolated transport only."""

import asyncio
import base64
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import time

import pytest
from PIL import Image, ImageCms, PngImagePlugin

from backend.app.services.pdf_import import sandbox
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.logo_image import reencode_logo
from backend.app.services.pdf_import.sandbox import SandboxUnavailable, run_logo

LIMITS = dict(
    max_pages=1,
    max_pixels=9_000_000,
    timeout_s=30,
    memory_mb=512,
    max_parallel=2,
    max_result_bytes=8 * 1024 * 1024,
)
SERVER = pathlib.Path(sandbox.__file__).parent / "server.py"


def image_bytes(fmt="PNG", size=(120, 48), mode="RGB", **save) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, (11, 61, 145) if mode == "RGB" else 0).save(
        buffer, format=fmt, **save
    )
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _pillow_limit_restored():
    # reencode_logo sets Pillow's process-wide limit, as the sandbox child may;
    # here it runs in the test process, so put it back afterwards
    before = Image.MAX_IMAGE_PIXELS
    # and start from Pillow's own default, whatever other tests left behind
    Image.MAX_IMAGE_PIXELS = int(1024 * 1024 * 1024 // 4 // 3)
    yield
    Image.MAX_IMAGE_PIXELS = before


def gps_exif() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (52.0, 22.0, 1.0)
    gps[3] = "E"
    gps[4] = (4.0, 53.0, 2.0)
    return exif.tobytes()


def decoded(result: dict):
    data = base64.b64decode(result["data"])
    return data, Image.open(io.BytesIO(data))


@pytest.mark.parametrize(
    "fmt,kind",
    [("PNG", "png"), ("JPEG", "jpeg"), ("WEBP", "webp")],
)
def test_png_jpeg_and_webp_are_reencoded_in_their_own_format(fmt, kind):
    upload = image_bytes(fmt)
    result = reencode_logo(upload)
    data, image = decoded(result)
    assert result["format"] == kind and image.format == fmt
    assert (result["width"], result["height"]) == (120, 48) == image.size
    assert result["content_type"] == f"image/{kind}"


@pytest.mark.parametrize("fmt", ["JPEG", "WEBP", "PNG"])
def test_exif_with_a_location_is_not_kept(fmt):
    upload = image_bytes(fmt, exif=gps_exif())
    assert Image.open(io.BytesIO(upload)).getexif().get_ifd(0x8825)
    data, image = decoded(reencode_logo(upload))
    assert not image.getexif()
    assert "exif" not in image.info
    assert b"PhoneMaker" not in data


def test_png_text_chunks_and_colour_profiles_are_not_kept():
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Someone Private")
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    upload = image_bytes("PNG", pnginfo=info, icc_profile=profile)
    data, image = decoded(reencode_logo(upload))
    assert b"Someone Private" not in data
    assert "icc_profile" not in image.info
    assert not getattr(image, "text", {})


def test_transparency_is_kept():
    buffer = io.BytesIO()
    Image.new("RGBA", (40, 40), (255, 0, 0, 0)).save(buffer, format="PNG")
    _, image = decoded(reencode_logo(buffer.getvalue()))
    assert image.mode == "RGBA" and image.getpixel((0, 0))[3] == 0


@pytest.mark.parametrize(
    "size", [(3001, 40), (10, 10), (6000, 6000)], ids=["wide", "tiny", "bomb"]
)
def test_sizes_outside_the_limits_are_refused(size):
    with pytest.raises(DocumentRefused) as refused:
        reencode_logo(image_bytes("PNG", size=size, mode="1"))
    assert refused.value.code == "bad_size"


@pytest.mark.parametrize(
    "data",
    [
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 64,
        image_bytes("PNG")[:60],
        image_bytes("JPEG")[:200],
        b"RIFF\x00\x00\x00\x00WEBPVP8 garbage",
    ],
    ids=["fake-png", "truncated-png", "truncated-jpeg", "fake-webp"],
)
def test_corrupt_or_truncated_files_are_refused(data):
    with pytest.raises(DocumentRefused) as refused:
        reencode_logo(data)
    assert refused.value.code == "unreadable"


@pytest.mark.parametrize(
    "data",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b"<html><script>alert(1)</script></html>",
        image_bytes("GIF"),
    ],
    ids=["svg", "html", "gif"],
)
def test_other_types_are_refused_unopened(data):
    with pytest.raises(DocumentRefused) as refused:
        reencode_logo(data)
    assert refused.value.code == "unsupported_type"


# --- the transport ---------------------------------------------------------------


async def test_the_logo_mode_never_runs_in_a_local_child():
    with pytest.raises(SandboxUnavailable):
        await run_logo(image_bytes(), **LIMITS)


@pytest.fixture(scope="module")
def socket_path():
    folder = tempfile.mkdtemp(prefix="bc-logo-sandbox-")
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
        time.sleep(0.05)
    yield path
    process.terminate()
    process.wait(timeout=10)


@pytest.mark.xdist_group("logo_sandbox")
async def test_over_the_socket_the_logo_is_reencoded_and_refusals_cross(socket_path):
    result = await run_logo(
        image_bytes("JPEG", exif=gps_exif()), socket_path=socket_path, **LIMITS
    )
    data, image = decoded(result)
    assert result["format"] == "jpeg" and image.size == (120, 48)
    assert not image.getexif()
    with pytest.raises(DocumentRefused) as refused:
        await run_logo(
            image_bytes("PNG", size=(6000, 6000), mode="1"),
            socket_path=socket_path,
            **LIMITS,
        )
    assert refused.value.code == "bad_size"
    # several at once, as uploads arrive
    results = await asyncio.gather(
        *(run_logo(image_bytes(), socket_path=socket_path, **LIMITS) for _ in range(3))
    )
    assert all(r["format"] == "png" for r in results)
