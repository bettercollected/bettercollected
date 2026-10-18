"""HMAC-SHA256 signatures for settings rows and the manifest, plus the
monotonic tracker that stops a service accepting older versions."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Tuple

from .canonical import SettingRow, canonical_manifest, canonical_row
from .crypto.keycheck import require_key

__all__ = [
    "Manifest",
    "MonotonicTracker",
    "sign_manifest",
    "sign_row",
    "verify_manifest",
    "verify_row",
]


def _mac(key: bytes, message: bytes) -> str:
    return hmac.new(require_key(key, "signing key"), message, hashlib.sha256).hexdigest()


def _same(a: str, b: str) -> bool:
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def sign_row(row: SettingRow, signing_key: bytes) -> str:
    """Hex signature of ``row`` (its own ``sig`` is not part of the input)."""
    return _mac(signing_key, canonical_row(row))


def verify_row(row: SettingRow, signing_key: bytes) -> bool:
    try:
        return _same(row.sig, sign_row(row, signing_key))
    except ValueError:  # an uncodable row never verifies
        return False


@dataclass(frozen=True)
class Manifest:
    """The set of ``key -> (version, row sig)`` at one revision, signed."""

    revision: int
    entries: Mapping[str, Tuple[int, str]]
    sig: str = ""


def sign_manifest(
    revision: int, entries: Mapping[str, Tuple[int, str]], signing_key: bytes
) -> Manifest:
    entries = dict(entries)
    sig = _mac(signing_key, canonical_manifest(revision, entries))
    return Manifest(revision, entries, sig)


def verify_manifest(manifest: Manifest, signing_key: bytes) -> bool:
    try:
        expected = _mac(
            signing_key, canonical_manifest(manifest.revision, dict(manifest.entries))
        )
    except (ValueError, TypeError):
        return False
    return _same(manifest.sig, expected)


@dataclass
class MonotonicTracker:
    """In-process memory of the highest version seen per key and the highest
    manifest revision. A version lower than one already seen is a rollback."""

    versions: Dict[str, int] = field(default_factory=dict)
    revision: int = 0

    def is_rollback(self, key: str, version: int) -> bool:
        return version < self.versions.get(key, 0)

    def revision_rolled_back(self, revision: int) -> bool:
        return revision < self.revision

    def record(self, key: str, version: int) -> None:
        if version > self.versions.get(key, 0):
            self.versions[key] = version

    def commit(self, rows: Iterable[SettingRow], revision: int) -> None:
        """Remember accepted rows and the manifest revision they came from."""
        for row in rows:
            self.record(row.key, row.version)
        self.revision = max(self.revision, revision)
