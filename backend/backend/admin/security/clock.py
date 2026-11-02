"""Time source for the security primitives (moved to ``common.security.clock``).

Re-exported here so the admin portal's imports keep working."""

from common.security.clock import Clock, FakeClock, SystemClock

__all__ = ["Clock", "FakeClock", "SystemClock"]
