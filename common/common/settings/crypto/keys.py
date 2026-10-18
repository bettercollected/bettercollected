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

import base64
import binascii
import os
import re
from typing import Mapping, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


MASTER_KEY_KEY = "SETTINGS_MASTER_KEY"
MIN_MASTER_KEY_BYTES = 32
KEY_BYTES = 32
_SALT = b"bettercollected/admin/hkdf-salt/v1"
_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_CONTEXT = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


class MasterKeyError(RuntimeError):
    """The master key is missing or unusable; the message never shows it."""


def parse_master_key(raw: Optional[str]) -> bytes:
    """Decode a base64 master key of at least 32 bytes, or raise without echoing it."""
    value = (raw or "").strip()
    if not value:
        raise MasterKeyError(
            f"{MASTER_KEY_KEY} is not set. Generate one with "
            f"`openssl rand -base64 48` and keep it: without it the stored second-factor "
            f"secrets and the audit chain cannot be recovered or verified."
        )
    padded = value + "=" * (-len(value) % 4)
    key = None
    for altchars in (None, b"-_"):  # standard, then URL-safe alphabet
        try:
            key = base64.b64decode(padded, altchars=altchars, validate=True)
            break
        except (binascii.Error, ValueError):
            continue
    if key is None:
        raise MasterKeyError(f"{MASTER_KEY_KEY} is not valid base64 (value not shown).")
    if len(key) < MIN_MASTER_KEY_BYTES:
        raise MasterKeyError(
            f"{MASTER_KEY_KEY} must decode to at least {MIN_MASTER_KEY_BYTES} bytes "
            f"(value not shown)."
        )
    return key


def derive_from_master(
    master: bytes,
    namespace: str,
    purpose: str,
    version: int = 1,
    context: Optional[str] = None,
) -> bytes:
    """Like ``derive_key`` for a master key already decoded to bytes."""
    if not _NAME.match(namespace or "") or not _NAME.match(purpose or ""):
        raise ValueError("namespace and purpose must be short lowercase names")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("key version must be a positive integer")
    if context is not None and not _CONTEXT.match(context):
        raise ValueError("key context has unsupported characters")
    info = f"{namespace}/{purpose}/v{version}" + (f"/{context}" if context else "")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_BYTES,
        salt=_SALT,
        info=info.encode(),
    ).derive(master)


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
    master = parse_master_key(env.get(MASTER_KEY_KEY))
    return derive_from_master(master, namespace, purpose, version, context)


def admin_key(
    purpose: str,
    version: int = 1,
    context: Optional[str] = None,
    *,
    env: Mapping[str, str] = os.environ,
) -> bytes:
    """``derive_key("admin", ...)``: ``audit``, ``pepper``, ``totp``, ..."""
    return derive_key("admin", purpose, version, context, env=env)
