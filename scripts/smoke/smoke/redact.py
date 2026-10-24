"""Keeps codes, tokens, cookies and addresses out of everything the suite writes.

Every string that reaches the report, the step summary or the console goes
through ``Redactor.scrub``. Known secret values (the API key, the mailbox
credentials, each sign-in code and access token once it is known) are replaced
literally; patterns catch the shapes a secret could have even when it was never
registered (an API key, a bearer token, a sign-in code, a JWT, a Google token,
an email address).
"""

from __future__ import annotations

import re
import threading
from typing import Iterable

REDACTED = "[redacted]"

# Shapes that never belong in a report, registered or not.
PATTERNS = [
    # workspace API keys: bc_<64 hex>
    (re.compile(r"bc_[A-Za-z0-9]{8,}"), REDACTED),
    # Authorization headers and the like
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}"), r"\1 " + REDACTED),
    # JWTs (session cookies)
    (re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"), REDACTED),
    # Google OAuth access and refresh tokens
    (re.compile(r"ya29\.[A-Za-z0-9._-]+"), REDACTED),
    (re.compile(r"1//[A-Za-z0-9._-]{10,}"), REDACTED),
    # sign-in codes: three letters or digits, a dash, three more (ABC-1D2)
    (re.compile(r"(?<![A-Za-z0-9])[A-Z0-9]{3}-[A-Z0-9]{3}(?![A-Za-z0-9])"), "[code]"),
    # email addresses (the run's plus-address included)
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[address]"),
    # cookie headers
    (re.compile(r"(?i)(set-cookie|cookie)\s*[:=]\s*[^\n]+"), r"\1: " + REDACTED),
]

# Values shorter than this are not registered: replacing them literally would
# shred ordinary text, and no real secret is that short.
MIN_SECRET_LENGTH = 6


class Redactor:
    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self._lock = threading.Lock()
        self._secrets: set[str] = set()
        for value in secrets:
            self.add(value)

    def add(self, value: str | None) -> None:
        """Register a secret value; every later scrub replaces it."""
        if value and len(value) >= MIN_SECRET_LENGTH:
            with self._lock:
                self._secrets.add(value)

    def scrub(self, text: object) -> str:
        out = "" if text is None else str(text)
        with self._lock:
            secrets = sorted(self._secrets, key=len, reverse=True)
        for value in secrets:
            out = out.replace(value, REDACTED)
        for pattern, replacement in PATTERNS:
            out = pattern.sub(replacement, out)
        return out

    def scrub_tree(self, value: object) -> object:
        """Scrub every string in a JSON-like structure (keys included)."""
        if isinstance(value, dict):
            return {self.scrub(k): self.scrub_tree(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.scrub_tree(v) for v in value]
        if isinstance(value, str):
            return self.scrub(value)
        return value
