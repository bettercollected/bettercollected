"""Subkeys derived from SETTINGS_MASTER_KEY with HKDF-SHA256.

One subkey per (namespace, purpose, version[, context]), so a leak or misuse of
one never touches another. ``info`` is ``<namespace>/<purpose>/v<version>`` plus
``/<context>`` when given; a new version yields an unrelated key, which is how
a purpose is rotated. The set of purposes is open: admin uses ``admin/audit``,
``admin/pepper`` and ``admin/totp``; later features register their own
(``settings/sign``, ``settings/wrap`` with a per-section context,
``tasks/request``) by simply naming them.
"""

from __future__ import annotations

import os
import re
from typing import Mapping, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.admin.config import MASTER_KEY_KEY, parse_master_key

KEY_BYTES = 32
_SALT = b"bettercollected/admin/hkdf-salt/v1"
_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_CONTEXT = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def derive_key(
    namespace: str,
    purpose: str,
    version: int = 1,
    context: Optional[str] = None,
    *,
    env: Mapping[str, str] = os.environ,
) -> bytes:
    """32 bytes for ``namespace/purpose/v<version>[/context]``, from the master
    key in ``env``. Stable for a given master key and arguments."""
    if not _NAME.match(namespace or "") or not _NAME.match(purpose or ""):
        raise ValueError("namespace and purpose must be short lowercase names")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("key version must be a positive integer")
    if context is not None and not _CONTEXT.match(context):
        raise ValueError("key context has unsupported characters")
    info = f"{namespace}/{purpose}/v{version}" + (f"/{context}" if context else "")
    master = parse_master_key(env.get(MASTER_KEY_KEY))
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_BYTES,
        salt=_SALT,
        info=info.encode(),
    ).derive(master)


def admin_key(
    purpose: str,
    version: int = 1,
    context: Optional[str] = None,
    *,
    env: Mapping[str, str] = os.environ,
) -> bytes:
    """``derive_key("admin", ...)``: ``audit``, ``pepper``, ``totp``, ..."""
    return derive_key("admin", purpose, version, context, env=env)
