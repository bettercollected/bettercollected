"""Read-only status of the background loops, kept in memory.

One shared holder (``StatusBoard``) per portal: the loop runner writes each
loop's state into it, the integrity monitor writes the integrity result, and
the Health page and the shell banner read it. Nothing here is persisted and
nothing carries a payload, address or secret: counts, fixed codes and times.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class LoopStatus:
    name: str
    leader: bool = False  # this process holds the loop's advisory lock
    last_run_at: Optional[datetime] = None
    last_outcome: str = "not run yet"  # a short fixed phrase with counts only
    last_ok: Optional[bool] = None
    consecutive_failures: int = 0
    runs: int = 0


@dataclass(frozen=True)
class IntegrityStatus:
    """Result of the latest settings integrity check. ``ok`` is None until the
    first check ran. ``problems`` are ``(setting name, fixed reason)`` pairs."""

    ok: Optional[bool] = None
    problems: Tuple[Tuple[str, str], ...] = ()
    last_run: Optional[datetime] = None


@dataclass
class StatusBoard:
    loops: Dict[str, LoopStatus] = field(default_factory=dict)
    integrity: IntegrityStatus = field(default_factory=IntegrityStatus)
    mail: str = "unknown"  # "ok" or "mail not configured"
    running: bool = False

    def update(self, name: str, **changes) -> LoopStatus:
        current = self.loops.get(name) or LoopStatus(name)
        self.loops[name] = replace(current, **changes)
        return self.loops[name]

    def snapshot(self) -> Dict[str, LoopStatus]:
        return dict(self.loops)
