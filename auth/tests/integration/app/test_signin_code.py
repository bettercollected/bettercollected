"""Sign-in codes are stored as a keyed hash, never as the code: a correct code
signs in once, a wrong one counts a try (five clear the code), an expired one
is refused without comparing it, and a plain code stored before codes were
hashed is refused (app/services/signin_code.py)."""

import asyncio
import calendar
import datetime as dt
import hmac
import logging
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from auth.__main__ import AccessLogWithoutQuery
from auth.app.container import container
from auth.app.repositories.user_repository import UserRepository
from auth.app.services import signin_code
from auth.app.services.auth_service import AuthService
from auth.app.services.user_service import UserService
from common.enums.roles import Roles

CODE = "ABC-123"
SECRET = "a-test-key"


def unique_email() -> str:
    return f"code-{uuid.uuid4().hex[:12]}@example.com"


def epoch(minutes: int) -> int:
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
    return calendar.timegm(later.utctimetuple())


@pytest.fixture
def no_mail():
    with patch("auth.app.services.auth_service.MailService") as mail_service:
        mail_service.return_value.send_message = AsyncMock()
        yield mail_service


@pytest_asyncio.fixture
async def repo(clean_postgres):
    yield UserRepository(container.pg_sessionmaker())
    await container.pg_engine().dispose()


@pytest_asyncio.fixture
async def pending(repo, no_mail):
    """An account with the code CODE pending (sent as a creator code)."""
    email = unique_email()
    with patch.object(AuthService, "generate_otp", return_value=CODE):
        await AuthService(None, repo, None).send_otp_to_mail(
            email, None, None, creator=True
        )
    return email


def service(repo) -> AuthService:
    return AuthService(None, repo, None)


# -- the helper ---------------------------------------------------------------------
class TestHelper:
    def test_the_stored_value_is_a_keyed_hash_not_the_code(self):
        value = signin_code.stored(
            signin_code.digest(CODE, "a@example.com", "FORM_CREATOR", 99, secret=SECRET)
        )
        assert CODE not in value and CODE.replace("-", "") not in value
        parsed = signin_code.parse(value)
        assert parsed.wrong_tries == 0 and len(parsed.digest) == 64
        # keyed: another key gives another hash
        assert parsed.digest != signin_code.digest(
            CODE, "a@example.com", "FORM_CREATOR", 99, secret="another-key"
        )

    def test_the_hash_is_bound_to_email_purpose_and_expiry(self):
        base = ("a@example.com", "FORM_CREATOR", 99)
        expected = signin_code.parse(
            signin_code.stored(signin_code.digest(CODE, *base, secret=SECRET))
        )
        assert signin_code.matches(expected, CODE, *base, secret=SECRET)
        # the email ignores case and surrounding blanks
        assert signin_code.matches(
            expected, CODE, " A@Example.com ", "FORM_CREATOR", 99, secret=SECRET
        )
        for other in (
            ("b@example.com", "FORM_CREATOR", 99),
            ("a@example.com", "FORM_RESPONDER", 99),
            ("a@example.com", "FORM_CREATOR", 100),
        ):
            assert not signin_code.matches(expected, CODE, *other, secret=SECRET)
        assert not signin_code.matches(expected, "ABC-124", *base, secret=SECRET)
        assert not signin_code.matches(expected, "", *base, secret=SECRET)
        assert not signin_code.matches(expected, None, *base, secret=SECRET)

    def test_a_purpose_enum_and_its_value_hash_alike(self):
        assert signin_code.digest(
            CODE, "a@example.com", Roles.FORM_CREATOR, 99, secret=SECRET
        ) == signin_code.digest(CODE, "a@example.com", "FORM_CREATOR", 99, secret=SECRET)

    def test_the_comparison_is_constant_time(self):
        expected = signin_code.parse(
            signin_code.stored(
                signin_code.digest(CODE, "a@example.com", "X", 99, secret=SECRET)
            )
        )
        with patch.object(
            signin_code.hmac, "compare_digest", wraps=hmac.compare_digest
        ) as compare:
            assert signin_code.matches(expected, CODE, "a@example.com", "X", 99, secret=SECRET)
            assert not signin_code.matches(
                expected, "WRONG-1", "a@example.com", "X", 99, secret=SECRET
            )
        assert compare.call_count == 2

    @pytest.mark.parametrize(
        "value",
        [None, "", CODE, "482913", "otp1$0$" + "z" * 64, "otp1$0$" + "a" * 63,
         "otp2$0$" + "a" * 64, "otp1$x$" + "a" * 64, " otp1$0$" + "a" * 64],
    )
    def test_anything_but_the_hash_format_is_not_a_code(self, value):
        assert signin_code.parse(value) is None

    def test_no_key_refuses_instead_of_hashing_with_an_empty_key(self):
        with pytest.raises(RuntimeError):
            signin_code.digest(CODE, "a@example.com", "X", 99, secret="")


# -- sign-in --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_correct_code_signs_in_once(repo, pending):
    stored = await repo.get_user_by_email(pending)
    assert CODE not in stored.otp_code
    assert signin_code.parse(stored.otp_code).wrong_tries == 0

    signed_in = await service(repo).validate_otp(pending, CODE)
    assert signed_in is not None and signed_in.sub == pending
    assert signed_in.email_verified is True
    after = await repo.get_user_by_email(pending)
    assert (after.otp_code, after.otp_expiry, after.otp_code_for) == (None, None, None)
    assert set(after.roles) == {"FORM_RESPONDER", "FORM_CREATOR"}

    # cleared after use: the same code never signs in again
    assert await service(repo).validate_otp(pending, CODE) is None


@pytest.mark.asyncio
async def test_a_wrong_code_is_refused_and_counted(repo, pending):
    assert await service(repo).validate_otp(pending, "WRONG-1") is None
    stored = await repo.get_user_by_email(pending)
    assert signin_code.parse(stored.otp_code).wrong_tries == 1
    # still the code it was: the right one works after a wrong try
    assert await service(repo).validate_otp(pending, CODE) is not None


@pytest.mark.asyncio
async def test_five_wrong_tries_clear_the_code(repo, pending):
    for attempt in range(1, signin_code.MAX_WRONG_TRIES):
        assert await service(repo).validate_otp(pending, f"BAD-00{attempt}") is None
        stored = await repo.get_user_by_email(pending)
        assert signin_code.parse(stored.otp_code).wrong_tries == attempt
    assert await service(repo).validate_otp(pending, "BAD-005") is None

    stored = await repo.get_user_by_email(pending)
    assert (stored.otp_code, stored.otp_expiry) == (None, None)
    # the right code no longer works: a new one must be requested
    assert await service(repo).validate_otp(pending, CODE) is None


@pytest.mark.asyncio
async def test_parallel_guesses_share_the_same_five_tries(repo, pending):
    guesses = [f"G{n:02d}-XYZ" for n in range(20)]
    results = await asyncio.gather(
        *(service(repo).validate_otp(pending, g) for g in guesses)
    )
    assert results == [None] * len(guesses)
    assert (await repo.get_user_by_email(pending)).otp_code is None
    assert await service(repo).validate_otp(pending, CODE) is None


@pytest.mark.asyncio
async def test_parallel_uses_of_the_right_code_sign_in_once(repo, pending):
    results = await asyncio.gather(
        *(service(repo).validate_otp(pending, CODE) for _ in range(5))
    )
    assert sum(r is not None for r in results) == 1


@pytest.mark.asyncio
async def test_an_expired_code_is_refused_without_comparing(repo, no_mail):
    email = unique_email()
    user = await repo.save_user(email)
    expiry = epoch(-1)
    await repo.set_user_otp(
        user.id,
        signin_code.stored(signin_code.digest(CODE, email, "FORM_CREATOR", expiry)),
        expiry,
        "FORM_CREATOR",
    )
    with patch.object(signin_code, "matches", wraps=signin_code.matches) as compare:
        assert await service(repo).validate_otp(email, CODE) is None
    compare.assert_not_called()
    assert (await repo.get_user_by_email(email)).otp_code is None


@pytest.mark.asyncio
async def test_a_plain_code_stored_before_hashing_is_refused(repo):
    email = unique_email()
    user = await repo.save_user(email, creator=False)
    # what 4.1.1 and earlier stored: the code itself
    await repo.set_user_otp(user.id, CODE, epoch(5), "FORM_CREATOR")

    assert await service(repo).validate_otp(email, CODE) is None
    after = await repo.get_user_by_email(email)
    assert (after.otp_code, after.otp_expiry, after.otp_code_for) == (None, None, None)
    assert "FORM_CREATOR" not in (after.roles or [])


@pytest.mark.asyncio
async def test_a_hash_moved_to_another_account_never_matches(repo, pending):
    other = unique_email()
    victim = await repo.save_user(other)
    source = await repo.get_user_by_email(pending)
    await repo.set_user_otp(
        victim.id, source.otp_code, source.otp_expiry, source.otp_code_for
    )
    assert await service(repo).validate_otp(other, CODE) is None


@pytest.mark.asyncio
async def test_a_code_asked_as_respondent_does_not_sign_in_as_creator(repo, pending):
    stored = await repo.get_user_by_email(pending)
    # the purpose changed in storage: the hash was made for the other one
    await repo.set_user_otp(stored.id, stored.otp_code, stored.otp_expiry, "FORM_RESPONDER")
    assert await service(repo).validate_otp(pending, CODE) is None


@pytest.mark.asyncio
async def test_unknown_accounts_and_missing_codes_are_refused(repo):
    assert await service(repo).validate_otp(unique_email(), CODE) is None
    email = unique_email()
    await repo.save_user(email)
    assert await service(repo).validate_otp(email, CODE) is None


@pytest.mark.asyncio
async def test_a_new_code_resets_the_tries(repo, pending, no_mail):
    for _ in range(signin_code.MAX_WRONG_TRIES - 1):
        await service(repo).validate_otp(pending, "WRONG-1")
    with patch.object(AuthService, "generate_otp", return_value="NEW-456"):
        await service(repo).send_otp_to_mail(pending, None, None, creator=True)
    stored = await repo.get_user_by_email(pending)
    assert signin_code.parse(stored.otp_code).wrong_tries == 0
    assert await service(repo).validate_otp(pending, CODE) is None  # the old code
    assert await service(repo).validate_otp(pending, "NEW-456") is not None


@pytest.mark.asyncio
async def test_the_code_is_mailed_but_never_stored(repo, no_mail):
    email = unique_email()
    with patch.object(AuthService, "generate_otp", return_value=CODE):
        await service(repo).send_otp_to_mail(email, None, None, creator=False)
    message = no_mail.return_value.send_message.call_args.args[0]
    assert CODE in message.body
    stored = await repo.get_user_by_email(email)
    assert CODE not in stored.model_dump_json()


@pytest.mark.asyncio
async def test_user_listings_never_carry_the_code(repo, pending):
    users = UserService(repo, None)
    stored = await repo.get_user_by_email(pending)
    for listed in (
        await users.get_users_info_from_emails([pending]),
        await users.get_user_info_from_user_ids([stored.id]),
    ):
        assert len(listed) == 1 and listed[0].email == pending
        assert (listed[0].otp_code, listed[0].otp_expiry, listed[0].otp_code_for) == (
            None,
            None,
            None,
        )
    # the stored code is untouched by listing it
    assert (await repo.get_user_by_email(pending)).otp_code == stored.otp_code


def test_the_code_is_refused_over_http_after_use(app_runner, no_mail):
    email = unique_email()
    with patch.object(AuthService, "generate_otp", return_value=CODE):
        sent = app_runner.get(
            "auth/otp/send", params={"receiver_email": email, "creator": False}
        )
    assert sent.status_code == 200, sent.text
    listed = app_runner.get("users", params={"emails": [email]}).json()["users_info"]
    assert listed[0]["otp_code"] is None and CODE not in str(listed)

    first = app_runner.get("auth/otp/validate", params={"email": email, "otp_code": CODE})
    assert first.status_code == 200 and first.json()["user"]["sub"] == email
    again = app_runner.get("auth/otp/validate", params={"email": email, "otp_code": CODE})
    assert again.status_code == 200 and again.json()["user"] is None


# -- the access log -------------------------------------------------------------------
def test_the_access_log_leaves_out_the_query_string():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        (
            "10.0.0.1:5000",
            "GET",
            f"/api/v1/auth/otp/validate?email=a%40example.com&otp_code={CODE}",
            "1.1",
            200,
        ),
        None,
    )
    assert AccessLogWithoutQuery().filter(record) is True
    line = record.getMessage()
    assert CODE not in line and "example.com" not in line
    assert '"GET /api/v1/auth/otp/validate HTTP/1.1" 200' in line
