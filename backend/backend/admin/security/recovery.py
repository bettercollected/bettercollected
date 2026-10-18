"""One-time recovery codes.

A code is 16 base32 characters (80 bits) shown as four groups of four. Only
``HMAC-SHA256(pepper, normalised code)`` is stored. The plaintext list exists
once, in the ``IssuedCodes`` returned by ``issue``; ``reveal`` hands it out a
single time.
"""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

CODE_COUNT = 10
CODE_CHARS = 16
GROUP = 4
_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


def normalise(code: str) -> str:
    """Upper-case, with spaces and dashes removed."""
    return "".join(ch for ch in str(code).upper() if ch not in " -\t\r\n")


def generate_code() -> str:
    raw = base64.b32encode(secrets.token_bytes(10)).decode("ascii")  # 80 bits
    return "-".join(raw[i : i + GROUP] for i in range(0, CODE_CHARS, GROUP))


def hash_code(pepper: bytes, code: str) -> str:
    digest = hmac.new(pepper, normalise(code).encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def is_well_formed(code: str) -> bool:
    norm = normalise(code)
    return len(norm) == CODE_CHARS and set(norm) <= _ALPHABET


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
