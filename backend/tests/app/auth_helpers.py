"""Tokens for tests: a live access token of some session (no session record
needed: access tokens are checked without one)."""

from common.ids import RecordId

from backend.app.services.auth_cookie_service import access_token_for
from common.models.user import User


def access_token(user: User) -> str:
    if not user.sid:
        user = user.model_copy(update={"sid": str(RecordId())})
    return access_token_for(user)
