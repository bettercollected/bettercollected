"""Compatibility re-export; the implementation lives in common.settings.crypto."""

from common.settings.crypto.keycheck import MIN_KEY_BYTES, WeakKeyError, require_key

__all__ = ["MIN_KEY_BYTES", "WeakKeyError", "require_key"]
