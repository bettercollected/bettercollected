"""Image addresses a form may hold: the single allow-list.

Respondent pages load a form's images from the stored URL (theme
backgrounds, page layout images, the welcome and ending images, field
images), so a form only ever points at us, never at a host that would see
respondents' visits. First-party addresses are:

- our own storage: ``AWS_PUBLIC_URL`` (or ``AWS_ENDPOINT_URL`` when no
  public URL is set, and the endpoint itself for objects stored before a
  public URL was configured), in our bucket, under the public folders the
  uploads and the built-in images use (``public/``, ``media_library/``,
  ``images/``);
- Unsplash photos served through our server:
  ``<API_PUBLIC_URL>/images/unsplash/<photo>`` (``services/unsplash_route.py``);
- the builder's two built-in placeholder images (``BUILTIN_IMAGE_URLS``).

An ``https://images.unsplash.com`` address (the picker's and the AI image
search's results) is accepted on input only to be rewritten to our Unsplash
route: ``first_party_image_url`` returns the address to store. Everything
else is refused here, in one place. Addresses copied in from elsewhere go
through ``POST /workspaces/{id}/images/import`` (``services/image_service.py``)
and come back as storage addresses.
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlsplit

from backend.app.services import unsplash_route
from backend.config import settings

MAX_IMAGE_URL_LENGTH = 2048
UNSPLASH_IMAGE_HOST = unsplash_route.UNSPLASH_IMAGE_HOST
# Folders under our bucket that hold publicly readable images.
PUBLIC_IMAGE_FOLDERS = ("public/", "media_library/", "images/")
# The builder's placeholders for a new image layout and a field image
# (webapp src/constants/global.ts), kept for instances whose storage is
# elsewhere.
BUILTIN_IMAGE_URLS = frozenset(
    {
        "https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2_layout_image.webp",
        "https://s3.eu-central-1.wasabisys.com/bettercollected/images/Default_field_image.png",
    }
)

IMAGE_URL_ERROR = (
    "Images must come from this form's own storage or from Unsplash "
    f"(https://{UNSPLASH_IMAGE_HOST}); other image addresses are refused. "
    "Upload the image, or copy it in from its address first."
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


def _parts(url) -> Optional[object]:
    """The split address when it is a plain, safe absolute one, else None."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url or len(url) > MAX_IMAGE_URL_LENGTH or _UNSAFE.search(url):
        return None
    try:
        parts = urlsplit(url)
        # Reject user-info and malformed ports outright.
        if parts.username is not None or parts.password is not None:
            return None
        parts.port
    except ValueError:
        return None
    return parts


def is_first_party_image_url(url: Optional[str]) -> bool:
    """Whether ``url`` may be stored as is: our storage, our Unsplash route
    or a built-in image."""
    parts = _parts(url)
    if parts is None:
        return False
    url = url.strip()
    return (
        url in BUILTIN_IMAGE_URLS
        or _is_storage_url(parts)
        or unsplash_route.is_route_url(url)
    )


def first_party_image_url(url: Optional[str]) -> Optional[str]:
    """The address to store for ``url``: itself (trimmed) when first-party,
    our route's address for an Unsplash photo, else None."""
    if is_first_party_image_url(url):
        return url.strip()
    if _parts(url) is None:
        return None
    return unsplash_route.to_route_url(url.strip())


def is_allowed_image_url(url: Optional[str]) -> bool:
    """Whether ``url`` is accepted on input (first-party, or an Unsplash
    photo that will be rewritten)."""
    return first_party_image_url(url) is not None


def checked_image_url(url: Optional[str]) -> Optional[str]:
    """The address to store, ``""`` for a blank one (which clears the image),
    or ``None`` when none was given. Raises ``ValueError`` for an address on
    any other host."""
    if url is None:
        return None
    if not isinstance(url, str):
        raise ValueError(IMAGE_URL_ERROR)
    if not url.strip():
        return ""
    stored = first_party_image_url(url)
    if stored is None:
        raise ValueError(IMAGE_URL_ERROR)
    return stored


def allowed_image_url_or_none(url: Optional[str]) -> Optional[str]:
    """For generated forms: the address to store, or None for anything else."""
    return first_party_image_url(url)
