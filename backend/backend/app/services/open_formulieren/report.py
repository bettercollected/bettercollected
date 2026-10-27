"""The import report: what was dropped, changed, flagged or ignored.

Every item has a stable ``reason`` code (the webapp keeps the English and
Dutch sentences, keyed by it) and carries only short plain strings: a key, a
label, a flat ``detail``. See docs/open-formulieren.md for the codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren.text import for_report

DROPPED = "dropped"
CHANGED = "changed"
FLAGGED = "flagged"
IGNORED = "ignored"
NOTED = "noted"

WARNING = "warning"
INFO = "info"

COMPONENT = "component"
LOGIC = "logic"
VARIABLE = "variable"
FEATURE = "feature"
SETTING = "setting"
ARCHIVE = "archive"

FLAG_NATIONAL_ID = "national_identity_number"


def _detail(detail: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """A flat object of short strings, numbers and booleans."""
    if not detail:
        return None
    clean: Dict[str, Any] = {}
    for key, value in list(detail.items())[:8]:
        if isinstance(value, bool) or isinstance(value, (int, float)):
            clean[str(key)[:40]] = value
        elif isinstance(value, str):
            clean[str(key)[:40]] = for_report(value, 80)
    return clean or None


@dataclass
class Report:
    items: List[Dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    dropped: int = 0
    flagged: int = 0
    _seen: Set[Tuple[Any, ...]] = field(default_factory=set)

    def add(
        self,
        code: str,
        kind: str,
        reason: str,
        severity: str = WARNING,
        *,
        key: Any = None,
        label: Any = None,
        step: Optional[int] = None,
        flag: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        once: bool = False,
    ) -> None:
        """Record an item. ``once``: only the first item with this kind,
        reason and detail is kept (form-wide notes)."""
        if once:
            marker = (kind, reason, tuple(sorted((detail or {}).items())))
            if marker in self._seen:
                return
            self._seen.add(marker)
        if code == DROPPED:
            self.dropped += 1
        if code == FLAGGED or flag:
            self.flagged += 1
        if len(self.items) >= limits.MAX_REPORT_ITEMS:
            self.truncated = True
            return
        item: Dict[str, Any] = {
            "code": code,
            "kind": kind,
            "reason": reason,
            "severity": severity,
        }
        if key is not None and for_report(key, limits.MAX_KEY_IN_REPORT):
            item["key"] = for_report(key, limits.MAX_KEY_IN_REPORT)
        if label is not None and for_report(label, limits.MAX_LABEL_IN_REPORT):
            item["label"] = for_report(label, limits.MAX_LABEL_IN_REPORT)
        if step is not None:
            item["step"] = step
        if flag:
            item["flag"] = flag
        clean = _detail(detail)
        if clean:
            item["detail"] = clean
        self.items.append(item)

    def as_dict(self) -> Dict[str, Any]:
        return {"truncated": self.truncated, "items": self.items}
