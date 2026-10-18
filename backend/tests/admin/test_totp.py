import base64
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.admin.security import totp
from backend.admin.security.clock import FakeClock

RFC_KEY = b"12345678901234567890"
RFC_SECRET = base64.b32encode(RFC_KEY).decode()
# RFC 6238 appendix B, SHA-1 (8 digits)
VECTORS = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


@pytest.mark.parametrize("when,expected", VECTORS)
def test_rfc6238_vectors_eight_digits(when, expected):
    assert totp.hotp(RFC_KEY, totp.step_for(when), digits=8) == expected


@pytest.mark.parametrize("when,expected", VECTORS)
def test_six_digit_code_is_the_tail(when, expected):
    assert totp.code_at(RFC_SECRET, when) == expected[-6:]


def test_rfc4226_vectors():
    expected = ["755224", "287082", "359152", "969429", "338314", "254676"]
    assert [totp.hotp(RFC_KEY, i) for i in range(6)] == expected


def test_generated_secret_shape_and_uniqueness():
    secret = totp.generate_secret()
    assert len(secret) == 32 and "=" not in secret
    assert len(totp.decode_secret(secret)) == 20
    assert totp.generate_secret() != secret


def test_decode_secret_tolerates_case_spaces_padding():
    assert totp.decode_secret(RFC_SECRET.lower()) == RFC_KEY
    spaced = " ".join(RFC_SECRET[i : i + 4] for i in range(0, len(RFC_SECRET), 4))
    assert totp.decode_secret(spaced) == RFC_KEY
    for bad in ("", "   ", "!!!!", "1890"):
        with pytest.raises(ValueError):
            totp.decode_secret(bad)


def test_verify_returns_matched_step_within_drift():
    clock = FakeClock(1111111109)
    step = totp.step_for(clock.time())
    for offset in (-1, 0, 1):
        code = totp.hotp(RFC_KEY, step + offset)
        assert totp.verify(RFC_SECRET, code, clock) == step + offset


def test_verify_rejects_outside_drift():
    clock = FakeClock(1111111109)
    step = totp.step_for(clock.time())
    near = {totp.hotp(RFC_KEY, step + o) for o in (-1, 0, 1)}
    for offset in (2, -2, 10):
        code = totp.hotp(RFC_KEY, step + offset)
        if code not in near:
            assert totp.verify(RFC_SECRET, code, clock) is None


def test_wrong_code_is_rejected():
    clock = FakeClock(1111111109)
    step = totp.step_for(clock.time())
    near = {totp.hotp(RFC_KEY, step + o) for o in (-1, 0, 1)}
    wrong = next(f"{n:06d}" for n in range(10**6) if f"{n:06d}" not in near)
    assert totp.verify(RFC_SECRET, wrong, clock) is None


def test_time_moving_changes_acceptance_without_sleeping():
    clock = FakeClock(59)
    code = totp.current_code(RFC_SECRET, clock)
    assert totp.verify(RFC_SECRET, code, clock) is not None
    clock.advance(90)  # three steps later: out of the window
    assert totp.verify(RFC_SECRET, code, clock) is None


@pytest.mark.parametrize(
    "garbage",
    [
        "",
        "12345",
        "1234567",
        "abcdef",
        "１２３４５６",
        "12 34",
        None,
        123456,
        "12345\x00",
        "9" * 500,
    ],
)
def test_verify_never_raises_on_garbage(garbage):
    clock = FakeClock(59)
    result = totp.verify(RFC_SECRET, garbage, clock)
    assert result is None or isinstance(result, int)


def test_verify_accepts_spaced_code_and_bad_secret_is_none():
    clock = FakeClock(59)
    code = totp.current_code(RFC_SECRET, clock)
    assert totp.verify(RFC_SECRET, f"{code[:3]} {code[3:]}", clock) == 1
    assert totp.verify("not base32!", code, clock) is None


def test_early_epoch_does_not_use_negative_steps():
    clock = FakeClock(5)
    assert totp.verify(RFC_SECRET, totp.hotp(RFC_KEY, 0), clock) == 0


def test_replay_guard():
    assert totp.next_last_used_step(None, 10) == 10
    assert totp.next_last_used_step(9, 10) == 10
    assert totp.next_last_used_step(10, 10) is None
    assert totp.next_last_used_step(11, 10) is None
    assert totp.next_last_used_step(0, 0) is None


def test_otpauth_uri_escaping():
    uri = totp.otpauth_uri("ABCD", "ann+x@example.org", "Better Collected & Co")
    parts = urlsplit(uri)
    assert parts.scheme == "otpauth" and parts.netloc == "totp"
    assert parts.path == "/Better%20Collected%20%26%20Co:ann%2Bx%40example.org"
    query = parse_qs(parts.query)
    assert query["secret"] == ["ABCD"]
    assert query["issuer"] == ["Better Collected & Co"]
    assert query["algorithm"] == ["SHA1"]
    assert query["digits"] == ["6"] and query["period"] == ["30"]
    assert " " not in uri and "&Co" not in uri


def test_otpauth_label_cannot_be_split_by_a_colon_in_the_issuer():
    uri = totp.otpauth_uri("ABCD", "a@b.c", "x:y")
    assert urlsplit(uri).path == "/x%3Ay:a%40b.c"
