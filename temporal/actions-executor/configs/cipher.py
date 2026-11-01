"""The executor's cipher, built the first time something opens or seals a value.

``configs/crypto.py`` (an identical copy of the Temporal worker's) requires
``AES_HEX_KEY`` the moment it is imported. Since 4.3 the backend hands over a
run's secrets already opened (``utilities/run_context.py``), so an executor under
``ACTION_ISOLATION=enforce`` needs no key at all and must not fail at start for
the lack of one. The Temporal path and a backend older than 4.3 still hand over
sealed values: the first use then imports ``configs.crypto``, which refuses with
the setting's name when the key is missing, empty, malformed or published.
"""


class _LazyCrypto:
    def __getattr__(self, name):
        from configs.crypto import crypto  # requires the key, here and not before

        return getattr(crypto, name)


crypto = _LazyCrypto()
