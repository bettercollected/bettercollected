"""The secret of a registration service, sealed at rest.

Sealed with the credential encryption the backend already uses for action
secrets and provider state (``Crypto``, the Fernet key ``AUTH_AES_HEX_KEY``),
inside a small envelope that names the workspace and the service: an unseal
refuses a ciphertext that was copied to another row or workspace
(``SecretUnreadable``). The secret is write-only: nothing returns, logs or
queues it, and an error never carries it.
"""

import json
from typing import Optional

from cryptography.fernet import InvalidToken

VERSION = 1


class SecretUnreadable(Exception):
    """The sealed value is not ours for this service (or cannot be read)."""


def seal(crypto, workspace_id, service_id, secret: str) -> str:
    return crypto.encrypt(
        json.dumps(
            {
                "v": VERSION,
                "workspace_id": str(workspace_id),
                "service_id": str(service_id),
                "secret": secret,
            }
        )
    )


def unseal(crypto, workspace_id, service_id, sealed: Optional[str]) -> Optional[str]:
    if not sealed:
        return None
    try:
        envelope = json.loads(crypto.decrypt(sealed))
        if (
            not isinstance(envelope, dict)
            or envelope.get("v") != VERSION
            or envelope.get("workspace_id") != str(workspace_id)
            or envelope.get("service_id") != str(service_id)
            or not isinstance(envelope.get("secret"), str)
        ):
            raise SecretUnreadable()
        return envelope["secret"]
    except (InvalidToken, ValueError, TypeError):
        raise SecretUnreadable()
