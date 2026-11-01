"""Drawn signature images in the keyset rotation (``scripts/rotate_response_keyset.py``).

Lives with the script, not in ``backend.admin.tasks.impl``: it uses the public
application's storage service and signature binding, which the task runner
never imports (``tests/admin/tasks/test_isolation.py``).

A drawn signature's image is sealed with the response keyset
(``backend.app.services.signatures.seal_image``) and kept as an object in the
file store, ``private/<workspace>/<form>/<response>/<file id>``, not in a row.
The row walk of ``keyset_core`` therefore never sees it: an image keeps the key
it was sealed with, and dropping that key would make it unreadable. This module
finds the images through the responses' answers and

* ``DrawnImages.scan`` counts them by the key they are sealed with (the key id
  is the ciphertext's header: nothing is decrypted), for ``reencrypt --dry-run``
  and for the ``drop-old`` guard;
* ``DrawnImages.reencrypt`` re-seals each one that is not under the primary key,
  with the same binding (workspace, form, response, question, file), puts it
  back under the same key and checks it reads back.

Every response is looked at, whether or not its own values are stale: a
response re-encrypted by an earlier run can still hold an image on an old key.

Counts only (never an id of a person, a path or a byte of an image). A storage
failure is counted and never ends the run; an object that is not there is
counted apart (``images_missing``: nothing to lose); an object that is not a
sealed image of this keyset, or that no candidate context opens, is
``images_unreadable`` / ``images_unopenable``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from common.services.keyset import (
    UnreadableCiphertext,
    ciphertext_key_id,
    is_ciphertext,
)

logger = logging.getLogger("rotate_response_keyset")

# The counters that stop ``drop-old``: an image still under a key other than the
# primary (that key is about to go), and one whose state could not be told or
# cannot be fixed here. ``images_missing`` does not: an object that is gone has
# nothing to lose.
BLOCKING = (
    "images_stale",
    "images_unreadable",
    "images_unopenable",
    "images_storage_errors",
    "images_unlocatable",
)


class ObjectTooLarge(Exception):
    """The object is larger than a sealed image can be."""


class ObjectStoreError(Exception):
    """The file store could not be read or written. Carries the error's type
    only, never the driver's message."""


class S3Objects:
    """The file store, through the backend's storage service (``AWSS3Service``
    with the ``AWS_*`` settings the backend runs with). Built on first use, so
    a rotation with no drawn signature never needs it."""

    def __init__(self, service: Any = None):
        self._service = service

    def _get(self):
        if self._service is None:
            from backend.app.services.aws_service import AWSS3Service
            from backend.config import settings

            aws = settings.aws_settings
            if not (aws.ACCESS_KEY_ID and aws.SECRET_ACCESS_KEY):
                raise ObjectStoreError("storage credentials not set")
            self._service = AWSS3Service(aws.ACCESS_KEY_ID, aws.SECRET_ACCESS_KEY)
        return self._service

    async def read(self, key: str) -> Optional[bytes]:
        """The object; ``None`` when the store says it does not exist."""
        from backend.app.services.signatures import SEALED_MAX_BYTES

        try:
            service = self._get()
            return await asyncio.to_thread(
                service.read_private_object, key, SEALED_MAX_BYTES
            )
        except ValueError:
            raise ObjectTooLarge from None
        except ObjectStoreError:
            raise
        except Exception as error:  # noqa: BLE001 - never surface a driver message
            raise ObjectStoreError(type(error).__name__) from None

    async def write(self, key: str, data: bytes) -> None:
        from backend.app.services.signatures import SEALED_CONTENT_TYPE

        try:
            service = self._get()
            await asyncio.to_thread(
                service.write_private_object, key, data, SEALED_CONTENT_TYPE
            )
        except ObjectStoreError:
            raise
        except Exception as error:  # noqa: BLE001
            raise ObjectStoreError(type(error).__name__) from None


@dataclass(frozen=True)
class Image:
    """One drawn signature of a response: where it is and what binds it."""

    response_id: str
    field_id: str
    file_id: str
    candidates: Tuple[Tuple[str, str], ...]  # (workspace, form) it may belong to

    def key(self, workspace: str, form_id: str) -> str:
        return f"private/{workspace}/{form_id}/{self.response_id}/{self.file_id}"

    def context(self) -> bytes:
        from backend.app.services.signatures import image_context

        return image_context(self.response_id, self.field_id, self.file_id)


@dataclass
class Found:
    """What a look at an image's object found."""

    status: str  # missing | error | unreadable | current | stale
    data: bytes = b""
    workspace: str = ""
    form_id: str = ""
    key_id: Optional[int] = None


def drawn_images(
    rotation,
    target,
    record: Dict[str, Any],
    links: Dict[str, List[str]],
    counts: Counter,
) -> List[Image]:
    """The drawn signatures a response's answers name. The answers are opened
    with the keyset (the plaintext is dropped at once); answers no context
    opens are counted (``images_answers_unopenable``): their images cannot
    be found."""
    from backend.app.services.form_response_service import is_plain_file_id

    answers = record.get("answers")
    contexts = target.contexts(record, links)
    candidates: Tuple[Tuple[str, str], ...]
    if is_ciphertext(answers):
        context, plain = rotation._open(contexts, bytes(answers))
        if context is None:
            counts["images_answers_unopenable"] += 1
            return []
        try:
            document = json.loads(plain)
        except (ValueError, TypeError):
            return []
        candidates = (context,)
    elif isinstance(answers, dict):
        document, candidates = answers, tuple(contexts)
    else:
        return []
    if not isinstance(document, dict):
        return []
    response_id = record.get("response_id")
    found: List[Image] = []
    for field_id, answer in document.items():
        value = answer.get("signature") if isinstance(answer, dict) else None
        if (
            not isinstance(value, dict)
            or value.get("method") != "drawn"
            or not value.get("file_id")
        ):
            continue
        file_id = value["file_id"]
        if not (isinstance(response_id, str) and response_id) or not is_plain_file_id(
            file_id
        ):
            # the object cannot be located: unknown, so it blocks drop-old
            counts["images_drawn"] += 1
            counts["images_unlocatable"] += 1
            continue
        found.append(Image(response_id, str(field_id), file_id, candidates))
    return found


def _count(counts: Counter, found: Found) -> None:
    if found.status == "error":
        counts["images_storage_errors"] += 1
    elif found.status in ("missing", "unreadable", "current"):
        counts[f"images_{found.status}"] += 1
    if found.key_id is not None:
        counts[f"images_key_{found.key_id}"] += 1


class DrawnImages:
    """The image pass, for ``keyset_core.scan`` and ``reencrypt_store``.
    ``objects``: ``read(key) -> bytes | None`` and ``write(key, data)``
    (``S3Objects``; a test passes an in-memory one)."""

    def __init__(self, objects: Any = None):
        self.objects = objects if objects is not None else S3Objects()

    async def _look(self, rotation, image: Image) -> Found:
        failed = False
        for workspace, form_id in image.candidates:
            try:
                data = await self.objects.read(image.key(workspace, form_id))
            except ObjectTooLarge:
                return Found("unreadable")
            except ObjectStoreError as failure:
                logger.warning(
                    "response %s: the file store could not be read for a "
                    "signature image (%s)",
                    image.response_id,
                    failure,
                )
                failed = True
                continue
            if data is None:
                continue
            key_id = ciphertext_key_id(data) if is_ciphertext(data) else None
            if key_id is None:  # not a sealed image of a keyset
                return Found("unreadable")
            return Found(
                "current" if key_id == rotation.primary else "stale",
                data,
                workspace,
                form_id,
                key_id,
            )
        return Found("error" if failed else "missing")

    async def scan(self, rotation, target, record, links, counts: Counter) -> None:
        """Counts only; changes nothing."""
        for image in drawn_images(rotation, target, record, links, counts):
            counts["images_drawn"] += 1
            found = await self._look(rotation, image)
            if found.status == "stale":
                counts["images_stale"] += 1
            _count(counts, found)

    async def reencrypt(
        self, rotation, target, record, links, counts: Counter
    ) -> None:
        """Seal each image of the response that is not under the primary key
        again, in place. Safe to repeat."""
        for image in drawn_images(rotation, target, record, links, counts):
            counts["images_drawn"] += 1
            found = await self._look(rotation, image)
            _count(counts, found)
            if found.status == "stale":
                await self._reseal(rotation, image, found, counts)

    async def _reseal(self, rotation, image: Image, found: Found, counts: Counter):
        context = image.context()
        key = image.key(found.workspace, found.form_id)
        try:
            plain = rotation.cipher.decrypt(
                found.workspace, found.form_id, found.data, context
            )
        except UnreadableCiphertext:
            counts["images_unopenable"] += 1
            logger.warning(
                "response %s: a signature image is not opened by its context; "
                "left as it is",
                image.response_id,
            )
            return
        new = rotation.cipher.encrypt(found.workspace, found.form_id, plain, context)
        if (
            ciphertext_key_id(new) != rotation.primary
            or rotation.cipher.decrypt(found.workspace, found.form_id, new, context)
            != plain
        ):
            raise RuntimeError("a re-sealed image did not read back")
        try:
            # a respondent's edit may have replaced the image since it was
            # read: write only over the object that was read
            if await self.objects.read(key) != found.data:
                counts["images_changed_concurrently"] += 1
                logger.info(
                    "response %s: a signature image changed while it was read; "
                    "left for the next run",
                    image.response_id,
                )
                return
            await self.objects.write(key, new)
            if await self.objects.read(key) != new:
                counts["images_readback_failed"] += 1
                logger.warning(
                    "response %s: a re-sealed signature image did not read back "
                    "as written; not counted",
                    image.response_id,
                )
                return
        except (ObjectStoreError, ObjectTooLarge) as failure:
            counts["images_storage_errors"] += 1
            logger.warning(
                "response %s: a signature image could not be re-sealed (%s)",
                image.response_id,
                failure,
            )
            return
        counts["images_resealed"] += 1


def blocking(counts: Dict[str, int]) -> Dict[str, int]:
    """The counters of ``counts`` that stop ``drop-old``, those above zero."""
    return {name: counts[name] for name in BLOCKING if counts.get(name)}
