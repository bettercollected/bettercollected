"""The process-wide cipher for stored responses, from ``MASTER_ENCRYPTION_KEYSET``.

Every service that encrypts or decrypts stored data with the keyset (the
backend, its jobs worker, the Google Forms integration) loads it here, once,
at startup, and is warned here when it holds a key published in the
repository (common.services.keyset).
"""

import os

from common.services.keyset import KEYSET_ENV, CryptoService, warn_if_published

__all__ = ["CryptoService", "crypto_service", "default_crypto_service"]


def default_crypto_service():
    encryption_keyset = os.environ.get(KEYSET_ENV, None)
    if not encryption_keyset:
        raise Exception("MASTER_ENCRYPTION_KEYSET environment variable is not set.")
    service = CryptoService(encryption_keyset)
    warn_if_published(encryption_keyset, KEYSET_ENV)
    return service


crypto_service = default_crypto_service()
