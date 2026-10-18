"""Settings keys derived from the master key, limited to the sections a
service reads.

``SectionKeys`` decodes the master key (and, during a rotation, the previous
one) once, derives what it needs and keeps no reference to the master itself,
so a service built for ``sections=["mail"]`` cannot open any other section.
Rows are signed with a per-section key (``settings/sign`` with the section as
context), so a service that holds only the ``mail`` section can neither forge
nor even verify rows of another section. The manifest is signed with the
section-less ``settings/sign`` key, which every reading service holds: a
compromised reader can therefore forge a manifest (but no row of a section it
does not hold), and the loader still checks each row's own signature and the
version tracker. That is the residual risk of a symmetric MAC for the manifest.

It always signs and seals with the current key; it verifies and opens with
the current key first, then the previous one.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Iterable, List, Optional, Tuple, Union

from .canonical import SettingRow
from .crypto import envelope
from .crypto.keycheck import require_key
from .crypto.keys import derive_from_master, parse_master_key
from .signing import Manifest, sign_manifest, sign_row, verify_manifest, verify_row

__all__ = ["SectionKeys", "SectionNotAllowed"]

NAMESPACE = "settings"
_SECTION = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

MasterKey = Union[str, bytes]


class SectionNotAllowed(PermissionError):
    """A section outside the ones this ``SectionKeys`` was built for."""


def _decode(master: MasterKey, name: str) -> bytes:
    if isinstance(master, str):
        return parse_master_key(master)
    return require_key(master, name)


def _kek_id(kek: bytes) -> str:
    return "w1-" + hashlib.sha256(b"kek-id" + kek).hexdigest()[:8]


class SectionKeys:
    def __init__(
        self,
        master: MasterKey,
        *,
        sections: Iterable[str],
        master_previous: Optional[MasterKey] = None,
    ):
        masters: List[bytes] = [_decode(master, "master key")]
        if master_previous:
            previous = _decode(master_previous, "previous master key")
            if previous != masters[0]:
                masters.append(previous)
        self._sections = frozenset(sections)
        for section in self._sections:
            if not _SECTION.match(section):
                raise ValueError("section has unsupported characters")
        self._sign: Tuple[bytes, ...] = tuple(
            derive_from_master(m, NAMESPACE, "sign") for m in masters
        )
        self._row_sign: Dict[str, Tuple[bytes, ...]] = {
            s: tuple(
                derive_from_master(m, NAMESPACE, "sign", 1, s) for m in masters
            )
            for s in self._sections
        }
        self._wrap: Dict[str, Tuple[bytes, ...]] = {
            s: tuple(
                derive_from_master(m, NAMESPACE, "wrap", 1, s) for m in masters
            )
            for s in self._sections
        }
        self._fingerprint = derive_from_master(masters[0], NAMESPACE, "fp")[:6].hex()

    def __repr__(self) -> str:
        return f"SectionKeys(sections={sorted(self._sections)!r})"

    @property
    def sections(self) -> frozenset:
        return self._sections

    @property
    def rotating(self) -> bool:
        """True while a previous master key is also accepted."""
        return len(self._sign) > 1

    @property
    def fingerprint(self) -> str:
        """Short, non-reversible id of the current master key, for reports."""
        return self._fingerprint

    # ---- signing

    def signing_key(self) -> bytes:
        """The manifest signing key (not used for rows)."""
        return self._sign[0]

    def sign_row(self, row: SettingRow) -> SettingRow:
        try:
            key = self._row_sign[row.section][0]
        except (KeyError, TypeError):
            raise SectionNotAllowed("section is not available to this service") from None
        return row.with_sig(sign_row(row, key))

    def verify_row(self, row: SettingRow) -> bool:
        keys = self._row_sign.get(row.section) if isinstance(row.section, str) else None
        return bool(keys) and any(verify_row(row, k) for k in keys)

    def sign_manifest(self, revision: int, rows: Iterable[SettingRow]) -> Manifest:
        entries = {r.key: (r.version, r.sig, tuple(r.readers)) for r in rows}
        return sign_manifest(revision, entries, self._sign[0])

    def verify_manifest(self, manifest: Manifest) -> bool:
        return any(verify_manifest(manifest, k) for k in self._sign)

    # ---- sealing

    def _keks(self, section: str) -> Tuple[bytes, ...]:
        try:
            return self._wrap[section]
        except (KeyError, TypeError):
            raise SectionNotAllowed("section is not available to this service") from None

    def wrap_key(self, section: str) -> bytes:
        return self._keks(section)[0]

    def seal(self, section: str, key: str, version: int, plaintext: str) -> str:
        """Envelope v2 for a secret value, under the current key."""
        kek = self.wrap_key(section)
        return envelope.encrypt_v2(
            plaintext.encode("utf-8"), kek, _kek_id(kek), key, version, section
        )

    def open(self, section: str, key: str, version: int, blob: str) -> str:
        """The secret value of ``blob``; current key first, then the previous."""
        last: Optional[Exception] = None
        for kek in self._keks(section):
            try:
                return envelope.decrypt_v2(blob, kek, key, version, section).decode(
                    "utf-8"
                )
            except envelope.EnvelopeError as exc:
                last = exc
        raise last or envelope.EnvelopeError("cannot decrypt envelope")

    def rewrap(self, section: str, key: str, version: int, blob: str) -> str:
        """Re-wrap ``blob``'s data key under the current key (rotation step)."""
        keks = self._keks(section)
        new = keks[0]
        last: Optional[Exception] = None
        for old in keks:
            try:
                return envelope.rewrap_v2(
                    blob, old, new, _kek_id(new), key, version, section
                )
            except envelope.EnvelopeError as exc:
                last = exc
        raise last or envelope.EnvelopeError("cannot decrypt envelope")

    def needs_rewrap(self, section: str, blob: str) -> bool:
        """Whether ``blob`` was not sealed under the current key."""
        return envelope.key_id_of(blob) != _kek_id(self.wrap_key(section))
