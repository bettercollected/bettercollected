"""An email address names one account whatever its case: sign-in codes,
provider sign-in, single sign-on and directory sync all reach the account
stored first, and none creates a case variant next to it."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from auth.app.container import container
from auth.app.repositories.user_repository import UserRepository
from auth.app.services import sso_service as sso_module
from auth.app.services.auth_service import AuthService
from auth.app.services.provider_sign_in import account_for_provider_sign_in
from auth.app.services.sso_service import SsoService
from tests.integration.app.test_sso_service import make_settings

pytestmark = pytest.mark.asyncio

STORED = "Jane.Doe@Example.com"


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
async def jane(repo):
    return await repo.save_user(STORED, "Jane", "Doe")


async def test_a_code_sign_in_in_another_case_reaches_the_same_account(
    repo, jane, no_mail
):
    service = AuthService(None, repo, None)

    await service.send_otp_to_mail("JANE.DOE@example.COM", None, None, creator=True)
    code = (await repo.get_user_by_email(STORED)).otp_code
    signed_in = await service.validate_otp("jane.doe@example.com", code)

    assert signed_in is not None and signed_in.id == str(jane.id)
    assert signed_in.sub == STORED  # the stored address, as it was written
    assert await repo.count() == 1


async def test_a_code_sign_up_never_adds_a_case_variant(repo, no_mail):
    service = AuthService(None, repo, None)

    await service.send_otp_to_mail("New.Person@Example.com", None, None, creator=False)
    await service.send_otp_to_mail("new.person@example.com", None, None, creator=True)

    assert await repo.count() == 1
    stored = await repo.get_user_by_email("NEW.PERSON@EXAMPLE.COM")
    assert stored.email == "New.Person@Example.com"
    assert stored.otp_code_for == "FORM_CREATOR"


async def test_a_provider_sign_in_in_another_case_reaches_the_same_account(repo, jane):
    account = await account_for_provider_sign_in(
        repo, "google", "jane.doe@example.com", True, creator=True
    )
    assert account.id == jane.id and account.email == STORED
    assert await repo.count() == 1


async def test_the_import_callback_finds_the_account_in_another_case(repo, jane):
    import jwt

    from auth.config import settings

    token = jwt.encode(
        {"email": "JANE.DOE@EXAMPLE.COM"}, settings.AUTH_JWT_SECRET, "HS256"
    )
    user = await AuthService(None, repo, None).handle_auth_callback(token, True)
    assert user.id == str(jane.id) and user.sub == STORED


def _assertion(email: str) -> str:
    return sso_module.crypto.encrypt(
        json.dumps(
            {
                "email": email,
                "tenant": "t",
                "first_name": None,
                "last_name": None,
                "issued_at": int(time.time()),
                "purpose": "sso_account",
            }
        )
    )


async def test_single_sign_on_and_directory_sync_reach_the_same_account(repo, jane):
    svc = SsoService(repo, make_settings())

    signed_in = await svc.account(_assertion("jane.doe@example.com"))
    looked_up = await svc.directory_account("JANE.DOE@example.com", create=True)

    assert signed_in.id == str(jane.id) and signed_in.sub == STORED
    assert looked_up == {"user": signed_in, "conflict": False}
    assert await repo.count() == 1


async def test_concurrent_sign_ups_in_two_cases_leave_one_account(repo, no_mail):
    """The unique index decides a race the lookups can't see: at most one of
    two simultaneous first sign-ins succeeds."""
    service = AuthService(None, repo, None)
    results = await asyncio.gather(
        service.send_otp_to_mail("race@example.com", None, None, creator=True),
        service.send_otp_to_mail("RACE@example.com", None, None, creator=True),
        return_exceptions=True,
    )
    assert any(r is None for r in results)
    assert await repo.count() == 1
