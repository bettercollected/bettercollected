"""Unsplash photos served through our own server.

Respondents never contact ``images.unsplash.com``: a form holds
``<API_PUBLIC_URL>/images/unsplash/<photo path>?<sizing>`` instead, and that
route (``services/image_service.py``) fetches the photo from Unsplash once,
re-encodes it in the document sandbox and serves it from our bucket.

This module only deals with addresses, so the allow-list
(``services/image_urls.py``), the route and the save-time checks agree:

- the photo path: one or two segments of letters, digits, ``-`` and ``_``
  (a second segment may also hold dots), never ``..`` or ``%``;
- the sizing parameters, from a fixed list (``w``, ``h``, ``q``, ``fit``,
  ``fm``, ``crop``, ``auto``); anything else (Unsplash's ``ixid``, ``ixlib``,
  ``cs``, ``dpr``...) is dropped, never forwarded.

``fetch_params`` turns a request's parameters into what we ask Unsplash for:
sizes rounded up to a fixed set of widths and qualities, so the cache holds a
bounded number of variants per photo.
"""

import hashlib
import ipaddress
import re
from typing import Dict, Iterable, Mapping, Optional, Tuple
from urllib.parse import urlencode, urlsplit, parse_qsl

from loguru import logger

from backend.config import settings

UNSPLASH_IMAGE_HOST = "images.unsplash.com"
UNSPLASH_ORIGIN = f"https://{UNSPLASH_IMAGE_HOST}"
ROUTE_PATH = "/images/unsplash/"

_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}"
_LAST_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}"
_PHOTO_PATH = re.compile(rf"(?:{_SEGMENT}/)?{_LAST_SEGMENT}")

# Next.js' image widths plus a few large ones; requests round up to these.
SIZES = (16, 32, 48, 64, 96, 128, 256, 384, 640, 750, 828, 1080, 1200, 1920, 2048)
SIZES += (2560, 3840)
MAX_SIDE = SIZES[-1]
DEFAULT_WIDTH = 1920
MAX_REQUESTED_SIDE = 10000

FITS = frozenset(
    {"clamp", "clip", "crop", "facearea", "fill", "fillmax", "max", "min", "scale"}
)
# exactly what our addresses carry: the AI image search's urls.regular
# (crop=entropy); the picker's urls.raw and the next/image loader send none
CROPS = frozenset({"entropy"})
# requested format -> what we ask for: never AVIF (the sandbox re-encodes
# PNG, JPEG and WebP only)
FORMATS = {"jpg": "jpg", "jpeg": "jpg", "pjpg": "jpg", "png": "png"}
FORMATS.update({"webp": "webp", "avif": "webp"})
# auto=format would let Unsplash pick by our Accept header; only compress is kept
AUTO = frozenset({"compress"})
PARAMS = ("auto", "crop", "fit", "fm", "h", "q", "w")


class BadImageParams(ValueError):
    pass


def is_photo_path(path: Optional[str]) -> bool:
    return (
        isinstance(path, str)
        and bool(_PHOTO_PATH.fullmatch(path))
        and ".." not in path
        and len(path) <= 300
    )


def _int(value: str, low: int, high: int) -> int:
    if not re.fullmatch(r"\d{1,6}", value or ""):
        raise BadImageParams("Image sizes must be whole numbers.")
    number = int(value)
    if not low <= number <= high:
        raise BadImageParams("Image size out of range.")
    return number


def _tokens(value: str, allowed: Iterable[str]) -> Tuple[str, ...]:
    tokens = [t.strip().lower() for t in (value or "").split(",")]
    allowed = set(allowed)
    if not tokens or any(t not in allowed for t in tokens if t) or not any(tokens):
        raise BadImageParams("Unknown image option.")
    return tuple(sorted({t for t in tokens if t}))


def clean_params(
    pairs: Iterable[Tuple[str, str]], strict: bool = True
) -> Dict[str, str]:
    """The allow-listed parameters, checked; others are dropped. A parameter
    given twice or with a bad value raises ``BadImageParams`` (``strict``) or
    is left out."""
    seen: Dict[str, str] = {}
    repeated = set()
    for key, value in pairs:
        if key not in PARAMS:
            continue
        if key in seen:
            repeated.add(key)
        seen[key] = value
    if repeated:
        if strict:
            raise BadImageParams("An image option is given twice.")
        for key in repeated:
            seen.pop(key)
    cleaned: Dict[str, str] = {}
    for key, value in seen.items():
        try:
            if key in ("w", "h"):
                cleaned[key] = str(_int(value, 1, MAX_REQUESTED_SIDE))
            elif key == "q":
                cleaned[key] = str(_int(value, 1, 100))
            elif key == "fit":
                if value.lower() not in FITS:
                    raise BadImageParams("Unknown image option.")
                cleaned[key] = value.lower()
            elif key == "fm":
                if value.lower() not in FORMATS:
                    raise BadImageParams("Unknown image format.")
                cleaned[key] = value.lower()
            elif key == "crop":
                cleaned[key] = ",".join(_tokens(value, CROPS))
            elif key == "auto":
                tokens = _tokens(value, AUTO | {"format", "enhance", "redeye"})
                kept = [t for t in tokens if t in AUTO]
                if kept:
                    cleaned[key] = ",".join(kept)
        except BadImageParams:
            if strict:
                raise
    return {key: cleaned[key] for key in sorted(cleaned)}


def _round_up(value: int) -> int:
    for size in SIZES:
        if value <= size:
            return size
    return MAX_SIDE


def fetch_params(params: Mapping[str, str]) -> Dict[str, str]:
    """What we ask Unsplash for, from cleaned parameters: bounded sizes and
    qualities, a format the sandbox re-encodes, never an upscale past
    ``MAX_SIDE`` on either side."""
    out: Dict[str, str] = {}
    fit = params.get("fit") or "max"
    out["fit"] = fit
    for key in ("w", "h"):
        if params.get(key):
            out[key] = str(_round_up(int(params[key])))
    if "w" not in out and "h" not in out:
        out["w"] = str(DEFAULT_WIDTH)
    if fit in ("max", "clip", "min", "scale"):
        # a bound on both sides, whatever the photo's shape
        out.setdefault("w", str(MAX_SIDE))
        out.setdefault("h", str(MAX_SIDE))
    if params.get("q"):
        out["q"] = str(min(100, max(10, -(-int(params["q"]) // 10) * 10)))
    if params.get("fm"):
        out["fm"] = FORMATS[params["fm"]]
    if params.get("crop"):
        out["crop"] = params["crop"]
    if params.get("auto"):
        out["auto"] = params["auto"]
    return {key: out[key] for key in sorted(out)}


def cache_key(path: str, params: Mapping[str, str]) -> str:
    """A name for one fetched variant: a hash of the photo path and the
    parameters we fetched it with."""
    canonical = f"{path}?{urlencode(sorted(params.items()))}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def upstream_url(path: str, params: Mapping[str, str]) -> str:
    query = urlencode(sorted(params.items()))
    return f"{UNSPLASH_ORIGIN}/{path}" + (f"?{query}" if query else "")


_LOOPBACK_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost"}


def _is_local_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    if host in _LOOPBACK_NAMES or host.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def _local_instance() -> bool:
    """Development or tests: the API itself runs on this machine
    (``API_HOST`` names localhost, as the cookie settings read it) or the
    environment says test."""
    api = settings.api_settings
    return "localhost" in (api.HOST or "") or (api.ENVIRONMENT or "").lower() == "test"


def route_configured() -> bool:
    """Whether we may store our Unsplash route's address on forms: only with
    an ``API_PUBLIC_URL`` that browsers can reach. Unset, or a loopback
    address outside development, fails closed: Unsplash addresses are then
    stored as they came (respondent pages still load them through the route,
    since the webapp knows its API host) instead of an address that would
    break the image for good."""
    parts = urlsplit((settings.api_settings.PUBLIC_URL or "").strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    if _is_local_host(parts.hostname) and not _local_instance():
        return False
    return True


def log_if_route_unconfigured() -> None:
    """One warning at startup when Unsplash addresses won't be rewritten."""
    if not route_configured():
        logger.warning(
            "API_PUBLIC_URL is unset or a local address: Unsplash images on "
            "forms are kept as Unsplash addresses, not rewritten to this API's "
            "/images/unsplash route. Set it to the API's public address."
        )


def route_base() -> str:
    """``<API_PUBLIC_URL>/images/unsplash/``"""
    base = (settings.api_settings.PUBLIC_URL or "").strip().rstrip("/")
    return f"{base}{ROUTE_PATH}"


def route_url(path: str, params: Optional[Mapping[str, str]] = None) -> str:
    query = urlencode(sorted((params or {}).items()))
    return route_base() + path + (f"?{query}" if query else "")


def unsplash_photo(url: str) -> Optional[Tuple[str, Dict[str, str]]]:
    """``(photo path, cleaned parameters)`` of an ``images.unsplash.com``
    address, or None for anything else. Unknown or bad parameters are
    dropped: the result is only ever turned into one of our addresses."""
    try:
        parts = urlsplit(url.strip())
        if parts.username is not None or parts.password is not None:
            return None
        if parts.port is not None:
            return None
    except (ValueError, AttributeError):
        return None
    if parts.scheme.lower() != "https" or parts.netloc.lower() != UNSPLASH_IMAGE_HOST:
        return None
    path = parts.path[1:] if parts.path.startswith("/") else ""
    if not is_photo_path(path) or parts.fragment:
        return None
    params = clean_params(parse_qsl(parts.query, keep_blank_values=True), strict=False)
    return path, params


def to_route_url(url: str) -> Optional[str]:
    """Our address for an Unsplash photo address, or None when ``url`` is not
    one."""
    photo = unsplash_photo(url)
    if photo is None:
        return None
    if not route_configured():
        # fail closed: keep the Unsplash address (see route_configured)
        return url.strip()
    return route_url(*photo)


def is_route_url(url: str) -> bool:
    """Whether ``url`` is one of our Unsplash addresses: our API's public
    address, a photo path, and only valid allow-listed parameters."""
    if not route_configured():
        return False
    base = urlsplit(route_base())
    if not base.scheme or not base.netloc:
        return False
    try:
        parts = urlsplit(url)
        if parts.username is not None or parts.password is not None:
            return False
        parts.port
    except ValueError:
        return False
    if (
        parts.scheme.lower() != base.scheme.lower()
        or parts.netloc.lower() != base.netloc.lower()
        or parts.fragment
        or not parts.path.startswith(base.path)
    ):
        return False
    if not is_photo_path(parts.path[len(base.path) :]):
        return False
    pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=False)
    if any(key not in PARAMS for key, _ in pairs):
        return False
    try:
        clean_params(pairs)
    except BadImageParams:
        return False
    return True
