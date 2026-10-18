"""Signed run requests: frozen vectors, tampering, constant-time comparison."""

from __future__ import annotations

import base64
import hmac
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.admin.security.keys import derive_key
from backend.admin.tasks import signing

MASTER = base64.b64encode(bytes(range(48))).decode()
KEY_HEX = "459f2fea29eaf022b9682f0914c7384df2e7962f70ec63eb24397b7f5aa29ee9"
PARAMS = {"rounds": 3, "decline": False}
PARAMS_HASH = "6f7a6641d29a49c24d82a63bedd91953c1d90a4a0f287f864568ff2cac719e0e"
AT = datetime(2026, 10, 18, 12, 0, 0, 123456, tzinfo=timezone.utc)
FIELDS = dict(
    id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
    task="selftest",
    version=1,
    params_hash=PARAMS_HASH,
    dry_run=False,
    requested_by="ops@example.org",
    requested_at=AT,
    nonce="n" * 32,
    resumes_run_id=None,
)
SIG_HEX = "ddbfec54106bb62f311672d2ece099070daa1fc2c1acabe971288fc727a07738"
SIG_RESUME_DRY_HEX = "cb4532411eb3f05d4e68612fe67740af94768897c5feb7ca490a0a035a2029bf"
ENCODED_PREFIX = "626574746572636f6c6c65637465642f7461736b732f726571756573742f7631"


@pytest.fixture
def key():
    return derive_key("tasks", "request", 1, env={"SETTINGS_MASTER_KEY": MASTER})


def row(key=None, **override):
    fields = {**FIELDS, **override}
    sig = signing.sign(
        key or bytes.fromhex(KEY_HEX),
        **{k: v for k, v in fields.items()},
    )
    return {
        **fields,
        "params": PARAMS,
        "sig_version": 1,
        "request_sig": sig,
    }


def test_frozen_key_and_signature_vectors(key):
    assert key.hex() == KEY_HEX
    assert signing.params_hash(PARAMS) == PARAMS_HASH
    assert signing.encode(**FIELDS).hex().startswith(ENCODED_PREFIX)
    assert signing.sign(key, **FIELDS).hex() == SIG_HEX
    other = {**FIELDS, "dry_run": True, "resumes_run_id": uuid.UUID("00000000-0000-4000-8000-000000000002")}
    assert signing.sign(key, **other).hex() == SIG_RESUME_DRY_HEX


def test_params_hash_ignores_key_order_but_not_values():
    assert signing.params_hash({"a": 1, "b": 2}) == signing.params_hash({"b": 2, "a": 1})
    assert signing.params_hash({"a": 1}) != signing.params_hash({"a": 2})


def test_a_valid_row_verifies(key):
    assert signing.verify_request(row(key), key)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", uuid.UUID("00000000-0000-4000-8000-000000000009")),
        ("task", "selftest_slow"),
        ("version", 2),
        ("params_hash", "0" * 64),
        ("dry_run", True),
        ("requested_by", "intruder@example.org"),
        ("requested_at", AT + timedelta(microseconds=1)),
        ("nonce", "m" * 32),
        ("resumes_run_id", uuid.UUID("00000000-0000-4000-8000-000000000002")),
    ],
)
def test_changing_any_signed_field_fails_verification(key, field, value):
    good = row(key)
    assert signing.verify_request({**good, field: value}, key) is False


def test_changed_params_fail_even_with_a_matching_hash_column(key):
    good = row(key)
    assert signing.verify_request({**good, "params": {"rounds": 99, "decline": False}}, key) is False


def test_a_signature_from_another_key_or_version_fails(key):
    other = derive_key("tasks", "request", 2, env={"SETTINGS_MASTER_KEY": MASTER})
    assert signing.verify_request(row(other), key) is False
    audit_key = derive_key("admin", "audit", 1, env={"SETTINGS_MASTER_KEY": MASTER})
    assert signing.verify_request(row(audit_key), key) is False


def test_malformed_rows_are_not_verified_and_never_raise(key):
    good = row(key)
    for bad in (
        {},
        {**good, "request_sig": b"short"},
        {**good, "request_sig": None},
        {**good, "requested_at": "yesterday"},
        {**good, "params": None},
        {**good, "version": "x"},
    ):
        assert signing.verify_request(bad, key) is False


def test_naive_timestamps_are_refused():
    with pytest.raises(ValueError):
        signing.sign(b"k" * 32, **{**FIELDS, "requested_at": datetime(2026, 1, 1)})


def test_the_encoding_is_length_prefixed_so_fields_cannot_shift():
    a = signing.encode(**{**FIELDS, "task": "a", "requested_by": "bc"})
    b = signing.encode(**{**FIELDS, "task": "ab", "requested_by": "c"})
    assert a != b


def test_verification_compares_in_constant_time(key, monkeypatch):
    calls = []
    real = hmac.compare_digest

    def spy(a, b):
        calls.append(1)
        return real(a, b)

    monkeypatch.setattr(signing.hmac, "compare_digest", spy)
    assert signing.verify_request(row(key), key)
    assert calls


def test_create_signs_a_request_the_runner_accepts(monkeypatch):
    monkeypatch.setenv("SETTINGS_MASTER_KEY", MASTER)
    request = signing.RunRequest.create(
        task="selftest",
        version=1,
        params=PARAMS,
        dry_run=True,
        requested_by="ops@example.org",
        requested_at=AT,
    )
    stored = {
        "id": request.id,
        "task": request.task,
        "version": request.version,
        "params": request.params,
        "params_hash": request.params_hash,
        "dry_run": request.dry_run,
        "requested_by": request.requested_by,
        "requested_at": request.requested_at,
        "nonce": request.nonce,
        "request_sig": request.request_sig,
        "sig_version": request.sig_version,
        "resumes_run_id": None,
    }
    assert signing.verify_request(stored)
    again = signing.RunRequest.create(
        task="selftest", version=1, params=PARAMS, dry_run=True,
        requested_by="ops@example.org", requested_at=AT,
    )
    assert again.nonce != request.nonce and again.request_sig != request.request_sig
