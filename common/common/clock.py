"""The clock every stamp reads: ``created_at``, ``updated_at``, windows, logins.

One function, so a test can fix the time by patching it in one place.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """The current time (aware UTC)."""
    return datetime.now(timezone.utc)
