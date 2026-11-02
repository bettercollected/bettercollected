"""The shared typed decoders (common ``jwt_service``): a session's access
token is the only kind ``decode_access_token`` accepts; the signature and the
expiry are checked first."""

import secrets
import time

import jwt
import pytest

from common.services.jwt_service import decode_access_token, decode_typed_with_ring

OLD = secrets.token_hex(32)
NEW = secrets.token_hex(32)


def _signed(secret, **claims):
    return jwt.encode({"sub": "a@example.com", **claims}, secret, algorithm="HS256")


def test_the_access_decoder_accepts_only_an_access_token():
    ring = f"{NEW},{OLD}"
    assert decode_access_token(_signed(OLD, typ="access"), ring)["sub"] == "a@example.com"
    assert decode_access_token(_signed(NEW, typ="access"), NEW)["typ"] == "access"
    for refused in (
        _signed(NEW, typ="refresh"),
        _signed(NEW, typ="other"),
        _signed(NEW, typ=None),
        _signed(NEW, typ=["access"]),
        _signed(NEW),
    ):
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(refused, ring)


def test_the_typed_decoder_still_checks_signature_and_expiry_first():
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(_signed("c" * 64, typ="access"), NEW)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(_signed(NEW, typ="access", exp=int(time.time()) - 10), NEW)
    assert decode_typed_with_ring(_signed(NEW, typ="refresh"), NEW, "refresh")["typ"] == "refresh"
    with pytest.raises(jwt.InvalidTokenError):
        decode_typed_with_ring(_signed(NEW, typ="access"), NEW, "refresh")
