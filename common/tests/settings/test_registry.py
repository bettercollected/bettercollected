import pytest

from common.configs import shipped_secrets
from common.settings.registry import (
    ENV_ONLY_KEYS,
    SEED_SPECS,
    Registry,
    RegistryError,
    Reload,
    SettingSpec,
    Tier,
    UnknownKeyError,
    ValidationError,
    ValueType,
    default_registry,
    normalize_value,
)


def strict(key, raw):
    problems = shipped_secrets.secret_problems(jwt_secrets={key: raw})
    return problems


@pytest.fixture
def reg():
    return default_registry(secret_problems=strict)


# ---------------------------------------------------------------- consistency


def test_seed_specs_are_consistent_and_complete():
    registry = default_registry()
    assert len(registry) == len(SEED_SPECS) >= 15
    assert len({s.key for s in SEED_SPECS}) == len(SEED_SPECS)
    for spec in registry:
        assert spec.storable and spec.key not in ENV_ONLY_KEYS
        assert spec.readers and spec.description
        if spec.tier is Tier.T4 or spec.is_secret:
            assert spec.reload_class is not Reload.H
        if spec.is_secret:
            assert spec.type is ValueType.STR and spec.default is None
        if spec.type is ValueType.URL:
            assert spec.tier is Tier.T3
        if spec.reload_class is Reload.H:
            assert spec.tier in (Tier.T1, Tier.T2)
    kinds = {(s.reload_class, s.tier) for s in registry}
    assert (Reload.H, Tier.T1) in kinds and (Reload.R, Tier.T3) in kinds
    assert registry.get("AUTH_JWT_SECRET").tier is Tier.T4
    assert registry.get("AI_COMPAT_BASE_URL").type is ValueType.URL


def test_seed_defaults_validate():
    registry = default_registry()
    for spec in registry:
        if spec.default is not None:
            assert registry.coerce(spec.key, spec.default) == spec.default


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(tier=Tier.T4, is_secret=True, reload_class=Reload.H),
        dict(is_secret=True, tier=Tier.T3, reload_class=Reload.H),
        dict(tier=Tier.T4),  # T4 but not secret
        dict(is_secret=True, tier=Tier.T1),
        dict(is_secret=True, tier=Tier.T3, type=ValueType.INT),
        dict(is_secret=True, tier=Tier.T3, default="x"),
        dict(type=ValueType.ENUM),
        dict(choices=("a",)),
        dict(internal_ok=True),
        dict(type=ValueType.URL),  # needs T3
        dict(type=ValueType.INT, min_value=5, max_value=1),
        dict(type=ValueType.STR, min_value=1),
        dict(type=ValueType.INT, default="abc"),
        dict(type=ValueType.INT, default=0, min_value=1),
        dict(type=ValueType.URL, tier=Tier.T3, default="http://x.example"),
        dict(readers=()),
        dict(readers=("backend", "backend")),
        dict(readers=("Backend",)),
        dict(section="Bad Section"),
        dict(key="lower"),
    ],
)
def test_inconsistent_specs_are_refused(kwargs):
    base = dict(key="SOME_KEY", section="misc", readers=("backend",))
    base.update(kwargs)
    with pytest.raises(RegistryError):
        SettingSpec(**base)


def test_t5_and_env_only_keys_cannot_be_store_keys():
    registry = Registry()
    t5 = SettingSpec("SOME_KEY", "misc", ("backend",), tier=Tier.T5)
    assert not t5.storable
    with pytest.raises(RegistryError):
        registry.register(t5)
    for key in ("DATABASE_URL", "SETTINGS_MASTER_KEY", "ADMIN_DATABASE_URL", "JOBS_X"):
        with pytest.raises(RegistryError):
            registry.register(SettingSpec(key, "misc", ("backend",)))
    ok = SettingSpec("SOME_KEY", "misc", ("backend",))
    registry.register(ok)
    with pytest.raises(RegistryError):
        registry.register(ok)  # twice


def test_lookup_and_reader_views(reg):
    assert "SSO_ENABLED" in reg and "NOPE" not in reg
    assert reg.get("SSO_ENABLED").reload_class is Reload.R
    assert "AUTH_JWT_SECRET" in {s.key for s in reg.for_reader("google")}
    assert "MAIL_PASSWORD" not in {s.key for s in reg.for_reader("google")}
    with pytest.raises(UnknownKeyError):
        reg.get("NOPE")
    assert reg.keys() == tuple(sorted(reg.keys()))


# ---------------------------------------------------------------- validation


def test_unknown_keys_are_rejected(reg):
    for key in ("NOPE", "", None, "DATABASE_URL"):
        with pytest.raises(ValidationError) as raised:
            reg.validate(key, "x")
        assert raised.value.reason == "unknown_key"


@pytest.mark.parametrize(
    "key,raw,expected",
    [
        ("AI_PROMPT_MAX_LENGTH", "4000", 4000),
        ("AI_PROMPT_MAX_LENGTH", 4000, 4000),
        ("AI_PROMPT_MAX_LENGTH", " 12 ", 12),
        ("SSO_ENABLED", "TRUE", True),
        ("SSO_ENABLED", "0", False),
        ("SSO_ENABLED", False, False),
        ("AI_DEFAULT_PROVIDER", "compat", "compat"),
        ("MAIL_SMTP_PORT", "465", 465),
        ("MAIL_SMTP_SERVER", "smtp.example.org", "smtp.example.org"),
    ],
)
def test_typed_values(reg, key, raw, expected):
    value = reg.validate(key, raw)
    assert value == expected and type(value) is type(expected)


@pytest.mark.parametrize(
    "key,raw,reason",
    [
        ("AI_PROMPT_MAX_LENGTH", "0", "out_of_range"),
        ("AI_PROMPT_MAX_LENGTH", "100001", "out_of_range"),
        ("AI_PROMPT_MAX_LENGTH", "12.5", "not_number"),
        ("AI_PROMPT_MAX_LENGTH", 12.5, "not_number"),
        ("AI_PROMPT_MAX_LENGTH", True, "not_number"),
        ("AI_PROMPT_MAX_LENGTH", "abc", "not_number"),
        ("MAIL_SMTP_PORT", "70000", "out_of_range"),
        ("SSO_ENABLED", "maybe", "not_bool"),
        ("SSO_ENABLED", 1, "not_bool"),
        ("AI_DEFAULT_PROVIDER", "Compat", "not_a_choice"),
        ("AI_DEFAULT_PROVIDER", "other", "not_a_choice"),
        ("MAIL_SMTP_SERVER", "a\nb", "control_characters"),
        ("MAIL_SMTP_SERVER", "x" * 9000, "too_long"),
        ("MAIL_SMTP_SERVER", 5, "not_string"),
    ],
)
def test_refused_values(reg, key, raw, reason):
    with pytest.raises(ValidationError) as raised:
        reg.validate(key, raw)
    assert raised.value.reason == reason
    assert key in str(raised.value)


def test_float_and_json_types():
    registry = Registry(
        [
            SettingSpec("RATIO", "misc", ("backend",), type=ValueType.FLOAT, min_value=0, max_value=1),
            SettingSpec("RULES", "misc", ("backend",), type=ValueType.JSON),
        ]
    )
    assert registry.validate("RATIO", "0.25") == 0.25
    for bad in ("nan", "inf", "2", "-1", "x"):
        with pytest.raises(ValidationError):
            registry.validate("RATIO", bad)
    assert registry.validate("RULES", '{"a": [1, 2]}') == {"a": [1, 2]}
    assert registry.validate("RULES", [1]) == [1]
    for bad in ("{", "5", '"s"', "null", "NaN"):
        with pytest.raises(ValidationError):
            registry.validate("RULES", bad)


def test_error_messages_never_contain_the_value(reg):
    needle = "needle-value-123"
    for key in ("AI_PROMPT_MAX_LENGTH", "SSO_ENABLED", "AI_COMPAT_BASE_URL",
                "AI_DEFAULT_PROVIDER"):
        with pytest.raises(ValidationError) as raised:
            reg.validate(key, needle)
        assert needle not in str(raised.value)


# ---------------------------------------------------------------- secrets


def test_secrets_pass_the_pluggable_check(reg):
    good = "a1" * 32
    assert reg.validate("AUTH_JWT_SECRET", good) == good
    published = "x"
    digests = {__import__("hashlib").sha256(published.encode()).hexdigest()}
    registry = default_registry(
        secret_problems=lambda k, v: shipped_secrets.secret_problems(
            jwt_secrets={k: v}, denylist=digests
        )
    )
    with pytest.raises(ValidationError) as raised:
        registry.validate("AUTH_JWT_SECRET", published)
    assert raised.value.reason == "weak_secret" and published != str(raised.value)


def test_fernet_checks_can_be_plugged_in_per_key():
    def check(key, value):
        keys = {key: value}
        if key == "AUTH_AES_HEX_KEY":
            return shipped_secrets.secret_problems(fernet_keys=keys)
        return shipped_secrets.secret_problems(jwt_secrets=keys)

    registry = default_registry(secret_problems=check)
    with pytest.raises(ValidationError):
        registry.validate("AUTH_AES_HEX_KEY", "not-a-fernet-key")
    key = "".join(["MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="])
    assert registry.validate("AUTH_AES_HEX_KEY", key) == key


@pytest.mark.parametrize(
    "raw", ["", " padded ", "'quoted'", '"quoted"', "\ttab", "new\nline"]
)
def test_secret_shape(reg, raw):
    with pytest.raises(ValidationError):
        reg.validate("MAIL_PASSWORD", raw)


def test_a_secret_without_a_configured_check_is_refused():
    with pytest.raises(ValidationError) as raised:
        default_registry().validate("MAIL_PASSWORD", "fine-value-1234")
    assert raised.value.reason == "no_secret_check"


def test_normalisation_matches_shipped_secrets():
    for raw in (None, "", "  ", "x", " x ", "'x'", '"x"', "' x '", "''", "'x\"", "a'b'", "\"'x'\""):
        assert normalize_value(raw) == shipped_secrets.normalize_secret(raw)


# ---------------------------------------------------------------- URLs

URL_CASES = [
    # (value, ok_when_https_only)
    ("https://api.example.org/v1", True),
    ("https://api.example.org:8443/v1?x=1", True),
    ("https://8.8.8.8/v1", True),
    ("https://[2001:4860:4860::8888]/", True),
    ("http://api.example.org", False),
    ("ftp://api.example.org", False),
    ("//api.example.org", False),
    ("api.example.org", False),
    ("https://", False),
    ("https://127.0.0.1/", False),
    ("https://127.0.0.1:9000/", False),
    ("https://127.9.9.9/", False),
    ("https://[::1]/", False),
    ("https://[::]/", False),
    ("https://0.0.0.0/", False),
    ("https://169.254.169.254/latest/meta-data", False),
    ("https://169.254.1.1/", False),
    ("https://100.100.100.200/", False),
    ("https://[fd00::1]/", False),
    ("https://[fd00:ec2::254]/", False),
    ("https://[fe80::1]/", False),
    ("https://[::ffff:127.0.0.1]/", False),
    ("https://[::ffff:7f00:1]/", False),
    ("https://[::ffff:169.254.169.254]/", False),
    ("https://10.0.0.5/", False),
    ("https://192.168.1.1/", False),
    ("https://172.16.0.1/", False),
    ("https://224.0.0.1/", False),
    ("https://localhost/", False),
    ("https://LOCALHOST:8080/", False),
    ("https://localhost./", False),
    ("https://app.localhost/", False),
    ("https://metadata.google.internal/computeMetadata/v1/", False),
    ("https://user@api.example.org/", False),
    ("https://user:pw@api.example.org/", False),
    ("https://:pw@api.example.org/", False),
    ("https://api.example.org@127.0.0.1/", False),
    ("https://2130706433/", False),  # decimal
    ("https://0x7f000001/", False),  # hex
    ("https://0x7f.0.0.1/", False),
    ("https://0177.0.0.1/", False),  # octal
    ("https://127.1/", False),  # short form
    ("https://127.0.1/", False),
    ("https://017700000001/", False),
    ("https://api.example.org:99999/", False),
    ("https://api.example.org:abc/", False),
    ("https://api.example.org/ x", False),
    (" https://api.example.org/", False),
    ("https://api.example.org/\n", False),
]


@pytest.mark.parametrize("value,ok", URL_CASES)
def test_url_rules_for_an_external_endpoint(reg, value, ok):
    if ok:
        assert reg.validate("AI_COMPAT_BASE_URL", value) == value
    else:
        with pytest.raises(ValidationError):
            reg.validate("AI_COMPAT_BASE_URL", value)


INTERNAL_OK = {
    "http://polis:5225",
    "http://polis:5225/path",
    "https://polis.internal.example/",
    "http://10.1.2.3:5225",  # compose network address
    "http://172.18.0.4:5225",
    "http://[fd12:3456::1]:5225",
}


@pytest.mark.parametrize("value", sorted(INTERNAL_OK))
def test_internal_ok_allows_http_and_compose_hosts(reg, value):
    assert reg.validate("SSO_POLIS_INTERNAL_URL", value) == value


@pytest.mark.parametrize(
    "value",
    [
        "http://localhost:5225",
        "http://127.0.0.1:5225",
        "http://[::1]:5225",
        "http://[::ffff:127.0.0.1]:5225",
        "http://0.0.0.0:5225",
        "http://169.254.169.254/",
        "http://[fe80::1]/",
        "http://[fd00:ec2::254]/",
        "http://metadata.google.internal/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://0177.0.0.1/",
        "http://user@polis:5225",
        "http://user:pw@polis:5225",
        "ftp://polis",
        "polis:5225",
        "http://polis:99999",
    ],
)
def test_internal_ok_still_refuses_loopback_metadata_and_userinfo(reg, value):
    with pytest.raises(ValidationError):
        reg.validate("SSO_POLIS_INTERNAL_URL", value)
