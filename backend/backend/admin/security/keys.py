"""Subkeys derived from SETTINGS_MASTER_KEY with HKDF-SHA256.

One subkey per purpose, so a leak or misuse of one never touches another.
``info`` is ``admin/<purpose>/v<version>``; a new version yields an unrelated
key, which is how a purpose is rotated.
"""

from __future__ import annotations

import os
from typing import Mapping

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.admin.config import MASTER_KEY_KEY, parse_master_key

PURPOSES = ("audit", "pepper", "totp")
KEY_BYTES = 32
_SALT = b"bettercollected/admin/hkdf-salt/v1"


def derive_key(
    purpose: str, version: int = 1, *, env: Mapping[str, str] = os.environ
) -> bytes:
    """32 bytes for ``purpose`` (``audit``, ``pepper`` or ``totp``), from the
    master key in ``env``. Stable for a given master key, purpose and version."""
    if purpose not in PURPOSES:
        raise ValueError(f"unknown key purpose {purpose!r}")
    if not isinstance(version, int) or version < 1:
        raise ValueError("key version must be a positive integer")
    master = parse_master_key(env.get(MASTER_KEY_KEY))
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_BYTES,
        salt=_SALT,
        info=f"admin/{purpose}/v{version}".encode(),
    ).derive(master)
