"""Key rings in the backend's consumers (docs/auth-key-rotation.md).

``AUTH_JWT_SECRET`` and ``AUTH_AES_HEX_KEY`` hold ``<current>[,<previous>]``:
the first signs and encrypts, every member verifies and decrypts. These tests
walk the steps of a rotation (old alone, ``[old,new]`` after add, ``[new,old]``
after promote, ``[new]`` after drop) through each place the backend uses the
keys. Throwaway keys only.
"""

import datetime as dt
import secrets
import time

import jwt
import pytest
from cryptography.fernet import Fernet
from pydantic import BaseModel

from backend.app.services import auth_cookie_service, response_cursor, session_service
from backend.app.services.ai import notice_token
from backend.app.services.form_drafts import tokens
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.app.services.response_export import links
from backend.config import settings
from common.configs.crypto import Crypto
from common.models.user import User
from common.services.jwt_service import JwtService, decode_with_ring, signing_secret

OLD = secrets.token_hex(32)
NEW = secrets.token_hex(32)
OLD_F = Fernet.generate_key().decode()
NEW_F = Fernet.generate_key().decode()


class Claims(BaseModel):
    id: str


def _ring(monkeypatch, value: str) -> None:
    monkeypatch.setattr(settings.auth_settings, "JWT_SECRET", value)


def _aes(monkeypatch, value: str) -> None:
    monkeypatch.setattr(settings.auth_settings, "AES_HEX_KEY", value)


# ------------------------------------------------------------------ JWT
def test_jwt_ring_signs_with_the_first_and_verifies_with_either():
    old_token = JwtService(OLD).encode(Claims(id="u1"))
    ring = JwtService(f"{NEW},{OLD}")
    assert ring.decode(old_token, Claims).id == "u1"
    new_token = ring.encode(Claims(id="u2"))
    assert jwt.decode(new_token, NEW, algorithms=["HS256"])["id"] == "u2"
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(new_token, OLD, algorithms=["HS256"])
    # the order of "add" ([old,new]) reads a token the new first key minted
    assert JwtService(f"{OLD},{NEW}").decode(new_token, Claims).id == "u2"
    # after the old key is dropped the old token is refused, the new one still reads
    assert JwtService(NEW).decode(new_token, Claims).id == "u2"
    with pytest.raises(jwt.InvalidSignatureError):
        JwtService(NEW).decode(old_token, Claims)
    with pytest.raises(jwt.InvalidSignatureError):
        JwtService("c" * 64).decode(new_token, Claims)


def test_jwt_ring_reports_expiry_only_for_a_correctly_signed_token():
    expired = jwt.encode({"id": "u", "exp": int(time.time()) - 5}, OLD, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_with_ring(expired, f"{NEW},{OLD}")
    forged = jwt.encode({"id": "u", "exp": int(time.time()) - 5}, "d" * 64, algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_with_ring(forged, f"{NEW},{OLD}")
    claims = decode_with_ring(expired, f"{NEW},{OLD}", options={"verify_exp": False})
    assert claims["id"] == "u"
    assert signing_secret(f"{NEW},{OLD}") == NEW and signing_secret(OLD) == OLD


# ------------------------------------------------------- sessions (cookies)
def _user() -> User:
    return User(id="64d1f0000000000000000001", sub="ring@example.com", sid="s-1", roles=[])


def test_a_session_survives_the_whole_rotation_until_its_key_is_dropped(monkeypatch):
    """Access and refresh tokens minted under the old key keep working through
    add and promote; only dropping the key ends the ones not re-issued."""
    _ring(monkeypatch, OLD)
    old_access = auth_cookie_service.access_token_for(_user())
    assert session_service.user_from_access_token(old_access) is not None

    _ring(monkeypatch, f"{OLD},{NEW}")  # add_key: new key accepted, old still signs
    assert session_service.user_from_access_token(old_access) is not None
    minted_during_add = auth_cookie_service.access_token_for(_user())
    assert jwt.decode(minted_during_add, OLD, algorithms=["HS256"])["typ"] == "access"

    _ring(monkeypatch, f"{NEW},{OLD}")  # promote: the new key signs, the old one still reads
    assert session_service.user_from_access_token(old_access) is not None
    assert session_service.user_from_access_token(minted_during_add) is not None
    minted_after_promote = auth_cookie_service.access_token_for(_user())
    assert jwt.decode(minted_after_promote, NEW, algorithms=["HS256"])["typ"] == "access"
    # a service that has not restarted yet (still [old,new]) reads it as well
    _ring(monkeypatch, f"{OLD},{NEW}")
    assert session_service.user_from_access_token(minted_after_promote) is not None

    _ring(monkeypatch, NEW)  # drop_old
    assert session_service.user_from_access_token(minted_after_promote) is not None
    assert session_service.user_from_access_token(old_access) is None
    assert session_service.decode_token(old_access) is None


def test_the_refresh_token_is_signed_by_the_first_member(monkeypatch):
    _ring(monkeypatch, f"{NEW},{OLD}")
    expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)
    from starlette.responses import Response

    response = Response()
    token = auth_cookie_service.set_refresh_token_to_response(
        _user(), response, jti="jti-1", expires_at=expires
    )
    assert jwt.decode(token, NEW, algorithms=["HS256"])["typ"] == "refresh"
    assert session_service.decode_token(token)["jti"] == "jti-1"


# --------------------------------------------------------- derived HMACs
def test_export_links_verify_under_either_member_and_mint_with_the_first(monkeypatch):
    args = ("e1", "w1", "f1", "u1")
    _ring(monkeypatch, OLD)
    old_link = links.issue(*args)
    _ring(monkeypatch, f"{NEW},{OLD}")
    assert links.check(old_link, *args) == links.VALID
    new_link = links.issue(*args)
    assert new_link != old_link
    _ring(monkeypatch, NEW)
    assert links.check(new_link, *args) == links.VALID
    assert links.check(old_link, *args) == links.INVALID
    _ring(monkeypatch, f"{NEW},{OLD}")
    assert links.check(old_link.replace(".", ".0", 1), *args) == links.INVALID


def test_notice_tokens_verify_under_either_member(monkeypatch):
    claims = dict(
        workspace_id="w1",
        form_id="6ac4fe01c5f99a0c65ac3299",
        provider="anthropic",
        provider_name="claude",
        enabled_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )
    now = dt.datetime.now(dt.timezone.utc)
    _ring(monkeypatch, OLD)
    old_token = notice_token.issue_token(**claims, now=now)
    _ring(monkeypatch, f"{NEW},{OLD}")
    assert notice_token.shown_at(old_token, **claims, now=now) is not None
    new_token = notice_token.issue_token(**claims, now=now)
    _ring(monkeypatch, NEW)
    assert notice_token.shown_at(new_token, **claims, now=now) is not None
    assert notice_token.shown_at(old_token, **claims, now=now) is None


def test_response_cursors_verify_under_either_member(monkeypatch):
    query = response_cursor.ResponseListQuery(size=10)
    anchor = response_cursor.Anchor(
        page=2, version=None, created_at=dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc), row_id="a" * 24
    )
    now = dt.datetime.now(dt.timezone.utc)
    _ring(monkeypatch, OLD)
    old_cursor = response_cursor.issue("w", "f", query, anchor, now=now)
    _ring(monkeypatch, f"{NEW},{OLD}")
    assert response_cursor.read(old_cursor, "w", "f", query, now=now).page == 2
    new_cursor = response_cursor.issue("w", "f", query, anchor, now=now)
    _ring(monkeypatch, NEW)
    assert response_cursor.read(new_cursor, "w", "f", query, now=now).page == 2
    with pytest.raises(response_cursor.InvalidCursor):
        response_cursor.read(old_cursor, "w", "f", query, now=now)


def test_the_rate_limiter_counts_under_the_current_member():
    def counter(secret):
        limiter = FixedWindowRateLimiter(repo=None, secret=secret)
        return limiter.counter_id("scope", "client", 7)

    assert counter(f"{NEW},{OLD}") == counter(NEW)  # the first member
    assert counter(OLD) != counter(NEW)


# ------------------------------------------------- the draft secrets (stored)
def test_draft_secrets_hashed_before_a_promotion_still_match_until_the_old_key_goes():
    old_keys = tokens.DraftKeys(OLD)
    link = old_keys.hash_secret(tokens.TOKEN, "d1", "link-secret")
    edit = old_keys.hash_secret(tokens.EDIT_KEY, "d1", "edit-secret")
    address = old_keys.address_key("form-1", "Someone@Example.com")

    adding = tokens.DraftKeys(f"{OLD},{NEW}")
    promoted = tokens.DraftKeys(f"{NEW},{OLD}")
    for ring in (adding, promoted):
        assert ring.matches(tokens.TOKEN, "d1", "link-secret", link)
        assert ring.matches(tokens.EDIT_KEY, "d1", "edit-secret", edit)
        assert not ring.matches(tokens.TOKEN, "d1", "link-secret", edit)  # purposes differ
        assert not ring.matches(tokens.TOKEN, "d1", "wrong", link)
        assert address in ring.address_keys("form-1", "someone@example.com")
    # new hashes use the first member and match the new key alone
    fresh = promoted.hash_secret(tokens.TOKEN, "d1", "link-secret")
    assert fresh != link and tokens.DraftKeys(NEW).matches(tokens.TOKEN, "d1", "link-secret", fresh)
    assert promoted.address_key("form-1", "x@y.test") == tokens.DraftKeys(NEW).address_key("form-1", "x@y.test")
    # after the old key is dropped the old hashes no longer match
    dropped = tokens.DraftKeys(NEW)
    assert not dropped.matches(tokens.TOKEN, "d1", "link-secret", link)
    assert address not in dropped.address_keys("form-1", "someone@example.com")
    assert not promoted.matches(tokens.TOKEN, "d1", "link-secret", None)


# ------------------------------------------------------ Fernet and PKCE
def test_sheets_oauth_state_and_pkce_survive_a_promotion(monkeypatch):
    from backend.app.services import google_sheets_oauth as sheets

    _aes(monkeypatch, OLD_F)
    state = Crypto(OLD_F).encrypt("{}")
    started = sheets.pkce_code_verifier(state)  # derived with the one key at the start
    ring = Crypto(f"{NEW_F},{OLD_F}")
    oauth = sheets.GoogleSheetsOAuth(ring)
    member = oauth._check_state_age(state)
    assert member == OLD_F
    _aes(monkeypatch, f"{NEW_F},{OLD_F}")
    # the exchange derives the verifier with the key that opens the state, so it matches
    assert sheets.pkce_code_verifier(state, member) == started
    # a request started after the promotion uses the new key, and still completes
    fresh = ring.encrypt("{}")
    fresh_verifier = sheets.pkce_code_verifier(fresh)
    assert fresh_verifier != sheets.pkce_code_verifier(fresh, OLD_F)
    assert fresh_verifier == sheets.pkce_code_verifier(fresh, oauth._check_state_age(fresh))
    with pytest.raises(Exception):
        oauth._check_state_age("not a state")


def test_the_oauth_state_of_an_integration_is_read_with_the_ring(monkeypatch):
    from backend.app.services.integration_oauth_state import IntegrationOAuthState, mint

    user = User(id="u1", sub="u1@example.com", sid="s1")
    state = mint(Crypto(OLD_F), user, None)
    reader = IntegrationOAuthState(Crypto(f"{NEW_F},{OLD_F}"), used_state_repo=None)
    assert reader.read(state, user)["user_id"] == "u1"
    with pytest.raises(Exception):
        IntegrationOAuthState(Crypto(NEW_F), used_state_repo=None).read(state, user)


def test_a_quoted_encryption_key_gives_the_same_pkce_verifier_at_the_start_and_the_exchange(monkeypatch):
    """One parser for every use of the key: the cipher, the state it opens and the
    verifier derived from it all see the key without its quotes."""
    from backend.app.services import google_sheets_oauth as sheets

    quoted = f"'{NEW_F},{OLD_F}'"
    _aes(monkeypatch, quoted)
    ring = Crypto(quoted)
    assert ring.member_count == 2
    state = ring.encrypt("{}")
    started = sheets.pkce_code_verifier(state)  # derived with the first key at the start
    oauth = sheets.GoogleSheetsOAuth(ring)
    member = oauth._check_state_age(state)
    assert member == NEW_F  # no quote in the key the state opened with
    assert sheets.pkce_code_verifier(state, member) == started
    unquoted = f"{NEW_F},{OLD_F}"
    _aes(monkeypatch, unquoted)
    assert sheets.pkce_code_verifier(state) == started  # the same as the unquoted ring


def test_the_algorithm_is_pinned_to_hs256_inside_decode_with_ring():
    claims = {"id": "u", "exp": int(time.time()) + 60}
    hs512 = jwt.encode(claims, OLD, algorithm="HS512")
    unsigned = jwt.encode(claims, None, algorithm="none")
    for token in (hs512, unsigned):
        # a caller cannot widen it
        for algorithms in (None, ["HS256"], ["HS512"], ["HS256", "HS512", "none"]):
            extra = {} if algorithms is None else {"algorithms": algorithms}
            with pytest.raises(jwt.PyJWTError):
                decode_with_ring(token, f"{NEW},{OLD}", **extra)
    assert decode_with_ring(jwt.encode(claims, OLD, algorithm="HS256"), f"{NEW},{OLD}", algorithms=["HS512"])["id"] == "u"
