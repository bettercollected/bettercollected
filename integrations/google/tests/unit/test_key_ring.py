"""The Google Forms integration under key rings (docs/auth-key-rotation.md):
session tokens verify under any member of ``AUTH_JWT_SECRET`` and the PKCE
verifier follows the key that opens the request's state. Throwaway keys only."""

import secrets
import time

import jwt
import pytest
from cryptography.fernet import Fernet

from common.services.jwt_service import decode_with_ring
from googleform.app.services import oauth_google
from googleform.config import settings

OLD = secrets.token_hex(32)
NEW = secrets.token_hex(32)
OLD_F = Fernet.generate_key().decode()
NEW_F = Fernet.generate_key().decode()


def test_a_token_signed_by_either_member_verifies_and_a_forgery_does_not():
    token = jwt.encode({"sub": "a@example.com", "exp": int(time.time()) + 60}, OLD, algorithm="HS256")
    assert decode_with_ring(token, f"{NEW},{OLD}", algorithms=["HS256"])["sub"] == "a@example.com"
    with pytest.raises(jwt.InvalidSignatureError):
        decode_with_ring(token, NEW, algorithms=["HS256"])


def test_the_pkce_verifier_is_derived_with_the_key_that_opens_the_state(monkeypatch):
    state = oauth_google._crypto.__class__(OLD_F).encrypt("{}")
    monkeypatch.setattr(oauth_google, "_crypto", oauth_google._crypto.__class__(OLD_F))
    monkeypatch.setattr(settings, "AUTH_AES_HEX_KEY", OLD_F)
    started = oauth_google.pkce_code_verifier(state)
    # the stack was promoted in between: the ring now starts with the new key
    monkeypatch.setattr(oauth_google, "_crypto", oauth_google._crypto.__class__(f"{NEW_F},{OLD_F}"))
    monkeypatch.setattr(settings, "AUTH_AES_HEX_KEY", f"{NEW_F},{OLD_F}")
    assert oauth_google.pkce_code_verifier(state) == started
    # a state that no member opens falls back to the current key
    assert oauth_google.pkce_code_verifier("not-a-state") == oauth_google.pkce_code_verifier(
        "not-a-state", NEW_F
    )
