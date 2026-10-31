"""The ``state`` of an integration's OAuth flow (the Google Sheets action).

``mint`` creates it when the flow starts (``GET /integration/{type}/oauth``)
and ``consume`` checks it when the code comes back
(``POST /integration/{type}/oauth/callback``). The state is:

- encrypted with the backend's key, so nobody else can mint or change one;
- bound to the user and the session that started the flow: another user, or
  another session of the same user, cannot use it;
- refused once it is older than ``STATE_MAX_AGE_SECONDS``;
- accepted once: its random nonce is recorded, by hash, on first use, in the
  same store that records accepted single sign-on states. The hash is taken
  over a label of its own, so the two flows' records never meet.
"""

import datetime as dt
import hashlib
import json
import secrets
from http import HTTPStatus
from typing import Optional

from common.configs.crypto import Crypto
from common.constants import MESSAGE_FORBIDDEN
from common.models.user import User
from common.records import RecordId
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.google_sheets_oauth import (
    MESSAGE_INVALID_STATE,
    STATE_MAX_AGE_SECONDS,
)

_NONCE_LABEL = b"integration-oauth-state-v1|"


def state_nonce_hash(nonce: str) -> str:
    return hashlib.sha256(_NONCE_LABEL + nonce.encode("utf-8")).hexdigest()


def mint(crypto: Crypto, user: User, client_referer_url: Optional[str]) -> str:
    return crypto.encrypt(
        json.dumps(
            {
                "client_referer_uri": client_referer_url,
                "user_id": user.id,
                "sid": user.sid,
                "nonce": secrets.token_urlsafe(32),
            }
        )
    )


class IntegrationOAuthState:
    def __init__(self, crypto: Crypto, used_state_repo):
        self._crypto = crypto
        self._used_states = used_state_repo

    def read(self, state: str, user: User) -> dict:
        """The state's content, when it is well formed, not expired, and was
        minted for this user's session; else the request is refused."""
        try:
            data = json.loads(
                Fernet.decrypt(self._crypto, state, ttl=STATE_MAX_AGE_SECONDS)
            )
        except (InvalidToken, TypeError, ValueError):
            raise HTTPException(HTTPStatus.BAD_REQUEST, MESSAGE_INVALID_STATE)
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("nonce"), str)
            or not data["nonce"]
        ):
            raise HTTPException(HTTPStatus.BAD_REQUEST, MESSAGE_INVALID_STATE)
        if data.get("user_id") != user.id or data.get("sid") != user.sid:
            logger.info("integration oauth state refused: another user or session")
            raise HTTPException(HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN)
        return data

    async def consume(self, data: dict) -> None:
        """Records the state as used; refuses one that was used before."""
        from backend.app.repositories.postgres.identity import StateAlreadyUsed
        from backend.app.schemas.sso_used_state import SsoUsedStateDocument

        now = dt.datetime.now(dt.timezone.utc)
        try:
            await self._used_states.claim(
                SsoUsedStateDocument(
                    id=RecordId(),
                    nonce_hash=state_nonce_hash(data["nonce"]),
                    # past the state's own expiry, so a replay is refused for
                    # as long as the state could be accepted at all
                    expires_at=now + dt.timedelta(seconds=STATE_MAX_AGE_SECONDS * 2),
                ),
                now,
            )
        except StateAlreadyUsed:
            logger.info("integration oauth state refused: already used")
            raise HTTPException(HTTPStatus.BAD_REQUEST, MESSAGE_INVALID_STATE)
