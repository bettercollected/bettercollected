from dataclasses import replace

import pytest

from common.settings.registry import Registry, SettingSpec, Tier, ValueType
from common.settings.signing import MonotonicTracker, sign_manifest
from common.settings.snapshot import (
    FakeSnapshot,
    ServiceState,
    SettingsReader,
    Snapshot,
    VerifiedSettings,
    verify_snapshot,
)

from common.settings.keys import SectionKeys

from settings_support import MASTER, OTHER_MASTER, plain_row, secret_row

REGISTRY = Registry(
    [
        SettingSpec(
            "MAIL_SMTP_PORT", "mail", ("backend", "auth"), type=ValueType.INT
        ),
        SettingSpec(
            "MAIL_PASSWORD", "mail", ("backend", "auth"), is_secret=True,
            tier=Tier.T3,
        ),
    ]
)


def run(snapshot, keys, tracker=None, **kw):
    return verify_snapshot(snapshot.rows(), snapshot.manifest(), keys, tracker, **kw)


def reasons(result):
    return {(r.key, r.reason) for r in result.rejections}


@pytest.fixture
def snap(keys):
    return FakeSnapshot.build([plain_row(), secret_row(keys)], keys, revision=5)


def test_clean_snapshot_is_accepted(snap, keys):
    assert isinstance(snap, Snapshot)
    result = run(snap, keys, registry=REGISTRY, service="backend")
    assert set(result.accepted) == {"MAIL_SMTP_PORT", "MAIL_PASSWORD"}
    assert result.rejections == [] and result.revision == 5
    reader = VerifiedSettings(result)
    assert isinstance(reader, SettingsReader)
    assert reader.revision == 5 and reader.get("MAIL_SMTP_PORT").value == 587
    assert reader.get("NOPE") is None


def test_bad_signature(snap, keys):
    snap.row_list[0] = replace(snap.row_list[0], value=25)  # manifest still lists it
    # the manifest entry carries the old sig, so the row's sig still matches it:
    result = run(snap, keys)
    assert reasons(result) == {("MAIL_SMTP_PORT", "bad_signature")}
    assert "MAIL_PASSWORD" in result.accepted


def test_row_resigned_by_someone_without_the_key(snap, keys):
    snap.row_list[0] = snap.row_list[0].with_sig("0" * 64)
    assert reasons(run(snap, keys)) == {("MAIL_SMTP_PORT", "manifest_mismatch")}


def test_manifest_missing_key_and_mismatch(snap, keys):
    entries = dict(snap.signed_manifest.entries)
    del entries["MAIL_PASSWORD"]
    entries["MAIL_SMTP_PORT"] = (2, entries["MAIL_SMTP_PORT"][1])
    forged = replace(snap.signed_manifest, entries=entries)  # old signature
    snap.signed_manifest = forged
    assert all(r.reason == "manifest_mismatch" for r in run(snap, keys).rejections)

    signed = sign_manifest(5, entries, keys.signing_key())
    snap.signed_manifest = signed
    assert reasons(run(snap, keys)) == {
        ("MAIL_PASSWORD", "manifest_missing_key"),
        ("MAIL_SMTP_PORT", "manifest_mismatch"),
    }


def test_missing_or_forged_manifest_rejects_everything(snap, keys):
    snap.signed_manifest = None
    result = run(snap, keys)
    assert result.accepted == {} and result.revision == 0
    assert {r.reason for r in result.rejections} == {"manifest_mismatch"}


def test_version_rollback_per_row_and_per_revision(snap, keys):
    tracker = MonotonicTracker({"MAIL_SMTP_PORT": 9}, revision=2)
    result = run(snap, keys, tracker)
    assert reasons(result) == {("MAIL_SMTP_PORT", "version_rollback")}
    # an older manifest revision (a replayed backup) rejects every row
    tracker = MonotonicTracker(revision=6)
    result = run(snap, keys, tracker)
    assert result.accepted == {}
    assert {r.reason for r in result.rejections} == {"manifest_mismatch"}


def test_verification_does_not_change_the_tracker_until_committed(snap, keys):
    tracker = MonotonicTracker()
    result = run(snap, keys, tracker)
    assert tracker.versions == {} and tracker.revision == 0
    tracker.commit(result.accepted.values(), result.revision)
    assert tracker.versions["MAIL_SMTP_PORT"] == 3 and tracker.revision == 5
    assert run(snap, keys, tracker).rejections == []  # same snapshot again


def test_unknown_key_and_reader_not_allowed(keys):
    other = plain_row(key="NOT_REGISTERED")
    narrow = plain_row(readers=("auth",))
    snap = FakeSnapshot.build([other, narrow, secret_row(keys)], keys)
    result = run(snap, keys, registry=REGISTRY, service="backend")
    assert reasons(result) == {
        ("NOT_REGISTERED", "unknown_key"),
        ("MAIL_SMTP_PORT", "reader_not_allowed"),
    }
    assert set(result.accepted) == {"MAIL_PASSWORD"}


def test_registry_readers_are_authoritative(keys):
    wide = plain_row(readers=("backend", "auth", "google"))
    snap = FakeSnapshot.build([wide], keys)
    assert reasons(run(snap, keys, registry=REGISTRY, service="google")) == {
        ("MAIL_SMTP_PORT", "reader_not_allowed")
    }


def test_rotation_accepts_rows_signed_with_the_previous_key(keys):
    snap = FakeSnapshot.build([plain_row()], SectionKeys(MASTER, sections=[]))
    during = SectionKeys(OTHER_MASTER, sections=[], master_previous=MASTER)
    assert run(snap, during).rejections == []
    assert run(snap, SectionKeys(OTHER_MASTER, sections=[])).accepted == {}


def test_messages_and_reports_carry_no_values(snap, keys):
    snap.row_list[1] = replace(snap.row_list[1], blob="v2:w1-00000000:AAAA")
    snap.row_list[0] = replace(snap.row_list[0], value="needle-value")
    result = run(snap, keys)
    text = " ".join(r.message() for r in result.rejections) + repr(result.rejections)
    assert result.rejections and "needle" not in text and "AAAA" not in text
    state = ServiceState.from_verification(
        "backend", result, env_overrides=["B", "A", "A"], keyset_fp="abc"
    )
    assert state.env_overrides == ("A", "B")
    assert state.rejected_keys == ("MAIL_PASSWORD", "MAIL_SMTP_PORT")
    assert state.to_report() == {
        "service": "backend",
        "revision_applied": 5,
        "env_overrides": ["A", "B"],
        "rejected_keys": ["MAIL_PASSWORD", "MAIL_SMTP_PORT"],
        "restart_pending": False,
        "keyset_fp": "abc",
    }
