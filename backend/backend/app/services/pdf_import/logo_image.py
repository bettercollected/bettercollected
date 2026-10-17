"""Check and re-encode an untrusted image (the sandbox's ``logo`` and ``image`` modes).

``logo``: an uploaded organisation logo. ``image``: a picture fetched from
elsewhere (an Unsplash photo served through our server, an image address a
person pasted in the editor) before it is stored in our bucket.

Native decoders (libpng, libjpeg, libwebp) parse the file here, so this only
ever runs in the isolated document sandbox (#703), never in the API process or
a local child. The API stores only what this returns: a fresh encoding of the
pixels, without the file's metadata (EXIF, including GPS, XMP, ICC, text
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

# ``image`` mode: photos, so larger; the pixel count is the real bound (memory)
IMAGE_MAX_SIDE = 8000
IMAGE_MAX_PIXELS = 40_000_000
IMAGE_SIZE_MESSAGE = "The image is too large."


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
    return _reencode(
        data,
        min_side=LOGO_MIN_SIDE,
        max_side=LOGO_MAX_SIDE,
        max_pixels=LOGO_MAX_SIDE * LOGO_MAX_SIDE,
        size_message=SIZE_MESSAGE,
        unsupported_message="The logo must be a PNG, JPEG or WebP image.",
        unreadable_message="The logo image could not be read.",
        quality=90,
    )


def reencode_image(data: bytes, max_pixels: int = IMAGE_MAX_PIXELS) -> dict:
    """The same as ``reencode_logo`` for a fetched picture: any size up to
    ``IMAGE_MAX_SIDE`` on a side and ``max_pixels`` (at most
    ``IMAGE_MAX_PIXELS``) in all."""
    return _reencode(
        data,
        min_side=1,
        max_side=IMAGE_MAX_SIDE,
        max_pixels=max(1, min(int(max_pixels), IMAGE_MAX_PIXELS)),
        size_message=IMAGE_SIZE_MESSAGE,
        unsupported_message="The image must be a PNG, JPEG or WebP file.",
        unreadable_message="The image could not be read.",
        quality=85,
    )


def _reencode(
    data: bytes,
    *,
    min_side: int,
    max_side: int,
    max_pixels: int,
    size_message: str,
    unsupported_message: str,
    unreadable_message: str,
    quality: int,
) -> dict:
    kind = sniff_logo_format(data)
    if kind is None:
        _refuse("unsupported_type", unsupported_message)
    pil_name, content_type = LOGO_FORMATS[kind]

    import warnings

    from PIL import Image, ImageOps

    # This process only: a sandbox child handles one file.
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as opened:
                if opened.format != pil_name:
                    _refuse("unreadable", unreadable_message)
                width, height = opened.size
                if (
                    max(width, height) > max_side
                    or min(width, height) < min_side
                    or width * height > max_pixels
                ):
                    _refuse("bad_size", size_message)
                opened.load()
                # A phone photo's rotation lives in EXIF, which is not kept.
                image = ImageOps.exif_transpose(opened)
                image = _pixels_only(_to_srgb(image))
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        _refuse("bad_size", size_message)
    except Exception as error:  # noqa: BLE001
        if type(error).__name__ == "DocumentRefused":
            raise
        _refuse("unreadable", unreadable_message)

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
        image.convert("RGB").save(out, format="JPEG", quality=quality, optimize=True)
    else:
        image = image.convert("RGBA" if has_alpha else "RGB")
        image.save(out, format="WEBP", quality=quality, method=4)
    width, height = image.size
    return {
        "format": kind,
        "content_type": content_type,
        "width": width,
        "height": height,
        "data": base64.b64encode(out.getvalue()).decode("ascii"),
    }
