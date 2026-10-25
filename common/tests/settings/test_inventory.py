"""The settings inventory: every spec is consistent, every environment name a
service reads is classified, and the committed table is current."""

import ast
import os
import re
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
    RETIRED,
    full_registry,
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
NOT_READ_YET = frozenset(
    {
        "SETTINGS_MASTER_KEY_PREVIOUS",
        "SETTINGS_STORE",
        # the admin sign-in mail section: saved by the host CLI first, read by the portal later
        *(
            f"ADMIN_MAIL_{n}"
            for n in (
                "USER", "PASSWORD", "SMTP_SERVER", "SMTP_PORT", "SENDER",
                "STARTTLS", "SSL_TLS", "USE_CREDENTIALS", "VALIDATE_CERTS",
            )
        ),
    }
)


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


ANCHOR = re.compile(r"^(?P<path>[\w./-]+\.py)::(?P<qualname>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)$")


def _symbol(tree: ast.Module, qualname: str) -> ast.AST:
    """The module or class level function, class or assignment named by the
    dotted ``qualname`` (no local variables); exactly one must match."""
    body, node = tree.body, None
    for i, part in enumerate(qualname.split(".")):
        found = []
        for child in body:
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name == part:
                    found.append(child)
            elif isinstance(child, (ast.Assign, ast.AnnAssign)) and (
                node is None or isinstance(node, ast.ClassDef)
            ):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                if any(isinstance(t, ast.Name) and t.id == part for t in targets):
                    found.append(child)
        assert len(found) == 1, f"{qualname}: {len(found)} symbols named {part!r}"
        node = found[0]
        body = getattr(node, "body", [])
        if i < len(qualname.split(".")) - 1:
            assert isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)), qualname
    return node


def _reads(node: ast.AST, key: str) -> bool:
    """Whether the code of ``node`` (decorators included, docstrings and
    comments not) reads ``key``: as the string ``key`` or as an attribute or
    name that is the key or the key without leading prefixes (a prefixed
    settings field: ``api_settings.ROOT_PATH`` reads ``API_ROOT_PATH``)."""
    parts = key.split("_")
    names = {"_".join(parts[i:]) for i in range(len(parts))}
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr in names:
            return True
        if isinstance(sub, ast.Name) and sub.id in names:
            return True
        if isinstance(sub, ast.Constant) and sub.value == key:
            return True
    return False


def _check_anchor(key: str, where: str, root: Path = ROOT) -> None:
    match = ANCHOR.match(where)
    assert match, f"{key}: {where!r} is not path::qualname"
    path = root / match["path"]
    assert path.is_file(), f"{key}: {match['path']} does not exist"
    tree = ast.parse(path.read_text(), filename=str(path))
    try:
        node = _symbol(tree, match["qualname"])
    except AssertionError as missing:
        raise AssertionError(f"{key}: {missing}") from None
    assert _reads(node, key), f"{key}: {where} does not read it"


@monorepo
def test_import_time_keys_name_a_symbol_that_reads_them():
    for key, where in TODO_LIVE.items():
        spec = next(s for s in INVENTORY if s.key == key)
        assert spec.reload_class is Reload.R, key
        _check_anchor(key, where)


def test_the_anchor_check_ignores_line_shifts_and_catches_a_removed_read(tmp_path):
    source = (
        "import settings\n\n\n"
        "class Box:\n"
        "    held = make(settings.aws.ACCESS_KEY_ID)\n\n"
        "    def sweep(self):\n"
        "        \"\"\"Mentions API_FLOW_EVENTS_RETENTION_DAYS only in prose.\"\"\"\n"
        "        return settings.api.FLOW_EVENTS_RETENTION_DAYS\n\n\n"
        "@app.periodic(cron=settings.scim.RECONCILE_CRON)\n"
        "def reconcile():\n"
        "    return os.environ.get(\"DB_ECHO\")\n"
    )
    anchors = {
        "AWS_ACCESS_KEY_ID": "pkg/mod.py::Box.held",
        "API_FLOW_EVENTS_RETENTION_DAYS": "pkg/mod.py::Box.sweep",
        "SCIM_RECONCILE_CRON": "pkg/mod.py::reconcile",
        "DB_ECHO": "pkg/mod.py::reconcile",
    }
    module = tmp_path / "pkg/mod.py"
    module.parent.mkdir()
    for text in (source, "\n\n# moved\n\n" + source.replace("    def", "\n\n    def")):
        module.write_text(text)
        for key, where in anchors.items():
            _check_anchor(key, where, tmp_path)

    removed = {
        "AWS_ACCESS_KEY_ID": source.replace("settings.aws.ACCESS_KEY_ID", "None"),
        "API_FLOW_EVENTS_RETENTION_DAYS": source.replace(
            "settings.api.FLOW_EVENTS_RETENTION_DAYS", "30"
        ),
        "SCIM_RECONCILE_CRON": source.replace("settings.scim.RECONCILE_CRON", '"0 3 * * *"'),
    }
    for key, text in removed.items():
        module.write_text(text)
        with pytest.raises(AssertionError, match="does not read it"):
            _check_anchor(key, anchors[key], tmp_path)
    module.write_text(source.replace("def sweep", "def swept"))
    key = "API_FLOW_EVENTS_RETENTION_DAYS"
    with pytest.raises(AssertionError, match="0 symbols"):
        _check_anchor(key, anchors[key], tmp_path)
    with pytest.raises(AssertionError, match="not path::qualname"):
        _check_anchor("DB_ECHO", "pkg/mod.py:12", tmp_path)
    with pytest.raises(AssertionError, match="0 symbols"):
        _check_anchor("DB_ECHO", "pkg/mod.py::reconcile.value", tmp_path)


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
        or name in RETIRED
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
    # GOOGLE_MONGO_DB: nothing reads it since 4.1 (the keyset and purge tasks cover
    # Postgres alone); the task-runner entry in docker-compose.deployment.yml still
    # names it, and goes with its note here
    exempt = {"NODE_ENV", "BC_RENDER_MAX_SIDE", "GOOGLE_MONGO_DB"}
    stale = sorted(n for n in NOT_A_SETTING if n not in seen and n not in exempt)
    assert not stale, f"NOT_A_SETTING names nothing lists any more: {stale}"


def test_retired_keys_are_not_settings_and_are_ignored_by_the_full_registry():
    keys = {s.key for s in all_specs()}
    assert RETIRED and not set(RETIRED) & (keys | set(ALIASES) | set(NOT_A_SETTING))
    assert default_registry().retired == frozenset(RETIRED)
    # Typeform (removed in 4.1): every name it used is retired, none is live
    assert {"TYPEFORM_CLIENT_ID", "TYPEFORM_CLIENT_SECRET", "TYPEFORM_ENABLED"} <= set(RETIRED)
    assert not any(k.startswith("TYPEFORM_") for k in keys)
    with pytest.raises(RegistryError):
        Registry([next(iter(INVENTORY))], retired=(next(iter(INVENTORY)).key,))


# The marketing tracker (Brevo) is removed; deployments may still set its three
# variables (or hold rows for them in the store) until the operator drops them.
BREVO_KEYS = {"BREVO_TRACKER_KEY", "BREVO_TRACKER_API_URL", "BREVO_CONTACTS_API_KEY"}


def test_the_former_marketing_tracker_keys_are_retired_not_settings():
    assert BREVO_KEYS <= set(RETIRED)
    assert not any(s.key.startswith("BREVO_") for s in all_specs())
    assert BREVO_KEYS <= full_registry().retired
    for key in BREVO_KEYS:
        assert _classified(key)


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


# ------------------------------------------------------------ resolver addresses


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "1.1.1.1",
        "1.1.1.1,9.9.9.9",
        " 1.1.1.1 ,  9.9.9.9 ",
        "2606:4700:4700::1111",
        "1.1.1.1, 2620:fe::fe",
    ],
)
def test_nameservers_accept_ip_addresses(raw):
    reg = inventory.full_registry()
    assert reg.validate("VERIFIED_DOMAINS_NAMESERVERS", raw) == raw
    assert reg.coerce("VERIFIED_DOMAINS_NAMESERVERS", raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        "dns.google",
        "1.1.1.1,dns.quad9.net",
        "1.1.1.1;9.9.9.9",
        "1.1.1.1 9.9.9.9",
        "1.1.1.1,",
        "1.1.1.1,,9.9.9.9",
        "1.1.1.1:53",
        "[2606:4700:4700::1111]",
        "10.0.0.0/8",
        "https://dns.google/dns-query",
        "fe80::1%eth0",
        ",".join(["1.1.1.1"] * 17),
    ],
)
def test_nameservers_refuse_names_and_other_separators(raw):
    reg = inventory.full_registry()
    for check in (reg.validate, reg.coerce):
        with pytest.raises(ValidationError) as raised:
            check("VERIFIED_DOMAINS_NAMESERVERS", raw)
        assert raised.value.reason == "bad_ip_list"
        assert str(raised.value).startswith("VERIFIED_DOMAINS_NAMESERVERS: ")
