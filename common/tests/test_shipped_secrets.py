"""The services refuse signing and encryption keys that are unset or public."""

import base64
import hashlib
import re
from pathlib import Path

import pytest

from common.configs.shipped_secrets import (
    SHIPPED_SECRET_SHA256,
    InsecureSecretError,
    is_shipped_secret,
    normalize_secret,
    require_secrets,
    secret_problems,
)

REPO = Path(__file__).resolve().parents[2]
GOOD_JWT = "a" * 64
GOOD_FERNET = base64.urlsafe_b64encode(b"k" * 32).decode()
# Stands in for a published value: the real ones are only known by their hash.
PUBLISHED = "published-in-an-old-readme"
DENYLIST = SHIPPED_SECRET_SHA256 | {hashlib.sha256(PUBLISHED.encode()).hexdigest()}


def _require(jwt, fernet):
    require_secrets(
        "test service",
        jwt_secrets={"AUTH_JWT_SECRET": jwt},
        fernet_keys={"AUTH_AES_HEX_KEY": fernet},
        denylist=DENYLIST,
    )


def test_own_values_pass():
    _require(GOOD_JWT, GOOD_FERNET)


@pytest.mark.parametrize("empty", [None, "", "   ", "''", '""'])
def test_empty_values_are_refused(empty):
    with pytest.raises(InsecureSecretError) as error:
        _require(empty, empty)
    message = str(error.value)
    assert "AUTH_JWT_SECRET is not set" in message
    assert "AUTH_AES_HEX_KEY is not set" in message
    assert "openssl rand -hex 32" in message


@pytest.mark.parametrize("quoted", [PUBLISHED, f"'{PUBLISHED}'", f' "{PUBLISHED}" '])
def test_published_values_are_refused_quoted_or_not(quoted):
    with pytest.raises(InsecureSecretError) as error:
        _require(quoted, GOOD_FERNET)
    message = str(error.value)
    assert "AUTH_JWT_SECRET is a value that was published" in message
    assert "AUTH_AES_HEX_KEY is" not in message
    assert PUBLISHED not in message


def test_malformed_fernet_key_is_refused():
    problems = secret_problems(fernet_keys={"AES_HEX_KEY": "not-a-fernet-key"})
    assert problems == ["AES_HEX_KEY is not a Fernet key (32 bytes, url-safe base64)"]


def test_the_message_never_contains_the_values():
    other = base64.urlsafe_b64encode(b"x" * 31).decode()
    with pytest.raises(InsecureSecretError) as error:
        _require(PUBLISHED, other)
    assert PUBLISHED not in str(error.value)
    assert other not in str(error.value)


def test_normalize_secret():
    assert normalize_secret("  'abc'  ") == "abc"
    assert normalize_secret('"abc"') == "abc"
    assert normalize_secret("'abc") == "'abc"
    assert normalize_secret(None) == ""


def test_ci_test_values_are_not_on_the_denylist():
    """CI's own values were never in a deployment file; tests keep using them."""
    ci = (REPO / ".github/workflows/ci.yml").read_text()
    for name in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY"):
        values = set(re.findall(rf"^\s+{name}:\s*\"?([^\"\s]+)\"?\s*$", ci, re.M))
        assert values, name
        for value in values:
            assert not is_shipped_secret(value), name


def test_denylist_holds_sha256_digests_only():
    assert len(SHIPPED_SECRET_SHA256) == 8
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in SHIPPED_SECRET_SHA256)


@pytest.mark.parametrize("service", ["worker", "actions-executor"])
def test_temporal_copies_are_identical(service):
    """The Temporal workers do not depend on common; they carry this file."""
    original = (REPO / "common/common/configs/shipped_secrets.py").read_text()
    copy = REPO / "temporal" / service / "settings" / "shipped_secrets.py"
    assert copy.read_text() == original


def test_deploy_script_carries_the_same_denylist():
    script = (REPO / "deploy/generate-secrets.sh").read_text()
    listed = set(re.findall(r"^([0-9a-f]{64})$", script, re.M))
    assert listed == set(SHIPPED_SECRET_SHA256)


def test_no_tracked_example_file_still_holds_a_published_value():
    """The files that once shipped them: any assignment of these keys there
    must be empty or a placeholder now."""
    names = r"(?:AUTH_JWT_SECRET|AUTH_AES_HEX_KEY|AES_HEX_KEY|GOOGLE_AES_KEY)"
    still_published = [
        path
        for path in (".env.deployment", "webapp/README.md")
        if any(
            is_shipped_secret(value)
            for value in re.findall(
                rf"{names}\s*[=:]\s*(\S+)", (REPO / path).read_text()
            )
        )
    ]
    assert still_published == []
