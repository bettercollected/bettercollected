"""MASTER_ENCRYPTION_KEYSET: a published key is warned about at startup (by
variable name only), and the keyset rotates with Tink's semantics."""

import base64
import io
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import tink
from tink import aead, cleartext_keyset_handle

from common.services import keyset as keysets
from common.services.keyset import (
    PUBLISHED_KEY_SHA256,
    CryptoService,
    KeysetError,
    UnreadableCiphertext,
    add_primary_key,
    add_secondary_key,
    ciphertext_key_id,
    encode_keyset,
    key_digest,
    keyset_ids_fingerprint,
    only_primary,
    promote,
    parse_keyset,
    published_key_ids,
    published_key_warning,
    warn_if_published,
)

REPO = Path(__file__).resolve().parents[2]
COMMON_DIR = REPO / "common"
# Every file that ever carried the published keyset and still does.
PUBLISHED_IN = (
    ".github/workflows/ci.yml",
    ".github/workflows/test.yml",
    "backend/.ci/docker-compose.yml",
)


def generated_keyset() -> str:
    aead.register()
    handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    buffer = io.StringIO()
    cleartext_keyset_handle.write(tink.JsonKeysetWriter(buffer), handle)
    return base64.b64encode(buffer.getvalue().encode()).decode()


def published_keyset() -> str:
    """The CI test keyset, which is the one the repository published."""
    text = (REPO / ".github/workflows/ci.yml").read_text()
    match = re.search(r'MASTER_ENCRYPTION_KEYSET:\s*"([^"]+)"', text)
    assert match
    return match.group(1)


def secret_fragments(value: str):
    """What a log line must never contain: the value, its decoded JSON and the
    key material (and its digest)."""
    keyset = parse_keyset(value)
    fragments = [value, base64.b64decode(value).decode()[:40]]
    for key in keyset.key:
        fragments.append(base64.b64encode(key.key_data.value).decode())
        fragments.append(key_digest(key))
    return fragments


# ------------------------------------------------------------ the denylist
@pytest.mark.parametrize("path", PUBLISHED_IN)
def test_every_keyset_in_the_repository_is_on_the_denylist(path):
    for value in re.findall(
        r'MASTER_ENCRYPTION_KEYSET:\s*"([^"]+)"', (REPO / path).read_text()
    ):
        assert published_key_ids(parse_keyset(value))


def test_the_denylist_holds_digests_only():
    assert all(re.fullmatch(r"[0-9a-f]{64}", d) for d in PUBLISHED_KEY_SHA256)


def test_a_generated_keyset_is_not_published():
    assert published_key_ids(parse_keyset(generated_keyset())) == []
    assert published_key_warning(generated_keyset()) is None


def test_the_match_is_on_key_material_not_on_the_encoding():
    """Re-encoded, reordered or with other keys added, a published key is found."""
    published = parse_keyset(published_keyset())
    raw_json = base64.b64decode(published_keyset()).decode()
    assert published_key_ids(parse_keyset(raw_json)) == [published.primary_key_id]
    rotated = add_primary_key(published)
    assert published_key_ids(parse_keyset(encode_keyset(rotated))) == [
        published.primary_key_id
    ]


# ---------------------------------------------------------------- warnings
def test_warns_by_name_for_a_published_primary(caplog):
    value = published_keyset()
    with caplog.at_level(logging.WARNING, logger=keysets.__name__):
        assert warn_if_published(value) is True
    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert "MASTER_ENCRYPTION_KEYSET is a keyset that was published" in record.message
    assert "docs/response-keyset-rotation.md" in record.message
    for fragment in secret_fragments(value):
        assert fragment not in caplog.text


def test_warns_while_a_published_key_remains_after_rotation(caplog):
    value = encode_keyset(add_primary_key(parse_keyset(published_keyset())))
    with caplog.at_level(logging.WARNING, logger=keysets.__name__):
        assert warn_if_published(value) is True
    assert "still holds a key that was published" in caplog.text
    assert "no longer the primary" in caplog.text
    for fragment in secret_fragments(value):
        assert fragment not in caplog.text


def test_no_warning_for_a_generated_keyset(caplog):
    with caplog.at_level(logging.WARNING, logger=keysets.__name__):
        assert warn_if_published(generated_keyset()) is False
    assert caplog.records == []


def test_after_drop_old_there_is_nothing_to_warn_about():
    rotated = add_primary_key(parse_keyset(published_keyset()))
    assert published_key_warning(encode_keyset(only_primary(rotated))) is None


def load_at_startup(keyset_value):
    """A fresh process loading the cipher, as every service does at startup."""
    env = {k: v for k, v in os.environ.items() if k != "MASTER_ENCRYPTION_KEYSET"}
    env["MASTER_ENCRYPTION_KEYSET"] = keyset_value
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from common.services.crypto_service import crypto_service\n"
            "print(crypto_service.published_key_in_keyset)",
        ],
        cwd=COMMON_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_startup_warns_for_the_published_keyset_and_never_logs_it():
    value = published_keyset()
    result = load_at_startup(value)
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "True"
    assert "MASTER_ENCRYPTION_KEYSET is a keyset that was published" in result.stderr
    for fragment in secret_fragments(value):
        assert fragment not in result.stderr + result.stdout


def test_startup_is_quiet_with_a_generated_keyset():
    result = load_at_startup(generated_keyset())
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "False"
    assert "MASTER_ENCRYPTION_KEYSET" not in result.stderr


# ---------------------------------------------------------------- rotation
def test_rotation_keeps_old_ciphertexts_readable_and_tags_new_ones():
    old = parse_keyset(generated_keyset())
    old_cipher = CryptoService(encode_keyset(old))
    stored = old_cipher.encrypt("ws", "form", b"an answer")
    assert ciphertext_key_id(stored) == old.primary_key_id

    rotated = add_primary_key(old)
    assert len(rotated.key) == 2
    assert rotated.primary_key_id != old.primary_key_id
    assert {k.key_id for k in old.key} < {k.key_id for k in rotated.key}
    cipher = CryptoService(encode_keyset(rotated))
    assert cipher.primary_key_id == rotated.primary_key_id
    assert cipher.decrypt("ws", "form", stored) == b"an answer"
    fresh = cipher.encrypt("ws", "form", b"an answer")
    assert ciphertext_key_id(fresh) == rotated.primary_key_id

    final = CryptoService(encode_keyset(only_primary(rotated)))
    assert final.decrypt("ws", "form", fresh) == b"an answer"
    with pytest.raises(UnreadableCiphertext):
        final.decrypt("ws", "form", stored)


def test_ciphertext_key_id_reads_stored_values_only():
    assert ciphertext_key_id(b"v1:\x01\x00\x00\x00\x2a" + b"x" * 28) == 42
    assert ciphertext_key_id(b"plain") is None
    assert ciphertext_key_id("v1:\x01\x00\x00\x00\x2a") is None  # str: plaintext
    assert ciphertext_key_id({"q1": "answer"}) is None


@pytest.mark.parametrize("bad", ["", "not a keyset", base64.b64encode(b"{}").decode()])
def test_bad_keysets_are_refused_without_quoting_them(bad):
    with pytest.raises(KeysetError) as error:
        parse_keyset(bad)
    if bad:
        assert bad not in str(error.value)
    assert published_key_warning(bad) is None


# ------------------------------------------------- two-step rotation
def test_add_secondary_keeps_the_primary_and_the_old_ciphertexts_readable():
    old = parse_keyset(generated_keyset())
    stored = CryptoService(encode_keyset(old)).encrypt("ws", "form", b"an answer")

    added = add_secondary_key(old)
    assert added.primary_key_id == old.primary_key_id
    assert len(added.key) == 2
    new_id = ({k.key_id for k in added.key} - {k.key_id for k in old.key}).pop()
    cipher = CryptoService(encode_keyset(added))
    assert cipher.primary_key_id == old.primary_key_id
    # still encrypts with the old key, so a service not yet updated can read it
    assert ciphertext_key_id(cipher.encrypt("ws", "form", b"x")) == old.primary_key_id
    assert cipher.decrypt("ws", "form", stored) == b"an answer"
    assert new_id not in {k.key_id for k in old.key}
    # the input is not modified
    assert len(old.key) == 1


def test_promote_makes_the_new_key_primary_and_changes_nothing_else():
    old = parse_keyset(generated_keyset())
    added = add_secondary_key(old)
    new_id = ({k.key_id for k in added.key} - {k.key_id for k in old.key}).pop()

    promoted = promote(added, new_id)
    assert promoted.primary_key_id == new_id
    assert [k.key_id for k in promoted.key] == [k.key_id for k in added.key]
    assert [key_digest(k) for k in promoted.key] == [key_digest(k) for k in added.key]
    assert added.primary_key_id == old.primary_key_id  # input untouched
    cipher = CryptoService(encode_keyset(promoted))
    assert ciphertext_key_id(cipher.encrypt("ws", "form", b"x")) == new_id
    # idempotent
    assert promote(promoted, new_id).primary_key_id == new_id


def test_promote_refuses_an_unknown_key_without_quoting_anything():
    keyset = parse_keyset(generated_keyset())
    with pytest.raises(KeysetError) as error:
        promote(keyset, keyset.primary_key_id + 1)
    assert "keyset" in str(error.value)


def test_the_heartbeat_fingerprint_is_ids_only_and_order_free():
    one = keyset_ids_fingerprint([3, 1, 2])
    assert one == keyset_ids_fingerprint(["2", "3", "1"])
    assert one != keyset_ids_fingerprint([1, 2])
    assert one.startswith("ks-") and len(one) == 15
    assert re.fullmatch(r"[A-Za-z0-9_.:-]{0,64}", one)
    # a fixed vector: the settings loader must compute the same value
    assert keyset_ids_fingerprint([1, 2, 3]) == one
    # TODO(settings loader): the test below compares with the loader once
    # `common.settings.loader` is in this tree.
    assert one == "ks-" + __import__("hashlib").sha256(b"bc-keyset-v1|1,2,3").hexdigest()[:12]


def test_the_fingerprint_equals_the_settings_loaders_when_it_exists():
    loader = pytest.importorskip("common.settings.loader")
    for ids in ([1], [3, 1, 2], [4294967295, 7]):
        assert keyset_ids_fingerprint(ids) == loader.keyset_fingerprint(ids)
