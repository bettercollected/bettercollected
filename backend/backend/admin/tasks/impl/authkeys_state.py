"""What the ``authkeys.*`` tasks share besides the walk: the key ring read from
the settings store (through ``keyset_state``, which verifies the row and writes
it through the one narrow definer function), the ring's members as ids, the
readiness check of the services, and the counts a drop of the old key is gated
on.

The two rings (``AUTH_JWT_SECRET``, ``AUTH_AES_HEX_KEY``) are T4 settings of
section ``auth_keys``, like the response keyset; the runner opens that section
and nothing else. A ring is ``<current>[,<previous>]`` (``common.settings.key_ring``).

Nothing here prints, logs or returns a member. A member is named by its id: 32
bits of an HMAC keyed by the member itself over a fixed label, so the id
identifies a key to the operator and says nothing about its value.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.admin.tasks.catalog.authkeys import Which
from backend.admin.tasks.impl import keyset_state as state
from backend.admin.tasks.spec import Refusal
from common.settings import key_ring
from common.settings.loader import keyset_fingerprint  # noqa: F401 - re-exported for tests

SETTING = {Which.jwt: "AUTH_JWT_SECRET", Which.aes: "AUTH_AES_HEX_KEY"}
MEMBER_ID_LABEL = b"bettercollected/auth-key-ring/member-id/v1"
# the services that read the rings through the settings store. The jobs worker
# and the SCIM reconcile run as instances of "backend".
RING_SERVICES = ("backend", "auth", "google")
FRESH_SECONDS = state.FRESH_SECONDS
RETIRED_AFTER_SECONDS = state.RETIRED_AFTER_SECONDS
MIN_JWT_MEMBER = key_ring.MIN_TOKEN_MEMBER


def member_id(member: str) -> int:
    """The id of one ring member (1 to 2**32-1)."""
    digest = hmac.new(member.encode(), MEMBER_ID_LABEL, hashlib.sha256).digest()
    return int.from_bytes(digest[:4], "big") or 1


@dataclass(frozen=True)
class Ring:
    which: Which
    members: tuple  # the secrets: never leave this process

    @property
    def ids(self) -> List[int]:
        return [member_id(m) for m in self.members]

    @property
    def primary_id(self) -> int:
        return member_id(self.members[0])

    @property
    def primary(self) -> str:
        return self.members[0]

    def __repr__(self) -> str:
        return f"Ring({self.which.value}, ids={self.ids})"

    def text(self) -> str:
        return key_ring.join(self.members)

    def member(self, wanted: int) -> Optional[str]:
        for candidate in self.members:
            if member_id(candidate) == wanted:
                return candidate
        return None

    def others(self, keep: str) -> List[str]:
        return [m for m in self.members if m != keep]


def parse_ring(which: Which, value: str) -> Ring:
    """The ring a stored value holds, or ``Refusal('ring_unreadable')``: one or
    two distinct members, each a Fernet key (aes) or a secret of at least 32
    characters (jwt)."""
    if which is Which.aes:
        members = key_ring.fernet_members(value)
    else:
        members = key_ring.token_members(value)
    if not 1 <= len(members) <= key_ring.MAX_MEMBERS or len(set(members)) != len(members):
        raise Refusal("ring_unreadable")
    for member in members:
        if which is Which.aes:
            try:
                Fernet(member)
            except (ValueError, TypeError):
                raise Refusal("ring_unreadable") from None
        elif len(member) < MIN_JWT_MEMBER or any(c.isspace() for c in member):
            raise Refusal("ring_unreadable")
    return Ring(which, tuple(members))


async def read_ring(ctx, which: Which):
    """(keys, stored, ring): the ring from the settings store, verified. Refuses
    ``key_not_in_store`` (an environment-only stack keeps its keys in files: see
    the runbook) and ``key_not_readable_by_runner`` (``settings-grant-runner``)."""
    from backend.admin.config import AdminConfigError

    try:
        keys = state.runner_keys()
    except AdminConfigError:
        raise Refusal("key_not_in_store") from None
    async with ctx.connection() as conn:
        stored = await state.read_stored(
            conn, keys, SETTING[which], hidden_code="key_not_readable_by_runner"
        )
    if stored is None:
        raise Refusal("key_not_in_store")
    return keys, stored, parse_ring(which, stored.value)


# -------------------------------------------------------------- consumers
async def check_ring_consumers(
    conn, *, name: str, min_revision: int, google_in_use: bool
) -> int:
    """Every service that reads the ring reports (a heartbeat newer than 2 minutes
    on every instance seen in the last 15), has restarted onto the settings
    revision that wrote the ring (``revision_applied`` at least ``min_revision``
    and no ``restart_pending``) and does not override the ring from its
    environment. A service applies a changed class-R setting only by restarting,
    so that is what proves it holds the ring now. Raises a ``Refusal`` naming the
    first failure; returns the number of instances."""
    required = [s for s in RING_SERVICES if s != "google" or google_in_use]
    found = await state.consumers(conn, list(RING_SERVICES))
    live = [c for c in found if c.age_seconds <= RETIRED_AFTER_SECONDS]
    for service in required:
        mine = [c for c in live if c.service == service]
        if not mine:
            raise Refusal("consumer_not_reporting")
        if not any(c.age_seconds <= FRESH_SECONDS for c in mine):
            raise Refusal("consumer_stale")
    if any(c.age_seconds > FRESH_SECONDS for c in live):
        raise Refusal("consumer_stale")
    if any(name in c.env_overrides for c in live):
        raise Refusal("consumer_env_override")
    if any(c.restart_pending for c in live):
        raise Refusal("consumer_restart_pending")
    if any(c.revision_applied < min_revision for c in live):
        raise Refusal("consumer_behind")
    return len(live)


# ----------------------------------------------------------------- counts
async def _scalar(conn, sql: str, **params) -> Optional[int]:
    """One integer from a count-only definer function; ``None`` when the
    function is missing, not executable or answers NULL (a store it cannot see)."""
    try:
        value = (await conn.execute(text(sql), params)).scalar()
    except DBAPIError:
        raise Refusal("counts_unavailable") from None
    return None if value is None else int(value)


async def jobs_pending(conn) -> int:
    """Queued or running purge, revocation and deletion jobs: each carries an
    argument sealed with the encryption key (``admin.sealed_jobs_pending()``)."""
    value = await _scalar(conn, "SELECT admin.sealed_jobs_pending()")
    if value is None:
        raise Refusal("counts_unavailable")
    return value


async def sessions_on_previous(conn, promoted_at: datetime) -> int:
    """Live sessions whose refresh token was issued before ``promoted_at``, so it
    is signed with the previous key (``admin.sessions_on_old_key``)."""
    value = await _scalar(conn, "SELECT admin.sessions_on_old_key(:t)", t=promoted_at)
    if value is None:
        raise Refusal("counts_unavailable")
    return value


async def drafts_on_previous(conn, promoted_at: datetime) -> int:
    """At most this many unexpired saved drafts hold a link or an edit key hashed
    with the previous key (``admin.drafts_on_old_key``)."""
    value = await _scalar(conn, "SELECT admin.drafts_on_old_key(:t)", t=promoted_at)
    if value is None:
        raise Refusal("counts_unavailable")
    return value


def event_ids(ids: Sequence[int]) -> List[str]:
    return [str(i) for i in ids][:20]
