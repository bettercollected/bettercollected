"""The full settings registry with the shipped-secret check plugged in.

``common.settings`` is a pure library and may not import ``common.configs``,
so the two are joined here, for the services and the admin portal.
"""

from typing import Iterable, List

from common.configs import shipped_secrets
from common.settings.inventory import full_registry
from common.settings.registry import Registry

JWT_KEYS = frozenset({"AUTH_JWT_SECRET"})
FERNET_KEYS = frozenset({"AUTH_AES_HEX_KEY"})
PLACEHOLDER_VALUES = frozenset({"random_api_key", "not-needed"})


def secret_problems(key: str, value: str) -> Iterable[str]:
    """One line per problem with a secret (naming the key, never the value):
    a published value anywhere, a malformed Fernet key, a known placeholder."""
    problems: List[str] = []
    if key in JWT_KEYS:
        problems += shipped_secrets.secret_problems(jwt_secrets={key: value})
    elif key in FERNET_KEYS:
        problems += shipped_secrets.secret_problems(fernet_keys={key: value})
    elif shipped_secrets.is_shipped_secret(value):
        problems.append(f"{key} is a value that was published in the repository")
    if value.strip() in PLACEHOLDER_VALUES:
        problems.append(f"{key} is a placeholder value")
    return problems


def default_registry() -> Registry:
    """Every storable key, validating secrets with ``secret_problems``."""
    return full_registry(secret_problems)
