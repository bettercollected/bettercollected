from typing import Optional

from cryptography.fernet import Fernet


class Crypto(Fernet):
    def encrypt(self, data: str) -> str:
        encrypted_data = super().encrypt(data.encode())
        return encrypted_data.decode()

    def decrypt(self, token: str, ttl: Optional[int] = None) -> str:
        data = super().decrypt(token)
        return data.decode()
