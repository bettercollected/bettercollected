"""deploy/generate-secrets.sh: the keys deploy.sh writes into the root .env."""

import base64
import hashlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

import tink
from tink import aead, cleartext_keyset_handle

from common.configs.shipped_secrets import is_shipped_secret

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "deploy" / "generate-secrets.sh"
NAMES = ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "MASTER_ENCRYPTION_KEYSET")
OWN_FERNET = base64.urlsafe_b64encode(b"o" * 32).decode()
# Stands in for a published value: the real ones are only known by their hash.
PUBLISHED = "published-in-an-old-readme"

pytestmark = pytest.mark.skipif(
    not (shutil.which("bash") and shutil.which("openssl")),
    reason="needs bash and openssl",
)


def run(tmp_path, root="", deployment="", existing=False, script=SCRIPT):
    root_env, deployment_env = tmp_path / ".env", tmp_path / ".env.deployment"
    if root is not None:
        root_env.write_text(root)
    deployment_env.write_text(deployment)
    env = {"PATH": os.environ["PATH"], "BC_EXISTING_STACK": str(existing).lower()}
    result = subprocess.run(
        ["bash", str(script), str(root_env), str(deployment_env)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return result, root_env


def values(root_env):
    found = {}
    for line in root_env.read_text().splitlines():
        name, _, value = line.partition("=")
        assert name not in found, f"{name} assigned twice"
        found[name] = value
    return found


def with_published_value_denied(tmp_path):
    """A copy of the script that also refuses PUBLISHED."""
    digest = hashlib.sha256(PUBLISHED.encode()).hexdigest()
    text = SCRIPT.read_text().replace(
        'shipped_sha256="\n', f'shipped_sha256="\n{digest}\n'
    )
    copy = tmp_path / "generate-secrets.sh"
    copy.write_text(text)
    return copy


def test_first_run_generates_usable_keys(tmp_path):
    result, root_env = run(
        tmp_path, root=None, deployment="AUTH_JWT_SECRET=\nAUTH_AES_HEX_KEY=\n"
    )
    assert result.returncode == 0, result.stderr
    found = values(root_env)
    assert set(found) == set(NAMES)
    assert re.fullmatch(r"[0-9a-f]{64}", found["AUTH_JWT_SECRET"])
    fernet = Fernet(found["AUTH_AES_HEX_KEY"])
    assert fernet.decrypt(fernet.encrypt(b"x")) == b"x"
    # read exactly as common.services.crypto_service reads it
    aead.register()
    keyset = base64.b64decode(found["MASTER_ENCRYPTION_KEYSET"]).decode("ascii")
    handle = cleartext_keyset_handle.read(tink.JsonKeysetReader(keyset))
    primitive = handle.primitive(aead.Aead)
    assert primitive.decrypt(primitive.encrypt(b"answer", b"ctx"), b"ctx") == b"answer"
    assert not any(is_shipped_secret(v) for v in found.values())
    # holds secrets: readable by the owner only
    assert stat.S_IMODE(root_env.stat().st_mode) == 0o600
    # no secret is ever printed
    for value in found.values():
        assert value not in result.stdout + result.stderr


def test_each_run_generates_different_keys(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first, root_env = run(tmp_path / "a")
    second, other_env = run(tmp_path / "b")
    assert first.returncode == second.returncode == 0
    a, b = values(root_env), values(other_env)
    assert all(a[name] != b[name] for name in NAMES)


def test_rerun_changes_nothing(tmp_path):
    result, root_env = run(tmp_path)
    assert result.returncode == 0, result.stderr
    before = root_env.read_text()
    again, _ = run(tmp_path, root=before, deployment=f"AUTH_AES_HEX_KEY={OWN_FERNET}\n")
    assert again.returncode == 0, again.stderr
    assert root_env.read_text() == before
    assert "Generated" not in again.stdout


def test_other_lines_and_set_values_are_kept(tmp_path):
    root = "UMAMI_APP_SECRET=abc\nAUTH_JWT_SECRET=mine\nAUTH_AES_HEX_KEY=\nTEMPORAL_API_KEY=def\n"
    result, root_env = run(tmp_path, root=root)
    assert result.returncode == 0, result.stderr
    found = values(root_env)
    assert found["UMAMI_APP_SECRET"] == "abc"
    assert found["TEMPORAL_API_KEY"] == "def"
    assert found["AUTH_JWT_SECRET"] == "mine"
    Fernet(found["AUTH_AES_HEX_KEY"])  # the empty assignment was replaced


def test_values_set_in_the_deployment_env_are_copied(tmp_path):
    deployment = (
        "AUTH_JWT_SECRET=my-own-secret\n"
        f"AUTH_AES_HEX_KEY='{OWN_FERNET}'\n"
        'MASTER_ENCRYPTION_KEYSET="a-keyset"\n'
    )
    result, root_env = run(tmp_path, deployment=deployment, existing=True)
    assert result.returncode == 0, result.stderr
    assert values(root_env) == {
        "AUTH_JWT_SECRET": "my-own-secret",
        "AUTH_AES_HEX_KEY": OWN_FERNET,
        "MASTER_ENCRYPTION_KEYSET": "a-keyset",
    }


def test_a_published_value_in_the_deployment_env_is_not_copied(tmp_path):
    script = with_published_value_denied(tmp_path)
    result, root_env = run(
        tmp_path, deployment=f"AUTH_JWT_SECRET='{PUBLISHED}'\n", script=script
    )
    assert result.returncode == 0, result.stderr
    assert values(root_env)["AUTH_JWT_SECRET"] != PUBLISHED
    assert "Not using AUTH_JWT_SECRET" in result.stderr
    assert PUBLISHED not in result.stdout + result.stderr


def test_a_published_value_in_the_root_env_is_refused_not_overwritten(tmp_path):
    script = with_published_value_denied(tmp_path)
    root = f"AUTH_JWT_SECRET={PUBLISHED}\n"
    result, root_env = run(tmp_path, root=root, script=script)
    assert result.returncode == 1
    assert "AUTH_JWT_SECRET in" in result.stderr
    assert values(root_env)["AUTH_JWT_SECRET"] == PUBLISHED


def test_existing_stack_without_a_keyset_stops_instead_of_generating(tmp_path):
    result, root_env = run(tmp_path, existing=True)
    assert result.returncode == 1
    assert "MASTER_ENCRYPTION_KEYSET is not set" in result.stderr
    assert "MASTER_ENCRYPTION_KEYSET" not in values(root_env)
    # the other two are generated, with what that means for a running stack
    assert "Everyone is signed out" in result.stdout
    assert "reconnect Google Forms" in result.stdout


def test_an_operator_made_root_env_is_made_private_before_secrets_are_added(tmp_path):
    root_env = tmp_path / ".env"
    root_env.write_text("PLATFORM_ADMIN_EMAILS=ops@example.test")  # no trailing newline
    root_env.chmod(0o644)
    result, root_env = run(tmp_path, root=None)
    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(root_env.stat().st_mode) == 0o600
    found = values(root_env)
    assert found["PLATFORM_ADMIN_EMAILS"] == "ops@example.test"
    assert all(found[name] for name in NAMES)
