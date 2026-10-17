"""Images respondents load from us instead of from a third party.

Two ways in, one way out (our bucket):

``serve_unsplash`` (``GET /images/unsplash/{photo}``, public)
    How respondent pages load a form's Unsplash photo: the form stores the
    canonical ``images.unsplash.com`` address and the webapp loads it through
    this route on its own API host (``services/unsplash_route.py``). The
    first request for a photo and size
    fetches it from ``https://images.unsplash.com`` (fixed host, no redirects
    followed, ``services/image_fetch.py``), has the document sandbox
    re-encode it without metadata, and stores the result in our bucket under
    ``public/image-cache/unsplash/``, named by a hash of the photo path and
    the parameters fetched; every request is then redirected to that copy.
    It is no open proxy: only a photo path, only allow-listed parameters,
    only that host. Rate-limited per client address, with a tighter limit on
    requests that have to fetch.

``import_image`` (``POST /workspaces/{id}/images/import``, ``form.edit``)
    An image address a person pasted in the editor. Fetched with the SSRF
    rules of ``services/image_fetch.py``, re-encoded in the sandbox, stored
    under ``public/media/<workspace>/``; the editor stores the returned
    address. Rate-limited per person.

This process never decodes an image: without the sandbox both answer 503.
"""

import asyncio
import base64
import binascii
import uuid
from collections import OrderedDict
from http import HTTPStatus
from typing import Dict, Iterable, Optional, Tuple

from beanie import PydanticObjectId
from common.models.user import User
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.services import unsplash_route
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.image_fetch import (
    MAX_IMAGE_BYTES,
    FetchRefused,
    fetch_image,
)
from backend.app.services.image_urls import first_party_image_url
from backend.app.services.pdf_import import sandbox
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.logo_image import (
    IMAGE_MAX_PIXELS,
    IMAGE_MAX_SIDE,
    LOGO_FORMATS,
    sniff_logo_format,
)
from backend.app.services.pdf_import.sandbox import SandboxUnavailable
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.app.utils.client_ip import rate_limit_key
from backend.config import settings

CACHE_FOLDER = "public/image-cache/unsplash"
MEDIA_FOLDER = "public/media"
# a re-encoding may come out larger than what was fetched
STORED_MAX_BYTES = 3 * MAX_IMAGE_BYTES
_EXTENSIONS = {"png": "png", "jpeg": "jpg", "webp": "webp"}
_KNOWN_LIMIT = 10_000

PROXY_SCOPE = "image-proxy"
PROXY_FETCH_SCOPE = "image-proxy-fetch"
PROXY_GLOBAL_FETCH_SCOPE = "image-proxy-fetch-all"
# the single counter every client's fetches share
GLOBAL_CLIENT = "all"
IMPORT_SCOPE = "image-import"

# what the editor says, by refusal code
COPY_FAILED = "We couldn't copy that image."
UPLOAD_INSTEAD = "Upload it instead."
_REASONS = {
    "invalid_url": "Check that the address starts with https://.",
    "not_allowed": "That address can't be used.",
    "unreachable": "The address didn't answer with an image.",
    "timeout": "It took too long to load.",
    "too_large": "It is larger than 10 MB.",
    "not_image": "It isn't a JPEG, PNG or WebP image.",
    "too_many_redirects": "The address redirects too many times.",
    "unreadable": "The file couldn't be read.",
    "bad_size": "The image is too large.",
}


class CheckedImage:
    def __init__(self, data: bytes, kind: str):
        self.data = data
        self.extension = _EXTENSIONS[kind]
        self.content_type = LOGO_FORMATS[kind][1]


async def _process_in_sandbox(data: bytes) -> dict:
    """The sandbox's ``image`` mode (``pdf_import/logo_image.py``). Tests
    replace it."""
    s = settings.pdf_import
    return await sandbox.run_image(
        data,
        max_pages=1,
        max_pixels=IMAGE_MAX_PIXELS,
        timeout_s=60,
        memory_mb=1024,
        max_parallel=s.MAX_PARALLEL_SANDBOXES,
        max_result_bytes=2 * STORED_MAX_BYTES,
        socket_path=s.SANDBOX_SOCKET,
        require_isolated=True,
    )


class ImageRefused(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _accept_result(kind: str, result) -> CheckedImage:
    """The sandbox parsed a file from elsewhere: check what it returns."""
    if not isinstance(result, dict) or result.get("format") != kind:
        raise ImageRefused("unreadable")
    width, height = result.get("width"), result.get("height")
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (width, height)):
        raise ImageRefused("unreadable")
    if not (1 <= min(width, height) and max(width, height) <= IMAGE_MAX_SIDE):
        raise ImageRefused("bad_size")
    encoded = result.get("data")
    if not isinstance(encoded, str) or len(encoded) > 2 * STORED_MAX_BYTES:
        raise ImageRefused("unreadable")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ImageRefused("unreadable")
    if not data or len(data) > STORED_MAX_BYTES or sniff_logo_format(data) != kind:
        raise ImageRefused("unreadable")
    return CheckedImage(data, kind)


async def reencode(data: bytes) -> CheckedImage:
    """The sandbox's re-encoding of ``data``, checked. Raises ImageRefused, or
    SandboxUnavailable."""
    kind = sniff_logo_format(data)
    if kind is None:
        raise ImageRefused("not_image")
    try:
        result = await _process_in_sandbox(data)
    except DocumentRefused as refused:
        if refused.code == "unsupported_type":
            raise ImageRefused("not_image")
        if refused.code == "bad_size":
            raise ImageRefused("bad_size")
        raise ImageRefused("unreadable")
    return _accept_result(kind, result)


def _copy_failed(code: str) -> HTTPException:
    reason = _REASONS.get(code, "")
    message = " ".join(part for part in (COPY_FAILED, reason, UPLOAD_INSTEAD) if part)
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": code, "message": message},
    )


def _unavailable(message: str) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        content={"code": "unavailable", "message": message},
    )


def _too_many(verdict) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        content={
            "code": "rate_limited",
            "message": "Too many requests; try again later.",
        },
        headers={"Retry-After": str(verdict.retry_after)},
    )


class ImageService:
    def __init__(
        self,
        aws_service: AWSS3Service,
        rate_limiter: FixedWindowRateLimiter,
        authorization_service: AuthorizationService,
    ):
        self._aws = aws_service
        self._limiter = rate_limiter
        self._authorization = authorization_service
        # cache key -> our copy's address, so a cached photo needs no store
        # request; bounded, oldest out first
        self._known: "OrderedDict[str, str]" = OrderedDict()
        self._locks: Dict[str, Tuple[asyncio.Lock, int]] = {}

    # -- Unsplash, through our server ---------------------------------------

    def _remember(self, key: str, url: str) -> None:
        self._known[key] = url
        self._known.move_to_end(key)
        while len(self._known) > _KNOWN_LIMIT:
            self._known.popitem(last=False)

    async def serve_unsplash(
        self,
        photo_path: str,
        query: Iterable[Tuple[str, str]],
        client: Optional[str],
    ) -> str:
        """The address of our copy of the photo, fetching it the first time.
        Raises 404 (not a photo path), 400 (bad parameters), 429, 502 (Unsplash
        did not give us an image) or 503 (no sandbox)."""
        if not unsplash_route.is_photo_path(photo_path):
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Not found")
        try:
            params = unsplash_route.clean_params(query)
        except unsplash_route.BadImageParams as bad:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, content=str(bad))
        api = settings.api_settings
        # an IPv6 client by its /64
        client_id = rate_limit_key(client)
        verdict = await self._limiter.hit(
            PROXY_SCOPE,
            client_id,
            api.IMAGE_PROXY_PER_WINDOW,
            api.IMAGE_PROXY_WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise _too_many(verdict)

        wanted = unsplash_route.fetch_params(params)
        key = unsplash_route.cache_key(photo_path, wanted)
        known = self._known.get(key)
        if known:
            self._known.move_to_end(key)
            return known
        object_key = f"{CACHE_FOLDER}/{key[:2]}/{key}"
        # one fetch per photo and size at a time in this process
        lock, users = self._locks.get(key, (None, 0))
        if lock is None:
            lock = asyncio.Lock()
        self._locks[key] = (lock, users + 1)
        try:
            async with lock:
                if key in self._known:
                    return self._known[key]
                if await asyncio.to_thread(self._aws.public_object_exists, object_key):
                    url = self._aws.public_url_of(object_key)
                else:
                    url = await self._fetch_unsplash(
                        photo_path, wanted, object_key, client_id
                    )
                self._remember(key, url)
                return url
        finally:
            lock, users = self._locks[key]
            if users <= 1:
                del self._locks[key]
            else:
                self._locks[key] = (lock, users - 1)

    async def _fetch_unsplash(
        self, photo_path: str, wanted: Dict[str, str], object_key: str, client: str
    ) -> str:
        api = settings.api_settings
        verdict = await self._limiter.hit(
            PROXY_FETCH_SCOPE,
            client,
            api.IMAGE_PROXY_FETCHES_PER_WINDOW,
            api.IMAGE_PROXY_WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise _too_many(verdict)
        # and a bound on all of them together: many addresses can't make us
        # fetch (and re-encode) more than this from Unsplash per window
        verdict = await self._limiter.hit(
            PROXY_GLOBAL_FETCH_SCOPE,
            GLOBAL_CLIENT,
            api.IMAGE_PROXY_GLOBAL_FETCHES_PER_WINDOW,
            api.IMAGE_PROXY_WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise _too_many(verdict)
        try:
            fetched = await fetch_image(
                unsplash_route.upstream_url(photo_path, wanted),
                allowed_hosts={unsplash_route.UNSPLASH_IMAGE_HOST},
                max_redirects=0,
            )
            checked = await reencode(fetched.data)
        except (FetchRefused, ImageRefused) as refused:
            logger.info(f"Unsplash image not served: {refused.code}")
            raise HTTPException(
                status_code=HTTPStatus.BAD_GATEWAY,
                content="The image could not be loaded.",
            )
        except SandboxUnavailable:
            logger.warning(
                "Unsplash image not served: the document sandbox is unavailable."
            )
            raise _unavailable("Images are unavailable. Try again in a moment.")
        return await asyncio.to_thread(
            self._aws.put_public_object,
            body=checked.data,
            key=object_key,
            content_type=checked.content_type,
        )

    # -- an image address pasted in the editor -------------------------------

    async def import_image(
        self, workspace_id: PydanticObjectId, url: str, user: User
    ) -> str:
        """Our address for the image at ``url``: as is when it is already
        first-party (an Unsplash photo by its canonical address), else a copy in
        our bucket. Raises 422 with a plain-language message the editor
        shows, 429 or 503."""
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        if not isinstance(url, str) or not url.strip():
            raise _copy_failed("invalid_url")
        first_party = first_party_image_url(url)
        if first_party is not None:
            return first_party
        api = settings.api_settings
        verdict = await self._limiter.hit(
            IMPORT_SCOPE,
            str(user.id),
            api.IMAGE_IMPORTS_PER_WINDOW,
            api.IMAGE_IMPORTS_WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise _too_many(verdict)
        try:
            fetched = await fetch_image(url.strip())
            checked = await reencode(fetched.data)
        except (FetchRefused, ImageRefused) as refused:
            # the code only: never the address, which may be private
            logger.info(f"Image copy refused: {refused.code}")
            raise _copy_failed(refused.code)
        except SandboxUnavailable:
            logger.warning("Image copy refused: the document sandbox is unavailable.")
            raise _unavailable(
                "Copying images is unavailable right now. Try again in a moment, "
                "or upload the image instead."
            )
        safe_workspace = "".join(c for c in str(workspace_id) if c.isalnum())
        key = f"{MEDIA_FOLDER}/{safe_workspace}/{uuid.uuid4().hex}.{checked.extension}"
        return await asyncio.to_thread(
            self._aws.put_public_object,
            body=checked.data,
            key=key,
            content_type=checked.content_type,
        )
