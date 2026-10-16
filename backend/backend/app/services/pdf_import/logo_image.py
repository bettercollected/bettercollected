"""Check and re-encode an uploaded organisation logo (the sandbox's ``logo`` mode).

Native decoders (libpng, libjpeg, libwebp) parse the upload here, so this only
ever runs in the isolated document sandbox (#703), never in the API process or
a local child. The API stores only what this returns: a fresh encoding of the
pixels, without the upload's metadata (EXIF, including GPS, XMP, ICC, text
chunks).

Import-safe for the sandbox child: no imports from the backend package, and
Pillow is imported only inside the function (the API imports the constants).
"""

from __future__ import annotations

import base64
import io

LOGO_MIN_SIDE = 16
LOGO_MAX_SIDE = 3000

# sniffed kind -> (Pillow's name, content type)
LOGO_FORMATS = {
    "png": ("PNG", "image/png"),
    "jpeg": ("JPEG", "image/jpeg"),
    "webp": ("WEBP", "image/webp"),
}

SIZE_MESSAGE = (
    f"The logo must be between {LOGO_MIN_SIDE} and {LOGO_MAX_SIDE} pixels on each side."
)


def sniff_logo_format(data: bytes):
    """The format the file's own first bytes declare, if it is one we take."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _refuse(code: str, message: str):
    from .analysis import DocumentRefused

    raise DocumentRefused(code, message)


def _to_srgb(image):
    """Pixels in sRGB with no colour profile attached: convert when the file
    carries one Pillow can apply, else drop it."""
    profile = image.info.get("icc_profile")
    if not profile:
        return image
    try:
        from PIL import ImageCms

        source = ImageCms.ImageCmsProfile(io.BytesIO(profile))
        target = ImageCms.createProfile("sRGB")
        mode = "RGBA" if "A" in image.getbands() else "RGB"
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert(mode)
        return ImageCms.profileToProfile(image, source, target, outputMode=mode)
    except Exception:  # noqa: BLE001 — a broken profile is dropped, not fatal
        return image


def _pixels_only(image):
    """A new image holding only the pixels (and a palette): no info, EXIF,
    XMP, ICC or text chunks can ride along into the saved file."""
    from PIL import Image

    clean = Image.frombytes(image.mode, image.size, image.tobytes())
    if image.mode == "P":
        clean.putpalette(image.getpalette())
        if "transparency" in image.info:
            clean.info["transparency"] = image.info["transparency"]
    return clean


def reencode_logo(data: bytes) -> dict:
    """``{format, content_type, width, height, data}`` (``data`` base64) or
    raises DocumentRefused: ``unsupported_type``, ``bad_size``, ``unreadable``."""
    kind = sniff_logo_format(data)
    if kind is None:
        _refuse("unsupported_type", "The logo must be a PNG, JPEG or WebP image.")
    pil_name, content_type = LOGO_FORMATS[kind]

    import warnings

    from PIL import Image, ImageOps

    # This process only: a sandbox child handles one file.
    Image.MAX_IMAGE_PIXELS = LOGO_MAX_SIDE * LOGO_MAX_SIDE
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as opened:
                if opened.format != pil_name:
                    _refuse("unreadable", "The logo image could not be read.")
                width, height = opened.size
                if (
                    max(width, height) > LOGO_MAX_SIDE
                    or min(width, height) < LOGO_MIN_SIDE
                ):
                    _refuse("bad_size", SIZE_MESSAGE)
                opened.load()
                # A phone photo's rotation lives in EXIF, which is not kept.
                image = ImageOps.exif_transpose(opened)
                image = _pixels_only(_to_srgb(image))
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        _refuse("bad_size", SIZE_MESSAGE)
    except Exception as error:  # noqa: BLE001
        if type(error).__name__ == "DocumentRefused":
            raise
        _refuse("unreadable", "The logo image could not be read.")

    out = io.BytesIO()
    has_alpha = "A" in image.getbands() or (
        image.mode == "P" and "transparency" in image.info
    )
    if kind == "png":
        if image.mode not in ("1", "L", "LA", "P", "RGB", "RGBA"):
            image = image.convert("RGBA" if has_alpha else "RGB")
        params = {"optimize": True}
        if image.mode == "P" and "transparency" in image.info:
            params["transparency"] = image.info["transparency"]
        # No pnginfo, icc_profile or exif: only the pixels are written.
        image.save(out, format="PNG", **params)
    elif kind == "jpeg":
        image.convert("RGB").save(out, format="JPEG", quality=90, optimize=True)
    else:
        image = image.convert("RGBA" if has_alpha else "RGB")
        image.save(out, format="WEBP", quality=90, method=4)
    width, height = image.size
    return {
        "format": kind,
        "content_type": content_type,
        "width": width,
        "height": height,
        "data": base64.b64encode(out.getvalue()).decode("ascii"),
    }
