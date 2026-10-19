import json
import logging
import os
import stat
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from loader_support import (
    JWT,
    LATER,
    PLANTED,
    FakeSource,
    config,
    hide,
    jwt_row,
    make_keys,
    plain_row,
    raw_of,
    rate_row,
    runtime,
    tamper,
)
from settings_support import MASTER, OTHER_MASTER

from common.settings.loader import (
    LoaderConfig,
    Poller,
    StoreError,
    keyset_fingerprint,
    load_snapshot,
    reset,
)
from common.settings.loader.disk import SnapshotError, read_snapshot, snapshot_path, write_snapshot

PORT = "API_ALLOWED_WORKSPACES"


def port_row(value=2525, version=3):
    return plain_row(key=PORT, section="limits", readers=("backend",), value=value, version=version)

RATE = "API_FLOW_EVENTS_PER_WINDOW"


@pytest.fixture
def keys():
    return make_keys()


@pytest.fixture(autouse=True)
def _reset():
    reset()
    yield
    reset()


def good(keys, revision=1, **kw):
    return raw_of(
        keys,
        [jwt_row(keys, version=kw.get("jwt", 1)), port_row(value=kw.get("port", 2525), version=revision + 2), rate_row(kw.get("rate", 5))],
        revision,
    )


# ------------------------------------------------------------ configuration


@pytest.mark.parametrize(
    "env,mode,active",
    [
        ({}, "auto", False),
        ({"DATABASE_URL": "postgresql://x/y"}, "auto", False),
        ({"SETTINGS_MASTER_KEY": MASTER}, "auto", False),
        ({"DATABASE_URL": "postgresql://x/y", "SETTINGS_MASTER_KEY": MASTER}, "auto", True),
        ({"SETTINGS_STORE": "off", "DATABASE_URL": "postgresql://x/y", "SETTINGS_MASTER_KEY": MASTER}, "off", False),
        ({"SETTINGS_STORE": "required"}, "required", True),
        ({"SETTINGS_STORE": "  Required "}, "required", True),
    ],
)
def test_mode_matrix(env, mode, active):
    cfg = LoaderConfig.from_env("backend", env)
    assert (cfg.mode, cfg.active) == (mode, active)


def test_bad_mode_snapshot_age_and_service():
    with pytest.raises(ValueError):
        LoaderConfig.from_env("backend", {"SETTINGS_STORE": "maybe"})
    with pytest.raises(ValueError):
        LoaderConfig.from_env("backend", {"SETTINGS_SNAPSHOT_MAX_AGE_DAYS": "0.5"})
    with pytest.raises(ValueError):
        LoaderConfig.from_env("Back end", {})
    assert LoaderConfig.from_env("backend", {}).snapshot_max_age_days == 7


def test_config_repr_hides_credentials():
    cfg = LoaderConfig.from_env("backend", {"DATABASE_URL": "postgresql://u:hunter2@h/d", "SETTINGS_MASTER_KEY": MASTER})
    assert "hunter2" not in repr(cfg) and MASTER not in repr(cfg)


def test_off_and_unconfigured_auto_load_nothing():
    assert load_snapshot("backend", env={"SETTINGS_STORE": "off"}) is None
    reset()
    assert load_snapshot("backend", env={}) is None


def test_required_without_database_or_key_refuses_to_start():
    with pytest.raises(StoreError, match="DATABASE_URL"):
        load_snapshot("backend", env={"SETTINGS_STORE": "required"})


def test_one_snapshot_per_process_and_one_service():
    env = {"SETTINGS_STORE": "off"}
    load_snapshot("backend", env=env)
    assert load_snapshot("backend", env=env) is None
    with pytest.raises(StoreError):
        load_snapshot("auth", env=env)


def test_malformed_master_key_is_a_start_error(tmp_path):
    with pytest.raises(StoreError, match="not valid"):
        runtime(tmp_path, FakeSource(), master_key="short")


# ------------------------------------------------------------ precedence


def test_env_beats_store_beats_default(tmp_path, keys):
    rt = runtime(tmp_path, FakeSource(good(keys)), env={PORT: "465"})
    rt.start()
    assert rt.resolve_key(PORT) is None  # the environment is the source
    rt.env = {PORT: ""}  # empty counts as unset
    assert rt.resolve_key(PORT).value == 2525
    rt.env = {PORT: '  ""  '}
    assert rt.resolve_key(PORT).value == 2525
    assert rt.resolve_key("API_ALLOWED_COLLABORATORS") is None  # no row: the default applies
    assert rt.resolve_key("NOT_A_SETTING") is None


def test_secret_comes_from_the_store_only_when_env_is_empty(tmp_path, keys):
    rt = runtime(tmp_path, FakeSource(good(keys)), env={JWT: ""})
    rt.start()
    assert rt.resolve_key(JWT).value == PLANTED
    rt.env = {JWT: "from-env"}
    assert rt.resolve_key(JWT) is None


# ------------------------------------------------------------ failure policy


def test_down_with_good_snapshot_uses_it(tmp_path, keys):
    source = FakeSource(good(keys, revision=3))
    runtime(tmp_path, source, mode="required").start()
    source.down = True
    rt = runtime(tmp_path, source, mode="required")
    rt.start()
    assert rt.origin == "snapshot" and rt.revision == 3
    assert rt.resolve_key(JWT).value == PLANTED
    assert rt.resolve_key(PORT).value == 2525


def test_down_without_snapshot_env_complete_starts(tmp_path):
    source = FakeSource()
    source.down = True
    rt = runtime(tmp_path, source, mode="required", env={JWT: "x" * 40})
    rt.start()
    assert rt.origin == "none" and rt.resolve_key(PORT) is None


def test_down_without_snapshot_env_incomplete_names_keys_not_values(tmp_path):
    source = FakeSource()
    source.down = True
    rt = runtime(tmp_path, source, mode="required", env={}, required=(JWT, "AUTH_AES_HEX_KEY"))
    with pytest.raises(StoreError) as err:
        rt.start()
    assert JWT in str(err.value) and "AUTH_AES_HEX_KEY" in str(err.value)


def test_down_without_snapshot_auto_still_starts(tmp_path, caplog):
    source = FakeSource()
    source.down = True
    runtime(tmp_path, source, mode="auto", env={}).start()


def test_fetch_retries_three_times_within_the_budget(tmp_path):
    calls, slept = [], []

    class Flaky(FakeSource):
        def fetch(self):
            calls.append(1)
            return super().fetch()

    source = Flaky()
    source.down = True
    rt = runtime(tmp_path, source, mode="auto")
    rt._sleep = slept.append
    rt.start()
    assert slept == [0.25, 0.5]  # three attempts, two waits


def test_reachable_but_bad_critical_row_is_fatal_and_never_uses_the_snapshot(tmp_path, keys):
    source = FakeSource(good(keys))
    runtime(tmp_path, source, mode="required").start()  # writes a good snapshot
    source.raw = tamper(good(keys, revision=2), JWT)
    rt = runtime(tmp_path, source, mode="required", env={})
    with pytest.raises(StoreError) as err:
        rt.start()
    assert JWT in str(err.value) and PLANTED not in str(err.value)
    assert not rt.current.get(JWT)  # nothing from the snapshot either


def test_bad_critical_row_in_auto_mode_falls_to_env_or_nothing_not_snapshot(tmp_path, keys):
    source = FakeSource(good(keys))
    runtime(tmp_path, source).start()
    source.raw = tamper(good(keys, revision=2), JWT)
    rt = runtime(tmp_path, source, env={})
    rt.start()
    assert rt.resolve_key(JWT) is None
    assert rt.resolve_key(PORT).value == 2525  # the other rows still apply


def test_bad_critical_row_with_env_value_starts(tmp_path, keys):
    source = FakeSource(tamper(good(keys), JWT))
    runtime(tmp_path, source, mode="required", env={JWT: "e" * 40}).start()


def test_bad_noncritical_row_falls_back_to_default(tmp_path, keys):
    rt = runtime(tmp_path, FakeSource(tamper(good(keys), RATE)), mode="required")
    rt.start()
    assert rt.resolve_key(RATE) is None
    assert rt.live_value(RATE) == (False, None)


def test_untrusted_manifest_at_start_is_fatal_for_critical_keys(tmp_path, keys):
    other = make_keys(OTHER_MASTER)
    rt = runtime(tmp_path, FakeSource(good(other)), mode="required", env={})
    with pytest.raises(StoreError, match="manifest was not trusted"):
        rt.start()


def test_empty_never_written_store_is_trusted_and_empty(tmp_path, keys):
    from common.settings.loader.source import RawSnapshot
    from common.settings.signing import Manifest

    # the environment supplies what the service cannot run without: nothing is expected
    # of the empty store
    rt = runtime(tmp_path, FakeSource(RawSnapshot([], Manifest(0, {}, ""))), mode="required",
                 env={JWT: "env-value"})
    rt.start()
    assert rt.revision == 0 and rt.resolve_key(PORT) is None


def test_required_refuses_an_empty_store_that_the_service_expected_to_hold_its_keys(tmp_path, keys):
    from common.settings.loader.source import RawSnapshot
    from common.settings.signing import Manifest

    wiped = FakeSource(RawSnapshot([], Manifest(0, {}, "")))
    with pytest.raises(StoreError) as err:
        runtime(tmp_path, wiped, mode="required", env={}).start()
    assert JWT in str(err.value) and "revision 0" in str(err.value)
    # `auto` keeps starting on environment and defaults, as before
    runtime(tmp_path, wiped, mode="auto", env={}).start()


def test_required_refuses_a_store_behind_the_snapshot_floor_even_when_empty(tmp_path, keys):
    from common.settings.loader.source import RawSnapshot
    from common.settings.signing import Manifest

    source = FakeSource(good(keys, revision=4))
    runtime(tmp_path, source, mode="required", env={}).start()
    source.raw = RawSnapshot([], Manifest(0, {}, ""))  # the database was wiped and re-created
    with pytest.raises(StoreError) as err:
        runtime(tmp_path, source, mode="required", env={JWT: "env-value"}).start()
    assert "behind" in str(err.value) and "SETTINGS_SNAPSHOT_DIR" in str(err.value)
    # the operator who intends it removes the snapshot directory
    for f in (tmp_path / "snap").rglob("*"):
        if f.is_file():
            f.unlink()
    runtime(tmp_path, source, mode="required", env={JWT: "env-value"}).start()


def test_a_fresh_snapshot_dir_has_no_floor_and_says_so(tmp_path, keys, caplog):
    """The residual risk, pinned: with no snapshot an older signed store is taken."""
    source = FakeSource(good(keys, revision=2))
    with caplog.at_level(logging.WARNING, logger="common.settings.loader"):
        rt = runtime(tmp_path, source, mode="required", env={})
        rt.start()
    assert rt.revision == 2
    assert any("rollback floor lives in a temporary directory" in r.getMessage() for r in caplog.records)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="common.settings.loader"):
        runtime(tmp_path, source, mode="required", env={}, snapshot_dir_explicit=True).start()
    assert not any("rollback floor" in r.getMessage() for r in caplog.records)


def test_the_floor_is_what_the_service_reports(tmp_path, keys):
    source = FakeSource(good(keys, revision=5))
    rt = runtime(tmp_path, source, env={})
    rt.start()
    source.raw = good(keys, revision=3)  # an older state is refused, the report stays at the floor
    rt.poll_once()
    assert rt.state().revision_applied == 5


def test_rejected_or_deleted_row_keeps_the_last_good_value(tmp_path, keys):
    source = FakeSource(good(keys, revision=1, port=111))
    rt = runtime(tmp_path, source, mode="required", env={})
    rt.start()
    assert rt.resolve_key(PORT).value == 111
    newer = raw_of(keys, [jwt_row(keys), port_row(value=222, version=4), rate_row()], 2)
    source.raw = tamper(newer, PORT)
    assert rt.poll_once() is True
    assert rt.resolve_key(PORT).value == 111 and rt.current.is_stale(PORT)
    source.raw = hide(raw_of(keys, [jwt_row(keys), port_row(value=222, version=4), rate_row()], 3), PORT)
    rt.poll_once()
    assert rt.resolve_key(PORT).value == 111  # row_missing: keep, never the default
    assert PORT in rt.state().rejected_keys


def test_manifest_rollback_is_refused(tmp_path, keys):
    source = FakeSource(good(keys, revision=5, port=555))
    rt = runtime(tmp_path, source, env={})
    rt.start()
    source.raw = good(keys, revision=3, port=333)
    assert rt.poll_once() is False
    assert rt.revision == 5 and rt.resolve_key(PORT).value == 555


def test_rollback_after_restart_is_refused_through_the_snapshot_floor(tmp_path, keys):
    source = FakeSource(good(keys, revision=5))
    runtime(tmp_path, source, mode="required").start()
    source.raw = good(keys, revision=2)  # an older, correctly signed store
    rt = runtime(tmp_path, source, mode="required", env={})
    with pytest.raises(StoreError):
        rt.start()


def test_a_lower_row_version_is_refused(tmp_path, keys):
    source = FakeSource(raw_of(keys, [port_row(value=2, version=7)], 4))
    rt = runtime(tmp_path, source, env={})
    rt.start()
    source.raw = raw_of(keys, [port_row(value=1, version=6)], 5)
    rt.poll_once()
    assert rt.resolve_key(PORT).value == 2


# ------------------------------------------------------------ disk snapshot


def _snap(tmp_path, keys, **cfg):
    source = FakeSource(good(keys, revision=2))
    runtime(tmp_path, source, mode="required", **cfg).start()
    source.down = True
    return source


def test_snapshot_file_is_private_atomic_and_holds_no_plaintext(tmp_path, keys):
    _snap(tmp_path, keys)
    path = Path(snapshot_path(str(tmp_path / "snap"), "backend"))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert [p.name for p in path.parent.iterdir()] == [path.name]
    body = path.read_text()
    assert PLANTED not in body and "v2:" in body


def test_snapshot_tampered_is_refused(tmp_path, keys):
    source = _snap(tmp_path, keys)
    path = Path(snapshot_path(str(tmp_path / "snap"), "backend"))
    doc = json.loads(path.read_text())
    for row in doc["rows"]:
        if row["key"] == PORT:
            row["value"] = 1
    path.write_text(json.dumps(doc))
    os.chmod(path, 0o600)
    rt = runtime(tmp_path, source, env={})
    rt.start()
    assert rt.origin == "snapshot" and rt.resolve_key(PORT) is None  # its signature failed
    assert rt.resolve_key(RATE).value == 5  # the untouched rows still apply


def test_snapshot_tampered_manifest_or_wrong_key_means_no_snapshot(tmp_path, keys):
    source = _snap(tmp_path, keys)
    rt = runtime(tmp_path, source, master_key=OTHER_MASTER, env={})
    rt.start()
    assert rt.origin == "none" and rt.resolve_key(PORT) is None
    with pytest.raises(StoreError):
        runtime(tmp_path, source, mode="required", master_key=OTHER_MASTER, env={}).start()


def test_snapshot_expires_after_the_configured_days(tmp_path, keys):
    source = _snap(tmp_path, keys)
    rt = runtime(tmp_path, source, env={}, now=LATER(8))
    rt.start()
    assert rt.origin == "none"
    rt = runtime(tmp_path, source, env={}, now=LATER(8), snapshot_max_age_days=10)
    rt.start()
    assert rt.origin == "snapshot"


def test_snapshot_with_loose_permissions_is_refused(tmp_path, keys):
    source = _snap(tmp_path, keys)
    os.chmod(snapshot_path(str(tmp_path / "snap"), "backend"), 0o644)
    rt = runtime(tmp_path, source, env={})
    rt.start()
    assert rt.origin == "none"
    with pytest.raises(SnapshotError) as err:
        read_snapshot(str(tmp_path / "snap"), "backend")
    assert err.value.reason == "insecure"


def test_snapshot_symlink_and_foreign_service_are_refused(tmp_path, keys):
    _snap(tmp_path, keys)
    d = tmp_path / "snap"
    real = d / "settings-backend.json"
    (d / "settings-auth.json").symlink_to(real)
    with pytest.raises(SnapshotError) as err:
        read_snapshot(str(d), "auth")
    assert err.value.reason == "insecure"
    real.rename(d / "other.json")
    with pytest.raises(SnapshotError) as err:
        read_snapshot(str(d), "backend")
    assert err.value.reason == "missing"


def test_an_open_directory_we_own_is_closed_not_refused(tmp_path, keys):
    d = tmp_path / "open"
    d.mkdir(mode=0o755)
    os.chmod(d, 0o755)
    raw = good(keys)
    path = write_snapshot(str(d), "backend", raw.rows, raw.manifest)
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_unwritable_snapshot_directory_does_not_stop_the_service(tmp_path, keys, caplog):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    caplog.set_level(logging.WARNING)
    rt = runtime(tmp_path, FakeSource(good(keys)), snapshot_dir=str(blocker / "sub"), env={})
    rt.start()
    assert rt.resolve_key(PORT).value == 2525
    assert "not written" in caplog.text


# ------------------------------------------------------------ hot reload and reporting


def test_reload_swaps_atomically_and_reports_names_only(tmp_path, keys, caplog):
    caplog.set_level(logging.DEBUG)
    source = FakeSource(good(keys, revision=1, rate=5))
    rt = runtime(tmp_path, source, env={PORT: "465", JWT: PLANTED})
    rt.start()
    assert rt.live_value(RATE) == (True, 5)
    before = rt.current
    source.raw = good(keys, revision=2, rate=9)
    assert rt.poll_once() is True
    assert rt.current is not before and rt.live_value(RATE) == (True, 9)
    assert rt.restart_pending is False  # only a hot key changed
    assert source.reports and source.reports[-1].revision_applied == 2
    assert rt.poll_once() is False  # same revision: nothing fetched again
    state = source.reports[-1].to_report()
    assert set(state["env_overrides"]) == {PORT, JWT}
    blob = json.dumps(state) + caplog.text
    assert PLANTED not in blob and "465" not in json.dumps(state)
    assert state["keyset_fp"] == keys.fingerprint


def test_restart_pending_when_a_restart_class_key_changes(tmp_path, keys):
    source = FakeSource(good(keys, revision=1, port=1))
    rt = runtime(tmp_path, source, env={})
    rt.start()
    source.raw = good(keys, revision=2, port=2)
    rt.poll_once()
    assert rt.restart_pending is True and source.reports[-1].restart_pending is True


def test_restart_not_pending_when_env_overrides_the_changed_key(tmp_path, keys):
    source = FakeSource(good(keys, revision=1, port=1))
    rt = runtime(tmp_path, source, env={PORT: "465"})
    rt.start()
    source.raw = good(keys, revision=2, port=2)
    rt.poll_once()
    assert rt.restart_pending is False


def test_env_overrides_hide_hot_values(tmp_path, keys):
    rt = runtime(tmp_path, FakeSource(good(keys)), env={RATE: "77"})
    rt.start()
    assert rt.live_value(RATE) == (False, None)


def test_no_value_in_logs_or_reports_with_planted_secrets(tmp_path, keys, caplog):
    caplog.set_level(logging.DEBUG)
    source = FakeSource(tamper(good(keys), JWT))
    rt = runtime(tmp_path, source, env={"AUTH_AES_HEX_KEY": PLANTED})
    rt.start()
    rt.report()
    text = caplog.text + json.dumps([s.to_report() for s in source.reports])
    assert PLANTED not in text
    assert "AUTH_JWT_SECRET version 1 rejected" in caplog.text


def test_rejected_key_names_are_reportable_names_only(tmp_path, keys):
    source = FakeSource(tamper(good(keys), RATE))
    rt = runtime(tmp_path, source, env={})
    rt.start()
    assert rt.state().rejected_keys == (RATE,)


def test_keyset_fingerprint_hook(tmp_path, keys):
    from common.settings.loader import set_keyset_key_ids

    assert keyset_fingerprint([2, 1]) == keyset_fingerprint(["1", "2"]) != keyset_fingerprint([1])
    rt = runtime(tmp_path, FakeSource(good(keys)))
    set_keyset_key_ids(lambda: [10, 20])
    try:
        assert rt.state().keyset_fp == keyset_fingerprint([10, 20])
        assert "10" not in rt.state().keyset_fp
        set_keyset_key_ids(lambda: 1 / 0)
        assert rt.state().keyset_fp == keys.fingerprint  # a failing hook falls back
    finally:
        set_keyset_key_ids(None)


def test_report_failure_never_raises(tmp_path, keys):
    source = FakeSource(good(keys))
    source.report_down = True
    rt = runtime(tmp_path, source)
    rt.start()
    rt.report_safely()


# ------------------------------------------------------------ poller


def test_poller_backoff_grows_is_capped_and_resets(tmp_path, keys):
    rt = runtime(tmp_path, FakeSource(good(keys)))
    p = Poller(rt, interval=10, jitter=0, max_backoff=100, rng=lambda: 0)
    assert p.next_delay() == 10
    p.failures = 1
    assert p.next_delay() == 20
    p.failures = 3
    assert p.next_delay() == 80
    p.failures = 9
    assert p.next_delay() == 100
    p2 = Poller(rt, interval=10, jitter=4, rng=lambda: 0.5)
    assert p2.next_delay() == 12


def test_poller_survives_errors_and_logs_class_name_only(tmp_path, keys, caplog):
    source = FakeSource(good(keys))
    rt = runtime(tmp_path, source)
    rt.start()

    def boom():
        raise RuntimeError(PLANTED)

    rt.poll_once = boom
    p = Poller(rt, interval=0.01, jitter=0)
    p.run_once()
    assert p.failures == 1 and "RuntimeError" in caplog.text and PLANTED not in caplog.text
    rt.poll_once = lambda: True
    p.run_once()
    assert p.failures == 0


def test_poller_thread_applies_changes_and_stops_cleanly(tmp_path, keys):
    source = FakeSource(good(keys, revision=1, rate=1))
    rt = runtime(tmp_path, source, env={})
    rt.start()
    p = Poller(rt, interval=0.01, jitter=0.0, heartbeat=0.01)
    p.start()
    source.raw = good(keys, revision=2, rate=42)
    for _ in range(300):
        if rt.live_value(RATE) == (True, 42):
            break
        threading.Event().wait(0.02)
    assert rt.live_value(RATE) == (True, 42)
    p.stop()
    assert not p.running
    assert source.reports  # first report plus heartbeats


def test_poller_keeps_running_while_the_store_is_down(tmp_path, keys):
    source = FakeSource(good(keys))
    rt = runtime(tmp_path, source, env={})
    rt.start()
    p = Poller(rt, interval=0.01, jitter=0.0, max_backoff=0.02)
    p.start()
    source.down = True
    threading.Event().wait(0.15)
    assert p.running and p.failures >= 1
    source.down = False
    source.raw = good(keys, revision=2, rate=8)
    for _ in range(300):
        if rt.live_value(RATE) == (True, 8):
            break
        threading.Event().wait(0.02)
    p.stop()
    assert rt.live_value(RATE) == (True, 8)


# ------------------------------------------------------------ import time and isolation


def test_import_time_construction_with_the_store_off():
    code = (
        "import sys\n"
        "from common.settings.loader import load_snapshot, current_runtime, live\n"
        "assert load_snapshot('backend') is None and current_runtime() is None\n"
        "assert live().get('API_FLOW_EVENTS_PER_WINDOW', 600) == 600\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('fastapi','backend','sqlalchemy')"
        " or m.startswith('common.services') or m == 'asyncpg']\n"
        "print('BAD=' + ','.join(bad))\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("SETTINGS_MASTER_KEY",)}
    env["SETTINGS_STORE"] = "off"
    env["DATABASE_URL"] = "postgresql://nobody@127.0.0.1:1/none"
    done = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=Path(__file__).parents[2],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-1500:]
    assert done.stdout.strip().splitlines()[-1] == "BAD="
