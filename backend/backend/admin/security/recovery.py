"""One-time recovery codes.

A code is 16 base32 characters (80 bits) shown as four groups of four (the shape
lives in ``common.security.recovery``). Only
``HMAC-SHA256(pepper, normalised code)`` is stored. The plaintext list exists
once, in the ``IssuedCodes`` returned by ``issue``; ``reveal`` hands it out a
single time.
"""

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from backend.admin.security.keycheck import require_key
from common.security.recovery import (  # noqa: F401  (re-exported)
    CODE_CHARS,
    CODE_COUNT,
    GROUP,
    generate_code,
    is_well_formed,
    normalise,
)


def hash_code(pepper: bytes, code: str) -> str:
    """HMAC-SHA256 of the normalised code; ``pepper`` must be 32+ bytes."""
    pepper = require_key(pepper, "recovery pepper")
    digest = hmac.new(pepper, normalise(code).encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def verify(pepper: bytes, code: str, stored_hashes: Sequence[str]) -> Optional[int]:
    """Index of the stored hash matching ``code``, or None.

    Compares against every stored hash in constant time (no early exit). The
    caller must then burn the matched code atomically (single use)."""
    candidate = hash_code(pepper, code)
    match: Optional[int] = None
    for index, stored in enumerate(stored_hashes):
        if hmac.compare_digest(candidate, str(stored)) and match is None:
            match = index
    return match if is_well_formed(code) else None


@dataclass
class IssuedCodes:
    """Fresh codes: ``hashes`` to store, plaintext revealed once."""

    hashes: List[str]
    _codes: Optional[List[str]] = field(default=None, repr=False)

    def reveal(self) -> List[str]:
        if self._codes is None:
            raise RuntimeError("recovery codes were already revealed")
        codes, self._codes = self._codes, None
        return codes

    def __repr__(self) -> str:
        return f"IssuedCodes(count={len(self.hashes)})"


def issue(pepper: bytes, count: int = CODE_COUNT) -> IssuedCodes:
    codes = [generate_code() for _ in range(count)]
    return IssuedCodes(hashes=[hash_code(pepper, c) for c in codes], _codes=codes)
