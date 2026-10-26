"""Ciphertext written by earlier releases still decrypts.

``tests/fixtures/golden_ciphertext.json`` holds values written once, with
throwaway keys generated for the file (they protect nothing): stored response
values (Tink AES-256-GCM, ``v1:`` prefix, bound to workspace and form) and the
Fernet tokens used for stored credentials. A dependency bump (tink,
cryptography, or anything under them) that changed what these formats mean
fails here before it can make stored data unreadable.

It also pins what stored data does NOT depend on: neither path loads
pycryptodome (the ``Crypto`` package), so that library is not a data-format
dependency.
"""

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

from common.configs.crypto import Crypto
from common.services.crypto_service import UnreadableCiphertext
from common.services.keyset import CryptoService

GOLDEN = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "golden_ciphertext.json").read_text(
        encoding="utf-8"
    )
)
RESPONSES = GOLDEN["stored_responses"]


@pytest.fixture(scope="module")
def service() -> CryptoService:
    return CryptoService(GOLDEN["tink_keyset_b64"])


def _stored(case) -> bytes:
    return base64.b64decode(case["ciphertext_b64"])


@pytest.mark.parametrize("case", RESPONSES, ids=lambda c: c["workspace_id"] + c["context"])
def test_stored_response_values_written_earlier_still_decrypt(service, case):
    stored = _stored(case)

    assert stored.startswith(b"v1:")
    assert case["plaintext"].encode() not in stored or case["plaintext"] == ""
    plain = service.decrypt(
        case["workspace_id"], case["form_id"], stored, context=case["context"].encode()
    )
    assert plain == case["plaintext"].encode("utf-8")


def test_stored_response_values_stay_bound_to_workspace_form_and_context(service):
    case = RESPONSES[0]
    stored = _stored(case)

    for workspace_id, form_id, context in (
        ("another-workspace", case["form_id"], b""),
        (case["workspace_id"], "another-form", b""),
        (case["workspace_id"], case["form_id"], b"another-context"),
    ):
        with pytest.raises(UnreadableCiphertext):
            service.decrypt(workspace_id, form_id, stored, context=context)


def test_what_is_written_now_round_trips_and_is_a_different_ciphertext(service):
    case = RESPONSES[1]
    written = service.encrypt(
        case["workspace_id"], case["form_id"], case["plaintext"]
    )

    assert written.startswith(b"v1:") and written != _stored(case)
    assert service.decrypt(
        case["workspace_id"], case["form_id"], written
    ) == case["plaintext"].encode("utf-8")


@pytest.mark.parametrize("case", GOLDEN["fernet_credentials"])
def test_stored_credential_tokens_written_earlier_still_decrypt(case):
    assert Crypto(GOLDEN["fernet_key"]).decrypt(case["token"]) == case["plaintext"]


def test_stored_data_does_not_depend_on_pycryptodome():
    """A fresh interpreter: decrypt both formats and load the PDF reader's
    crypto provider, then check the ``Crypto`` package was never imported and
    that the provider is the ``cryptography`` one."""
    program = (
        "import base64, json, sys\n"
        "from pathlib import Path\n"
        "g = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
        "from common.services.keyset import CryptoService\n"
        "from common.configs.crypto import Crypto\n"
        "from pypdf._crypt_providers import crypt_provider\n"
        "c = g['stored_responses'][0]\n"
        "CryptoService(g['tink_keyset_b64']).decrypt(\n"
        "    c['workspace_id'], c['form_id'], base64.b64decode(c['ciphertext_b64']))\n"
        "Crypto(g['fernet_key']).decrypt(g['fernet_credentials'][0]['token'])\n"
        "assert 'Crypto' not in sys.modules and 'Cryptodome' not in sys.modules\n"
        "assert crypt_provider[0] == 'cryptography', crypt_provider\n"
    )
    fixture = Path(__file__).parent.parent / "fixtures" / "golden_ciphertext.json"
    done = subprocess.run(
        [sys.executable, "-I", "-c", program, str(fixture)],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr[-500:]
