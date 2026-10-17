"""The organisation logo a form shows at the top of every respondent page.

Rules (DESIGN.md §9, "Organisation logo"):

- PNG, JPEG or WebP only, recognised here by their first bytes; never SVG (it
  can carry scripts) or anything else, whatever the file is called or the
  browser says it is.
- At most 1 MB and 16–3000 px on each side.
- This process never decodes an upload. The document sandbox (the PDF
  import's isolated container, ``pdf_import/logo_image.py``) decodes it,
  checks its size and re-encodes it without metadata (EXIF, GPS, XMP, ICC);
  only those re-encoded bytes are stored. Without the sandbox, uploads are
  refused (503), never decoded here.
- Stored in our own bucket, under ``public/form-logos/<form id>/``, and read
  from there: a form never points at a logo somewhere else, so respondent
  pages make no third-party request for it.
"""

import base64
import binascii
import uuid
from dataclasses import dataclass
from http import HTTPStatus

from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.logo_image import (
    LOGO_FORMATS,
    LOGO_MAX_SIDE,
    LOGO_MIN_SIDE,
    SIZE_MESSAGE,
    sniff_logo_format,
)
from backend.app.services.pdf_import import sandbox
from backend.app.services.pdf_import.sandbox import SandboxUnavailable
from backend.config import settings

LOGO_MAX_BYTES = 1024 * 1024
# the re-encoded file may come out a little larger than the upload
LOGO_STORED_MAX_BYTES = 2 * LOGO_MAX_BYTES
LOGO_FOLDER = "public/form-logos"
_EXTENSIONS = {"png": "png", "jpeg": "jpg", "webp": "webp"}

# kept for callers that sniff before reading the whole upload
sniff_image_format = sniff_logo_format


@dataclass(frozen=True)
class CheckedLogo:
    data: bytes
    extension: str
    content_type: str
    width: int
    height: int


def _refuse(status: HTTPStatus, message: str):
    raise HTTPException(status_code=status, content=message)


def precheck_logo_bytes(data: bytes) -> str:
    """The cheap checks, without decoding: size and the first bytes. Returns
    the declared format, or raises 413/415/422."""
    if not data:
        _refuse(HTTPStatus.UNPROCESSABLE_ENTITY, "The logo file is empty.")
    if len(data) > LOGO_MAX_BYTES:
        _refuse(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "The logo must be 1 MB or smaller."
        )
    kind = sniff_logo_format(data)
    if kind is None:
        _refuse(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            "The logo must be a PNG, JPEG or WebP image.",
        )
    return kind


async def _process_in_sandbox(data: bytes) -> dict:
    """The sandbox's re-encoding (``pdf_import/logo_image.py``). Tests replace it."""
    s = settings.pdf_import
    return await sandbox.run_logo(
        data,
        max_pages=1,
        max_pixels=LOGO_MAX_SIDE * LOGO_MAX_SIDE,
        timeout_s=30,
        memory_mb=512,
        max_parallel=s.MAX_PARALLEL_SANDBOXES,
        max_result_bytes=4 * LOGO_STORED_MAX_BYTES,
        socket_path=s.SANDBOX_SOCKET,
        require_isolated=True,
    )


def _accept_result(kind: str, result: dict) -> CheckedLogo:
    """The sandbox parsed an attacker's file: check everything it returns."""
    unreadable = (HTTPStatus.UNPROCESSABLE_ENTITY, "The logo image could not be read.")
    if not isinstance(result, dict) or result.get("format") != kind:
        _refuse(*unreadable)
    width, height = result.get("width"), result.get("height")
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (width, height)):
        _refuse(*unreadable)
    if not (
        LOGO_MIN_SIDE <= min(width, height) and max(width, height) <= LOGO_MAX_SIDE
    ):
        _refuse(HTTPStatus.UNPROCESSABLE_ENTITY, SIZE_MESSAGE)
    encoded = result.get("data")
    if not isinstance(encoded, str) or len(encoded) > 2 * LOGO_STORED_MAX_BYTES:
        _refuse(*unreadable)
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        _refuse(*unreadable)
    if not data or len(data) > LOGO_STORED_MAX_BYTES or sniff_logo_format(data) != kind:
        _refuse(*unreadable)
    return CheckedLogo(
        data=data,
        extension=_EXTENSIONS[kind],
        content_type=LOGO_FORMATS[kind][1],
        width=width,
        height=height,
    )


async def check_logo_bytes(data: bytes) -> CheckedLogo:
    """Accept a logo or raise: 413 too large, 415 not PNG/JPEG/WebP, 422
    unreadable or out of the size limits, 503 when the sandbox is unavailable.
    The returned bytes are the sandbox's re-encoding, never the upload."""
    kind = precheck_logo_bytes(data)
    try:
        result = await _process_in_sandbox(data)
    except SandboxUnavailable:
        logger.warning("Logo upload refused: the document sandbox is unavailable.")
        _refuse(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "Logo processing is unavailable. Try again in a moment.",
        )
    except DocumentRefused as refused:
        if refused.code == "bad_size":
            _refuse(HTTPStatus.UNPROCESSABLE_ENTITY, SIZE_MESSAGE)
        if refused.code == "unsupported_type":
            _refuse(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "The logo must be a PNG, JPEG or WebP image.",
            )
        _refuse(HTTPStatus.UNPROCESSABLE_ENTITY, "The logo image could not be read.")
    return _accept_result(kind, result)


async def read_logo_upload(upload) -> CheckedLogo:
    """Read an uploaded logo (at most one byte over the limit) and check it."""
    data = await upload.read(LOGO_MAX_BYTES + 1)
    return await check_logo_bytes(data)


def logo_key(owner: str, extension: str) -> str:
    """A new key for a logo of ``owner`` (a form id, or ``templates``)."""
    safe_owner = "".join(c for c in str(owner) if c.isalnum() or c in "-_")
    return f"{LOGO_FOLDER}/{safe_owner or 'unknown'}/{uuid.uuid4().hex}.{extension}"


def logo_folder(form_id: str) -> str:
    safe_owner = "".join(c for c in str(form_id or "") if c.isalnum() or c in "-_")
    if not safe_owner:
        raise ValueError("a form id is needed")
    return f"{LOGO_FOLDER}/{safe_owner}/"


def logo_extension_of(url: str) -> str:
    tail = url.rsplit(".", 1)[-1].lower() if "." in url else ""
    return tail if tail in {"png", "jpg", "jpeg", "webp"} else "img"
