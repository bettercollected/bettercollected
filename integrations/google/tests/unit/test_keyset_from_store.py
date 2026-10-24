"""The integration starts on a response keyset held only in the settings store.

``MASTER_ENCRYPTION_KEYSET`` absent from the environment, the keyset in the store
(as after ``bootstrap-keys`` or ``settings-prune``): importing the app in any
order must succeed, whatever imports ``common.services.crypto_service`` before
the configuration has loaded the settings snapshot, and the credentials must
encrypt and decrypt with the store's keyset."""

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
# read by the process's one ``load_snapshot`` when googleform.config runs it.
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
from googleform.app import get_application
from googleform.app.repositories.oauth_credential import OauthCredentialRepository

assert current_runtime() is not None
get_application()
crypto_service.load()  # what the startup hook does
sealed = OauthCredentialRepository.encrypt_token("user-1", '{"token": "t"}')
assert CryptoService(STORE_KEYSET).decrypt("personal", "user-1", sealed) == b'{"token": "t"}'
assert OauthCredentialRepository.decrypt_token("user-1", sealed).token == "t"
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
        timeout=120,
    )


@pytest.mark.parametrize(
    "first_import",
    [
        # the import that failed: the credential repository loads crypto_service
        "import googleform.app.repositories.oauth_credential",
        # crypto_service before anything of the integration
        "import common.services.crypto_service",
        "import googleform.app",
    ],
)
def test_the_app_starts_on_a_store_only_keyset(first_import, tmp_path):
    out = run_python(first_import + "\n" + ROUND_TRIP, tmp_path, store=True)
    assert out.returncode == 0, out.stderr[-3000:]
    assert out.stdout.strip().splitlines()[-1] == "ok"


def test_without_a_keyset_the_import_succeeds_and_the_first_use_fails(tmp_path):
    out = run_python(
        "import googleform.app\n"
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


def test_the_startup_hook_builds_the_cipher_first(monkeypatch):
    import asyncio

    from googleform.app import asgi

    class NoKeyset:
        def load(self):
            raise Exception(MISSING)

    monkeypatch.setattr(asgi, "crypto_service", NoKeyset())
    loop = asyncio.new_event_loop()  # leaves the current event loop alone
    try:
        with pytest.raises(Exception, match="neither in the environment nor in the settings store"):
            loop.run_until_complete(asgi.on_startup())
    finally:
        loop.close()
