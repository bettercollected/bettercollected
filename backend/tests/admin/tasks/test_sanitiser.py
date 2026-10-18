"""The event sanitiser: contract, caps, and a fuzz with planted secrets."""

from __future__ import annotations

import base64
import enum
import json
import random
import string
import uuid

import pytest

from backend.admin.tasks.sanitiser import (
    MAX_EVENT_BYTES,
    EventRejected,
    EventSink,
    exception_class_name,
    scrub,
)


class Codes(str, enum.Enum):
    step = "step"
    other = "other"


def sink(**kw):
    return EventSink(Codes, **kw)


def test_only_declared_codes_pass():
    s = sink()
    assert s.build(Codes.step).code == "step"
    assert s.build("other").code == "other"
    for bad in ("undeclared", "", None, 5, "STEP"):
        with pytest.raises(EventRejected):
            s.build(bad)


def test_counters_are_small_named_integers():
    s = sink()
    assert s.build("step", {"done": 3}).counts == {"done": 3}
    for bad in (
        {"done": "3"},
        {"done": 1.5},
        {"done": True},
        {"Bad Name": 1},
        {"x": 2**60},
        {f"c{i}": i for i in range(17)},
    ):
        with pytest.raises(EventRejected):
            s.build("step", bad)


def test_ids_are_capped_and_pattern_checked():
    s = sink()
    assert len(s.build("step", ids=[f"f{i}" for i in range(20)]).ids) == 20
    with pytest.raises(EventRejected):
        s.build("step", ids=[f"f{i}" for i in range(21)])
    for bad in ("has space", "a/b", "x" * 65, "", "-leading", "user@example.org", 5, None):
        with pytest.raises(EventRejected):
            s.build("step", ids=[bad])


def test_uuids_and_object_ids_survive_in_ids_only():
    s = sink()
    u = str(uuid.uuid4())
    oid = "507f1f77bcf86cd799439011"
    assert s.build("step", ids=[u, oid]).ids == [u, oid]
    assert scrub(oid) != oid  # redacted outside ids
    assert scrub("5" * 25, allow_object_id=True) != "5" * 25  # longer runs never pass


def test_exceptions_record_the_class_name_only():
    assert exception_class_name(ValueError("password=hunter2")) == "ValueError"

    class Weird(Exception):
        pass

    Weird.__name__ = "not a name!"
    assert exception_class_name(Weird("x")) == "Exception"


def test_the_event_count_cap_ends_with_one_truncated_marker():
    s = sink(max_events=10)
    out = [s.build("step", {"n": i}) for i in range(30)]
    kept = [e for e in out if e is not None]
    assert len(kept) == 10
    assert [e.code for e in kept].count("truncated") == 1
    assert kept[-1].code == "truncated"
    assert s.truncated and s.dropped == 21
    assert [e.seq for e in kept] == list(range(1, 11))


def test_the_byte_cap_also_truncates():
    s = sink(max_bytes=300)
    kept = [e for e in (s.build("step", ids=[f"id{i}" for i in range(20)]) for _ in range(50)) if e]
    assert kept[-1].code == "truncated"
    assert sum(e.size() for e in kept[:-1]) <= 300


def test_an_oversized_id_list_is_shortened_to_fit_the_row():
    s = sink()
    event = s.build("step", {f"c{i}": 2**50 for i in range(16)}, ids=["a" * 64] * 20)
    assert event.size() <= MAX_EVENT_BYTES


def _planted():
    # deterministic: pytest-xdist workers must collect identical test ids
    rng = random.Random(7)

    def hexs(n):
        return rng.randbytes(n).hex()

    def raw(n):
        return rng.randbytes(n)

    out = [
        hexs(16),
        hexs(32),
        base64.b64encode(raw(32)).decode(),
        base64.urlsafe_b64encode(raw(33)).decode().rstrip("="),
        "Bearer abcdefghijklmnopqrstuvwx1234",
        "sk-" + base64.urlsafe_b64encode(raw(30)).decode().rstrip("="),
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghijklmnop",
        "password-hunter2",
        "api_key_value",
        "my-secret-thing",
        "Fernet-gAAAAAB" + base64.urlsafe_b64encode(raw(30)).decode().rstrip("="),
    ]
    for _ in range(200):
        out.append("".join(rng.choice(string.hexdigits) for _ in range(rng.randint(24, 80))))
    return out


@pytest.mark.parametrize("secret", _planted())
def test_planted_secrets_never_reach_a_stored_event(secret):
    s = sink()
    for payload in (
        {"ids": [secret]},
        {"counts": {secret: 1}},
    ):
        try:
            event = s.build("step", **payload)
        except EventRejected:
            continue  # rejected outright is fine
        stored = json.dumps([event.code, event.counts, event.ids])
        assert secret not in stored
    assert secret not in scrub(f"prefix {secret} suffix")


def test_scrub_leaves_ordinary_words_and_short_values_alone():
    for fine in ("form_17", "batch_done", "responses", "a1b2c3", str(uuid.uuid4()), "snake_case_word_without_digits_at_all"):
        assert scrub(fine) == fine
    assert scrub("x" * 3 + "deadbeef" * 4) != "x" * 3 + "deadbeef" * 4


def test_the_audit_mask_words_redact_the_whole_value():
    for risky in ("token_9", "my_password", "api-key-1", "otp_x"):
        assert scrub(risky) == "[redacted]"
