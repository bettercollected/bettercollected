"""Minimum key length for HMAC keys and peppers."""

MIN_KEY_BYTES = 32


class WeakKeyError(ValueError):
    """A key is too short. The message names the key, never its value."""


def require_key(key: object, name: str) -> bytes:
    """``key`` as bytes, or WeakKeyError when it is not bytes of at least
    ``MIN_KEY_BYTES``."""
    if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
        raise WeakKeyError(f"{name} must be at least {MIN_KEY_BYTES} bytes")
    return bytes(key)
