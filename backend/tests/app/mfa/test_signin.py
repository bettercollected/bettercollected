"""The second-factor step of a sign-in, and the claim every token carries."""

import ast
import datetime as dt
import http.cookies
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from common.models.user import User
from common.security import totp
from common.security.clock import FakeClock

import backend
from backend.app.container import container
from backend.app.services.auth_cookie_service import access_token_for
from backend.app.services.mfa.signin import CHALLENGE_COOKIE, CHALLENGE_TYP
from backend.app.services.session_service import (
    SessionService,
    decode_token,
    user_from_access_token,
)
from backend.config import settings
from tests.app.mfa.helpers import enrolled, new_clock, service, signed_in
from tests.app.services.test_auth_call_sites import FakeAuth

OTP = "/api/v1/auth/otp/validate"
CHALLENGE = "/api/v1/auth/mfa/challenge"


def cookies_of(response) -> dict:
    found = {}
    headers = response.headers
    getter = getattr(headers, "get_list", None) or headers.getlist
    for header in getter("set-cookie"):
        jar = http.cookies.SimpleCookie(header)
        for name, morsel in jar.items():
            found[name] = morsel.value if morsel["max-age"] != "0" else None
    return found


def code_for(secret: str, offset: int = 0) -> str:
    return totp.hotp(totp.decode_secret(secret), totp.step_for(time.time()) + offset)


async def enrolled_account(email="staff@example.org"):
    """An account with an authenticator app; returns (account, secret, codes)."""
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(email, now=clock.now())
    secret, codes = await enrolled(svc, clock, account)
    return account, secret, codes


def otp_reply(account):
    return {
        "user": {
            "id": account.user.id,
            "sub": account.user.sub,
            "roles": ["FORM_RESPONDER"],
        }
    }


async def first_factor(client, account):
    with patch(
        "common.services.http_client.HttpClient.get",
        AsyncMock(return_value=otp_reply(account)),
    ):
        return await client.post(
            OTP, json={"email": account.user.sub, "otp_code": "ABC-123"}
        )


async def session_count() -> int:
    return await container.session_repo().count()


@pytest.fixture()
async def staff(totp_on):
    account, secret, codes = await enrolled_account()
    return account, secret, codes


async def test_an_account_with_a_factor_gets_a_challenge_and_no_session(client, staff):
    account, secret, codes = staff
    before = await session_count()
    reply = await first_factor(client, account)
    assert reply.status_code == 200, reply.text
    assert reply.json() == {"mfaRequired": True}
    cookies = cookies_of(reply)
    assert cookies.get(CHALLENGE_COOKIE)
    assert "Authorization" not in cookies and "RefreshToken" not in cookies
    assert await session_count() == before
    # the challenge carries no permission: it is not an access token
    assert user_from_access_token(cookies[CHALLENGE_COOKIE]) is None
    claims = decode_token(cookies[CHALLENGE_COOKIE])
    assert claims["typ"] == CHALLENGE_TYP and claims["id"] == account.user.id
    assert set(claims) <= {"typ", "jti", "exp", "id", "sub", "roles", "plan", "email_verified", "method"}


async def test_the_right_code_makes_the_session_with_the_claim(client, staff):
    account, secret, codes = staff
    challenge = cookies_of(await first_factor(client, account))[CHALLENGE_COOKIE]
    before = await session_count()
    reply = await client.post(
        CHALLENGE, cookies={CHALLENGE_COOKIE: challenge}, json={"code": code_for(secret, 1)}
    )
    assert reply.status_code == 200, reply.text
    assert reply.headers["cache-control"] == "no-store"
    cookies = cookies_of(reply)
    assert cookies[CHALLENGE_COOKIE] is None  # cleared
    claims = decode_token(cookies["Authorization"])
    assert claims["mfa"] is True and claims["id"] == account.user.id
    assert decode_token(cookies["RefreshToken"])["mfa"] is True
    assert await session_count() == before + 1
    session = await container.session_repo().get(claims["sid"])
    assert session.mfa_at is not None and session.mfa_method == "totp"
    assert session.method == "otp"


async def test_a_wrong_code_makes_no_session_and_the_challenge_stays_usable(client, staff):
    account, secret, codes = staff
    challenge = cookies_of(await first_factor(client, account))[CHALLENGE_COOKIE]
    before = await session_count()
    bad = await client.post(
        CHALLENGE, cookies={CHALLENGE_COOKIE: challenge}, json={"code": "000000"}
    )
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_code"
    assert "Authorization" not in cookies_of(bad)
    assert await session_count() == before
    good = await client.post(
        CHALLENGE, cookies={CHALLENGE_COOKIE: challenge}, json={"code": codes[0]}
    )
    assert good.status_code == 200
    session = await container.session_repo().get(
        decode_token(cookies_of(good)["Authorization"])["sid"]
    )
    assert session.mfa_method == "recovery"
    assert good.json()["recoveryLeft"] == 9


async def test_a_challenge_makes_one_session_only(client, staff):
    account, secret, codes = staff
    challenge = cookies_of(await first_factor(client, account))[CHALLENGE_COOKIE]
    first = await client.post(
        CHALLENGE, cookies={CHALLENGE_COOKIE: challenge}, json={"code": codes[0]}
    )
    assert first.status_code == 200
    before = await session_count()
    again = await client.post(
        CHALLENGE, cookies={CHALLENGE_COOKIE: challenge}, json={"code": codes[1]}
    )
    assert again.status_code == 401 and again.json()["code"] == "mfa_challenge_expired"
    assert await session_count() == before


async def test_a_bad_challenge_is_refused(client, staff):
    account, secret, codes = staff
    good = cookies_of(await first_factor(client, account))[CHALLENGE_COOKIE]
    claims = decode_token(good)
    key = settings.auth_settings.JWT_SECRET.split(",")[0]
    expired = jwt.encode({**claims, "exp": int(time.time()) - 5}, key, algorithm="HS256")
    forged = jwt.encode(claims, "another-secret-" * 4, algorithm="HS256")
    as_access = access_token_for(account.user)
    unsigned = jwt.encode(claims, key=None, algorithm="none")
    for bad in (expired, forged, as_access, unsigned, "garbage", ""):
        reply = await client.post(
            CHALLENGE, cookies={CHALLENGE_COOKIE: bad} if bad else {}, json={"code": codes[0]}
        )
        assert reply.status_code == 401, bad[:10]
        assert reply.json()["code"] == "mfa_challenge_expired"
    # and none of them used a recovery code up
    assert (await service(new_clock()).status(account.user)).recovery_left == 10


async def test_a_challenge_for_a_user_whose_factor_was_removed_gets_no_session(client, staff):
    account, secret, codes = staff
    challenge = cookies_of(await first_factor(client, account))[CHALLENGE_COOKIE]
    await container.user_totp_repo().delete_for_user(account.user.id)
    reply = await client.post(
        CHALLENGE, cookies={CHALLENGE_COOKIE: challenge}, json={"code": codes[0]}
    )
    assert reply.status_code == 409 and reply.json()["code"] == "no_factor"


async def test_without_a_factor_or_with_the_switch_off_sign_in_is_as_before(client, totp_on, monkeypatch):
    # no factor
    plain = await signed_in("plain@example.org")
    reply = await first_factor(client, plain)
    assert reply.json() == "Logged In successfully"
    assert "Authorization" in cookies_of(reply)
    # a factor, but the switch is off: no challenge for an enrolled user either
    account, secret, codes = await enrolled_account("off@example.org")
    monkeypatch.setattr(settings.totp, "ENABLED", False)
    reply = await first_factor(client, account)
    assert reply.json() == "Logged In successfully"
    cookies = cookies_of(reply)
    assert "Authorization" in cookies and CHALLENGE_COOKIE not in cookies
    assert "mfa" not in decode_token(cookies["Authorization"])
    # and the challenge route is inert
    other = await client.post(CHALLENGE, cookies={CHALLENGE_COOKIE: "x"}, json={"code": "1"})
    assert other.status_code == 422 and other.json()["code"] == "totp_off"


async def test_single_sign_on_and_respondent_sessions_are_never_challenged(totp_on):
    account, secret, codes = await enrolled_account("sso@example.org")
    signin = container.mfa_signin_service()
    assert await signin.required_for(account.user, "otp") is True
    assert await signin.required_for(account.user, "sso") is False
    respondent = account.user.model_copy(update={"session_scope": "respondent"})
    assert await signin.required_for(respondent, "otp") is False


async def test_google_sign_in_is_challenged_too(client, staff, monkeypatch):
    account, secret, codes = staff
    monkeypatch.setattr(settings.api_settings, "CLIENT_URL", "https://app.example.org")
    user = {"id": account.user.id, "sub": account.user.sub, "roles": ["FORM_CREATOR"]}
    with patch.object(
        type(container.auth_service()),
        "basic_auth_callback",
        AsyncMock(return_value=(user, "https://app.example.org/forms")),
    ):
        reply = await client.get(
            "/api/v1/auth/google/basic/callback",
            params={"code": "c", "state": "s"},
            follow_redirects=False,
        )
    assert reply.status_code == 307, reply.text
    assert reply.headers["location"] == (
        "https://app.example.org/login?mfa=1&next=https%3A%2F%2Fapp.example.org%2Fforms"
    )
    cookies = cookies_of(reply)
    assert cookies.get(CHALLENGE_COOKIE) and "Authorization" not in cookies


async def test_the_step_up_and_the_enrolment_reissue_the_access_token_with_the_claim(client, totp_on):
    account = await signed_in("promote@example.org")
    enrol = (await client.post("/api/v1/auth/mfa/totp/enrol", cookies=account.cookies, json={})).json()
    secret = "".join(enrol["secret"].split())
    confirmed = await client.post(
        "/api/v1/auth/mfa/totp/confirm",
        cookies=account.cookies,
        json={"factorId": enrol["factorId"], "code": code_for(secret)},
    )
    assert decode_token(cookies_of(confirmed)["Authorization"])["mfa"] is True
    # a session that signed in before enrolling gets promoted in place
    old = await signed_in("promote2@example.org")
    session = await container.session_repo().get(old.user.sid)
    await container.session_repo().save(session.model_copy(update={"user_id": account.user.id}))
    mine = old.user.model_copy(update={"id": account.user.id})
    cookies = {"Authorization": access_token_for(mine)}
    assert "mfa" not in decode_token(cookies["Authorization"])
    reply = await client.post(
        "/api/v1/auth/mfa/verify", cookies=cookies, json={"code": code_for(secret, 1)}
    )
    assert reply.status_code == 200, reply.text
    assert decode_token(cookies_of(reply)["Authorization"])["mfa"] is True
    assert (await container.session_repo().get(old.user.sid)).mfa_at is not None


async def test_a_client_cannot_name_its_own_second_factor(client):
    """The claim is only ever read from a token this backend signed."""
    account = await signed_in("forge@example.org")
    claims = decode_token(access_token_for(account.user))
    forged = jwt.encode({**claims, "mfa": True}, "not-our-key-" * 4, algorithm="HS256")
    assert user_from_access_token(forged) is None
    assert user_from_access_token(access_token_for(account.user)).mfa is None
    body = await client.post(
        "/api/v1/auth/mfa/verify", cookies={"Authorization": forged}, json={"code": "1"}
    )
    assert body.status_code == 401


async def test_a_refresh_keeps_the_claim_and_a_session_without_it_never_gains_one(monkeypatch):
    monkeypatch.setattr(settings.auth_settings, "INTERNAL_NOTIFY_KEY", "k")
    from starlette.requests import Request
    from starlette.responses import Response
    import backend.app.services.session_service as session_module

    monkeypatch.setattr(session_module.httpx, "AsyncClient", FakeAuth)
    FakeAuth.calls, FakeAuth.status_code = [], 200
    from tests.app.controllers.data import testUser

    async def refreshed(mfa_method):
        signed = Response()
        await container.session_service().start(
            User(id=testUser.id, sub=testUser.sub, roles=["FORM_CREATOR"]),
            signed,
            mfa_method=mfa_method,
        )
        refresh = cookies_of(signed)["RefreshToken"]
        request = Request(
            {"type": "http", "headers": [(b"cookie", f"RefreshToken={refresh}".encode())]}
        )
        out = Response()
        user = await container.session_service().refresh(request, out, rotate=True)
        return user, cookies_of(out)

    user, cookies = await refreshed("totp")
    assert user.mfa is True
    assert decode_token(cookies["Authorization"])["mfa"] is True
    assert decode_token(cookies["RefreshToken"])["mfa"] is True  # the rotated one too
    user, cookies = await refreshed(None)
    assert user.mfa is None and "mfa" not in decode_token(cookies["Authorization"])


# every place the backend signs a token, and where its user comes from. A new one
# fails here until it is added and shown to carry the session's ``mfa``.
TOKEN_MINTS = {
    # the session's own record
    "services/session_service.py:SessionService.start",
    "services/session_service.py:SessionService.refresh",
    # the user of the live access token (it already carries the claim)
    "controllers/auth_router.py:AuthRoutes._auth_callback",
    "controllers/price_suggestion.py:",
    "controllers/coupon_controller.py:",
    # the session just promoted (the claim is set on purpose)
    "controllers/mfa_router.py:_promoted",
    # the signing itself
    "services/auth_cookie_service.py:access_token_for",
    "services/auth_cookie_service.py:set_access_token_to_response",
    "services/auth_cookie_service.py:set_refresh_token_to_response",
}
MINT_NAMES = {"access_token_for", "set_access_token_to_response", "set_refresh_token_to_response", "_encode"}


def _mint_sites():
    package = Path(backend.__file__).parent / "app"
    sites = set()
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        stack = []

        def walk(node):
            name = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                stack.append(node.name)
                name = node.name
            if isinstance(node, ast.Call):
                func = node.func
                called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
                if called in MINT_NAMES:
                    rel = path.relative_to(package).as_posix()
                    qualified = ".".join(stack) if stack and rel != "services/auth_cookie_service.py" else (stack[0] if stack else "")
                    sites.add(f"{rel}:{qualified}")
            for child in ast.iter_child_nodes(node):
                walk(child)
            if name is not None:
                stack.pop()

        walk(tree)
    return sites


def test_every_token_mint_is_a_known_one():
    found = _mint_sites()
    known = {s.split(":")[0] + ":" for s in TOKEN_MINTS}
    unexpected = sorted(s for s in found if s.split(":")[0] + ":" not in known)
    assert not unexpected, (
        "a new place signs tokens: show that its user carries the session's "
        f"`mfa` and add it to TOKEN_MINTS: {unexpected}"
    )
