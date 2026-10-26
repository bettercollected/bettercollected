"""Per-key checks of secret values (``common.settings.secret_checks``) and how
the registry applies them: writers refuse weak or malformed key material,
readers (a registry built without the checks) never refuse a stored row."""

import base64
import os
import secrets

import pytest

from common.settings import inventory
from common.settings import secret_checks as sc
from common.settings.registry import Registry, SettingSpec, Tier, ValidationError


def fernet() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


# ----------------------------------------------------------------- token


@pytest.mark.parametrize(
    "value",
    [secrets.token_hex(32), secrets.token_urlsafe(48), "stable-strong-secret-value-0123456789abcdef"],
    # ids name the kind, never the value (the values are random)
    ids=["token-hex-32", "token-urlsafe-48", "operator-chosen"],
)
def test_token_accepts_what_the_deploy_scripts_and_operators_generate(value):
    assert sc.check_token(value) is None


@pytest.mark.parametrize(
    "value, code",
    [
        ("abc", "too_short"),
        ("12345678", "too_short"),
        ("a" * 31, "too_short"),
        ("random_api_key", "placeholder"),
        ("changeme", "placeholder"),
        ("k" * 40, "low_entropy"),
        ("ab" * 20, "low_entropy"),
        ("0123456789" * 4, "low_entropy"),
        ("aaaaaaaaaaaaaaaabbbbbbbbbbbbbbbb", "low_entropy"),
    ],
)
def test_token_refuses_weak_values_with_a_code(value, code):
    problem = sc.check_token(value)
    assert problem is not None and problem[0] == code
    assert value not in problem[1]  # the message never echoes the value


# ---------------------------------------------------------------- fernet


def test_fernet_accepts_a_real_key_and_what_openssl_makes():
    assert sc.check_fernet(fernet()) is None
    padded = base64.b64encode(os.urandom(32)).decode().replace("+", "-").replace("/", "_")
    assert sc.check_fernet(padded) is None  # deploy/generate-secrets.sh's shape


@pytest.mark.parametrize(
    "value",
    ["notafernetkey", "", "AAAA", base64.urlsafe_b64encode(b"x" * 31).decode(), base64.urlsafe_b64encode(b"x" * 33).decode()],
)
def test_fernet_refuses_malformed_keys(value):
    assert sc.check_fernet(value)[0] == "not_fernet"


def test_fernet_refuses_a_key_of_nearly_identical_bytes():
    zero = base64.urlsafe_b64encode(bytes(32)).decode()
    assert sc.check_fernet(zero)[0] == "low_entropy"
    assert sc.check_fernet(base64.urlsafe_b64encode(b"ab" * 16).decode())[0] == "low_entropy"


# ----------------------------------------------------------- pairs, lists


def test_key_pairs():
    assert sc.check_key_pairs("app_123:" + secrets.token_hex(16)) is None
    assert sc.check_key_pairs("1:" + secrets.token_hex(16) + ",2:" + secrets.token_hex(16)) is None
    for bad in ("", "nocolon", ":secret0123456789abcdef", "id:short", "id:has space 0123456789abc",
                "a:" + "s" * 20 + ",a:" + "t" * 20, "bad id:" + "s" * 20, "a:" + "s" * 20 + ","):
        assert sc.check_key_pairs(bad)[0] == "bad_pairs", bad


def test_secret_list_is_one_or_two_secrets():
    one, two = secrets.token_hex(16), secrets.token_hex(16)
    assert sc.check_secret_list(one) is None and sc.check_secret_list(f"{one},{two}") is None
    for bad in ("", "short", f"{one},{two},{one}", f"{one},", f"{one}, {two}"):
        assert sc.check_secret_list(bad)[0] == "bad_list", bad


# ---------------------------------------------------------- identity key


def test_an_identity_key_is_hex_or_base64_of_at_least_32_random_bytes():
    import base64

    raw = secrets.token_bytes(32)
    for good in (raw.hex(), base64.b64encode(raw).decode(), base64.urlsafe_b64encode(raw).decode(),
                 secrets.token_hex(64), f" {raw.hex()}\n"):
        assert sc.check_identity_key(good) is None, good[:4]
        assert sc.decode_identity_key(good) is not None
    assert sc.decode_identity_key(raw.hex()) == raw  # hex first: `openssl rand -hex 32` means its bytes


def test_a_short_alike_or_placeholder_identity_key_is_refused():
    for bad, code in (
        ("", "not_identity_key"),
        ("short", "not_identity_key"),
        (secrets.token_hex(31), "not_identity_key"),  # 31 bytes
        (secrets.token_hex(16), "not_identity_key"),
        ("ab" * 32, "not_identity_key"),  # 32 bytes, two values
        ("a" * 64, "not_identity_key"),
        ("changeme", "placeholder"),
        ("z" * 70, "not_identity_key"),  # neither hex nor base64 of enough variety
        ("0123456789abcdef" * 4, "not_identity_key"),  # a repeated block
        (bytes(range(32)).hex(), "not_identity_key"),  # a counting sequence
        (bytes(range(0, 64, 2)).hex(), "not_identity_key"),  # any arithmetic sequence
        (bytes(range(1, 33)).hex() + "0", "not_identity_key"),  # odd number of hex digits
        (bytes(i % 8 for i in range(33)).hex(), "not_identity_key"),  # 33 bytes of a few values
        ("correcthorsebatterystaplecorrecthorsebatterystaple", "not_identity_key"),  # a base64-valid passphrase
    ):
        problem = sc.check_identity_key(bad)
        assert problem is not None and problem[0] == code, bad
        assert bad.strip() not in problem[1] or not bad.strip()  # never echoes the value


def test_the_decode_rules_are_fixed():
    """Hex first (even length, either case); else standard or url-safe base64
    with optional padding; the decoded bytes are the key."""
    import base64

    raw = secrets.token_bytes(32)
    assert sc.decode_identity_key(raw.hex().upper()) == raw
    assert sc.decode_identity_key(base64.b64encode(raw).decode().rstrip("=")) == raw
    assert sc.decode_identity_key(base64.urlsafe_b64encode(raw).decode().rstrip("=")) == raw
    # 64 hex digits are 32 bytes of hex, never 48 bytes of base64
    assert len(sc.decode_identity_key(raw.hex())) == 32
    assert sc.decode_identity_key(raw.hex() + "0") is None


# --------------------------------------------------------------- registry


def _spec(key="AUTH_JWT_SECRET", fmt="token"):
    return SettingSpec(key, section="auth_keys", readers=("backend",), is_secret=True, tier=Tier.T4, format=fmt)


def test_writers_refuse_and_readers_accept():
    never_problems = lambda key, value: []  # noqa: E731
    writer = Registry([_spec()], secret_problems=never_problems, format_checks=sc.FORMAT_CHECKS)
    reader = Registry([_spec()], secret_problems=never_problems)
    with pytest.raises(ValidationError) as err:
        writer.validate("AUTH_JWT_SECRET", "abc")
    assert err.value.reason == "too_short"
    assert reader.validate("AUTH_JWT_SECRET", "abc") == "abc"  # an older stored value still loads
    assert writer.validate("AUTH_JWT_SECRET", secrets.token_hex(32))


def test_a_format_nobody_can_check_fails_closed_for_writers():
    writer = Registry(
        [_spec("MASTER_ENCRYPTION_KEYSET", "tink_keyset")],
        secret_problems=lambda k, v: [],
        format_checks=sc.FORMAT_CHECKS,  # no tink check supplied
    )
    with pytest.raises(ValidationError) as err:
        writer.validate("MASTER_ENCRYPTION_KEYSET", "anything-long-enough-0123456789")
    assert err.value.reason == "no_secret_check"


def test_formats_belong_to_the_right_kind_of_setting():
    with pytest.raises(Exception):
        SettingSpec("SOME_TEXT", section="misc", readers=("backend",), format="token")  # not a secret
    with pytest.raises(Exception):
        _spec(fmt="host")  # a plain format on a secret
    with pytest.raises(Exception):
        _spec(fmt="nope")


def test_the_inventory_names_a_format_for_exactly_the_key_material():
    with_format = {s.key: s.format for s in inventory.INVENTORY if s.is_secret and s.format}
    assert with_format == {
        "AUTH_JWT_SECRET": "token",
        "AUTH_AES_HEX_KEY": "fernet",
        "AUTH_INTERNAL_NOTIFY_KEY": "token",
        "TEMPORAL_API_KEY": "token",
        "MASTER_ENCRYPTION_KEYSET": "tink_keyset",
        "CUSTOM_DOMAIN_ASSERTION_KEYS": "key_pairs",
        "CUSTOM_DOMAIN_WEBHOOK_SECRETS": "secret_list",
        "RESPONDENT_IDENTITY_KEY": "identity_key",
    }
    assert set(with_format.values()) <= sc.SECRET_FORMATS


def test_the_actions_executor_reads_no_key_material():
    """It runs user-authored code: no key material is registered for it."""
    offenders = {s.key for s in inventory.all_specs() if s.is_secret and inventory.EXECUTOR in s.readers}
    # its own database login and monitoring key only; no signing or encryption key
    assert offenders <= {"DATABASE_URL", "ELASTIC_APM_API_KEY"}
    for key in ("AUTH_AES_HEX_KEY", "API_KEY", "AES_HEX_KEY", "AUTH_JWT_SECRET", "TEMPORAL_API_KEY"):
        spec = next(s for s in inventory.all_specs() if s.key == key)
        assert inventory.EXECUTOR not in spec.readers, key


# ----------------------------------------------- a retired reader in older rows


def test_rows_written_before_a_reader_was_retired_are_still_accepted():
    """AUTH_AES_HEX_KEY rows written while the actions executor was a registered
    reader list it; readers must not refuse them as a changed spec."""
    from settings_support import MASTER, MOMENT

    from common.settings.canonical import SettingRow
    from common.settings.keys import SectionKeys
    from common.settings.registry import default_registry
    from common.settings.signing import MonotonicTracker
    from common.settings.snapshot import FakeSnapshot, verify_snapshot

    keys = SectionKeys(MASTER, sections=["auth_keys"])
    key = "AUTH_AES_HEX_KEY"

    def row(readers):
        return SettingRow(
            key=key, section="auth_keys", readers=readers, is_secret=True, reload_class="R",
            version=1, updated_at=MOMENT, blob=keys.seal("auth_keys", key, 1, fernet()),
        )

    registry = default_registry()
    old = ("actions_executor", "auth", "backend", "google", "temporal_worker")
    snap = FakeSnapshot.build([row(old)], keys, revision=2)
    result = verify_snapshot(
        snap.rows(), snap.manifest(), keys, MonotonicTracker(), registry=registry, service="backend"
    )
    assert key in result.accepted and result.rejections == []
    # a name that was never a reader is still a changed spec
    snap = FakeSnapshot.build([row(("auth", "backend", "intruder"))], keys, revision=2)
    result = verify_snapshot(
        snap.rows(), snap.manifest(), keys, MonotonicTracker(), registry=registry, service="backend"
    )
    assert {(r.key, r.reason) for r in result.rejections} == {(key, "spec_mismatch")}
    # and the executor itself is not a reader of the current key
    assert inventory.EXECUTOR not in registry.get(key).readers
    assert registry.get(key).retired_readers == (inventory.EXECUTOR,)
