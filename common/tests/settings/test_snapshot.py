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
    entries["MAIL_SMTP_PORT"] = (2,) + entries["MAIL_SMTP_PORT"][1:]
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
    # a row naming more readers than the registry allows is refused outright
    assert reasons(run(snap, keys, registry=REGISTRY, service="backend")) == {
        ("MAIL_SMTP_PORT", "spec_mismatch")
    }
    narrow = FakeSnapshot.build([plain_row(readers=("backend",))], keys)
    assert reasons(run(narrow, keys, registry=REGISTRY, service="auth")) == {
        ("MAIL_SMTP_PORT", "reader_not_allowed")
    }


def test_rotation_accepts_rows_signed_with_the_previous_key(keys):
    snap = FakeSnapshot.build([plain_row()], SectionKeys(MASTER, sections=["mail"]))
    during = SectionKeys(OTHER_MASTER, sections=["mail"], master_previous=MASTER)
    assert run(snap, during).rejections == []
    assert run(snap, SectionKeys(OTHER_MASTER, sections=["mail"])).accepted == {}


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


def retention_row(value, version=1, **changes):
    return plain_row(
        key="API_FLOW_EVENTS_RETENTION_DAYS",
        section="retention",
        readers=("backend",),
        version=version,
        value=value,
        **changes,
    )


RETENTION_REGISTRY = Registry(
    [
        SettingSpec(
            "API_FLOW_EVENTS_RETENTION_DAYS",
            "retention",
            ("backend",),
            type=ValueType.INT,
            tier=Tier.T2,
            default=90,
        ),
        SettingSpec("MAIL_SMTP_PORT", "mail", ("backend", "auth"), type=ValueType.INT),
    ]
)


@pytest.fixture
def retention_keys():
    return SectionKeys(MASTER, sections=["mail", "retention"])


def test_a_deleted_row_is_detected_and_keeps_its_last_good_value(retention_keys):
    from common.settings.resolve import Source, resolve

    keys = retention_keys
    kw = dict(registry=RETENTION_REGISTRY, service="backend")
    full = FakeSnapshot.build([plain_row(), retention_row(30)], keys, revision=1)
    first = run(full, keys, **kw)
    assert first.rejections == []
    good = VerifiedSettings(first)
    tracker = MonotonicTracker()
    tracker.commit(first.accepted.values(), first.revision)

    # the view drops the row; the signed manifest of the same revision still lists it
    view = FakeSnapshot(
        [r for r in full.rows() if r.key != "API_FLOW_EVENTS_RETENTION_DAYS"],
        full.manifest(),
    )
    second = run(view, keys, tracker, **kw)
    assert reasons(second) == {("API_FLOW_EVENTS_RETENTION_DAYS", "row_missing")}
    assert set(second.accepted) == {"MAIL_SMTP_PORT"}

    reader = VerifiedSettings(second, previous=good)
    assert reader.stale_keys == ("API_FLOW_EVENTS_RETENTION_DAYS",)
    got = resolve(
        "API_FLOW_EVENTS_RETENTION_DAYS",
        {},
        reader.get("API_FLOW_EVENTS_RETENTION_DAYS"),
        90,
        RETENTION_REGISTRY,
    )
    assert (got.value, got.source) == (30, Source.STORE)  # not the default 90
    # without a previous good load there is nothing to keep: the default applies
    cold = VerifiedSettings(second)
    assert cold.get("API_FLOW_EVENTS_RETENTION_DAYS") is None


def test_missing_rows_are_judged_against_what_the_service_may_read(retention_keys):
    keys = retention_keys
    full = FakeSnapshot.build([plain_row(), retention_row(30)], keys)
    # auth is not a reader of the retention key: its view legitimately lacks it
    view = FakeSnapshot([plain_row_signed for plain_row_signed in full.rows() if plain_row_signed.key == "MAIL_SMTP_PORT"], full.manifest())
    assert run(view, keys, registry=RETENTION_REGISTRY, service="auth").rejections == []
    assert run(view, keys, service="backend").rejections[0].reason == "row_missing"
    # no service given: no per-service expectation
    assert run(view, keys).rejections == []


def test_a_row_dropped_and_manifest_entry_readers_cannot_be_forged(retention_keys):
    keys = retention_keys
    full = FakeSnapshot.build([retention_row(30)], keys)
    manifest = full.manifest()
    entries = dict(manifest.entries)
    entries["API_FLOW_EVENTS_RETENTION_DAYS"] = (
        1, entries["API_FLOW_EVENTS_RETENTION_DAYS"][1], ("auth",),
    )  # hide the key from backend's expectations
    forged = replace(manifest, entries=entries)
    result = run(FakeSnapshot([], forged), keys, service="backend")
    assert result.accepted == {} and {r.reason for r in result.rejections} == {"manifest_mismatch"}


def test_each_row_must_match_the_registry_on_section_and_secret_flag(keys):
    cases = {
        "section": plain_row(section="ai"),
        "secret flag": plain_row(is_secret=True, value=None, blob="v2:w1-00000000:AAAA"),
        "reload class": plain_row(reload_class="H"),
    }
    for name, forged in cases.items():
        snap = FakeSnapshot.build([forged], keys)
        assert reasons(run(snap, keys, registry=REGISTRY, service="backend")) == {
            ("MAIL_SMTP_PORT", "spec_mismatch")
        }, name
    # a secret row sealed under another section (the forger's own key) and
    # labelled with that section is refused for the section mismatch alone
    blob = keys.seal("ai", "MAIL_PASSWORD", 1, "x")
    forged = secret_row(keys)
    forged = replace(forged, section="ai", blob=blob)
    snap = FakeSnapshot.build([forged], keys)
    assert reasons(run(snap, keys, registry=REGISTRY, service="backend")) == {
        ("MAIL_PASSWORD", "spec_mismatch")
    }


def test_rows_of_an_unheld_section_do_not_verify_per_section_keys():
    admin = SectionKeys(MASTER, sections=["mail", "ai"])
    reader = SectionKeys(MASTER, sections=["mail"])
    ai_row = admin.sign_row(plain_row(key="AI_X", section="ai", readers=("backend",)))
    mail_row = admin.sign_row(plain_row())
    assert reader.verify_row(mail_row) and not reader.verify_row(ai_row)
    from common.settings.keys import SectionNotAllowed

    with pytest.raises(SectionNotAllowed):
        reader.sign_row(ai_row)
    # a section key signs only its own section
    assert not admin.verify_row(replace(mail_row, section="ai"))
