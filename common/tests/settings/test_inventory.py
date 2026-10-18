"""The settings inventory: every spec is consistent, every environment name a
service reads is classified, and the committed table is current."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import env_scan
from common.configs import settings_registry
from common.settings import inventory
from common.settings.inventory import (
    ALIASES,
    ENV_ONLY_INVENTORY,
    INVENTORY,
    NOT_A_SETTING,
    NOT_A_SETTING_PREFIXES,
    READERS,
    TODO_LIVE,
    all_specs,
)
from common.settings.registry import (
    ENV_ONLY_KEYS,
    Registry,
    RegistryError,
    Reload,
    Tier,
    ValidationError,
    ValueType,
    default_registry,
    is_env_only,
)

ROOT = env_scan.ROOT
HAS_MONOREPO = (ROOT / "backend/backend/config").is_dir()
monorepo = pytest.mark.skipif(not HAS_MONOREPO, reason="needs the whole repository")

# Keys the consumers read at call time, each proven by a test in
# backend/tests/app/services/test_live_settings_reads.py. Changing this set
# means changing that test.
HOT_KEYS = frozenset(
    {
        "API_FLOW_EVENTS_PER_WINDOW",
        "API_FLOW_EVENTS_WINDOW_SECONDS",
        "API_PUBLIC_API_REQUESTS_PER_WINDOW",
        "API_PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW",
        "API_PUBLIC_API_WINDOW_SECONDS",
        "API_IMAGE_PROXY_PER_WINDOW",
        "API_IMAGE_PROXY_FETCHES_PER_WINDOW",
        "API_IMAGE_PROXY_WINDOW_SECONDS",
        "API_IMAGE_PROXY_GLOBAL_FETCHES_PER_WINDOW",
        "API_IMAGE_IMPORTS_PER_WINDOW",
        "API_IMAGE_IMPORTS_WINDOW_SECONDS",
        "API_EDITOR_OPS_SAVE_ENABLED",
        "API_EDITOR_OPS_PER_WINDOW",
        "API_EDITOR_OPS_WINDOW_SECONDS",
        "AI_RATE_LIMIT_WINDOW_SECONDS",
        "AI_RATE_LIMIT_PER_USER",
        "AI_RATE_LIMIT_PER_WORKSPACE",
        "AI_RATE_LIMIT_FIX_PER_USER",
        "AI_DAILY_REQUEST_BUDGET",
        "AI_DAILY_TOKEN_BUDGET",
    }
)

# Registered ahead of the code that reads them (the store loader).
NOT_READ_YET = frozenset({"SETTINGS_MASTER_KEY_PREVIOUS", "SETTINGS_STORE"})


# ------------------------------------------------------------ consistency


def test_the_inventory_is_complete_in_size_and_unique():
    keys = [s.key for s in all_specs()]
    assert len(keys) == len(set(keys))
    assert len(INVENTORY) >= 150 and len(ENV_ONLY_INVENTORY) >= 50
    assert not set(keys) & set(ALIASES) and not set(keys) & set(NOT_A_SETTING)


def test_every_spec_has_known_readers_and_a_description():
    for spec in all_specs():
        assert set(spec.readers) <= READERS, spec.key
        assert spec.description and spec.description.endswith((".", ")")), spec.key
        assert len(spec.description) <= 160, spec.key


def test_stored_and_environment_only_keys_do_not_overlap():
    for spec in INVENTORY:
        assert spec.tier is not Tier.T5 and not is_env_only(spec.key), spec.key
    for spec in ENV_ONLY_INVENTORY:
        assert spec.tier is Tier.T5 and is_env_only(spec.key), spec.key
        reg = Registry()
        with pytest.raises(RegistryError):
            reg.register(spec)
    # every explicit environment-only key is documented
    assert ENV_ONLY_KEYS <= {s.key for s in ENV_ONLY_INVENTORY}


def test_key_material_and_secrets_are_never_hot():
    for spec in all_specs():
        if spec.tier is Tier.T4:
            assert spec.is_secret and spec.reload_class is Reload.R, spec.key
        if spec.is_secret:
            assert spec.reload_class is Reload.R and spec.default is None, spec.key
            assert spec.tier is not Tier.T1, spec.key
        if spec.reload_class is Reload.H:
            assert spec.tier in (Tier.T1, Tier.T2), spec.key


def test_urls_and_dangerous_settings_are_guarded():
    for spec in all_specs():
        if spec.type is ValueType.URL:
            assert spec.tier in (Tier.T3, Tier.T5), spec.key
        if spec.reload_class is Reload.B:
            assert spec.tier is Tier.T5, spec.key
    by_key = {s.key: s for s in INVENTORY}
    for key in ("SSO_ENABLED", "AI_COMPAT_BASE_URL", "MAIL_SMTP_SERVER", "MAIL_PASSWORD",
                "EVENT_WEBHOOK_URL", "SSO_REDIRECT_URI", "GOOGLE_REDIRECT_URIS", "MONGO_URI",
                "AWS_SECRET_ACCESS_KEY", "STRIPE_SECRET", "API_TRUSTED_PROXIES"):
        assert by_key[key].tier is Tier.T3, key
    for key in ("DEBUG", "RESPONSE_VALIDATION_ENFORCE", "AUTH_ACCESS_TOKEN_EXPIRY_IN_MINUTES",
                "AUTH_REFRESH_TOKEN_EXPIRY_IN_DAYS"):
        assert by_key[key].tier is Tier.T2, key
    for key in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "AUTH_INTERNAL_NOTIFY_KEY",
                "TEMPORAL_API_KEY", "MASTER_ENCRYPTION_KEYSET"):
        assert by_key[key].tier is Tier.T4, key


def test_defaults_validate_against_their_own_spec():
    reg = default_registry()
    for spec in INVENTORY:
        if spec.default is not None:
            assert reg.coerce(spec.key, spec.default) == spec.default, spec.key
    for spec in ENV_ONLY_INVENTORY:
        if spec.default is not None:
            from common.settings.registry import coerce_value

            assert coerce_value(spec, spec.default) == spec.default, spec.key


def test_the_default_registry_is_the_full_inventory():
    assert default_registry().keys() == tuple(sorted(s.key for s in INVENTORY))
    assert set(inventory.full_registry().keys()) == {s.key for s in INVENTORY}


def test_hot_keys_are_exactly_the_proven_set():
    assert {s.key for s in all_specs() if s.reload_class is Reload.H} == HOT_KEYS


def test_every_hot_key_is_a_proven_live_consumer():
    from common.settings.loader.proven import LIVE_PROVEN

    assert HOT_KEYS == LIVE_PROVEN


def test_every_hot_key_has_a_live_read_test():
    tests = ROOT / "backend/tests/app/services/test_live_settings_reads.py"
    if not tests.is_file():
        pytest.skip("needs the whole repository")
    text = tests.read_text()
    missing = sorted(key for key in HOT_KEYS if key not in text)
    assert not missing, f"no live-read test names {missing}"


@monorepo
def test_import_time_keys_name_a_real_line():
    for key, where in TODO_LIVE.items():
        spec = next(s for s in INVENTORY if s.key == key)
        assert spec.reload_class is Reload.R, key
        path, _, number = where.rpartition(":")
        line = (ROOT / path).read_text().splitlines()[int(number) - 1]
        parts = key.split("_")
        suffixes = ["_".join(parts[i:]) for i in range(1, len(parts))]
        assert any(s in line for s in suffixes), f"{key}: line {number} of {path} does not read it"


# --------------------------------------------------------------- secrets


def test_the_shipped_secret_check_is_wired_in():
    reg = settings_registry.default_registry()
    with pytest.raises(ValidationError) as placeholder:
        reg.validate("TEMPORAL_API_KEY", "random_api_key")
    assert placeholder.value.reason == "weak_secret"
    with pytest.raises(ValidationError) as malformed:
        reg.validate("AUTH_AES_HEX_KEY", "not-a-fernet-key")
    assert "Fernet" in str(malformed.value) and "not-a-fernet-key" not in str(malformed.value)
    good = "0123456789abcdef" * 4
    assert reg.validate("AUTH_JWT_SECRET", good) == good
    assert reg.validate("MAIL_PASSWORD", "fine-value-1234") == "fine-value-1234"


def test_the_pure_registry_has_no_secret_check_of_its_own():
    with pytest.raises(ValidationError) as caught:
        default_registry().validate("MAIL_PASSWORD", "fine-value-1234")
    assert caught.value.reason == "no_secret_check"


# ---------------------------------------------------------- completeness


def _classified(name: str) -> bool:
    return (
        name in {s.key for s in all_specs()}
        or name in ALIASES
        or name in NOT_A_SETTING
        or name.startswith(NOT_A_SETTING_PREFIXES)
        or is_env_only(name)
    )


@monorepo
def test_every_environment_name_a_service_reads_is_classified():
    unclassified = {n: w for n, w in env_scan.all_names().items() if not _classified(n)}
    assert not unclassified, (
        "classify these in common/common/settings/inventory.py (INVENTORY, "
        f"ENV_ONLY_INVENTORY, ALIASES or NOT_A_SETTING): {unclassified}"
    )


@monorepo
def test_every_spec_is_read_by_some_service():
    seen = set(env_scan.all_names())
    stale = sorted(
        s.key
        for s in all_specs()
        if s.key not in seen
        and s.key not in NOT_READ_YET
        and not s.key.startswith(("ADMIN_DB_ROLE_",))
    )
    assert not stale, f"specs no service reads or lists: {stale}"


@monorepo
def test_every_note_in_not_a_setting_is_still_listed_somewhere():
    seen = set(env_scan.all_names())
    stale = sorted(
        n for n in NOT_A_SETTING if n not in seen and n not in {"NODE_ENV", "BC_RENDER_MAX_SIDE"}
    )
    assert not stale, f"NOT_A_SETTING names nothing lists any more: {stale}"


@monorepo
def test_aliases_point_at_registered_keys_and_are_read():
    keys = {s.key for s in all_specs()}
    assert set(ALIASES.values()) <= keys
    assert set(ALIASES) <= set(env_scan.all_names())


@monorepo
def test_the_scanner_finds_what_it_should():
    names = env_scan.all_names()
    for expected in (
        "AI_RATE_LIMIT_PER_USER",  # prefixed pydantic field
        "TRUSTED_PROXIES",  # alias
        "DB_READ_SOURCE",  # key constant read through env.get
        "MAIL_STARTTLS",  # helper call
        "PORT",  # os.getenv with a bare name
        "MASTER_ENCRYPTION_KEYSET",  # *_ENV constant
        "CUSTOM_DOMAIN_ASSERTION_MODE",  # webapp process.env
        "JOBS_QUEUES",
    ):
        assert expected in names, expected


# ---------------------------------------------------------------- golden


def test_the_committed_table_is_current():
    path = ROOT / "docs/settings-inventory.md"
    if not path.is_file() and not HAS_MONOREPO:
        pytest.skip("needs the whole repository")
    assert path.read_text() == inventory.markdown(), (
        "run `uv run python -m common.settings.inventory --markdown > docs/settings-inventory.md`"
    )


def test_the_markdown_has_no_secret_defaults_and_every_key():
    text = inventory.markdown()
    for spec in all_specs():
        assert f"| `{spec.key}` |" in text
    for line in text.splitlines():
        if "| yes |" in line:
            assert line.rstrip().endswith("|  |"), line


def test_the_module_prints_the_table():
    done = subprocess.run(
        [sys.executable, "-m", "common.settings.inventory", "--markdown"],
        cwd=Path(inventory.__file__).parents[2],
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-500:]
    assert done.stdout == inventory.markdown()
