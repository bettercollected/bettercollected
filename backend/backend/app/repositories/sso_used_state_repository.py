import datetime as dt

from pymongo.errors import DuplicateKeyError

from backend.app.schemas.sso_used_state import SsoUsedStateDocument
from common.db.routing import write_op


class StateAlreadyUsed(Exception):
    """This sign-in's nonce was accepted before (a replayed callback)."""


class SsoUsedStateRepository:
    @write_op(replay=True)
    async def claim(
        self, document: SsoUsedStateDocument, now: dt.datetime
    ) -> SsoUsedStateDocument:
        """Record the nonce; StateAlreadyUsed when it is recorded already
        (the unique index decides, so two racing callbacks can't both pass).
        Mongo's TTL index drops expired records."""
        try:
            return await document.insert()
        except DuplicateKeyError:
            raise StateAlreadyUsed(document.nonce_hash)
