"""The address of a webhook, sealed at rest.

An address can hold a token (``https://host/hook?key=...``), so it is stored
like the signing secret: encrypted with the credential encryption the backend
already uses (``Crypto``), inside an envelope that names the workspace, the
webhook and the purpose. An unseal refuses a ciphertext copied to another
webhook or workspace, and a sealed address can never be opened as a secret or
the other way round (the envelopes differ: ``url`` here, ``secret`` in
``registration/secrets.py``). Only the host is kept in clear, for the privacy
panel and the list.
"""

import json
from typing import Optional

from cryptography.fernet import InvalidToken

from backend.app.services.registration.secrets import SecretUnreadable

VERSION = 1
PURPOSE = "webhook_url"


def seal_url(crypto, workspace_id, webhook_id, url: str) -> str:
    return crypto.encrypt(
        json.dumps(
            {
                "v": VERSION,
                "purpose": PURPOSE,
                "workspace_id": str(workspace_id),
                "webhook_id": str(webhook_id),
                "url": url,
            }
        )
    )


def unseal_url(crypto, workspace_id, webhook_id, sealed: Optional[str]) -> str:
    try:
        envelope = json.loads(crypto.decrypt(sealed or ""))
        if (
            not isinstance(envelope, dict)
            or envelope.get("v") != VERSION
            or envelope.get("purpose") != PURPOSE
            or envelope.get("workspace_id") != str(workspace_id)
            or envelope.get("webhook_id") != str(webhook_id)
            or not isinstance(envelope.get("url"), str)
            or not envelope["url"]
        ):
            raise SecretUnreadable()
        return envelope["url"]
    except (InvalidToken, ValueError, TypeError):
        raise SecretUnreadable()
