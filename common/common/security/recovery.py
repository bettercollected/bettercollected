"""The shape of one-time recovery codes (pure; no storage, no hashing).

A code is 16 base32 characters (80 bits) shown as four groups of four. How a
code is stored (which hash, which key) is each service's choice: the admin
portal keeps an HMAC under a pepper, the app keeps an unkeyed SHA-256 bound to
the user so that a key rotation cannot strand it.
"""

import base64
import secrets

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


def is_well_formed(code: str) -> bool:
    norm = normalise(code)
    return len(norm) == CODE_CHARS and set(norm) <= _ALPHABET
