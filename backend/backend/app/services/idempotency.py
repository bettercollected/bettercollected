"""``Idempotency-Key`` for the public API's POSTs (create, ops, publish).

Per API key, a client key is bound to the first request that used it (a
hash of its method, path and body) for 24 hours:

- the same key with the same request again gets the stored response,
  replayed (``Idempotent-Replayed: true``), and nothing runs twice;
- the same key with a different request is refused (422
  ``idempotency_key_reused``);
- while the first request still runs, a retry gets 409
  ``idempotency_in_progress``.

Final answers are kept, errors included (a 412 stays a 412). A server
failure (5xx), a conflict (409) or a rate limit (429) is not: the key is
released so a retry runs the request.
"""

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Optional

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.repositories.idempotency_repository import IdempotencyRepository
from backend.app.schemas.api_idempotency_record import (
    IDEMPOTENCY_DONE,
    ApiIdempotencyRecordDocument,
)

IDEMPOTENCY_TTL = dt.timedelta(hours=24)
MAX_KEY_LENGTH = 255
# answers that are not final: a retry with the same key runs again
RETRYABLE_STATUSES = {HTTPStatus.CONFLICT, HTTPStatus.TOO_MANY_REQUESTS}


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: str
    etag: Optional[str]


def request_hash(method: str, path: str, body: bytes) -> str:
    """The fingerprint of a request: JSON bodies compared by value (key
    order and whitespace do not matter), anything else byte for byte."""
    try:
        canonical = json.dumps(
            json.loads(body), sort_keys=True, separators=(",", ":")
        ).encode()
    except ValueError:
        canonical = body
    digest = hashlib.sha256()
    for part in (method.upper().encode(), path.encode(), canonical):
        digest.update(part)
        digest.update(b"\0")
    return digest.hexdigest()


def _record_id(key_id: str, idempotency_key: str) -> str:
    message = f"{key_id}\n{idempotency_key}".encode()
    return hashlib.sha256(message).hexdigest()[:24]


def _refusal(status: HTTPStatus, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, content={"code": code, "message": message})


class IdempotencyService:
    def __init__(self, idempotency_repo: IdempotencyRepository):
        self._repo = idempotency_repo

    @staticmethod
    def check_key(idempotency_key: str) -> None:
        if not (
            0 < len(idempotency_key) <= MAX_KEY_LENGTH
            and idempotency_key.isascii()
            and idempotency_key.isprintable()
        ):
            raise _refusal(
                HTTPStatus.BAD_REQUEST,
                "invalid_idempotency_key",
                f"Idempotency-Key must be 1 to {MAX_KEY_LENGTH} printable ASCII "
                "characters.",
            )

    async def begin(
        self, key_id: str, idempotency_key: str, fingerprint: str
    ) -> Optional[StoredResponse]:
        """Claim the key for this request (None: run it), or the stored
        response of the request that already used it."""
        self.check_key(idempotency_key)
        record_id = _record_id(key_id, idempotency_key)
        for _ in range(2):
            existing = await self._repo.find(record_id)
            if existing is not None:
                if existing.request_hash != fingerprint:
                    raise _refusal(
                        HTTPStatus.UNPROCESSABLE_ENTITY,
                        "idempotency_key_reused",
                        "This Idempotency-Key was already used for a different "
                        "request. Use a new key for a new request.",
                    )
                if existing.state == IDEMPOTENCY_DONE:
                    return StoredResponse(
                        existing.status_code, existing.body or "", existing.etag
                    )
                raise _refusal(
                    HTTPStatus.CONFLICT,
                    "idempotency_in_progress",
                    "A request with this Idempotency-Key is still running. "
                    "Retry when it has finished.",
                )
            record = ApiIdempotencyRecordDocument(
                id=PydanticObjectId(record_id),
                key_id=key_id,
                request_hash=fingerprint,
                expires_at=dt.datetime.now(dt.timezone.utc) + IDEMPOTENCY_TTL,
            )
            if await self._repo.claim(record):
                return None
        raise _refusal(
            HTTPStatus.CONFLICT,
            "idempotency_in_progress",
            "A request with this Idempotency-Key is still running.",
        )

    async def finish(
        self,
        key_id: str,
        idempotency_key: str,
        status_code: int,
        body: str,
        etag: Optional[str] = None,
    ) -> None:
        record_id = _record_id(key_id, idempotency_key)
        if status_code >= 500 or status_code in RETRYABLE_STATUSES:
            await self._repo.release(record_id)
        else:
            await self._repo.complete(record_id, status_code, body, etag)

    async def abandon(self, key_id: str, idempotency_key: str) -> None:
        await self._repo.release(_record_id(key_id, idempotency_key))
