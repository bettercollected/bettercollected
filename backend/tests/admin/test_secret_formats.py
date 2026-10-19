"""The store refuses weak or malformed key material at every write path and still
takes every format the deploy scripts generate."""

from __future__ import annotations

import base64
import json
import os
import secrets

import pytest
from cryptography.fernet import Fernet

from backend.admin.services import host_settings as host
from backend.admin.services.settings_store import Actor, SettingsError, store_registry
from common.settings.registry import ValidationError
from tests.admin.conftest import needs_postgres
from tests.admin.test_settings_store import CLI, svc  # noqa: F401  (fixture)

REGISTRY = store_registry()


def shell_keyset() -> str:
    """The keyset ``deploy/generate-secrets.sh`` writes: one AES-256-GCM key whose
    value is the serialized AesGcmKey proto (field 3, 32 bytes)."""
    key_id = (int.from_bytes(os.urandom(4), "big") & 0x7FFFFFFF) or 1
    value = base64.b64encode(b"\x1a\x20" + os.urandom(32)).decode()
    doc = {
        "primaryKeyId": key_id,
        "key": [
            {
                "keyData": {
                    "typeUrl": "type.googleapis.com/google.crypto.tink.AesGcmKey",
                    "value": value,
                    "keyMaterialType": "SYMMETRIC",
                },
                "status": "ENABLED",
                "keyId": key_id,
                "outputPrefixType": "TINK",
            }
        ],
    }
    return base64.b64encode(json.dumps(doc, separators=(",", ":")).encode()).decode()


def refused(key: str, value: str) -> str:
    with pytest.raises(ValidationError) as err:
        REGISTRY.validate(key, value)
    if len(value) > 6:  # a short value would match the message text by chance
        assert value not in str(err.value) and value not in repr(err.value)
    return err.value.reason


# ------------------------------------------------------------- refusals


@pytest.mark.parametrize(
    "key, value, reason",
    [
        ("AUTH_JWT_SECRET", "abc", "too_short"),
        ("AUTH_JWT_SECRET", "12345678", "too_short"),
        ("AUTH_JWT_SECRET", "k" * 40, "low_entropy"),
        ("AUTH_INTERNAL_NOTIFY_KEY", "x", "too_short"),
        ("TEMPORAL_API_KEY", "random_api_key", "weak_secret"),  # the known placeholder
        ("AUTH_AES_HEX_KEY", "notafernetkey", "weak_secret"),
        ("AUTH_AES_HEX_KEY", base64.urlsafe_b64encode(bytes(32)).decode(), "low_entropy"),
        ("MASTER_ENCRYPTION_KEYSET", "junk", "bad_keyset"),
        ("MASTER_ENCRYPTION_KEYSET", base64.b64encode(b'{"key": []}').decode(), "bad_keyset"),
        ("MASTER_ENCRYPTION_KEYSET", base64.b64encode(b'{"primaryKeyId": 5, "key": [{"keyId": 6}]}').decode(), "bad_keyset"),
        ("CUSTOM_DOMAIN_ASSERTION_KEYS", "just-a-secret-without-an-id", "bad_pairs"),
        ("CUSTOM_DOMAIN_WEBHOOK_SECRETS", "short", "bad_list"),
    ],
)
def test_weak_or_malformed_key_material_is_refused(key, value, reason):
    assert refused(key, value) == reason


def test_a_keyset_whose_key_is_the_wrong_size_is_refused():
    doc = json.loads(base64.b64decode(shell_keyset()))
    doc["key"][0]["keyData"]["value"] = base64.b64encode(b"\x1a\x03abc").decode()
    assert refused("MASTER_ENCRYPTION_KEYSET", base64.b64encode(json.dumps(doc).encode()).decode()) == "bad_keyset"


def test_a_keyset_with_no_enabled_primary_is_refused():
    doc = json.loads(base64.b64decode(shell_keyset()))
    doc["key"][0]["status"] = "DISABLED"
    assert refused("MASTER_ENCRYPTION_KEYSET", base64.b64encode(json.dumps(doc).encode()).decode()) == "bad_keyset"


# ------------------------------------------- the formats we generate still pass


def test_every_generated_format_is_accepted():
    for key in host.GENERATED_KEYS:
        assert REGISTRY.validate(key, host.generate_value(key))
    assert REGISTRY.validate("AUTH_JWT_SECRET", secrets.token_hex(32))  # openssl rand -hex 32
    openssl_fernet = base64.b64encode(os.urandom(32)).decode().replace("+", "-").replace("/", "_")
    assert REGISTRY.validate("AUTH_AES_HEX_KEY", openssl_fernet)  # deploy/generate-secrets.sh
    assert REGISTRY.validate("AUTH_AES_HEX_KEY", Fernet.generate_key().decode())
    assert REGISTRY.validate("MASTER_ENCRYPTION_KEYSET", shell_keyset())
    assert REGISTRY.validate("CUSTOM_DOMAIN_ASSERTION_KEYS", "app_abc123:" + secrets.token_hex(24))
    assert REGISTRY.validate("CUSTOM_DOMAIN_WEBHOOK_SECRETS", secrets.token_hex(24) + "," + secrets.token_hex(24))


def test_the_published_keyset_is_still_accepted_with_its_warning_elsewhere():
    """A stack that used the published keyset cannot switch (its responses would be
    unreadable), so the store takes it; the portal and the services warn instead."""
    from common.services import keyset as keyset_module

    published = keyset_module.encode_keyset(keyset_module.add_primary_key(keyset_module.tink_pb2.Keyset()))
    assert REGISTRY.validate("MASTER_ENCRYPTION_KEYSET", published)


def test_other_secrets_have_no_format_and_keep_their_rules():
    assert REGISTRY.validate("OPENAI_API_KEY", "sk-test-0123456789")
    assert REGISTRY.validate("STRIPE_SECRET", "short-but-allowed")


# ------------------------------------------------------ every write path


@needs_postgres
async def test_set_and_import_refuse_weak_key_material(svc):
    with pytest.raises(SettingsError) as err:
        await svc.import_once("AUTH_JWT_SECRET", "abc", CLI)
    assert err.value.code == "invalid_value"
    assert "abc" not in str(err.value)
    assert await svc.import_once("AUTH_JWT_SECRET", secrets.token_hex(32), CLI) is not None


@needs_postgres
async def test_the_host_import_plan_refuses_with_the_check_code(svc):
    weak = {"backend": {"AUTH_JWT_SECRET": "abc", "AUTH_AES_HEX_KEY": "notafernetkey"}}
    plan = await host.plan_import(svc, weak)
    assert dict(plan.refused) == {"AUTH_JWT_SECRET": "too_short", "AUTH_AES_HEX_KEY": "weak_secret"}
    assert plan.would_import == {}


@needs_postgres
async def test_the_host_set_refuses_a_weak_secret(svc):
    with pytest.raises(Exception) as err:
        await host.set_value(svc, "TEMPORAL_API_KEY", "x", Actor("cli"))
    assert "x" != str(err.value)
    assert (await svc.stored()).values.get("TEMPORAL_API_KEY") is None
