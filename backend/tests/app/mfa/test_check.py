"""Presenting the second factor: replay, recovery codes, limits, lock."""

import asyncio
import time

import pytest
from common.security.clock import FakeClock

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_audit_event import (
    TOTP_LOCKED,
    TOTP_RECOVERY_USED,
)
from backend.app.services.mfa import service as mfa
from backend.config import settings
from tests.app.mfa.helpers import (
    code_now,
    enrolled,
    new_clock,
    service,
    signed_in,
)

pytestmark = pytest.mark.usefixtures("totp_on")


def code_of(error: HTTPException) -> str:
    return error.content["code"]


async def refusal(coro) -> HTTPException:
    with pytest.raises(HTTPException) as refused:
        await coro
    return refused.value


async def setup():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    secret, codes = await enrolled(svc, clock, account)
    clock.advance(30)  # the enrolment used this step
    return clock, svc, account, secret, codes


def wrong_code(secret, clock):
    near = {code_now(secret, clock, o) for o in (-1, 0, 1)}
    return next(f"{n:06d}" for n in range(10**6) if f"{n:06d}" not in near)


async def test_a_right_code_is_accepted_once_and_a_replay_is_refused():
    clock, svc, account, secret, _ = await setup()
    code = code_now(secret, clock)
    assert (await svc.check_code(account.user, code)).method == "totp"
    again = await refusal(svc.check_code(account.user, code))
    assert again.status_code == 422 and code_of(again) == "invalid_code"
    # the code before it (still inside the window) is a replay too
    older = await refusal(svc.check_code(account.user, code_now(secret, clock, -1)))
    assert code_of(older) == "invalid_code"
    clock.advance(30)
    assert (await svc.check_code(account.user, code_now(secret, clock))).method == "totp"


async def test_a_code_with_spaces_is_accepted_and_garbage_never_raises():
    clock, svc, account, secret, _ = await setup()
    # each wrong one uses a slot of the five; the rest of the garbage is
    # covered by the shared verify() tests
    garbage = [None, "1" * 500, "０１２３４５", "\x00" * 6]
    for bad in garbage:
        assert code_of(await refusal(svc.check_code(account.user, bad))) == "invalid_code"
    spaced = code_now(secret, clock)
    assert (await svc.check_code(account.user, f"{spaced[:3]} {spaced[3:]}")).method == "totp"


async def test_the_same_code_in_parallel_works_once():
    clock, svc, account, secret, _ = await setup()
    code = code_now(secret, clock)
    results = await asyncio.gather(
        *(svc.check_code(account.user, code) for _ in range(3)), return_exceptions=True
    )
    accepted = [r for r in results if not isinstance(r, Exception)]
    assert len(accepted) == 1
    assert all(code_of(r) == "invalid_code" for r in results if isinstance(r, Exception))


async def test_a_recovery_code_works_once_and_is_audited():
    clock, svc, account, _, codes = await setup()
    verified = await svc.check_code(account.user, codes[0].lower().replace("-", " "))
    assert verified.method == "recovery" and verified.recovery_left == 9
    again = await refusal(svc.check_code(account.user, codes[0]))
    assert code_of(again) == "invalid_code"
    events = [e.event for e in await container.workspace_audit_repo().many()]
    assert TOTP_RECOVERY_USED in events
    assert codes[0] not in repr(await container.workspace_audit_repo().many())
    assert (await svc.status(account.user)).recovery_left == 9


async def test_the_same_recovery_code_in_parallel_works_once():
    clock, svc, account, _, codes = await setup()
    results = await asyncio.gather(
        *(svc.check_code(account.user, codes[3]) for _ in range(3)),
        return_exceptions=True,
    )
    assert len([r for r in results if not isinstance(r, Exception)]) == 1
    assert (await svc.status(account.user)).recovery_left == 9


async def test_a_recovery_code_of_another_account_is_refused():
    clock, svc, mine, _, my_codes = await setup()
    theirs = await signed_in("other@example.org", now=clock.now())
    await enrolled(svc, clock, theirs)
    clock.advance(30)
    refused = await refusal(svc.check_code(theirs.user, my_codes[0]))
    assert code_of(refused) == "invalid_code"
    # mine is still unused
    assert (await svc.status(mine.user)).recovery_left == 10


async def test_five_wrong_codes_lock_the_step_even_for_a_right_code():
    clock, svc, account, secret, _ = await setup()
    bad = wrong_code(secret, clock)
    for _ in range(5):
        assert code_of(await refusal(svc.check_code(account.user, bad))) == "invalid_code"
    locked = await refusal(svc.check_code(account.user, code_now(secret, clock)))
    assert locked.status_code == 429 and code_of(locked) == "mfa_locked"
    assert locked.content["retry_after"] > 0 and locked.headers["Retry-After"]
    events = [e.event for e in await container.workspace_audit_repo().many()]
    assert events.count(TOTP_LOCKED) == 1
    clock.advance(16 * 60)
    assert (await svc.check_code(account.user, code_now(secret, clock))).method == "totp"


async def test_a_correct_code_gives_its_slot_back():
    clock, svc, account, secret, _ = await setup()
    bad = wrong_code(secret, clock)
    for _ in range(4):
        await refusal(svc.check_code(account.user, bad))
    # four wrong ones and then right ones: right ones do not count
    assert (await svc.check_code(account.user, code_now(secret, clock))).method == "totp"
    clock.advance(30)
    assert (await svc.check_code(account.user, code_now(secret, clock))).method == "totp"


async def test_twenty_parallel_wrong_guesses_evaluate_at_most_five(monkeypatch):
    clock, svc, account, secret, _ = await setup()
    evaluated = {"n": 0}
    real = mfa.verify

    def counting(*args, **kwargs):
        evaluated["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(mfa, "verify", counting)
    bad = wrong_code(secret, clock)
    results = await asyncio.gather(
        *(svc.check_code(account.user, bad) for _ in range(20)), return_exceptions=True
    )
    assert evaluated["n"] <= 5
    codes = {code_of(r) for r in results}
    assert codes <= {"invalid_code", "too_many_attempts", "mfa_locked"}
    assert all(isinstance(r, HTTPException) for r in results)


async def test_a_client_address_with_too_many_wrong_codes_is_refused():
    # start on a window edge: the test moves the clock by minutes and the
    # address budget is a fixed 10-minute window
    clock = FakeClock(time.time() // 600 * 600)
    svc = service(clock)
    address = "203.0.113.9"
    for n in range(4):  # four accounts, five wrong codes each: twenty from one address
        account = await signed_in(f"user{n}@example.org", now=clock.now())
        secret, _ = await enrolled(svc, clock, account)
        clock.advance(30)
        bad = wrong_code(secret, clock)
        for _ in range(5):
            await refusal(svc.check_code(account.user, bad, address))
    fresh = await signed_in("fresh@example.org", now=clock.now())
    secret, _ = await enrolled(svc, clock, fresh)
    clock.advance(30)
    blocked = await refusal(
        svc.check_code(fresh.user, code_now(secret, clock), address)
    )
    assert blocked.status_code == 429 and code_of(blocked) == "too_many_attempts"
    # another address is not affected
    assert (
        await svc.check_code(fresh.user, code_now(secret, clock), "203.0.113.10")
    ).method == "totp"


async def test_no_factor_is_a_conflict():
    clock = new_clock()
    svc = service(clock)
    account = await signed_in(now=clock.now())
    refused = await refusal(svc.check_code(account.user, "123456"))
    assert refused.status_code == 409 and code_of(refused) == "no_factor"


async def test_step_up_marks_the_session():
    clock, svc, account, secret, codes = await setup()
    session = await container.session_repo().get(account.user.sid)
    assert session.mfa_method == "totp"
    other = await signed_in("same@example.org", now=clock.now())
    # a session that signed in before enrolling gets promoted in place
    mine = account.user.model_copy(update={"sid": other.user.sid})
    await container.session_repo().save(
        (await container.session_repo().get(other.user.sid)).model_copy(
            update={"user_id": account.user.id}
        )
    )
    await svc.step_up(mine, codes[1])
    promoted = await container.session_repo().get(other.user.sid)
    assert promoted.mfa_at is not None and promoted.mfa_method == "recovery"


async def test_everything_is_inert_while_the_switch_is_off(monkeypatch):
    clock, svc, account, secret, _ = await setup()
    monkeypatch.setattr(settings.totp, "ENABLED", False)
    for call in (
        svc.check_code(account.user, code_now(secret, clock)),
        svc.begin_enrolment(account.user),
        svc.confirm_enrolment(account.user, "x", "123456"),
    ):
        refused = await refusal(call)
        assert refused.status_code == 422 and code_of(refused) == "totp_off"
    assert (await svc.status(account.user)).available is False
    # what is stored stays
    assert await container.user_totp_repo().confirmed(account.user.id) is not None


async def test_regenerating_codes_needs_a_code_and_kills_the_old_ones():
    clock, svc, account, secret, codes = await setup()
    refused = await refusal(svc.regenerate_recovery_codes(account.user, None))
    assert code_of(refused) == "invalid_code"
    fresh = await svc.regenerate_recovery_codes(account.user, codes[0])
    assert len(fresh.recovery_codes) == 10
    assert not set(fresh.recovery_codes) & set(codes)
    assert code_of(await refusal(svc.check_code(account.user, codes[1]))) == "invalid_code"
    assert (await svc.check_code(account.user, fresh.recovery_codes[0])).method == "recovery"


async def test_turning_it_off_needs_a_code_and_ends_the_other_sessions():
    clock, svc, account, secret, codes = await setup()
    other = await signed_in("x@example.org", now=clock.now())
    await container.session_repo().save(
        (await container.session_repo().get(other.user.sid)).model_copy(
            update={"user_id": account.user.id}
        )
    )
    refused = await refusal(svc.disable(account.user, "000000"))
    assert code_of(refused) == "invalid_code"
    status = await svc.disable(account.user, code_now(secret, clock))
    assert status.enabled is False
    repo = container.user_totp_repo()
    assert await repo.confirmed(account.user.id) is None
    assert await repo.codes_left(account.user.id) == 0
    mine = await container.session_repo().get(account.user.sid)
    elsewhere = await container.session_repo().get(other.user.sid)
    assert mine.revoked_at is None
    assert elsewhere.revoked_at is not None and elsewhere.revoke_reason == "mfa_reset"


async def test_deleting_the_account_removes_the_factor_and_codes():
    clock, svc, account, _, _ = await setup()
    other = await signed_in("keep@example.org", now=clock.now())
    await enrolled(svc, clock, other)
    assert await svc.delete_for_account(account.user.id) == 1
    repo = container.user_totp_repo()
    assert await repo.confirmed(account.user.id) is None
    assert await repo.codes_left(account.user.id) == 0
    assert await repo.confirmed(other.user.id) is not None
    assert await repo.codes_left(other.user.id) == 10


async def lock_out(svc, account, secret, clock):
    bad = wrong_code(secret, clock)
    for _ in range(5):
        await refusal(svc.check_code(account.user, bad))
    locked = await refusal(svc.check_code(account.user, code_now(secret, clock)))
    assert code_of(locked) == "mfa_locked"
    return locked.content["retry_after"]


async def test_each_lock_before_an_accepted_code_lasts_longer_and_a_code_starts_over(notices):
    clock = new_clock()
    svc = service(clock, notifier=container.mfa_notifier())
    account = await signed_in("esc@example.org", now=clock.now())
    secret, _ = await enrolled(svc, clock, account)
    clock.advance(30)
    waits = []
    for expected in (15, 60, 360, 1440, 1440):
        retry = await lock_out(svc, account, secret, clock)
        waits.append(round(retry / 60))
        assert abs(retry - expected * 60) <= 5
        clock.advance(expected * 60 + 60)
    assert waits == [15, 60, 360, 1440, 1440]
    # a code accepted after the lock ran out begins again from the shortest
    assert (await svc.check_code(account.user, code_now(secret, clock))).method == "totp"
    clock.advance(30)
    assert abs(await lock_out(svc, account, secret, clock) - 15 * 60) <= 5
    await container.mfa_notifier().flush()
    assert [n["minutes"] for n in notices if n["kind"] == "locked"] == [15, 60, 360, 1440, 1440, 15]
