from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from common.settings.canonical import (
    CanonicalError,
    canonical_json,
    canonical_manifest,
    canonical_row,
    format_timestamp,
)
from common.settings.crypto.keys import derive_from_master
from common.settings.signing import (
    MonotonicTracker,
    sign_manifest,
    sign_row,
    verify_manifest,
    verify_row,
)

from settings_support import MASTER_BYTES, MOMENT, plain_row

SIGN_KEY = derive_from_master(MASTER_BYTES, "settings", "sign")

# Frozen vectors: a change to any of these breaks every stored signature.
SIGN_KEY_HEX = "49feaf6a4a290c7e1076fbdfba8c8ab767a6cd4007f97a464a4aafa8ea6756a3"
ROW_CANONICAL_HEX = (
    "0000001262632d73657474696e67732d726f772d76310000000e4d41494c5f534d54505f504f"
    "5254000000046d61696c000000020000000461757468000000076261636b656e640000000130"
    "000000015200000001760000000335383700000000000000030000001b323032362d31302d31"
    "385431323a33303a30352e3132333435365a"
)
ROW_SIG = "b86594dac85c96dc1e503ca2da15c5447992da166e4fccde588d0c4978e1ae43"
SECRET_ROW_SIG = "c311e638b770d016a8c0487e635a23d527cf8d4d93cd819f4b26480e4ba39116"
MANIFEST_SIG = "a9fa711127866699abb6064cbad23782bcabe4eff0dd827dddfbac2ad4992726"


def secret(**changes):
    fields = dict(
        key="MAIL_PASSWORD",
        section="mail",
        readers=("auth", "backend"),
        is_secret=True,
        reload_class="R",
        version=1,
        updated_at=datetime(2026, 10, 18, 12, 30, 5, tzinfo=timezone.utc),
        value=None,
        blob="v2:w1-00000000:AAAA",
    )
    fields.update(changes)
    return plain_row(**fields)


def test_frozen_vectors():
    assert SIGN_KEY.hex() == SIGN_KEY_HEX
    assert canonical_row(plain_row()).hex() == ROW_CANONICAL_HEX
    assert sign_row(plain_row(), SIGN_KEY) == ROW_SIG
    assert sign_row(secret(), SIGN_KEY) == SECRET_ROW_SIG
    manifest = sign_manifest(7, {"A": (1, "aa"), "B": (2, "bb")}, SIGN_KEY)
    assert manifest.sig == MANIFEST_SIG


def test_verify_round_trip_and_wrong_key():
    row = plain_row()
    signed = row.with_sig(sign_row(row, SIGN_KEY))
    assert verify_row(signed, SIGN_KEY)
    assert not verify_row(signed, derive_from_master(MASTER_BYTES, "settings", "x"))
    assert not verify_row(row.with_sig(""), SIGN_KEY)
    assert not verify_row(row.with_sig("zz"), SIGN_KEY)


@pytest.mark.parametrize(
    "changes",
    [
        {"key": "MAIL_SMTP_SERVER"},  # key swap
        {"readers": ("backend", "auth", "google")},  # readers widened
        {"readers": ("backend",)},
        {"section": "ai"},
        {"is_secret": True, "value": None, "blob": "v2:w1-00000000:AAAA"},
        {"reload_class": "H"},
        {"value": 588},
        {"value": "587"},
        {"version": 2},  # rollback
        {"version": 4},
        {"updated_at": MOMENT + timedelta(microseconds=1)},
    ],
)
def test_every_signed_field_is_covered(changes):
    row = plain_row()
    signed = row.with_sig(sign_row(row, SIGN_KEY))
    assert not verify_row(replace(signed, **changes), SIGN_KEY)


def test_blob_swap_and_secret_flag_are_covered():
    signed = secret().with_sig(sign_row(secret(), SIGN_KEY))
    assert verify_row(signed, SIGN_KEY)
    assert not verify_row(replace(signed, blob="v2:w1-00000000:AAAB"), SIGN_KEY)


def test_reader_order_does_not_matter_but_membership_does():
    a = plain_row(readers=("backend", "auth"))
    b = plain_row(readers=("auth", "backend"))
    assert canonical_row(a) == canonical_row(b)


def test_length_prefix_prevents_field_boundary_games():
    a = plain_row(key="AB", section="c" + "d")
    b = plain_row(key="ABc", section="d")
    assert canonical_row(a) != canonical_row(b)


def test_timestamps_are_utc_and_fixed_precision():
    plus2 = timezone(timedelta(hours=2))
    assert format_timestamp(datetime(2026, 1, 2, 5, 4, 5, tzinfo=plus2)) == (
        "2026-01-02T03:04:05.000000Z"
    )
    assert canonical_row(plain_row(updated_at=MOMENT)) == canonical_row(
        plain_row(updated_at=MOMENT.astimezone(plus2))
    )
    with pytest.raises(CanonicalError):
        format_timestamp(datetime(2026, 1, 1))


def test_canonical_json_is_one_text_per_value():
    assert canonical_json({"b": [1, 2], "a": "é"}) == '{"a":"\\u00e9","b":[1,2]}'
    with pytest.raises(CanonicalError):
        canonical_json(float("nan"))
    with pytest.raises(CanonicalError):
        canonical_json(object())


def test_row_shape_rules():
    with pytest.raises(CanonicalError):
        canonical_row(plain_row(blob="v2:x"))  # plain row with a blob
    with pytest.raises(CanonicalError):
        canonical_row(secret(blob=None))
    with pytest.raises(CanonicalError):
        canonical_row(secret(value="x"))
    with pytest.raises(CanonicalError):
        canonical_row(plain_row(readers=("a", "a")))
    with pytest.raises(CanonicalError):
        canonical_row(plain_row(readers=()))
    assert not verify_row(plain_row(readers=()), SIGN_KEY)


def test_a_weak_signing_key_is_refused():
    with pytest.raises(ValueError):
        sign_row(plain_row(), b"short")


def test_manifest_tamper():
    entries = {"A": (1, "aa"), "B": (2, "bb")}
    manifest = sign_manifest(7, entries, SIGN_KEY)
    assert verify_manifest(manifest, SIGN_KEY)
    for changed in (
        replace(manifest, revision=6),
        replace(manifest, entries={"A": (1, "aa")}),  # key removed
        replace(manifest, entries={**entries, "C": (1, "cc")}),
        replace(manifest, entries={**entries, "B": (1, "bb")}),  # version rollback
        replace(manifest, entries={**entries, "B": (2, "bc")}),
        replace(manifest, sig=""),
    ):
        assert not verify_manifest(changed, SIGN_KEY)
    assert canonical_manifest(1, {"B": (1, "x"), "A": (1, "y")}) == canonical_manifest(
        1, {"A": (1, "y"), "B": (1, "x")}
    )
    with pytest.raises(CanonicalError):
        canonical_manifest(1, {"A:B": (1, "x")})


def test_row_and_manifest_domains_differ():
    # A manifest signature can never pass for a row and vice versa.
    row = plain_row()
    assert sign_row(row, SIGN_KEY) != sign_manifest(3, {}, SIGN_KEY).sig


def test_monotonic_tracker():
    tracker = MonotonicTracker()
    assert not tracker.is_rollback("A", 1)
    tracker.commit([plain_row(key="A", version=5)], revision=9)
    assert tracker.is_rollback("A", 4)
    assert not tracker.is_rollback("A", 5)
    assert not tracker.is_rollback("A", 6)
    assert tracker.revision_rolled_back(8) and not tracker.revision_rolled_back(9)
    tracker.commit([plain_row(key="A", version=2)], revision=3)  # never lowers
    assert tracker.versions["A"] == 5 and tracker.revision == 9


def test_repr_hides_the_value():
    assert "587" not in repr(plain_row())
