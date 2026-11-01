"""Signature questions: the drawn image and the stamp on a stored signature.

A ``signature`` answer is a drawn image or a typed name (``common/signature.py``
holds the answer's shape). The typed name is plain text in the answer. The drawn
image is a PNG the respondent's browser made; it is stored like an uploaded
file, as a private object under the response's folder, and the answer holds only
its id.

What happens to it before anything is stored (``prepare_signatures``, run by a
submission and by a respondent's edit once the answers are known to be valid):

- an image must be named by a drawn answer of a signature question and sent with
  that question; an id with no image, an image for another question, a second
  image for one question and an id the response does not hold are refused
  (422 ``invalid_answers``, rule ``signature_image``). An image sent for a
  signature question that no answer names is dropped, never stored;
- this process never decodes the image: it checks size and the PNG signature,
  then the isolated document sandbox decodes it and writes a fresh PNG without
  metadata (the ``image`` mode the logo upload and fetched pictures use). What
  the sandbox returns is untrusted too and is checked again. The stored object
  is that re-encoding, never the upload. Without the sandbox a drawn signature
  is refused (503 "try again"); a typed one never needs it;
- drawn signatures are anonymous work on a shared resource: they take at most
  half the sandbox's slots, wait for one of theirs only briefly and the whole
  call is cut off (503 either way), and one client address or one form may send
  only so many a minute (429);
- the stored object is the PNG **encrypted with the response keyset** (the one
  that encrypts the response's answers), bound to the workspace, form, response,
  question and file, so a copy moved to another response or question does not
  decrypt. It is read back only by the authorised single-response image route
  (``FormResponseService.signature_image``), never through a storage link;
- a file part must belong to a file upload or signature question of the form,
  and never carries the id of a file another question of the response holds,
  so an edit can't replace a stored drawing with bytes of its own;
- an image with no ink at all cannot be told apart without decoding it here,
  which this process never does: the respondent form never sends one (nothing
  drawn is no answer), and a hand-made one only signs with a blank image;
- the server stamps ``signed_at`` (a respondent's clock is no evidence); on an
  edit the stamp changes only when the signature did.

Nothing here claims a signature has legal weight.
"""

import asyncio
import base64
import binascii
import datetime as dt
import io
import json
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Set
from urllib.parse import quote

from loguru import logger
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.services.answer_validation import (
    ERROR_CODE,
    ERROR_MESSAGE,
    SIGNATURE_IMAGE,
    signature_shape,
    signature_problem,
)
from backend.app.services.new_question_types import _walk
from backend.app.services.pdf_import import sandbox
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.sandbox import SandboxUnavailable

SIGNATURE = "signature"
# What a browser sends: at most 1200 x 600 px of dark ink on transparent
# pixels, a few KB. The cap leaves room and bounds the sandbox's work.
UPLOAD_MAX_BYTES = 150 * 1024
STORED_MAX_BYTES = 150 * 1024
MAX_PIXELS = 1_000_000
MIN_SIDE = 16
MAX_WIDTH = 2000
MAX_HEIGHT = 1000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The sandbox's own limit for one image; its socket read allows 15 s more
# (pdf_import/sandbox.py).
SANDBOX_TIMEOUT_S = 10
SANDBOX_MEMORY_MB = 512
# Drawn signatures take at most half the sandbox's parallel slots (the logo
# upload and the PDF import share them) and wait at most GATE_WAIT_S for one of
# theirs; once in, the whole sandbox call (a shared slot included) is over
# after CALL_LIMIT_S. Either way the signature is refused with 503 "try again":
# respondents are anonymous, so nothing of theirs waits without a bound.
GATE_WAIT_S = 2
CALL_LIMIT_S = 20
# Drawn signatures one client address (a /64 for IPv6) and one form may send
# in a minute (429 beyond); a browser sends one per signature question. The
# limit counts images, not submissions. Clients with no readable address share
# a small per-form bucket instead of one for everybody.
PER_CLIENT_PER_MINUTE = 20
PER_FORM_PER_MINUTE = 300
# All clients of a form whose address is unknown, together (see signature_throttle).
PER_UNKNOWN_PER_FORM_PER_MINUTE = 10

BUSY_MESSAGE = (
    "Too many drawn signatures are being processed. Try again in a moment, or "
    "type your name instead."
)
UNAVAILABLE_MESSAGE = (
    "Processing a drawn signature is unavailable. Try again in a moment, or "
    "type your name instead."
)


# What the encrypted object is stored as (it is ciphertext, not an image).
SEALED_CONTENT_TYPE = "application/octet-stream"
# The Tink prefix and key id, the version prefix and the tag are added to the
# image (common/services/keyset.py): a little under 40 bytes.
SEALED_MAX_BYTES = STORED_MAX_BYTES + 256
# A signed-in user may fetch this many drawn images a minute (one response page
# shows one or a few).
READS_PER_MINUTE = 60


def image_context(response_id: Any, field_id: Any, file_id: Any) -> bytes:
    """What an image is bound to besides the workspace and form the keyset's
    cipher already binds (``workspace|form|`` + this, as the AEAD's associated
    data). A JSON list, so no choice of ids can make two different tuples read
    the same."""
    return json.dumps(
        ["signature-image", str(response_id), str(field_id), str(file_id)],
        separators=(",", ":"),
    ).encode()


def seal_image(
    workspace_id: Any,
    form_id: Any,
    response_id: Any,
    field_id: Any,
    file_id: Any,
    png: bytes,
) -> bytes:
    """The image encrypted with the response keyset (its current primary key;
    the ciphertext names the key, so rotation re-encrypts it like the answers)."""
    from common.services.crypto_service import crypto_service

    return crypto_service.encrypt(
        str(workspace_id),
        str(form_id),
        png,
        image_context(response_id, field_id, file_id),
    )


def open_image(
    workspace_id: Any,
    form_id: Any,
    response_id: Any,
    field_id: Any,
    file_id: Any,
    stored: bytes,
) -> Optional[bytes]:
    """The PNG in a stored object, or None when it is not what is stored
    here: not ciphertext (an image stored before encryption existed is never
    served), bound to another response, question or file, or not a PNG of
    the size ``prepare_signatures`` allows."""
    from common.services.crypto_service import UnreadableCiphertext, crypto_service
    from common.services.keyset import is_ciphertext

    if not isinstance(stored, (bytes, bytearray)) or not is_ciphertext(stored):
        return None
    try:
        data = crypto_service.decrypt(
            str(workspace_id),
            str(form_id),
            bytes(stored),
            image_context(response_id, field_id, file_id),
        )
    except UnreadableCiphertext:
        return None
    if not isinstance(data, bytes) or not data.startswith(PNG_SIGNATURE):
        return None
    if len(data) > STORED_MAX_BYTES:
        return None
    return data


def signature_image_path(workspace_id: Any, response_id: Any, field_id: Any) -> str:
    """The path (under the API's root) of the route serving a drawn signature's
    image: what the single-response read carries in place of a link."""
    return (
        f"/workspaces/{quote(str(workspace_id), safe='')}"
        f"/submissions/{quote(str(response_id), safe='')}"
        f"/signatures/{quote(str(field_id), safe='')}"
    )


async def read_throttle(user_id: Any) -> None:
    """429 when this user fetched too many drawn images in the last minute."""
    from backend.app.container import container

    verdict = await container.rate_limiter().hit(
        "signature_image_read", str(user_id), READS_PER_MINUTE, 60
    )
    if not verdict.allowed:
        raise HTTPException(
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            content={"code": "rate_limited", "message": "Too many requests; try again later."},
            headers={"Retry-After": str(verdict.retry_after)},
        )


@dataclass
class PreparedSignatures:
    """``answers``: the answers with every signature answer rebuilt from what
    is allowed (and stamped). ``form_files``: the parts to store (a signature
    part is the sandbox's re-encoding). ``replaced``: ids of images stored
    earlier that no answer names any more (an edit that redrew or retyped)."""

    answers: Any
    form_files: Optional[list]
    replaced: List[str] = field(default_factory=list)


def signature_fields(form: Any) -> Dict[str, Any]:
    """The form's signature questions by id."""
    found: Dict[str, Any] = {}
    for item in _walk(form):
        kind = getattr(item, "type", None)
        if getattr(kind, "value", kind) == SIGNATURE and getattr(item, "id", None):
            found[str(item.id)] = item
    return found


def _problem(field_id: str) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={
            "code": ERROR_CODE,
            "message": ERROR_MESSAGE,
            "errors": [{"fieldId": field_id, "rule": SIGNATURE_IMAGE}],
        },
    )


async def _process_in_sandbox(data: bytes) -> dict:
    """The sandbox's re-encoding (``pdf_import/logo_image.py``). Tests replace it."""
    from backend.config import settings

    s = settings.pdf_import
    return await sandbox.run_image(
        data,
        max_pages=1,
        max_pixels=MAX_PIXELS,
        timeout_s=SANDBOX_TIMEOUT_S,
        memory_mb=SANDBOX_MEMORY_MB,
        max_parallel=s.MAX_PARALLEL_SANDBOXES,
        max_result_bytes=4 * STORED_MAX_BYTES,
        socket_path=s.SANDBOX_SOCKET,
        require_isolated=True,
    )


_gate: Optional[asyncio.Semaphore] = None
_gate_size = 0


def _signature_gate() -> asyncio.Semaphore:
    """The semaphore of drawn signatures in the sandbox: half its parallel
    slots (at least one), separate from the logo and the PDF import's."""
    global _gate, _gate_size
    from backend.config import settings

    size = max(1, settings.pdf_import.MAX_PARALLEL_SANDBOXES // 2)
    if _gate is None or _gate_size != size:
        _gate, _gate_size = asyncio.Semaphore(size), size
    return _gate


async def signature_throttle(workspace_id: Any, form_id: Any, client: Optional[str]) -> None:
    """429 when this client or this form sent too many drawn signatures in
    the last minute (services/rate_limiter.py; counters are keyed hashes).
    Called once per drawn image.

    A client whose address can't be told (``rate_limit_key`` gives "unknown")
    never shares a bucket with every other such client on the platform: it is
    counted under its form, with the small cap PER_UNKNOWN_PER_FORM_PER_MINUTE
    for all unknown clients of that form together, so it fails closed for that
    form only."""
    from backend.app.container import container
    from backend.app.utils.client_ip import rate_limit_key

    limiter = container.rate_limiter()
    form = f"{workspace_id}:{form_id}"
    address = rate_limit_key(client)
    if address == "unknown":
        client_bucket = ("signature_unknown_client", form, PER_UNKNOWN_PER_FORM_PER_MINUTE)
    else:
        client_bucket = ("signature_client", address, PER_CLIENT_PER_MINUTE)
    for scope, key, limit in (
        client_bucket,
        ("signature_form", form, PER_FORM_PER_MINUTE),
    ):
        verdict = await limiter.hit(scope, key, limit, 60)
        if not verdict.allowed:
            raise HTTPException(
                status_code=HTTPStatus.TOO_MANY_REQUESTS,
                content={"code": "rate_limited", "message": "Too many requests; try again later."},
                headers={"Retry-After": str(verdict.retry_after)},
            )


def _accept(result: Any) -> Optional[bytes]:
    """The sandbox parsed an attacker's file: check everything it returns.
    The re-encoded PNG, or None when anything is off."""
    if not isinstance(result, dict) or result.get("format") != "png":
        return None
    width, height = result.get("width"), result.get("height")
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (width, height)):
        return None
    if min(width, height) < MIN_SIDE or width > MAX_WIDTH or height > MAX_HEIGHT:
        return None
    if width * height > MAX_PIXELS:
        return None
    encoded = result.get("data")
    if not isinstance(encoded, str) or len(encoded) > 2 * STORED_MAX_BYTES:
        return None
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not data.startswith(PNG_SIGNATURE):
        return None
    if not data or len(data) > STORED_MAX_BYTES:
        return None
    return data


async def checked_image(data: bytes, field_id: str) -> bytes:
    """The PNG to store for an uploaded drawing, or a refusal: 422 for an
    image that is empty, too large, not a PNG, not readable or blank; 503 when
    the sandbox is unavailable (never the respondent's fault)."""
    if not data or len(data) > UPLOAD_MAX_BYTES or not data.startswith(PNG_SIGNATURE):
        raise _problem(field_id)
    gate = _signature_gate()
    try:
        await asyncio.wait_for(gate.acquire(), GATE_WAIT_S)
    except asyncio.TimeoutError:
        logger.warning("Drawn signature refused: the signature slots of the sandbox are busy.")
        raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE, content=BUSY_MESSAGE)
    try:
        result = await asyncio.wait_for(_process_in_sandbox(data), CALL_LIMIT_S)
    except asyncio.TimeoutError:
        logger.warning("Drawn signature refused: the sandbox did not answer in time.")
        raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE, content=BUSY_MESSAGE)
    except SandboxUnavailable:
        logger.warning("Drawn signature refused: the document sandbox is unavailable.")
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE, content=UNAVAILABLE_MESSAGE
        )
    except DocumentRefused:
        raise _problem(field_id)
    finally:
        gate.release()
    accepted = _accept(result)
    if accepted is None:
        raise _problem(field_id)
    return accepted


def _plain(answer: Any) -> Any:
    if hasattr(answer, "model_dump"):
        return answer.model_dump(mode="json", exclude_none=True)
    return answer


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stored_signature(stored: Any, field_id: str) -> Optional[Dict[str, Any]]:
    answer = _plain((stored or {}).get(field_id))
    value = answer.get("signature") if isinstance(answer, dict) else None
    return value if isinstance(value, dict) and signature_shape(value) else None


async def _read(part: Any) -> bytes:
    """The bytes of an uploaded part, at most one over the cap."""
    stream = part.file
    if hasattr(stream, "read"):
        data = await stream.read(UPLOAD_MAX_BYTES + 1)
        if hasattr(stream, "seek"):
            await stream.seek(0)
        return data
    return b""


def _replacement(part: Any, data: bytes) -> Any:
    """``part`` with the sandbox's bytes in place of the upload, marked so the
    store encrypts it (``upload_files_to_s3_and_update_url``)."""
    from fastapi import UploadFile

    from backend.app.models.dtos.response_dtos import FormFileResponse

    return FormFileResponse(
        file_id=part.file_id,
        field_id=part.field_id,
        filename=f"{part.file_id}.png",
        file=UploadFile(file=io.BytesIO(data), filename=f"{part.file_id}.png"),
        content_type=SEALED_CONTENT_TYPE,
        signature=True,
    )


FILE_QUESTIONS = ("file_upload", "input_file_upload")


def part_fields(*forms: Any) -> Set[str]:
    """The ids of the questions a file part may belong to: the file upload
    and signature questions of the forms given."""
    found: Set[str] = set()
    for form in forms:
        for item in _walk(form):
            kind = getattr(item, "type", None)
            if getattr(kind, "value", kind) in (SIGNATURE, *FILE_QUESTIONS) and getattr(item, "id", None):
                found.add(str(item.id))
    return found


def signature_ids_of(*forms: Any) -> Set[str]:
    """The ids of the signature questions of the forms given."""
    found: Set[str] = set()
    for form in forms:
        found.update(signature_fields(form))
    return found


def _stored_file_ids(stored: Any) -> Dict[str, str]:
    """The id of the file each stored answer holds, by question: a drawn
    signature's image and an upload's file."""
    found: Dict[str, str] = {}
    for key, raw in (stored or {}).items():
        answer = _plain(raw)
        if not isinstance(answer, dict):
            continue
        signature = answer.get("signature")
        meta = answer.get("file_metadata")
        if isinstance(signature, dict) and signature.get("file_id"):
            found[str(key)] = str(signature["file_id"])
        elif isinstance(meta, dict) and meta.get("id"):
            found[str(key)] = str(meta["id"])
    return found


def _refuse_files(message: str = "Invalid file.") -> HTTPException:
    return HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content=message)


def _without_foreign_signatures(answers: Any, fields: Dict[str, Any]) -> Any:
    """``answers`` without a ``signature`` slot on any key that is not a
    signature question of the form (the slot is meaningless there)."""
    if not isinstance(answers, dict):
        return answers
    out = answers
    for key, raw in answers.items():
        if key in fields:
            continue
        answer = _plain(raw)
        if isinstance(answer, dict) and answer.get("signature") is not None:
            if out is answers:
                out = dict(answers)
            out[key] = {k: v for k, v in answer.items() if k != "signature"}
    return out


async def prepare_signatures(
    form: Any,
    answers: Any,
    form_files: Optional[list],
    stored: Any = None,
    also: Iterable[Any] = (),
    throttle: Optional[Callable[[], Awaitable[None]]] = None,
) -> PreparedSignatures:
    """Check, process and stamp the signatures of a submission (``stored``
    None) or of a respondent's edit (``stored``: the answers before the edit,
    of which ``answers`` carries the changed ones).

    Whatever the form, a file part must belong to a file upload or signature
    question of the form (``also``: other versions of it whose ids answers may
    use), and a part never carries the id of a file another question of this
    response holds: a stored drawing is only ever replaced by the sandbox's
    re-encoding of a drawing for its own question. ``throttle`` is awaited
    before each drawing goes to the sandbox (the limit counts images)."""
    fields = signature_fields(form)
    answers = _without_foreign_signatures(answers, fields)
    parts = list(form_files or [])
    stored_ids = _stored_file_ids(stored)
    if parts:
        allowed = part_fields(form, *also)
        ids = [str(part.file_id) for part in parts]
        if len(set(ids)) != len(ids):
            # two parts with one id would overwrite one object
            raise _refuse_files("Invalid file id.")
        for part in parts:
            if str(part.field_id) not in allowed:
                raise _refuse_files()
            owner = next((k for k, v in stored_ids.items() if v == str(part.file_id)), None)
            if owner is not None and owner != str(part.field_id):
                raise _refuse_files("Invalid file id.")
    # A part for a signature question is only ever stored as the sandbox's
    # re-encoding of a drawing a drawn answer of the form names. Without such an
    # answer to bind it (no answers at all, as in an edit that sends none, or a
    # question that exists only in another version of the form) it is refused:
    # passing it through would store its raw bytes, possibly over the stored image.
    other_versions = signature_ids_of(*also)
    uploads = part_fields(form) - set(fields)
    for part in parts:
        field_id = str(part.field_id)
        if field_id in fields:
            if not isinstance(answers, dict):
                raise _refuse_files()
        elif field_id in other_versions and field_id not in uploads:
            raise _refuse_files()
    if not fields or not isinstance(answers, dict):
        return PreparedSignatures(answers, form_files)
    by_field: Dict[str, list] = {}
    kept: list = []
    for part in parts:
        if str(part.field_id) in fields:
            by_field.setdefault(str(part.field_id), []).append(part)
        else:
            kept.append(part)

    out = dict(answers)
    replaced: List[str] = []
    named: Dict[str, str] = {}
    for field_id in fields:
        mine = by_field.get(field_id, [])
        if field_id not in answers:
            # an edit that does not touch the question keeps what is stored;
            # an image nobody names is dropped
            continue
        answer = _plain(answers[field_id])
        value = answer.get("signature") if isinstance(answer, dict) else None
        if value is None:
            # emptied (an edit clearing it): the stored image goes
            previous = _stored_signature(stored, field_id)
            if previous and previous.get("file_id"):
                replaced.append(str(previous["file_id"]))
            continue
        if not isinstance(value, dict) or not signature_shape(value):
            raise _problem(field_id)
        if signature_problem(value):
            raise _problem(field_id)
        previous = _stored_signature(stored, field_id)
        previous_id = str(previous["file_id"]) if previous and previous.get("file_id") else None
        clean: Dict[str, Any]
        if value["method"] == "typed":
            clean = {"method": "typed", "name": value["name"]}
            unchanged = (
                previous
                and previous.get("method") == "typed"
                and previous.get("name") == value["name"]
            )
            clean["signed_at"] = (
                previous.get("signed_at") if unchanged and previous.get("signed_at") else _now()
            )
            if previous_id:
                replaced.append(previous_id)
        else:
            file_id = str(value["file_id"])
            # another question's file, or one another signature names, is not this one's to name
            held_elsewhere = any(owner != field_id and held == file_id for owner, held in stored_ids.items())
            if held_elsewhere or file_id in named:
                raise _problem(field_id)
            named[file_id] = field_id
            matching = [part for part in mine if str(part.file_id) == file_id]
            if len(mine) > 1 or (mine and not matching):
                raise _problem(field_id)
            if matching:
                if throttle is not None:
                    await throttle()
                data = await checked_image(await _read(matching[0]), field_id)
                kept.append(_replacement(matching[0], data))
                clean = {"method": "drawn", "file_id": file_id, "signed_at": _now()}
                if previous_id and previous_id != file_id:
                    replaced.append(previous_id)
            elif previous and previous.get("method") == "drawn" and previous_id == file_id:
                # an edit that sends the stored answer back: nothing changes
                clean = {
                    "method": "drawn",
                    "file_id": file_id,
                    "signed_at": previous.get("signed_at") or _now(),
                }
            else:
                raise _problem(field_id)
        rebuilt = {k: v for k, v in answer.items() if k != "signature"}
        rebuilt["type"] = SIGNATURE
        rebuilt["signature"] = clean
        out[field_id] = rebuilt
    # what the response still holds after the edit is never deleted: the
    # images of the signatures it ends with (changed or not) and the files of
    # its other questions
    in_use = set(named)
    for key, held in stored_ids.items():
        if key not in fields or key not in answers:
            in_use.add(held)
    replaced = [file_id for file_id in dict.fromkeys(replaced) if file_id not in in_use]
    return PreparedSignatures(out, kept or None, replaced)


async def delete_stored_images(
    aws: Any, workspace_id: Any, form_id: Any, response_id: Any, file_ids: List[str]
) -> None:
    """Remove drawn images an edit replaced. A storage failure never fails the
    edit (the response's folder goes with the response anyway); only ids are
    logged."""
    from backend.app.services.form_response_service import is_plain_file_id

    for file_id in file_ids:
        if not is_plain_file_id(file_id):
            continue
        try:
            # blocking storage call: off the event loop
            await run_in_threadpool(
                aws.delete_file_from_s3,
                key=f"private/{workspace_id}/{form_id}/{response_id}/{file_id}",
            )
        except Exception:  # noqa: BLE001 - never fail the edit over storage
            logger.warning(
                "Response {}: a replaced signature image could not be removed",
                response_id,
            )
