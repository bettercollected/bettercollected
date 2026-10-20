"""The Google Forms integration refuses to start without its own AUTH_JWT_SECRET and
AUTH_AES_HEX_KEY (common/configs/shipped_secrets.py)."""

import base64
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from common.services.keyset import (
    add_primary_key,
    encode_keyset,
    key_digest,
    only_primary,
    parse_keyset,
)

SERVICE_DIR = Path(__file__).resolve().parents[2]
GOOD_JWT = "b" * 64
GOOD_FERNET = base64.urlsafe_b64encode(b"f" * 32).decode()
# Stands in for a published value: the real ones are only known by their hash.
PUBLISHED = "published-in-an-old-readme"

# A fresh process loading the settings, as at startup, with PUBLISHED added
# to the denylist.
PROGRAM = (
    "import hashlib\n"
    "import common.configs.shipped_secrets as shipped\n"
    "shipped.SHIPPED_SECRET_SHA256 |= {hashlib.sha256(%r.encode()).hexdigest()}\n"
    "import googleform.config\n" % PUBLISHED
)


def start(jwt_secret, fernet_key):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AUTH_")}
    env.update(
        AUTH_JWT_SECRET=jwt_secret,
        AUTH_AES_HEX_KEY=fernet_key,
        DOTENV_PATH=str(SERVICE_DIR / "no-such-dir" / ".env"),
    )
    return subprocess.run(
        [sys.executable, "-c", PROGRAM],
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_starts_with_its_own_values():
    result = start(GOOD_JWT, GOOD_FERNET)
    assert result.returncode == 0, result.stderr[-2000:]


@pytest.mark.parametrize(
    "jwt_secret, fernet_key, problem",
    [
        ("", GOOD_FERNET, "AUTH_JWT_SECRET is not set"),
        (GOOD_JWT, "", "AUTH_AES_HEX_KEY is not set"),
        (PUBLISHED, GOOD_FERNET, "AUTH_JWT_SECRET is a value that was published"),
        (
            f"'{PUBLISHED}'",
            GOOD_FERNET,
            "AUTH_JWT_SECRET is a value that was published",
        ),
        (GOOD_JWT, "not-a-key", "AUTH_AES_HEX_KEY is not a Fernet key"),
    ],
    # ids name the case, never the values (they would look like keys)
    ids=["jwt-unset", "fernet-unset", "jwt-published", "jwt-published-quoted", "fernet-malformed"],
)
def test_refuses_to_start(jwt_secret, fernet_key, problem):
    result = start(jwt_secret, fernet_key)
    assert result.returncode != 0
    assert (
        "InsecureSecretError: Refusing to start the Google Forms integration"
        in result.stderr
    )
    assert problem in result.stderr
    assert "openssl rand -hex 32" in result.stderr
    assert PUBLISHED not in result.stderr


# MASTER_ENCRYPTION_KEYSET (which encrypts the Google credentials) is warned
# about, not refused: a new keyset could not read what is stored
# (docs/response-keyset-rotation.md).
def load_keyset(keyset_value):
    """A fresh process importing what loads the keyset at startup."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("AUTH_")}
    env.update(
        AUTH_JWT_SECRET=GOOD_JWT,
        AUTH_AES_HEX_KEY=GOOD_FERNET,
        MASTER_ENCRYPTION_KEYSET=keyset_value,
        DOTENV_PATH=str(SERVICE_DIR / "no-such-dir" / ".env"),
    )
    return subprocess.run(
        [sys.executable, "-c", "import googleform.app.repositories.oauth_credential"],
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def published_keyset():
    """CI's test keyset, which is the one the repository published."""
    ci = (SERVICE_DIR.parents[1] / ".github" / "workflows" / "ci.yml").read_text()
    return re.search(r'MASTER_ENCRYPTION_KEYSET:\s*"([^"]+)"', ci).group(1)


def test_warns_about_a_published_keyset_by_name_only():
    value = published_keyset()
    result = load_keyset(value)
    assert result.returncode == 0, result.stderr[-2000:]
    assert "MASTER_ENCRYPTION_KEYSET is a keyset that was published" in result.stderr
    assert value not in result.stderr
    for key in parse_keyset(value).key:
        assert key_digest(key) not in result.stderr


def test_no_keyset_warning_with_a_generated_keyset():
    generated = encode_keyset(
        only_primary(add_primary_key(parse_keyset(published_keyset())))
    )
    result = load_keyset(generated)
    assert result.returncode == 0, result.stderr[-2000:]
    assert "MASTER_ENCRYPTION_KEYSET" not in result.stderr
