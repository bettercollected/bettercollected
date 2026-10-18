"""Action-bound, single-use step-up tokens.

A token proves "a second-factor code was entered a moment ago, for exactly this
action". It is for actions that must not ride on the plain freshness window
(settings, tasks, key changes): ``issue(session, action_hash)`` after a fresh
factor verification, ``consume(session, token, action_hash)`` by the route that
performs the action.

Storage: the token is stateless, ``<expiry>.<nonce>.<mac>`` with
``mac = HMAC(admin/stepup subkey, session id | action hash | expiry | nonce)``,
so it works only for that session and that action. Single use is enforced by
burning ``SHA-256(token)`` in the existing ``admin.attempts`` counter table
(atomic ``INSERT .. ON CONFLICT DO UPDATE .. RETURNING``: the caller that sees
count 1 wins). That needs no new table, no change to the sessions table and no
migration, and the counter rows are removed by the limiter's regular cleanup.
Only the hash of a token is ever stored.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional

from backend.admin.security.clock import Clock
from backend.admin.security.keycheck import require_key
from backend.admin.security.ratelimit import AttemptStore
from backend.admin.services.sessions import Session, SessionService

TOKEN_SECONDS = 120
MAX_TOKEN = 200


def action_hash(name: str, *parts: object) -> str:
    """A canonical hex digest of an action: its name and the values it acts on
    (length-prefixed, so ``("a", "bc")`` and ``("ab", "c")`` differ)."""
    digest = hashlib.sha256()
    for item in (name, *parts):
        data = str(item).encode("utf-8")
        digest.update(len(data).to_bytes(4, "big"))
        digest.update(data)
    return digest.hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class StepUpService:
    def __init__(
        self, clock: Clock, sessions: SessionService, store: AttemptStore, key: bytes
    ) -> None:
        self._clock = clock
        self._sessions = sessions
        self._store = store
        self._key = require_key(key, "step-up key")

    def _mac(self, session_id, action: str, expiry: int, nonce: str) -> str:
        message = f"stepup|{session_id}|{action}|{expiry}|{nonce}".encode()
        return _b64(hmac.new(self._key, message, hashlib.sha256).digest())

    def issue(self, session: Session, action: str) -> Optional[str]:
        """A token for ``action`` (an ``action_hash``), valid 120 s, or None
        unless the session's factor code was verified within that time."""
        if not self._sessions.stepup_fresh(session, TOKEN_SECONDS):
            return None
        expiry = int(self._clock.time()) + TOKEN_SECONDS
        nonce = _b64(secrets.token_bytes(16))
        return f"{expiry}.{nonce}.{self._mac(session.id, action, expiry, nonce)}"

    async def consume(self, session: Session, token: Optional[str], action: str) -> bool:
        """Burn ``token`` and return True only for its first use, by the session
        it was issued to, for the action it was issued for, before it expires."""
        if (
            session.mfa_state != "mfa_ok"
            or not isinstance(token, str)
            or len(token) > MAX_TOKEN
            or token.count(".") != 2
        ):
            return False
        raw_expiry, nonce, mac = token.split(".")
        if not (raw_expiry.isascii() and raw_expiry.isdigit()):
            return False
        expiry = int(raw_expiry)
        expected = self._mac(session.id, action, expiry, nonce)
        if not hmac.compare_digest(expected.encode(), mac.encode("utf-8", "replace")):
            return False
        if self._clock.time() >= expiry:
            return False
        burn = "stepup:" + hashlib.sha256(token.encode()).hexdigest()
        count = await self._store.increment(burn, datetime.fromtimestamp(expiry, timezone.utc))
        return count == 1
