"""Enrolling an authenticator app: start, confirm, what is stored."""

import json

import pytest
from sqlalchemy import text

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_audit_event import TOTP_ENROLLED
from backend.app.services.mfa import sealing
from backend.app.services.registration.secrets import SecretUnreadable
from tests.app.mfa.helpers import code_now, new_clock, secret_of, service, signed_in

pytestmark = pytest.mark.usefixtures("totp_on")


def code_of(error: HTTPException) -> str:
    return error.content["code"]


async def raw_rows() -> str:
    """Every stored row of the factor tables as text (to look for secrets)."""
    engine = container.pg_engine()
    async with engine.connect() as conn:
        rows = []
        for table in ("user_totp_factors", "user_recovery_codes", "workspace_audit_events"):
            result = await conn.execute(text(f"SELECT doc::text FROM app.{table}"))
            rows.extend(r[0] for r in result)
    return "\n".join(rows)


async def test_enrolment_returns_the_secret_the_uri_and_a_qr_image_once():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    enrol = await svc.begin_enrolment(account.user)
    secret = secret_of(enrol)
    assert len(secret) == 32 and enrol.secret.count(" ") == 7
    assert enrol.uri.startswith("otpauth://totp/Test:mfa%40example.org?")
    assert f"secret={secret}" in enrol.uri and "issuer=Test" in enrol.uri
    assert enrol.qr.startswith("data:image/svg+xml")
    # an inline image: no script, no link
    assert "script" not in enrol.qr.lower() and "href" not in enrol.qr.lower()
    status = await svc.status(account.user)
    assert status.available and not status.enabled


async def test_the_secret_is_sealed_and_never_stored_in_clear():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    enrol = await svc.begin_enrolment(account.user)
    secret = secret_of(enrol)
    stored = await raw_rows()
    assert secret not in stored and enrol.secret not in stored
    factor = await container.user_totp_repo().pending(account.user.id)
    # the repr of the record carries no ciphertext either
    assert factor.secret_sealed not in repr(factor)
    crypto = container.crypto()
    assert sealing.unseal_secret(crypto, account.user.id, factor.id, factor.secret_sealed) == secret
    # bound to the account and the factor: a copy elsewhere is refused
    for user_id, factor_id in (("someone-else", factor.id), (account.user.id, "0" * 24)):
        with pytest.raises(SecretUnreadable):
            sealing.unseal_secret(crypto, user_id, factor_id, factor.secret_sealed)
    # and it cannot be opened as another kind of sealed value
    other = crypto.encrypt(json.dumps({"v": 1, "purpose": "webhook_url", "user_id": account.user.id,
                                       "factor_id": str(factor.id), "secret": "x"}))
    with pytest.raises(SecretUnreadable):
        sealing.unseal_secret(crypto, account.user.id, factor.id, other)


async def test_an_old_session_may_not_add_a_factor():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(age_minutes=16, now=clock.now())
    with pytest.raises(HTTPException) as refused:
        await svc.begin_enrolment(account.user)
    assert refused.value.status_code == 403
    assert code_of(refused.value) == "recent_proof_required"
    assert await container.user_totp_repo().pending(account.user.id) is None


async def test_confirming_issues_ten_codes_stores_only_hashes_and_marks_the_session():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    enrol = await svc.begin_enrolment(account.user)
    secret = secret_of(enrol)
    result = await svc.confirm_enrolment(
        account.user, enrol.factor_id, code_now(secret, clock)
    )
    codes = result.recovery_codes
    assert len(codes) == 10 and len(set(codes)) == 10
    stored = await raw_rows()
    for code in codes:
        assert code not in stored and code.replace("-", "") not in stored
    assert secret not in stored
    status = await svc.status(account.user)
    assert status.enabled and status.recovery_left == 10
    assert await container.user_totp_repo().pending(account.user.id) is None
    session = await container.session_repo().get(account.user.sid)
    assert session.mfa_at is not None and session.mfa_method == "totp"
    events = await container.workspace_audit_repo().many()
    assert [e.event for e in events] == [TOTP_ENROLLED]
    assert events[0].user_id == account.user.id
    assert secret not in repr(events) and codes[0] not in repr(events)


async def test_a_wrong_code_does_not_enrol_and_says_nothing_about_why():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    enrol = await svc.begin_enrolment(account.user)
    secret = secret_of(enrol)
    near = {code_now(secret, clock, o) for o in (-1, 0, 1)}
    wrong = next(f"{n:06d}" for n in range(10**6) if f"{n:06d}" not in near)
    for bad in (wrong, "", "abcdef", "1" * 40):
        with pytest.raises(HTTPException) as refused:
            await svc.confirm_enrolment(account.user, enrol.factor_id, bad)
        assert refused.value.status_code == 422 and code_of(refused.value) == "invalid_code"
    assert not (await svc.status(account.user)).enabled


async def test_starting_again_replaces_the_pending_factor():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    first = await svc.begin_enrolment(account.user)
    second = await svc.begin_enrolment(account.user)
    assert first.factor_id != second.factor_id
    with pytest.raises(HTTPException) as refused:
        await svc.confirm_enrolment(
            account.user, first.factor_id, code_now(secret_of(first), clock)
        )
    assert code_of(refused.value) == "invalid_code"
    await svc.confirm_enrolment(
        account.user, second.factor_id, code_now(secret_of(second), clock)
    )
    assert (await svc.status(account.user)).enabled


async def test_a_pending_factor_expires_after_fifteen_minutes():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    enrol = await svc.begin_enrolment(account.user)
    clock.advance(16 * 60)
    with pytest.raises(HTTPException) as refused:
        await svc.confirm_enrolment(
            account.user, enrol.factor_id, code_now(secret_of(enrol), clock)
        )
    assert code_of(refused.value) == "invalid_code"
    # the daily purge keeps it for an hour, then deletes it
    assert await svc.purge_pending() == 0
    clock.advance(3600)
    assert await svc.purge_pending() == 1
    assert await container.user_totp_repo().pending(account.user.id) is None


async def test_another_account_cannot_confirm_my_pending_factor():
    clock = new_clock()
    svc = service(clock)
    mine = await signed_in("mine@example.org", now=clock.now())
    theirs = await signed_in("theirs@example.org", now=clock.now())
    enrol = await svc.begin_enrolment(mine.user)
    with pytest.raises(HTTPException) as refused:
        await svc.confirm_enrolment(
            theirs.user, enrol.factor_id, code_now(secret_of(enrol), clock)
        )
    assert code_of(refused.value) == "invalid_code"
    assert not (await svc.status(theirs.user)).enabled


async def test_a_failure_part_way_through_confirming_leaves_nothing_enrolled(monkeypatch):
    from backend.app.repositories.postgres.user_totp import PostgresUserTotpRepository

    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    enrol = await svc.begin_enrolment(account.user)
    original = PostgresUserTotpRepository._upsert_statement
    calls = {"n": 0}

    def failing(self, values, row=None):
        calls["n"] += 1
        if calls["n"] == 5:  # the factor, then four of the ten codes
            raise RuntimeError("injected")
        return original(self, values, row)

    monkeypatch.setattr(PostgresUserTotpRepository, "_upsert_statement", failing)
    with pytest.raises(RuntimeError):
        await svc.confirm_enrolment(
            account.user, enrol.factor_id, code_now(secret_of(enrol), clock)
        )
    monkeypatch.undo()
    repo = container.user_totp_repo()
    assert await repo.confirmed(account.user.id) is None
    assert await repo.pending(account.user.id) is not None
    assert await repo.codes_left(account.user.id) == 0
    assert await container.workspace_audit_repo().many() == []
    session = await container.session_repo().get(account.user.sid)
    assert session.mfa_at is None


async def test_replacing_a_factor_needs_a_current_code_and_drops_the_old_codes():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    secret, old_codes = await _enrolled(svc, clock, account)
    with pytest.raises(HTTPException) as refused:
        await svc.begin_enrolment(account.user)
    assert code_of(refused.value) == "invalid_code"
    clock.advance(30)
    again = await svc.begin_enrolment(account.user, current_code=code_now(secret, clock))
    new_secret = secret_of(again)
    clock.advance(30)
    result = await svc.confirm_enrolment(
        account.user, again.factor_id, code_now(new_secret, clock)
    )
    assert len(result.recovery_codes) == 10
    # the old recovery codes are gone, the old secret no longer works
    assert await container.user_totp_repo().codes_left(account.user.id) == 10
    clock.advance(30)
    with pytest.raises(HTTPException):
        await svc.check_code(account.user, old_codes[0])
    with pytest.raises(HTTPException):
        await svc.check_code(account.user, code_now(secret, clock))


async def _enrolled(svc, clock, account):
    from tests.app.mfa.helpers import enrolled

    return await enrolled(svc, clock, account)
