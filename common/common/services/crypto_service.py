import base64
import os
from typing import Union

import tink
from tink import aead, cleartext_keyset_handle


class UnreadableCiphertext(ValueError):
    """A stored value carries the ciphertext prefix but does not decrypt:
    corrupted, encrypted under another key or context, or plaintext that
    happened to start with the prefix (stored before ``encrypt`` stopped
    passing such values through). The message never includes the value."""


class CryptoService:
    def __init__(self, keyset: str):
        super(CryptoService, self).__init__()
        self.version = "v1"
        self.ciphertext_prefix: bytes = bytes(self.version + ":", "utf-8")
        self.crypto = self.setup_crypto(keyset)

    def setup_crypto(self, keyset: str):
        aead.register()
        decoded_keyset = base64.b64decode(keyset).decode("ascii")
        keyset_handle = cleartext_keyset_handle.read(
            tink.JsonKeysetReader(decoded_keyset)
        )
        return keyset_handle.primitive(aead.Aead)

    def encrypt(
        self,
        workspace_id: str,
        form_id: str,
        data: Union[bytes, str],
        context: bytes = b"",
    ):
        # Always encrypts: a plaintext that starts with the prefix ("v1:...")
        # is still plaintext. Callers holding ciphertext must not call this.
        data = bytes(data, "utf-8") if isinstance(data, str) else data
        full_context = self.compose_full_context(workspace_id, form_id, context)
        ciphertext = self.crypto.encrypt(data, full_context)
        return self.ciphertext_prefix + ciphertext

    def decrypt(
        self, workspace_id: str, form_id: str, data: bytes, context: bytes = b""
    ):
        if isinstance(data, str) or not data.startswith(self.ciphertext_prefix):
            return data
        ciphertext = data[len(self.ciphertext_prefix) :]
        full_context = self.compose_full_context(workspace_id, form_id, context)
        try:
            return self.crypto.decrypt(ciphertext, full_context)
        except tink.TinkError:
            raise UnreadableCiphertext("stored value could not be decrypted") from None

    def compose_full_context(self, workspace_id: str, form_id: str, context: bytes):
        return bytes(f"{workspace_id}|{form_id}|", "utf-8") + context


def default_crypto_service():
    encryption_keyset = os.environ.get("MASTER_ENCRYPTION_KEYSET", None)
    if not encryption_keyset:
        raise Exception("MASTER_ENCRYPTION_KEYSET environment variable is not set.")
    return CryptoService(encryption_keyset)


crypto_service = default_crypto_service()
