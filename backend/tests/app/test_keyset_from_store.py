"""The backend and its jobs worker start on a response keyset held only in the
settings store.

``MASTER_ENCRYPTION_KEYSET`` absent from the environment, the keyset in the store
(as after ``bootstrap-keys`` or ``settings-prune``): importing them in any order
must succeed, whatever imports ``common.services.crypto_service`` before the
configuration has loaded the settings snapshot, and responses must encrypt and
decrypt with the store's keyset."""

import base64
import os
import subprocess
import sys
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[2]
MASTER = base64.b64encode(bytes(range(48))).decode()
MISSING = "MASTER_ENCRYPTION_KEYSET is set neither in the environment nor in the settings store."

# A settings store holding only the keyset (signed with SETTINGS_MASTER_KEY),
# read by the process's one ``load_snapshot`` when backend.config runs it.
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

ROUND_TRIP = """
from common.settings.loader import current_runtime
from common.services.crypto_service import crypto_service
from common.services.keyset import CryptoService
from backend.app import get_application
import backend.jobs.worker  # noqa: F401
from backend.app.repositories.postgres import responses  # noqa: F401

assert current_runtime() is not None
get_application()
crypto_service.load()  # what the startup (app lifespan, jobs worker) does
sealed = crypto_service.encrypt("w1", "f1", '{"q": "a"}')
assert CryptoService(STORE_KEYSET).decrypt("w1", "f1", sealed) == b'{"q": "a"}'
assert crypto_service.decrypt("w1", "f1", sealed) == b'{"q": "a"}'
print("ok")
"""


def run_python(program, tmp_path, *, store):
    env = {k: v for k, v in os.environ.items() if k != "MASTER_ENCRYPTION_KEYSET"}
    env.setdefault("AUTH_JWT_SECRET", "b" * 64)
    env.setdefault("AUTH_AES_HEX_KEY", base64.urlsafe_b64encode(b"f" * 32).decode())
    env["DOTENV_PATH"] = str(SERVICE_DIR / "no-such-dir" / ".env")
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
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.parametrize(
    "first_import",
    [
        # a repository that loads crypto_service, imported first
        "import backend.app.repositories.postgres.responses",
        # crypto_service before anything of the backend
        "import common.services.crypto_service",
        # the jobs worker's entry point
        "import backend.jobs.worker",
        "import backend.app",
    ],
)
def test_the_backend_starts_on_a_store_only_keyset(first_import, tmp_path):
    out = run_python(first_import + "\n" + ROUND_TRIP, tmp_path, store=True)
    assert out.returncode == 0, out.stderr[-3000:]
    assert out.stdout.strip().splitlines()[-1] == "ok"


def test_without_a_keyset_the_import_succeeds_and_the_first_use_fails(tmp_path):
    out = run_python(
        "import common.services.crypto_service\n"
        "import backend.app\n"
        "import backend.jobs.worker\n"
        "from common.services.crypto_service import crypto_service\n"
        "try:\n"
        "    crypto_service.load()\n"
        "except Exception as exc:\n"
        "    print('refused:', exc)\n",
        tmp_path,
        store=False,
    )
    assert out.returncode == 0, out.stderr[-3000:]
    assert out.stdout.strip().splitlines()[-1] == "refused: " + MISSING


class NoKeyset:
    """A process-wide cipher with no keyset to build from."""

    def load(self):
        raise Exception(MISSING)


async def test_the_app_lifespan_builds_the_cipher_first(monkeypatch):
    from fastapi import FastAPI

    from backend.app import asgi

    monkeypatch.setattr(asgi, "crypto_service", NoKeyset())
    with pytest.raises(Exception, match="neither in the environment nor in the settings store"):
        async with asgi.lifespan(FastAPI()):
            pytest.fail("started without a keyset")


async def test_the_jobs_worker_builds_the_cipher_first(monkeypatch):
    from backend.jobs import worker

    monkeypatch.setattr(worker, "crypto_service", NoKeyset())
    monkeypatch.setattr(
        worker,
        "check_postgres_at_startup",
        lambda *a, **k: pytest.fail("started without a keyset"),
    )
    with pytest.raises(Exception, match="neither in the environment nor in the settings store"):
        await worker.main()
