"""``crypto_service`` is built on first use, not on import.

A stack whose keyset lives only in the settings store has it once the service's
configuration has loaded the snapshot; importing ``common.services.crypto_service``
before that (any import order) must not fail, and the first use must find the
keyset in the store. Without a keyset anywhere, the first use fails loudly."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from tink.proto import tink_pb2

from common.services.crypto_service import LazyCryptoService, default_crypto_service
from common.services.keyset import CryptoService, add_primary_key, encode_keyset

COMMON_DIR = Path(__file__).resolve().parents[1]
MASTER = base64.b64encode(bytes(range(48))).decode()
MISSING = "MASTER_ENCRYPTION_KEYSET is set neither in the environment nor in the settings store."

# A settings store holding only the keyset (signed with MASTER), installed so the
# process's one ``load_snapshot`` reads it, as a service's configuration does.
STORE_STUB = """
import os
from datetime import datetime, timezone
from types import SimpleNamespace

import common.settings.loader as _loader
from common.services.keyset import add_primary_key, encode_keyset
from common.settings.canonical import SettingRow
from common.settings.keys import SectionKeys
from common.settings.loader import runtime as _runtime_module
from common.settings.loader.source import RawSnapshot
from common.settings.registry import default_registry
from common.settings.snapshot import FakeSnapshot
from tink.proto import tink_pb2

_NAME = "MASTER_ENCRYPTION_KEYSET"
STORE_KEYSET = encode_keyset(add_primary_key(tink_pb2.Keyset()))
_keys = SectionKeys(os.environ["SETTINGS_MASTER_KEY"], sections=["auth_keys"])
_spec = default_registry().get(_NAME)
_row = SettingRow(
    _NAME, _spec.section, _spec.readers, True, _spec.reload_class.value, 1,
    datetime(2026, 10, 24, tzinfo=timezone.utc),
    blob=_keys.seal(_spec.section, _NAME, 1, STORE_KEYSET),
)
_snap = FakeSnapshot.build([_row], _keys, 1)
_raw = RawSnapshot(list(_snap.row_list), _snap.signed_manifest)
_source = SimpleNamespace(fetch=lambda: _raw, fetch_revision=lambda: 1, report_state=lambda *a: None)
_real_load_snapshot = _runtime_module.load_snapshot


def _load_snapshot(service, **kwargs):
    kwargs.setdefault("source", _source)
    return _real_load_snapshot(service, **kwargs)


_loader.load_snapshot = _load_snapshot
"""


def run_python(program, tmp_path, *, store):
    env = {k: v for k, v in os.environ.items() if k != "MASTER_ENCRYPTION_KEYSET"}
    env["DOTENV_PATH"] = "/nonexistent.env"
    env["SETTINGS_SNAPSHOT_DIR"] = str(tmp_path / "snapshot")
    if store:
        env.update(SETTINGS_STORE="required", SETTINGS_MASTER_KEY=MASTER)
        if not env.get("DATABASE_URL"):  # never connected: the store is the stub
            env["DATABASE_URL"] = "postgresql://unused/unused"
        program = STORE_STUB + program
    else:
        env["SETTINGS_STORE"] = "off"
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=COMMON_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_importing_without_a_keyset_succeeds_and_the_first_use_fails_loudly(tmp_path):
    out = run_python(
        "from common.services.crypto_service import crypto_service\n"
        "print('imported', crypto_service.loaded)\n"
        "try:\n"
        "    crypto_service.encrypt('w', 'f', 'x')\n"
        "except Exception as exc:\n"
        "    print('refused:', exc)\n"
        "else:\n"
        "    print('encrypted without a keyset')\n",
        tmp_path,
        store=False,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    lines = out.stdout.strip().splitlines()
    assert lines == ["imported False", "refused: " + MISSING]


def test_imported_before_the_snapshot_it_uses_the_store_keyset(tmp_path):
    out = run_python(
        "from common.services.crypto_service import crypto_service\n"
        "from common.settings.loader import current_runtime, load_snapshot\n"
        "assert current_runtime() is None and not crypto_service.loaded\n"
        "load_snapshot('backend')\n"
        "sealed = crypto_service.encrypt('w1', 'f1', 'answer')\n"
        "assert crypto_service.decrypt('w1', 'f1', sealed) == b'answer'\n"
        "from common.services.keyset import CryptoService\n"
        "assert CryptoService(STORE_KEYSET).decrypt('w1', 'f1', sealed) == b'answer'\n"
        "print('ok')\n",
        tmp_path,
        store=True,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "ok"


def _keyset():
    return encode_keyset(add_primary_key(tink_pb2.Keyset()))


def test_it_is_built_once_across_threads():
    calls = []
    barrier = threading.Barrier(8)
    keyset = _keyset()

    def factory():
        calls.append(1)
        return CryptoService(keyset)

    lazy = LazyCryptoService(factory)
    results = []

    def use():
        barrier.wait()
        results.append(lazy.load())

    threads = [threading.Thread(target=use) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert len({id(r) for r in results}) == 1


def test_a_failed_build_is_not_remembered():
    keyset = {"value": ""}

    def factory():
        if not keyset["value"]:
            raise Exception(MISSING)
        return CryptoService(keyset["value"])

    lazy = LazyCryptoService(factory)
    for _ in range(2):
        with pytest.raises(Exception, match="neither in the environment nor in the settings store"):
            lazy.encrypt("w", "f", "x")
    assert not lazy.loaded
    keyset["value"] = _keyset()
    sealed = lazy.encrypt("w", "f", "x")
    assert lazy.decrypt("w", "f", sealed) == b"x"
    assert lazy.primary_key_id == lazy.load().primary_key_id
    assert lazy.published_key_in_keyset is False


def test_reset_builds_it_again(monkeypatch):
    first, second = _keyset(), _keyset()
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", first)
    lazy = LazyCryptoService(default_crypto_service)
    sealed = lazy.encrypt("w", "f", "x")
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", second)
    assert lazy.decrypt("w", "f", sealed) == b"x"  # still the first keyset
    lazy.reset()
    assert not lazy.loaded
    assert CryptoService(second).decrypt("w", "f", lazy.encrypt("w", "f", "y")) == b"y"
