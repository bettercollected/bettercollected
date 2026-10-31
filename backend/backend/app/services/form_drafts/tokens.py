"""The secrets of a draft: the magic link's token and the edit key.

Both are 256 random bits (``token_urlsafe(32)``) prefixed with the draft's id
and a dot, so a draft is found by its id and the secret is compared against
the stored hash in constant time. Only a keyed hash (HMAC-SHA256, the key
derived from a server secret, a different label per purpose) is stored: a
database read gives neither a token nor an edit key, and a token is never
valid as an edit key or the other way round. An address is stored the same
way (``address_key``), never in clear.
"""

import hashlib
import hmac
import re
import secrets
import unicodedata
from typing import Optional, Tuple

_KEY_LABEL = b"bettercollected form draft v1\0"
TOKEN = "link"
EDIT_KEY = "edit"
# a draft id (24 hex digits), a dot and 43 URL-safe characters
_SHAPE = re.compile(r"([0-9a-f]{24})\.([A-Za-z0-9_-]{43})")


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def compose(draft_id, secret: str) -> str:
    return f"{draft_id}.{secret}"


def split(value: object) -> Optional[Tuple[str, str]]:
    """(draft id, secret) of a token or edit key, None when it is not shaped
    like one (nothing is looked up then)."""
    if not isinstance(value, str) or len(value) > 80:
        return None
    match = _SHAPE.fullmatch(value)
    return (match.group(1), match.group(2)) if match else None


def normalised_address(address: str) -> str:
    local, at, domain = unicodedata.normalize("NFC", address.strip()).rpartition("@")
    if not at:
        return local.casefold()
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    return f"{local.casefold()}@{domain.casefold()}"


class DraftKeys:
    def __init__(self, secret: str):
        self._key = hashlib.sha256(_KEY_LABEL + (secret or "").encode()).digest()

    def _mac(self, purpose: str, *parts: str) -> str:
        message = "\0".join((purpose, *parts)).encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def hash_secret(self, purpose: str, draft_id, secret: str) -> str:
        return self._mac(purpose, str(draft_id), secret)

    def matches(
        self, purpose: str, draft_id, secret: str, stored: Optional[str]
    ) -> bool:
        """Constant time; False for a draft that has no such secret set."""
        expected = self._mac(purpose, str(draft_id), secret)
        return hmac.compare_digest(expected, stored or "0" * len(expected))

    def address_key(self, form_id, address: str) -> str:
        """The keyed hash of a normalised address on one form: the local part
        folded (Unicode normal form C, case folded), the domain in its ASCII form
        (an internationalised domain and its punycode are one mailbox)."""
        return self._mac("address", str(form_id), normalised_address(address))
