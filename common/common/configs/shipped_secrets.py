"""Refuse to run with signing or encryption keys that are unset or public.

Earlier versions of this repository shipped concrete values for
``AUTH_JWT_SECRET`` and ``AUTH_AES_HEX_KEY`` (a Fernet key, despite the name)
in deployment env files, compose files and READMEs. A stack still using one
lets anyone forge session tokens and decrypt or forge Fernet-encrypted data
(OAuth and SSO state, form-action secrets, SCIM webhook secrets), so the
services refuse to start with them, or with no value at all.

Standard library only: the Temporal workers, which do not depend on
``common``, carry identical copies of this file in
``temporal/*/settings/shipped_secrets.py`` (``common/tests`` checks them).
"""

import base64
import binascii
import hashlib
from typing import Iterable, Mapping, Optional

# SHA-256 of every value published for these keys, never the values
# themselves. deploy/generate-secrets.sh carries the same list.
SHIPPED_SECRET_SHA256 = frozenset(
    {
        "a75934b93de0f24eb3da8b1f4234d7c3dfcf8f057377739a7378383898555de3",
        "af61f0e17db65ce007dccccd9165d3467e9c97c3d12e4c9507a9a06ec7aa1103",
        "dfad509a1373435ed0c21fd96e686e3a6879d30dae9796ac1eec38b6916497be",
        "4f4c538d1c81f4b9083fc33240e62f4101f1d21434b4f698f0d03f77a5d89207",
        "5a90a68596fcebfd2676d9313557584bd68b143dd234750c419ece1b8f82fe5a",
        "33d902e58f189bbb7266454cdbd9741bb3bd956a300c4a04ef0b24cd221a2da3",
        "c47af94f4a9ae7811b6d01bf1abb251f927ec915c8d78bbe07b56d513295058a",
        "0cf506f170c8c321831425c7a7cc8dc745a0104493b7e98d1ed653bb1e5f913b",
    }
)

JWT_SECRET_HINT = "openssl rand -hex 32"
FERNET_KEY_HINT = (
    'python3 -c "import base64,os; '
    'print(base64.urlsafe_b64encode(os.urandom(32)).decode())"'
)


class InsecureSecretError(RuntimeError):
    """A signing or encryption key is unset, malformed or public."""


def normalize_secret(value: Optional[str]) -> str:
    """The value as an env file means it: trimmed, one pair of quotes removed."""
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1].strip()
    return value


def is_shipped_secret(
    value: Optional[str], denylist: Optional[Iterable[str]] = None
) -> bool:
    """Whether the value is one that was published (denylist: SHA-256
    digests, SHIPPED_SECRET_SHA256 unless given)."""
    if denylist is None:
        denylist = SHIPPED_SECRET_SHA256
    digest = hashlib.sha256(normalize_secret(value).encode()).hexdigest()
    return digest in frozenset(denylist)


def is_fernet_key(value: Optional[str]) -> bool:
    try:
        return len(base64.urlsafe_b64decode(normalize_secret(value))) == 32
    except (binascii.Error, ValueError):
        return False


def secret_problems(
    jwt_secrets: Optional[Mapping[str, Optional[str]]] = None,
    fernet_keys: Optional[Mapping[str, Optional[str]]] = None,
    denylist: Optional[Iterable[str]] = None,
) -> list:
    """One line per unusable key, naming the variable, never its value."""
    problems = []
    for kind, secrets in (("jwt", jwt_secrets or {}), ("fernet", fernet_keys or {})):
        for name, value in secrets.items():
            if not normalize_secret(value):
                problems.append(f"{name} is not set")
            elif is_shipped_secret(value, denylist):
                problems.append(
                    f"{name} is a value that was published in the bettercollected "
                    "repository, so anyone can use it"
                )
            elif kind == "fernet" and not is_fernet_key(value):
                problems.append(
                    f"{name} is not a Fernet key (32 bytes, url-safe base64)"
                )
    return problems


def require_secrets(
    service: str,
    jwt_secrets: Optional[Mapping[str, Optional[str]]] = None,
    fernet_keys: Optional[Mapping[str, Optional[str]]] = None,
    denylist: Optional[Iterable[str]] = None,
) -> None:
    """Raise InsecureSecretError, saying what to set, unless every key is usable."""
    problems = secret_problems(jwt_secrets, fernet_keys, denylist)
    if not problems:
        return
    hints = [f"{name}: `{JWT_SECRET_HINT}`" for name in (jwt_secrets or {})]
    hints += [f"{name}: `{FERNET_KEY_HINT}`" for name in (fernet_keys or {})]
    raise InsecureSecretError(
        f"Refusing to start {service}: "
        + "; ".join(problems)
        + ". Generate your own values and set them as environment variables, "
        "the same in every service (the workers' AES_HEX_KEY is AUTH_AES_HEX_KEY): "
        + "; ".join(hints)
        + ". deploy.sh generates them into the root .env on its first run. "
        "A new AUTH_JWT_SECRET signs everyone out; see docs/DEVELOPERS_GUIDE.md."
    )
