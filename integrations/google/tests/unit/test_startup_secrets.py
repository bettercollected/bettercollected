"""The Google Forms integration refuses to start without its own AUTH_JWT_SECRET and
AUTH_AES_HEX_KEY (common/configs/shipped_secrets.py)."""

import base64
import os
import subprocess
import sys
from pathlib import Path

import pytest

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
