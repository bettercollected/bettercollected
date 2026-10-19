"""``common.services.keyset_source`` resolves the keyset without building the
process-wide cipher, so a service's configuration can register the key-id
provider before its settings snapshot (and with it a store-only keyset) is
loaded."""

import subprocess
import sys

from tink.proto import tink_pb2

from common.services import keyset_source
from common.services.keyset import add_primary_key, encode_keyset


def test_importing_it_builds_no_cipher():
    program = (
        "import sys\n"
        "import common.services.keyset_source\n"
        "print('loaded' if 'common.services.crypto_service' in sys.modules else 'clean')\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip() == "clean"


def test_key_ids_come_from_the_environment_keyset(monkeypatch):
    keyset = add_primary_key(add_primary_key(tink_pb2.Keyset()))
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", encode_keyset(keyset))
    assert keyset_source.configured_key_ids() == [k.key_id for k in keyset.key]


def test_no_keyset_resolves_to_empty(monkeypatch):
    from common.settings.loader import runtime

    monkeypatch.delenv("MASTER_ENCRYPTION_KEYSET", raising=False)
    monkeypatch.setattr(runtime, "_runtime", None)
    assert keyset_source.configured_keyset() == ""
