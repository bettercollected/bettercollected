from typing import Optional

from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from common.db.routing import write_op


class BlacklistedRefreshTokenRepository:
    async def find_by_token(self, token: str) -> Optional[BlackListedRefreshTokens]:
        return await BlackListedRefreshTokens.find_one({"token": token})

    @write_op
    async def add(self, token: str, expiry) -> BlackListedRefreshTokens:
        return await BlackListedRefreshTokens(token=token, expiry=expiry).save()
