"""Snapshots of the store and their verification.

A ``Snapshot`` is what a loader reads: the rows visible to one service and the
signed manifest. ``verify_snapshot`` accepts only rows whose signature, manifest
entry, version and reader list check out and reports every other row as a
``Rejection``. Nothing here carries a value in a message or a report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Protocol,
    Tuple,
    runtime_checkable,
)

from .canonical import SettingRow
from .keys import SectionKeys
from .registry import Registry
from .signing import Manifest, MonotonicTracker

__all__ = [
    "FakeSnapshot",
    "Rejection",
    "RejectionReason",
    "ServiceState",
    "SettingsReader",
    "Snapshot",
    "Verification",
    "VerifiedSettings",
    "verify_snapshot",
]


class RejectionReason(str, Enum):
    BAD_SIGNATURE = "bad_signature"
    MANIFEST_MISSING_KEY = "manifest_missing_key"
    MANIFEST_MISMATCH = "manifest_mismatch"
    VERSION_ROLLBACK = "version_rollback"
    UNKNOWN_KEY = "unknown_key"
    READER_NOT_ALLOWED = "reader_not_allowed"


@dataclass(frozen=True)
class Rejection:
    key: str
    version: int
    reason: str

    def message(self) -> str:
        return f"setting {self.key} version {self.version} rejected: {self.reason}"


@runtime_checkable
class Snapshot(Protocol):
    """Rows visible to the reading service, and the signed manifest."""

    def rows(self) -> Iterable[SettingRow]: ...

    def manifest(self) -> Optional[Manifest]: ...


@runtime_checkable
class SettingsReader(Protocol):
    """Verified settings for one service."""

    @property
    def revision(self) -> int: ...

    def get(self, key: str) -> Optional[SettingRow]:
        """The verified row for ``key`` (secrets still sealed), or None."""
        ...


@dataclass
class FakeSnapshot:
    """In-memory snapshot for tests."""

    row_list: List[SettingRow] = field(default_factory=list)
    signed_manifest: Optional[Manifest] = None

    def rows(self) -> Iterable[SettingRow]:
        return list(self.row_list)

    def manifest(self) -> Optional[Manifest]:
        return self.signed_manifest

    @classmethod
    def build(
        cls, rows: Iterable[SettingRow], keys: SectionKeys, revision: int = 1
    ) -> "FakeSnapshot":
        """Sign ``rows`` (which may be unsigned) and a manifest over them."""
        signed = [keys.sign_row(r) for r in rows]
        return cls(signed, keys.sign_manifest(revision, signed))


class Verification(NamedTuple):
    accepted: Dict[str, SettingRow]
    rejections: List[Rejection]
    revision: int  # of the manifest; 0 when it was not trusted


def verify_snapshot(
    rows: Iterable[SettingRow],
    manifest: Optional[Manifest],
    keys: SectionKeys,
    seen_versions: Optional[MonotonicTracker] = None,
    *,
    registry: Optional[Registry] = None,
    service: Optional[str] = None,
) -> Verification:
    """Check every row. Does not change ``seen_versions``: call its
    ``commit(accepted.values(), revision)`` once the result is applied.

    Per row, in order: key known to ``registry``; ``service`` allowed by the
    registry and the row; present in the manifest with the same version and
    signature; own signature; version not lower than one already seen. A
    missing, badly signed or older manifest rejects every row
    (``manifest_mismatch``): without it, deletions and rollbacks go unseen.
    """
    rows = list(rows)
    seen = seen_versions or MonotonicTracker()
    accepted: Dict[str, SettingRow] = {}
    rejected: List[Rejection] = []

    def reject(row: SettingRow, reason: RejectionReason) -> None:
        rejected.append(Rejection(row.key, row.version, reason.value))

    trusted = (
        manifest is not None
        and keys.verify_manifest(manifest)
        and not seen.revision_rolled_back(manifest.revision)
    )
    if not trusted:
        for row in rows:
            reject(row, RejectionReason.MANIFEST_MISMATCH)
        return Verification(accepted, rejected, 0)
    assert manifest is not None
    for row in rows:
        spec = None
        if registry is not None:
            if row.key not in registry:
                reject(row, RejectionReason.UNKNOWN_KEY)
                continue
            spec = registry.get(row.key)
        if service is not None and (
            service not in row.readers
            or (spec is not None and service not in spec.readers)
        ):
            reject(row, RejectionReason.READER_NOT_ALLOWED)
            continue
        entry = manifest.entries.get(row.key)
        if entry is None:
            reject(row, RejectionReason.MANIFEST_MISSING_KEY)
            continue
        if entry != (row.version, row.sig):
            reject(row, RejectionReason.MANIFEST_MISMATCH)
            continue
        if not keys.verify_row(row):
            reject(row, RejectionReason.BAD_SIGNATURE)
            continue
        if seen.is_rollback(row.key, row.version):
            reject(row, RejectionReason.VERSION_ROLLBACK)
            continue
        accepted[row.key] = row
    return Verification(accepted, rejected, manifest.revision)


class VerifiedSettings:
    """A ``SettingsReader`` over the rows ``verify_snapshot`` accepted."""

    def __init__(self, verification: Verification):
        self._rows = dict(verification.accepted)
        self._revision = verification.revision
        self.rejections: Tuple[Rejection, ...] = tuple(verification.rejections)

    @property
    def revision(self) -> int:
        return self._revision

    def get(self, key: str) -> Optional[SettingRow]:
        return self._rows.get(key)


@dataclass(frozen=True)
class ServiceState:
    """What a service reports about itself. Names and counts only: no value,
    no row content."""

    service: str
    revision_applied: int
    env_overrides: Tuple[str, ...] = ()
    rejected_keys: Tuple[str, ...] = ()
    restart_pending: bool = False
    keyset_fp: str = ""

    def to_report(self) -> Mapping[str, object]:
        return {
            "service": self.service,
            "revision_applied": self.revision_applied,
            "env_overrides": sorted(self.env_overrides),
            "rejected_keys": sorted(self.rejected_keys),
            "restart_pending": self.restart_pending,
            "keyset_fp": self.keyset_fp,
        }

    @classmethod
    def from_verification(
        cls,
        service: str,
        verification: Verification,
        *,
        env_overrides: Iterable[str] = (),
        restart_pending: bool = False,
        keyset_fp: str = "",
    ) -> "ServiceState":
        return cls(
            service=service,
            revision_applied=verification.revision,
            env_overrides=tuple(sorted(set(env_overrides))),
            rejected_keys=tuple(sorted({r.key for r in verification.rejections})),
            restart_pending=restart_pending,
            keyset_fp=keyset_fp,
        )
