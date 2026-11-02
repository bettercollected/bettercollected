"""The shared secret of a TOTP factor, sealed at rest, and the hash of a
recovery code.

The secret is encrypted with the credential encryption the backend already
uses (``Crypto``: the ``AUTH_AES_HEX_KEY`` ring, so ``authkeys.reencrypt``
carries it through a key rotation), inside an envelope that names the user, the
factor and the purpose. An unseal refuses a ciphertext copied to another factor
or user, and a sealed secret can never be opened as another kind of sealed value
(the purposes differ). The plaintext is never logged or returned after
enrolment.

A recovery code is stored as an unkeyed SHA-256 bound to the user id: a code is
80 random bits, so no key is needed to resist guessing, and a keyed hash would
die with a key at ``drop_old`` (the code itself is gone, nothing could re-hash
it).
"""

import hashlib
import json
from typing import Optional

from cryptography.fernet import InvalidToken
from common.security.recovery import normalise

from backend.app.services.registration.secrets import SecretUnreadable

VERSION = 1
PURPOSE = "totp_secret"
_HASH_LABEL = b"bettercollected recovery code v1\0"


def seal_secret(crypto, user_id, factor_id, secret: str) -> str:
    return crypto.encrypt(
        json.dumps(
            {
                "v": VERSION,
                "purpose": PURPOSE,
                "user_id": str(user_id),
                "factor_id": str(factor_id),
                "secret": secret,
            }
        )
    )


def unseal_secret(crypto, user_id, factor_id, sealed: Optional[str]) -> str:
    try:
        envelope = json.loads(crypto.decrypt(sealed or ""))
        if (
            not isinstance(envelope, dict)
            or envelope.get("v") != VERSION
            or envelope.get("purpose") != PURPOSE
            or envelope.get("user_id") != str(user_id)
            or envelope.get("factor_id") != str(factor_id)
            or not isinstance(envelope.get("secret"), str)
            or not envelope["secret"]
        ):
            raise SecretUnreadable()
        return envelope["secret"]
    except (InvalidToken, ValueError, TypeError):
        raise SecretUnreadable()


def hash_recovery_code(user_id, code: str) -> str:
    """SHA-256 (hex) of the normalised code, bound to the user."""
    message = _HASH_LABEL + str(user_id).encode() + b"\0" + normalise(code).encode()
    return hashlib.sha256(message).hexdigest()
