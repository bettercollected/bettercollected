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
- an image with no ink at all cannot be told apart without decoding it here,
  which this process never does: the respondent form never sends one (nothing
  drawn is no answer), and a hand-made one only signs with a blank image;
- the server stamps ``signed_at`` (a respondent's clock is no evidence); on an
  edit the stamp changes only when the signature did.

Nothing here claims a signature has legal weight.
"""

import base64
import binascii
import datetime as dt
import io
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Dict, List, Optional

from loguru import logger

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
# What a browser sends: at most 1200 x 480 px of dark ink on transparent
# pixels, a few KB. The cap leaves room and bounds the sandbox's work.
UPLOAD_MAX_BYTES = 150 * 1024
STORED_MAX_BYTES = 150 * 1024
MAX_PIXELS = 1_000_000
MIN_SIDE = 16
MAX_WIDTH = 2000
MAX_HEIGHT = 1000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SANDBOX_TIMEOUT_S = 15
SANDBOX_MEMORY_MB = 512

UNAVAILABLE_MESSAGE = (
    "Processing a drawn signature is unavailable. Try again in a moment, or "
    "type your name instead."
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
    try:
        result = await _process_in_sandbox(data)
    except SandboxUnavailable:
        logger.warning("Drawn signature refused: the document sandbox is unavailable.")
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE, content=UNAVAILABLE_MESSAGE
        )
    except DocumentRefused:
        raise _problem(field_id)
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
    """``part`` with the sandbox's bytes in place of the upload."""
    from fastapi import UploadFile

    from backend.app.models.dtos.response_dtos import FormFileResponse

    return FormFileResponse(
        file_id=part.file_id,
        field_id=part.field_id,
        filename=f"{part.file_id}.png",
        file=UploadFile(file=io.BytesIO(data), filename=f"{part.file_id}.png"),
    )


async def prepare_signatures(
    form: Any,
    answers: Any,
    form_files: Optional[list],
    stored: Any = None,
) -> PreparedSignatures:
    """Check, process and stamp the signatures of a submission (``stored``
    None) or of a respondent's edit (``stored``: the answers before the edit,
    of which ``answers`` carries the changed ones). A form with no signature
    question is returned untouched."""
    fields = signature_fields(form)
    if not fields or not isinstance(answers, dict):
        return PreparedSignatures(answers, form_files)
    parts = list(form_files or [])
    ids = [str(part.file_id) for part in parts]
    if len(set(ids)) != len(ids):
        # two parts with one id would overwrite one object
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content="Invalid file id."
        )
    by_field: Dict[str, list] = {}
    kept: list = []
    for part in parts:
        if str(part.field_id) in fields:
            by_field.setdefault(str(part.field_id), []).append(part)
        else:
            kept.append(part)

    out = dict(answers)
    replaced: List[str] = []
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
            named = [part for part in mine if str(part.file_id) == file_id]
            if len(mine) > 1 or (mine and not named):
                raise _problem(field_id)
            if named:
                data = await checked_image(await _read(named[0]), field_id)
                kept.append(_replacement(named[0], data))
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
    return PreparedSignatures(out, kept or None, replaced)


def delete_stored_images(
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
            aws.delete_file_from_s3(
                key=f"private/{workspace_id}/{form_id}/{response_id}/{file_id}"
            )
        except Exception:  # noqa: BLE001 - never fail the edit over storage
            logger.warning(
                "Response {}: a replaced signature image could not be removed",
                response_id,
            )
