from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from common.configs.shipped_secrets import fernet_members


class Crypto(Fernet):
    """The Fernet cipher of the services' stored secrets and OAuth state.

    ``key`` is a key ring (docs/auth-key-rotation.md): one Fernet key, or two
    separated by a comma, current first. Everything is encrypted with the first
    key; a value sealed with any member is read. As a ``Fernet`` it keeps the
    first key, so ``isinstance`` checks and the one-key behaviour are unchanged.
    """

    def __init__(self, key):
        text = key.decode() if isinstance(key, (bytes, bytearray)) else key
        members = fernet_members(text) if isinstance(text, str) else []
        # a bad or empty key fails here, as a plain Fernet always has
        super().__init__(members[0] if members else key)
        self._members: List[str] = members or [key]
        self._ring = MultiFernet([Fernet(member) for member in self._members])

    def encrypt(self, data: str) -> str:
        return self._ring.encrypt(data.encode()).decode()

    def decrypt(self, token: str, ttl: Optional[int] = None) -> str:
        return self._ring.decrypt(token, ttl).decode()

    def opening_member(self, token: str, ttl: Optional[int] = None) -> Optional[str]:
        """The ring member (a key) that opens ``token``, or None. For values
        derived from the key that sealed them (PKCE verifiers); never log it."""
        for member in self._members:
            try:
                Fernet(member).decrypt(token, ttl)
                return member
            except (InvalidToken, TypeError, ValueError):
                continue
        return None

    def opening_position(self, token: str, ttl: Optional[int] = None) -> Optional[int]:
        """0 for the current key, 1 for the previous one, None when neither
        opens ``token`` (what ``authkeys.reencrypt`` classifies by)."""
        for position, member in enumerate(self._members):
            try:
                Fernet(member).decrypt(token, ttl)
                return position
            except (InvalidToken, TypeError, ValueError):
                continue
        return None

    @property
    def member_count(self) -> int:
        return len(self._members)
