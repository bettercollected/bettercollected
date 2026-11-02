from typing import Any, Sequence, Type, TypeVar

import jwt

from pydantic import BaseModel

from common.settings.key_ring import primary, token_members

T = TypeVar("T", bound=BaseModel)


def decode_with_ring(token: str, secret_ring: str, **options: Any) -> dict:
    """The claims of ``token``, verified against every member of the key ring
    ``secret_ring`` (``AUTH_JWT_SECRET``: one secret, or two, current first;
    docs/auth-key-rotation.md). A token signed with any member verifies; one
    signed with none raises ``InvalidSignatureError`` like a single key would.
    Expiry and other claim errors are raised as PyJWT raises them (only after
    the signature checked out). The algorithm is pinned to HS256 here, whatever the
    caller passes: a ring member is an HMAC secret, never a public key."""
    members: Sequence[str] = token_members(secret_ring) or [secret_ring]
    options.pop("algorithms", None)
    options["algorithms"] = ["HS256"]
    failure: Exception = jwt.InvalidSignatureError("Signature verification failed")
    for member in members:
        try:
            return jwt.decode(token, key=member, **options)
        except jwt.InvalidSignatureError as error:
            failure = error
    raise failure


# The ``typ`` claim of the session tokens the backend issues
# (backend/app/services/auth_cookie_service.py).
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def decode_typed_with_ring(
    token: str, secret_ring: str, token_type: str, **options: Any
) -> dict:
    """The claims of ``token`` like :func:`decode_with_ring`, but only when its
    ``typ`` claim is exactly ``token_type``; a token of another kind, or one
    without a ``typ``, raises ``InvalidTokenError`` (checked after the
    signature, so a forgery still raises ``InvalidSignatureError``)."""
    claims = decode_with_ring(token, secret_ring, **options)
    if claims.get("typ") != token_type:
        raise jwt.InvalidTokenError(f"Not a {token_type} token")
    return claims


def decode_access_token(token: str, secret_ring: str, **options: Any) -> dict:
    """The claims of a session *access* token (``typ == "access"``); a refresh
    token or any other signed token is refused."""
    return decode_typed_with_ring(token, secret_ring, ACCESS_TOKEN_TYPE, **options)


def signing_secret(secret_ring: str) -> str:
    """The member that signs: the first of the ring."""
    return primary(token_members(secret_ring)) or secret_ring


class JwtService:
    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret

    def encode(self, model: BaseModel) -> str:
        return jwt.encode(
            model.model_dump(exclude_none=True), key=signing_secret(self.jwt_secret)
        )

    def decode(self, token: str, model: Type[T]) -> T:
        decoded_data = decode_with_ring(token, self.jwt_secret, algorithms=["HS256"])
        return model.model_validate(decoded_data)
