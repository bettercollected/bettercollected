"""Snapshots of the store and their verification.

A ``Snapshot`` is what a loader reads: the rows visible to one service and the
signed manifest. ``verify_snapshot`` accepts only rows whose signature, manifest
entry, version and reader list check out and reports every other row as a
``Rejection``. Nothing here carries a value in a message or a report.

A rejected key keeps its last good value: ``VerifiedSettings(verification,
previous=...)`` serves the previously accepted row for any key that is
rejected or missing now, and reports it in ``stale_keys``. Only a key that was
never accepted falls back to the default (a secret fails closed in ``resolve``).

Missing rows. Reader views show a service only its own rows, while the manifest
covers every key. Each manifest entry therefore carries the signed ``readers``
set, and ``verify_snapshot(..., service=...)`` computes the keys that service
must see (``Manifest.keys_for``); a key in that set with no row in the view is
rejected as ``row_missing``. The view/loader must therefore (1) hand over the
complete signed manifest, unfiltered, together with the rows of the view, and
(2) include in the view every row whose ``readers`` contains the service. A
view that hides a row is then detected, not silently defaulted.

NOT HERE (lands with the store): ``MonotonicTracker`` is in memory, so a restart
forgets versions and a replayed older snapshot is accepted. The store side must
(a) keep the highest manifest revision outside the settings tables (for example
in the signed disk snapshot and the service heartbeat), (b) fail closed when
rows exist but no trusted manifest does, and (c) seed the tracker from that.
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
    SPEC_MISMATCH = "spec_mismatch"  # section, secret flag, reload class or readers
    ROW_MISSING = "row_missing"  # the signed manifest lists it, the view does not


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
    (``manifest_mismatch``, plus one with key ``*`` so an empty view still shows it): without it, deletions and rollbacks go unseen.
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
        # also when there are no rows: the loader must learn the manifest is untrusted
        rejected.append(Rejection("*", 0, RejectionReason.MANIFEST_MISMATCH.value))
        return Verification(accepted, rejected, 0)
    assert manifest is not None
    for row in rows:
        spec = None
        if registry is not None:
            if row.key not in registry:
                reject(row, RejectionReason.UNKNOWN_KEY)
                continue
            spec = registry.get(row.key)
            if (
                row.section != spec.section
                or row.is_secret != spec.is_secret
                or str(getattr(row.reload_class, "value", row.reload_class))
                != spec.reload_class.value
                or not set(row.readers) <= set(spec.readers)
            ):
                reject(row, RejectionReason.SPEC_MISMATCH)
                continue
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
        if entry != (row.version, row.sig, tuple(sorted(row.readers))):
            reject(row, RejectionReason.MANIFEST_MISMATCH)
            continue
        if not keys.verify_row(row):
            reject(row, RejectionReason.BAD_SIGNATURE)
            continue
        if seen.is_rollback(row.key, row.version):
            reject(row, RejectionReason.VERSION_ROLLBACK)
            continue
        accepted[row.key] = row
    if service is not None:
        presented = {row.key for row in rows}
        for key in manifest.keys_for(service):
            if key in presented:
                continue
            if registry is not None and (
                key not in registry or service not in registry.get(key).readers
            ):
                continue
            rejected.append(
                Rejection(key, manifest.entries[key][0], RejectionReason.ROW_MISSING.value)
            )
    return Verification(accepted, rejected, manifest.revision)


class VerifiedSettings:
    """A ``SettingsReader`` over the rows ``verify_snapshot`` accepted. With
    ``previous`` (the reader built from the last good load), a key that is
    rejected or missing now keeps its last good row."""

    def __init__(
        self,
        verification: Verification,
        previous: Optional["VerifiedSettings"] = None,
    ):
        self._rows = dict(verification.accepted)
        self._revision = verification.revision
        self.rejections: Tuple[Rejection, ...] = tuple(verification.rejections)
        stale = []
        if previous is not None:
            for key, row in previous._rows.items():
                if key not in self._rows and any(r.key == key for r in self.rejections):
                    self._rows[key] = row
                    stale.append(key)
        self.stale_keys: Tuple[str, ...] = tuple(sorted(stale))

    def is_stale(self, key: str) -> bool:
        return key in self.stale_keys

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
