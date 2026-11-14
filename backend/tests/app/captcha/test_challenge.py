"""The challenge and its proof, pure (services/captcha/challenge.py): tampering,
expiry, binding, difficulty bounds, key rotation."""

import base64
import datetime as dt
import json

import pytest

from backend.app.services.captcha import challenge as ch
from backend.app.services.captcha.pressure import Pressure
from backend.app.services.captcha.service import CaptchaService
from backend.config import settings

NOW = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)
W, F = "64a1b2c3d4e5f60718293a4b", "64a1b2c3d4e5f60718293a4c"


def make(bits=14, client="203.0.113.7", now=NOW, **over):
    args = dict(
        purpose="submit", workspace_id=W, form_id=F, bits=bits, client=client, now=now
    )
    args.update(over)
    return ch.issue(**args)


def ok(text, **over):
    args = dict(
        purpose="submit", workspace_id=W, form_id=F, client="203.0.113.7", now=NOW
    )
    args.update(over)
    return ch.check(ch.proof(text, ch.solve(text)), **args)


def refused(header, **over):
    args = dict(
        purpose="submit", workspace_id=W, form_id=F, client="203.0.113.7", now=NOW
    )
    args.update(over)
    with pytest.raises(ch.Refused) as error:
        ch.check(header, **args)
    return error.value.code


def edit(text, **claims):
    payload, signature = text.split(".")
    data = json.loads(base64.urlsafe_b64decode(payload + "=="))
    data.update(claims)
    return ch._b64(json.dumps(data, separators=(",", ":")).encode()) + "." + signature


def test_a_solved_challenge_passes_and_states_what_it_binds():
    claims = ok(make())
    assert (claims.purpose, claims.workspace_id, claims.form_id, claims.bits) == (
        "submit",
        W,
        F,
        14,
    )
    assert claims.tag and len(claims.tag) == 16


def test_the_work_is_eight_subpuzzles_of_bits_minus_three():
    text = make(bits=14)
    counters = ch.solve(text)
    assert len(counters) == 8
    for index, counter in enumerate(counters):
        assert ch.leading_zero_bits(ch._hash(text, index, str(counter))) >= 11


def test_a_missing_proof_is_missing():
    assert refused(None) == ch.MISSING
    assert refused("") == ch.MISSING


@pytest.mark.parametrize(
    "header",
    ["x", "a.b", "a.b.c.d", "é.é.é", "A" * 2000, "a.b.1,2,3"],
)
def test_garbage_is_invalid(header):
    assert refused(header) == ch.INVALID


def test_a_changed_claim_breaks_the_signature():
    text = make()
    for claim in ({"b": 14, "w": "other"}, {"b": 12}, {"e": 9999999999999}, {"t": ""}):
        header = ch.proof(edit(text, **claim), ch.solve(text))
        assert refused(header) == ch.INVALID, claim


def test_a_changed_signature_or_counter_is_invalid():
    text = make()
    counters = ch.solve(text)
    payload, signature = text.split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    assert refused(ch.proof(f"{payload}.{flipped}", counters)) == ch.INVALID
    bad = list(counters)
    bad[3] += 1
    # almost surely not a solution too (one more than a solution has 1/2 chance per bit)
    header = ch.proof(text, bad)
    try:
        ch.check(
            header,
            purpose="submit",
            workspace_id=W,
            form_id=F,
            client="203.0.113.7",
            now=NOW,
        )
    except ch.Refused as error:
        assert error.code == ch.INVALID
    # counters that are not plain digits, or too many or few, never pass
    for counters_text in (
        "1,2,3",
        ",".join(["-1"] * 8),
        ",".join(["1e3"] * 8),
        ",".join(["9" * 20] * 8),
    ):
        assert refused(f"{text}.{counters_text}") == ch.INVALID


def test_another_challenges_counters_do_not_solve_this_one():
    one, two = make(), make()
    assert refused(ch.proof(two, ch.solve(one))) == ch.INVALID


def test_expiry_is_fifteen_minutes_with_a_minute_of_skew():
    text = make()
    ok(text, now=NOW + dt.timedelta(minutes=15, seconds=59))
    assert (
        refused(
            ch.proof(text, ch.solve(text)),
            now=NOW + dt.timedelta(minutes=16, seconds=1),
        )
        == ch.EXPIRED
    )
    assert ch.TTL == dt.timedelta(minutes=15)


def test_wrong_form_workspace_or_purpose_is_invalid():
    text = make()
    header = ch.proof(text, ch.solve(text))
    assert refused(header, form_id="64a1b2c3d4e5f60718293a4d") == ch.INVALID
    assert refused(header, workspace_id="64a1b2c3d4e5f60718293a4d") == ch.INVALID
    assert refused(header, purpose="mail") == ch.INVALID


def test_another_network_is_invalid_and_an_unknown_one_is_not_bound():
    text = make(client="203.0.113.7")
    header = ch.proof(text, ch.solve(text))
    assert refused(header, client="198.51.100.23") == ch.INVALID
    assert refused(header, client="") == ch.INVALID
    # issued to a client the server could not tell: no binding, any network
    unbound = make(client="")
    assert (
        ch.check(
            ch.proof(unbound, ch.solve(unbound)),
            purpose="submit",
            workspace_id=W,
            form_id=F,
            client="198.51.100.23",
            now=NOW,
        ).tag
        == ""
    )


def test_the_tag_salt_changes_every_utc_day_and_a_challenge_near_midnight_verifies():
    key = ch._keys()[0]
    day = ch.day_number(NOW)
    assert ch.ip_tag(key, day, "203.0.113.7") != ch.ip_tag(key, day + 1, "203.0.113.7")
    assert ch.ip_tag(key, day, "") == ""
    late = dt.datetime(2026, 11, 12, 23, 59, tzinfo=dt.timezone.utc)
    text = make(now=late)
    ok(text, now=late + dt.timedelta(minutes=5))  # verified on the next UTC day


def test_difficulty_outside_the_bounds_is_never_accepted():
    for bits in (13, 21, 22, 40):
        text = make(bits=bits)
        # signed by us, but a server never issues it: refused whatever the work
        header = f"{text}.{','.join(['0'] * 8)}"
        assert refused(header) == ch.INVALID


def test_a_challenge_survives_a_key_rotation(monkeypatch):
    current = settings.auth_settings.JWT_SECRET
    text = make()
    header = ch.proof(text, ch.solve(text))
    new = "n" * 64
    monkeypatch.setattr(settings.auth_settings, "JWT_SECRET", f"{new},{current}")
    ch.check(
        header,
        purpose="submit",
        workspace_id=W,
        form_id=F,
        client="203.0.113.7",
        now=NOW,
    )
    # a ring that no longer holds the old key rejects it
    monkeypatch.setattr(settings.auth_settings, "JWT_SECRET", new)
    assert refused(header) == ch.INVALID


def test_a_server_without_a_secret_issues_nothing_and_accepts_nothing(monkeypatch):
    text = make()
    header = ch.proof(text, ch.solve(text))
    monkeypatch.setattr(settings.auth_settings, "JWT_SECRET", "")
    assert make() is None
    assert refused(header) == ch.INVALID


# ------------------------------------------------------------------ difficulty


def service(**kw):
    return CaptchaService(rate_limiter=None, pressure=Pressure(), **kw)


def test_the_base_is_seventeen_and_signed_in_pays_three_less(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 17)
    s = service()
    assert s.difficulty("203.0.113.7", F, False) == 17
    assert s.difficulty("203.0.113.8", F, True) == 14


def test_signed_in_never_goes_below_fourteen(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 14)
    assert service().difficulty("203.0.113.7", F, True) == 14


def test_pressure_adds_bits_and_the_total_stops_at_the_ceiling(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 17)
    s = service()
    client = "203.0.113.7"
    seen = [s.difficulty(client, F, False) for _ in range(300)]
    assert seen[:30] == [17] * 30  # an office or a school behind one address is free
    assert seen[30] == 18 and max(seen) == 19  # +1 per doubling, at most +2
    for _ in range(3):
        s.pressure.failed(client)
    assert s.difficulty(client, F, False) == 20  # 2 for issues and 2 for failures
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_DIFFICULTY_BOOST", 4)
    for _ in range(300):
        s.pressure.submitted(F)
    assert s.difficulty(client, F, False) == 20
    assert ch.MAX_BITS == 20 and ch.MIN_BITS == 14


def test_issue_pressure_starts_after_thirty_and_doubles_from_there(monkeypatch):
    from backend.app.services.captcha import service as svc

    assert (svc.FREE_ISSUES, svc.MAX_ISSUE_PRESSURE) == (30, 2)
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 17)
    s = service()
    client = "203.0.113.7"
    seen = [s.difficulty(client, F, False) for _ in range(61)]
    assert seen[:30] == [17] * 30  # the 30th challenge is still free
    assert seen[30] == 18  # the 31st is the first with pressure
    assert seen[59] == 18  # up to 60 (one doubling) it stays at +1
    assert seen[60] == 19  # the 61st is past the second doubling


def test_issue_pressure_never_adds_more_than_two_bits(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 14)
    s = service()
    client = "203.0.113.7"
    # far past every doubling the kept stamps can count: 500 challenges
    seen = [s.difficulty(client, F, False) for _ in range(500)]
    assert max(seen) == 16 and seen[-1] == 16
    # failures and the form's rate are separate and unchanged; all together stop at +4
    for _ in range(3):
        s.pressure.failed(client)
    for _ in range(300):
        s.pressure.submitted(F)
    assert s.difficulty(client, F, False) == 18


def test_a_busy_form_and_the_operator_boost_raise_it(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 17)
    s = service()
    for _ in range(31):
        s.pressure.submitted(F)
    assert s.difficulty("203.0.113.1", F, False) == 18
    for _ in range(100):
        s.pressure.submitted(F)
    assert s.difficulty("203.0.113.2", F, False) == 19
    assert s.difficulty("203.0.113.3", "another-form", False) == 17
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_DIFFICULTY_BOOST", 1)
    assert s.difficulty("203.0.113.4", "another-form", False) == 18


def test_an_unknown_client_is_not_counted_for_pressure(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 17)
    s = service()
    assert {s.difficulty("", F, False) for _ in range(50)} == {17}
    assert not s.pressure._issued._keys


def test_the_pressure_memory_is_bounded(monkeypatch):
    from backend.app.services.captcha import pressure

    monkeypatch.setattr(pressure, "MAX_KEYS", 50)
    p = Pressure()
    for n in range(500):
        p.issued(f"client-{n}")
    assert len(p._issued._keys) == 50


def test_the_pressure_stamps_stay_bounded_for_one_busy_client():
    from backend.app.services.captcha import pressure
    from backend.app.services.captcha.service import CHALLENGES_PER_MINUTE

    now = [1_000.0]
    p = Pressure(clock=lambda: now[0])
    assert pressure.MAX_STAMPS == 512
    # a client at the route's limit (300 a minute) for two hours
    for _ in range(2 * 60):
        for _ in range(CHALLENGES_PER_MINUTE):
            p.issued("203.0.113.7")
        now[0] += 60
    stamps = p._issued._keys["203.0.113.7"]
    assert len(stamps) <= pressure.MAX_STAMPS
    # nothing older than the longest window survives the next add
    assert min(stamps) > now[0] - pressure.WINDOW - 60


def test_the_challenge_limit_can_be_reached_and_refuses_the_next_one():
    from backend.app.services.captcha import pressure
    from backend.app.services.captcha.service import CHALLENGES_PER_MINUTE

    # the kept stamps must hold a whole minute at the limit, or the count
    # would stop short of it and nothing would ever be refused
    assert CHALLENGES_PER_MINUTE == 300
    assert pressure.MAX_STAMPS > CHALLENGES_PER_MINUTE
    now = [1_000.0]
    p = Pressure(clock=lambda: now[0])
    for n in range(CHALLENGES_PER_MINUTE):
        assert p.ask("203.0.113.7", "submit", CHALLENGES_PER_MINUTE) == (True, 0), n
        now[0] += 0.1  # 300 within 30 seconds
    allowed, wait = p.ask("203.0.113.7", "submit", CHALLENGES_PER_MINUTE)  # the 301st
    assert allowed is False and wait >= 1
    # per client and per purpose
    assert p.ask("198.51.100.23", "submit", CHALLENGES_PER_MINUTE) == (True, 0)
    assert p.ask("203.0.113.7", "mail", CHALLENGES_PER_MINUTE) == (True, 0)
    # a refused request is not counted, and the minute lets the client in again
    now[0] += 61
    assert p.ask("203.0.113.7", "submit", CHALLENGES_PER_MINUTE) == (True, 0)


def test_stamps_older_than_the_window_are_dropped_when_the_key_is_added_to():
    from backend.app.services.captcha import pressure

    now = [0.0]
    p = Pressure(clock=lambda: now[0])
    for _ in range(100):
        p.issued("c")
    now[0] += pressure.WINDOW + 1
    p.issued("c")
    assert len(p._issued._keys["c"]) == 1


def test_idle_keys_do_not_pile_up_when_others_are_added():
    from backend.app.services.captcha import pressure

    now = [0.0]
    p = Pressure(clock=lambda: now[0])
    for n in range(1000):
        p.issued(f"client-{n}")
    now[0] += pressure.WINDOW + 1
    p.issued("fresh")
    assert list(p._issued._keys) == ["fresh"]


def test_a_discounted_challenge_says_so_and_a_full_price_one_does_not():
    plain = make()
    assert "s" not in ch.unverified_claims(plain) and not ok(plain).discounted
    discounted = make(discounted=True)
    assert ch.unverified_claims(discounted)["s"] == 1 and ok(discounted).discounted


def test_the_discount_flag_cannot_be_dropped_or_added_without_the_key():
    discounted = make(discounted=True)
    assert refused(ch.proof(edit(discounted, s=0), [0] * 8)) == ch.INVALID
    assert refused(ch.proof(edit(make(), s=1), [0] * 8)) == ch.INVALID


def test_the_discount_is_only_for_a_signed_in_difficulty(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 17)
    s = service()
    assert s._difficulty("203.0.113.7", F, True) == (14, True)
    assert s._difficulty("203.0.113.8", F, False) == (17, False)
    # at the floor nothing was taken off, so nothing is flagged
    monkeypatch.setattr(settings.api_settings, "CAPTCHA_BASE_BITS_SUBMIT", 14)
    assert s._difficulty("203.0.113.9", F, True) == (14, False)
