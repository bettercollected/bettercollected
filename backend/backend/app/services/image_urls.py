"""Image addresses that automated edits may put on a form.

Respondent pages load a form's images straight from the stored URL (theme
backgrounds, page layout images, the welcome image). Edits that no person
picked by hand — AI turns, API keys over MCP, AI form creation — may only
point at hosts the product already serves images from, so a respondent's
browser never contacts a host the form owner did not choose:

- our own storage: ``AWS_PUBLIC_URL`` (or ``AWS_ENDPOINT_URL`` when no
  public URL is set, and the endpoint itself for objects stored before a
  public URL was configured), in our bucket, under the public folders the
  uploads use (``public/`` and ``media_library/``);
- Unsplash images (``https://images.unsplash.com``), the source of the
  builder's image picker and the AI's image search.

Everything else is refused here, in one place.
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlsplit

from backend.config import settings

MAX_IMAGE_URL_LENGTH = 2048
UNSPLASH_IMAGE_HOST = "images.unsplash.com"
# Folders under our bucket that hold publicly readable images.
PUBLIC_IMAGE_FOLDERS = ("public/", "media_library/")

IMAGE_URL_ERROR = (
    "Images must come from this form's own storage or from Unsplash "
    f"(https://{UNSPLASH_IMAGE_HOST}); other image addresses are refused."
)

# Whitespace, control characters and characters that could break out of a
# CSS url("...") or an HTML attribute.
_UNSAFE = re.compile(r"[\s\x00-\x1f\x7f\"'<>\\`()]")


def _storage_bases() -> Tuple[str, ...]:
    aws = settings.aws_settings
    bases = []
    for base in (aws.public_base_url, aws.ENDPOINT_URL):
        base = (base or "").strip().rstrip("/")
        if base and base not in bases:
            bases.append(base)
    return tuple(bases)


def _is_storage_url(parts) -> bool:
    bucket = (settings.aws_settings.BUCKET or "").strip("/")
    if not bucket or parts.query or parts.fragment:
        return False
    for base in _storage_bases():
        base_parts = urlsplit(base)
        if (
            parts.scheme.lower() != base_parts.scheme.lower()
            or parts.netloc.lower() != base_parts.netloc.lower()
        ):
            continue
        prefix = f"{base_parts.path.rstrip('/')}/{bucket}/"
        if not parts.path.startswith(prefix):
            continue
        key = parts.path[len(prefix) :]
        segments = key.split("/")
        if (
            key.startswith(PUBLIC_IMAGE_FOLDERS)
            and all(segments[1:])
            and ".." not in segments
            and "%" not in key
        ):
            return True
    return False


def _is_unsplash_url(parts) -> bool:
    return (
        parts.scheme.lower() == "https"
        and parts.netloc.lower() == UNSPLASH_IMAGE_HOST
        and parts.path.startswith("/")
        and len(parts.path) > 1
    )


def is_allowed_image_url(url: Optional[str]) -> bool:
    """Whether ``url`` is a non-blank image address on an allowed host."""
    if not isinstance(url, str):
        return False
    url = url.strip()
    if not url or len(url) > MAX_IMAGE_URL_LENGTH or _UNSAFE.search(url):
        return False
    try:
        parts = urlsplit(url)
        # Reject user-info and malformed ports outright.
        if parts.username is not None or parts.password is not None:
            return False
        parts.port
    except ValueError:
        return False
    return _is_unsplash_url(parts) or _is_storage_url(parts)


def checked_image_url(url: Optional[str]) -> Optional[str]:
    """The trimmed URL, ``""`` for a blank one (which clears the image), or
    ``None`` when none was given. Raises ``ValueError`` for an address on any
    other host."""
    if url is None:
        return None
    if not isinstance(url, str):
        raise ValueError(IMAGE_URL_ERROR)
    url = url.strip()
    if not url:
        return ""
    if not is_allowed_image_url(url):
        raise ValueError(IMAGE_URL_ERROR)
    return url


def allowed_image_url_or_none(url: Optional[str]) -> Optional[str]:
    """For generated forms: keep an allowed address, drop anything else."""
    return url.strip() if is_allowed_image_url(url) else None
