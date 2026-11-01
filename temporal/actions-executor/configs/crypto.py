from typing import Optional

from cryptography.fernet import Fernet, MultiFernet

from settings.application import require_aes_hex_key, settings
from settings.shipped_secrets import fernet_members


class Crypto(Fernet):
    """One Fernet key, or a ring of two ("<current>,<previous>", the stack's
    AUTH_AES_HEX_KEY during a rotation, docs/auth-key-rotation.md): everything
    is encrypted with the first key, a value sealed with either is read."""

    def __init__(self, key):
        text = key.decode() if isinstance(key, (bytes, bytearray)) else key
        members = fernet_members(text) if isinstance(text, str) else []
        super().__init__(members[0] if members else key)
        self._ring = MultiFernet([Fernet(member) for member in (members or [key])])

    def encrypt(self, data: str) -> str:
        return self._ring.encrypt(data.encode()).decode()

    def decrypt(self, token: str, ttl: Optional[int] = None) -> str:
        return self._ring.decrypt(token, ttl).decode()


require_aes_hex_key()
crypto = Crypto(settings.aes_hex_key)
