"""The Google Forms integration reports the fingerprint of the keyset it holds in
its settings-store heartbeat, like the backend: the admin keyset tasks compare it
with the stored keyset before a promote, a re-encryption or dropping a key."""

import base64
import os
import subprocess
import sys
from pathlib import Path

from tink.proto import tink_pb2

from common.services.keyset import add_primary_key, encode_keyset
from common.settings.loader import keyset_fingerprint

SERVICE_DIR = Path(__file__).resolve().parents[2]

# A fresh process loading the settings as at startup, then printing the
# fingerprint the heartbeat would carry (never the keyset).
PROGRAM = (
    "import googleform.config\n"
    "from common.settings.loader import keyset_fingerprint\n"
    "from common.settings.loader import runtime\n"
    "provider = runtime._key_ids_provider\n"
    "print('fp=' + (keyset_fingerprint(provider()) if provider else 'none'))\n"
)


def test_the_heartbeat_carries_the_keyset_fingerprint():
    keyset = add_primary_key(add_primary_key(tink_pb2.Keyset()))
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AUTH_", "SETTINGS_", "MASTER_ENCRYPTION_"))
    }
    env.update(
        AUTH_JWT_SECRET="c" * 64,
        AUTH_AES_HEX_KEY=base64.urlsafe_b64encode(b"g" * 32).decode(),
        MASTER_ENCRYPTION_KEYSET=encode_keyset(keyset),
        SETTINGS_STORE="off",
        DOTENV_PATH=str(SERVICE_DIR / "no-such-dir" / ".env"),
    )
    result = subprocess.run(
        [sys.executable, "-c", PROGRAM],
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    expected = keyset_fingerprint([k.key_id for k in keyset.key])
    assert f"fp={expected}" in result.stdout.splitlines()
