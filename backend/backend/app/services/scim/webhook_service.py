"""The directory sync webhook (``POST /api/v1/scim/webhook/{directory_id}``).

Polis calls it over the internal network, but it is safe to expose: it is
unauthenticated except for the signature, so the order is

1. size cap, the directory (our id, in the path: one read by primary key),
2. the ``BoxyHQ-Signature`` (HMAC-SHA256 over the raw body with the
   directory's secret, constant-time, at most ``SCIM_SIGNATURE_TOLERANCE_SECONDS``
   old or early) -- nothing else is read or parsed before it passes,
3. then the JSON: every event must name this directory's Polis id, tenant and
   product,
4. each event is claimed once (``scim_events``, by a hash of directory, type,
   data and the signed time; Polis gives events no id and resends the same
   signed request on retries), so duplicates answer 200 at once,
5. and applied. A failure releases the claim and answers 503, so Polis
   retries (3 times) and the retry is applied, not skipped.

Unknown directories and bad signatures get the same 401. Nothing logs a
body, an email or a secret.
"""

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict

from beanie import PydanticObjectId
from loguru import logger

from backend.app.repositories.scim_repository import (
    ScimDirectoryRepository,
    ScimEventRepository,
    ScimEventSeen,
)
from backend.app.schemas.scim import ScimDirectoryDocument, ScimEventDocument
from backend.app.services.scim.signature import (
    SIGNATURE_HEADERS,
    BadSignature,
    verify,
)
from backend.app.services.scim.sync_service import DirectoryUser, ScimSyncService
from backend.config import settings

USER_EVENTS = ("user.created", "user.updated", "user.deleted")
GROUP_EVENTS = ("group.created", "group.updated", "group.deleted")
MEMBERSHIP_EVENTS = ("group.user_added", "group.user_removed")
MAX_EVENTS_PER_REQUEST = 500


@dataclass
class WebhookReply:
    status: int
    body: Dict[str, Any]


def _reply(status: int, code: str, **extra) -> WebhookReply:
    return WebhookReply(status, {"code": code, **extra})


def event_key(directory_id, event: Dict[str, Any], timestamp_ms: int) -> str:
    material = json.dumps(
        [
            str(directory_id),
            event.get("event"),
            event.get("data"),
            timestamp_ms,
        ],
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class ScimWebhookService:
    def __init__(
        self,
        directory_repo: ScimDirectoryRepository,
        event_repo: ScimEventRepository,
        sync_service: ScimSyncService,
        crypto,
    ):
        self._directories = directory_repo
        self._events = event_repo
        self._sync = sync_service
        self._crypto = crypto

    async def receive(self, directory_id: str, headers, body: bytes) -> WebhookReply:
        if len(body) > settings.scim.MAX_WEBHOOK_BYTES:
            return _reply(413, "too_large")
        directory = await self._directories.get(directory_id)
        signature = next(
            (headers.get(name) for name in SIGNATURE_HEADERS if headers.get(name)),
            None,
        )
        if directory is None:
            logger.info("SCIM webhook refused: unknown directory")
            return _reply(401, "invalid_signature")
        try:
            secret = self._crypto.decrypt(directory.webhook_secret)
        except Exception:  # noqa: BLE001 — a key change: nothing verifies
            logger.error("SCIM webhook: directory {} secret unreadable", directory.id)
            return _reply(401, "invalid_signature")
        try:
            timestamp = verify(
                signature, body, secret, settings.scim.SIGNATURE_TOLERANCE_SECONDS
            )
        except BadSignature as bad:
            logger.info(
                "SCIM webhook refused for directory {}: {}", directory.id, bad.code
            )
            return _reply(401, "invalid_signature")

        try:
            payload = json.loads(body)
        except ValueError:
            return _reply(400, "invalid_body")
        events = payload if isinstance(payload, list) else [payload]
        if (
            not events
            or len(events) > MAX_EVENTS_PER_REQUEST
            or not all(isinstance(e, dict) for e in events)
        ):
            return _reply(400, "invalid_body")
        for event in events:
            if (
                event.get("directory_id") != directory.polis_directory_id
                or event.get("tenant") != directory.polis_tenant
                or event.get("product") != directory.polis_product
            ):
                logger.warning(
                    "SCIM webhook refused for directory {}: tenant mismatch",
                    directory.id,
                )
                return _reply(403, "tenant_mismatch")
        if not settings.sso.is_configured:
            # signed and ours, but SSO is off on the instance: Polis retries,
            # and a resync catches up once it is back
            return _reply(503, "scim_disabled")

        applied = duplicates = 0
        for event in events:
            key = event_key(directory.id, event, timestamp)
            now = dt.datetime.now(dt.timezone.utc)
            try:
                await self._events.claim(
                    ScimEventDocument(
                        id=PydanticObjectId(),
                        event_key=key,
                        directory_id=directory.id,
                        event_type=str(event.get("event") or "")[:64],
                        expires_at=now
                        + dt.timedelta(seconds=settings.scim.EVENT_RETENTION_SECONDS),
                    ),
                    now,
                )
            except ScimEventSeen:
                duplicates += 1
                continue
            try:
                await self.apply(directory, event)
            except Exception as error:  # noqa: BLE001 — let Polis retry
                await self._events.release(key)
                logger.error(
                    "SCIM webhook: event {} of directory {} failed: {}",
                    event.get("event"),
                    directory.id,
                    type(error).__name__,
                )
                return _reply(503, "retry")
            applied += 1
        if applied:
            await self._touch(directory, str(events[-1].get("event") or ""))
        return WebhookReply(200, {"applied": applied, "duplicates": duplicates})

    async def _touch(self, directory: ScimDirectoryDocument, event_type: str) -> None:
        fresh = await self._directories.get(directory.id) or directory
        now = dt.datetime.now(dt.timezone.utc)
        fresh.last_event_at = now
        fresh.last_event_type = event_type[:64]
        fresh.updated_at = now
        await self._directories.save(fresh)

    async def apply(self, directory: ScimDirectoryDocument, event: Dict[str, Any]):
        kind = event.get("event")
        data = event.get("data")
        if not isinstance(data, dict):
            logger.info("SCIM event {} without data ignored", kind)
            return
        if kind in USER_EVENTS:
            user = DirectoryUser.of(data)
            if user is not None:
                await self._sync.apply_user(
                    directory, user, deleted=kind == "user.deleted"
                )
        elif kind in ("group.created", "group.updated"):
            await self._sync.apply_group(directory, data)
        elif kind == "group.deleted":
            await self._sync.delete_group(directory, str(data.get("id") or ""))
        elif kind in MEMBERSHIP_EVENTS:
            group = data.get("group")
            user = DirectoryUser.of(data)
            if isinstance(group, dict) and user is not None:
                await self._sync.set_membership(
                    directory, group, user, member=kind == "group.user_added"
                )
        else:
            logger.info("SCIM event type {} ignored", str(kind)[:64])
