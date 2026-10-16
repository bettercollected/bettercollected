"""The organisation logo a form shows at the top of every respondent page.

Rules (DESIGN.md §9, "Organisation logo"):

- PNG, JPEG or WebP only, recognised by their first bytes and decoded once to
  be sure; never SVG (it can carry scripts) or anything else, whatever the
  file is called or the browser says it is.
- At most 1 MB and 3000 px on either side, at least 16 px.
- Stored in our own bucket, under ``public/form-logos/<form id>/``, and read
  from there: a form never points at a logo somewhere else, so respondent
  pages make no third-party request for it.
"""

import io
import uuid
import warnings
from dataclasses import dataclass
from http import HTTPStatus
from typing import Optional

from PIL import Image

from backend.app.exceptions import HTTPException

LOGO_MAX_BYTES = 1024 * 1024
LOGO_MAX_SIDE = 3000
LOGO_MIN_SIDE = 16
LOGO_FOLDER = "public/form-logos"

# format -> (file extension, content type, Pillow's name for it)
_FORMATS = {
    "png": ("png", "image/png", "PNG"),
    "jpeg": ("jpg", "image/jpeg", "JPEG"),
    "webp": ("webp", "image/webp", "WEBP"),
}


@dataclass(frozen=True)
class CheckedLogo:
    data: bytes
    extension: str
    content_type: str
    width: int
    height: int


def sniff_image_format(data: bytes) -> Optional[str]:
    """The format the file's own first bytes declare, if it is one we take."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _refuse(status: HTTPStatus, message: str):
    raise HTTPException(status_code=status, content=message)


def check_logo_bytes(data: bytes) -> CheckedLogo:
    """Accept a logo file or raise: 413 too large, 415 not PNG/JPEG/WebP,
    422 unreadable or out of the size limits."""
    if not data:
        _refuse(HTTPStatus.UNPROCESSABLE_ENTITY, "The logo file is empty.")
    if len(data) > LOGO_MAX_BYTES:
        _refuse(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "The logo must be 1 MB or smaller."
        )
    kind = sniff_image_format(data)
    if kind is None:
        _refuse(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            "The logo must be a PNG, JPEG or WebP image.",
        )
    extension, content_type, pil_name = _FORMATS[kind]
    size_problem = (
        f"The logo must be between {LOGO_MIN_SIDE} and "
        f"{LOGO_MAX_SIDE} pixels on each side."
    )
    # Pillow's decompression-bomb limit is process-wide (the PDF import sets
    # it too): hold it at the largest logo while this one is opened, so the
    # check never depends on what ran before. No await in between.
    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = LOGO_MAX_SIDE * LOGO_MAX_SIDE
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != pil_name:
                    raise ValueError("format mismatch")
                width, height = image.size
                if (
                    max(width, height) > LOGO_MAX_SIDE
                    or min(width, height) < LOGO_MIN_SIDE
                ):
                    _refuse(HTTPStatus.UNPROCESSABLE_ENTITY, size_problem)
                # Decode it once: a file that only starts like an image is refused.
                image.load()
    except HTTPException:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        _refuse(HTTPStatus.UNPROCESSABLE_ENTITY, size_problem)
    except Exception:
        _refuse(HTTPStatus.UNPROCESSABLE_ENTITY, "The logo image could not be read.")
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit
    return CheckedLogo(
        data=data,
        extension=extension,
        content_type=content_type,
        width=width,
        height=height,
    )


async def read_logo_upload(upload) -> CheckedLogo:
    """Read an uploaded logo (at most one byte over the limit) and check it."""
    data = await upload.read(LOGO_MAX_BYTES + 1)
    return check_logo_bytes(data)


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
