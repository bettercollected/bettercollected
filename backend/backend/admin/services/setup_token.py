"""The first-run setup token.

The host operator asks for a token on the console (``setup-token``). It is 160
random bits, shown once, valid for 60 minutes and good for one redemption. Only
a keyed hash is stored (HMAC-SHA256 with a subkey derived from the master key,
context ``setup-token``), so a database copy cannot be used to sign in, and
nothing logs the token: the audit rows say that one was issued, replaced or
redeemed, never what it was.

This module holds the primitives. The portal's setup pages build on
``redeem`` (single use, constant-time compare, 20 wrong tries lock the token for
good) and add their own per-address limits.
"""

from __future__ import annotations

import base64
import hmac
import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories.tables import factors, setup_tokens
from common.settings.crypto.keys import derive_from_master

TOKEN_BITS = 160
TTL = timedelta(minutes=60)
MAX_FAILED_ATTEMPTS = 20
_GROUP = 4
_LOCK_KEY = 4099217756181324507  # serialises issuing and redeeming


class SetupTokenError(Exception):
    """A refusal with a short stable code; the message never has a token."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ActiveToken:
    expires_at: datetime
    failed_attempts: int


def mac_key(master: bytes) -> bytes:
    return derive_from_master(master, "admin", "setup", 1, "setup-token")


def normalise(token: str) -> str:
    """Upper case, without the grouping dashes and spaces."""
    return re.sub(r"[\s-]+", "", token or "").upper()


def display(token: str) -> str:
    """The token as the operator reads it: groups of four."""
    return "-".join(token[i : i + _GROUP] for i in range(0, len(token), _GROUP))


def _mac(key: bytes, token: str) -> bytes:
    return hmac.new(key, normalise(token).encode(), hashlib.sha256).digest()


def _new_token() -> str:
    return base64.b32encode(secrets.token_bytes(TOKEN_BITS // 8)).decode().rstrip("=")


async def _lock(conn: AsyncConnection) -> None:
    await conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})


async def _now(conn: AsyncConnection) -> datetime:
    return (await conn.execute(text("SELECT clock_timestamp()"))).scalar_one()


async def enrolment_complete(conn: AsyncConnection) -> bool:
    """Whether any admin has a confirmed second factor: setup is over."""
    row = (
        await conn.execute(
            select(factors.c.id).where(factors.c.confirmed_at.is_not(None)).limit(1)
        )
    ).first()
    return row is not None


async def active(conn: AsyncConnection) -> Optional[ActiveToken]:
    """The token that could still be redeemed, if any."""
    now = await _now(conn)
    row = (
        await conn.execute(
            select(setup_tokens.c.expires_at, setup_tokens.c.failed_attempts).where(
                setup_tokens.c.consumed_at.is_(None),
                setup_tokens.c.revoked_at.is_(None),
                setup_tokens.c.locked_at.is_(None),
                setup_tokens.c.expires_at > now,
            )
        )
    ).first()
    return ActiveToken(row[0], row[1]) if row else None


async def issue(
    conn: AsyncConnection, master: bytes, issued_by: str, *, replace: bool = False
) -> tuple[str, bool]:
    """Create a token and return ``(token, replaced)``. Run in the caller's
    transaction, together with its audit row.

    Refused with ``setup_closed`` once any admin has a confirmed second factor
    (reset that factor with ``reset-factor`` first), and with ``token_active``
    when an unexpired token exists and ``replace`` is not set."""
    await _lock(conn)
    if await enrolment_complete(conn):
        raise SetupTokenError("setup_closed")
    now = await _now(conn)
    live = await active(conn)
    if live is not None and not replace:
        raise SetupTokenError("token_active")
    revoked = (
        await conn.execute(
            update(setup_tokens)
            .where(
                setup_tokens.c.consumed_at.is_(None),
                setup_tokens.c.revoked_at.is_(None),
                setup_tokens.c.locked_at.is_(None),
            )
            .values(revoked_at=now)
        )
    ).rowcount
    token = _new_token()
    try:
        await conn.execute(
            setup_tokens.insert().values(
                token_mac=_mac(mac_key(master), token),
                issued_by=issued_by[:200],
                expires_at=now + TTL,
            )
        )
    except IntegrityError:  # cannot happen under the lock; fail closed anyway
        raise SetupTokenError("token_active") from None
    return token, bool(revoked)


async def redeem(
    conn: AsyncConnection, master: bytes, token: str, *, count_failures: bool = True
) -> bool:
    """Consume the active token if ``token`` is it. A wrong token counts as a
    failed attempt; the 20th locks the token for good. Constant-time compare;
    the same ``False`` for a wrong, expired, used, revoked or locked token.

    ``count_failures=False`` (the caller's address is over its try limits) still
    lets the right token through but does not let a wrong one use up the
    token's tries, so a flood from an address cannot burn the token."""
    await _lock(conn)
    now = await _now(conn)
    row = (
        await conn.execute(
            select(
                setup_tokens.c.id, setup_tokens.c.token_mac, setup_tokens.c.failed_attempts
            )
            .where(
                setup_tokens.c.consumed_at.is_(None),
                setup_tokens.c.revoked_at.is_(None),
                setup_tokens.c.locked_at.is_(None),
                setup_tokens.c.expires_at > now,
            )
            .with_for_update()
        )
    ).first()
    candidate = _mac(mac_key(master), token or "")
    if row is None:
        hmac.compare_digest(candidate, candidate)  # keep the work alike
        return False
    if hmac.compare_digest(bytes(row.token_mac), candidate):
        await conn.execute(
            update(setup_tokens).where(setup_tokens.c.id == row.id).values(consumed_at=now)
        )
        return True
    if not count_failures:
        return False
    failed = row.failed_attempts + 1
    values = {"failed_attempts": failed}
    if failed >= MAX_FAILED_ATTEMPTS:
        values["locked_at"] = now
    await conn.execute(update(setup_tokens).where(setup_tokens.c.id == row.id).values(**values))
    return False
