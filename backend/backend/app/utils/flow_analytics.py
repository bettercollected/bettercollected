"""Aggregation for anonymous flow events — kept pure for testability."""

from typing import Any, Dict, List

SUBMIT = "__submit__"


def aggregate_flow_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Fold raw flow events into what the builder's Insights overlay needs.

    Each event: {session_id, from_page, to_page, created_at}. A session that
    never reaches ``__submit__`` counts as a drop-off on the last page it
    entered (its final ``to_page``).

    Returns camelCase keys (consumed directly by the webapp):
      totalSessions, submittedSessions,
      dropOffs: {page_id: sessions that went dark there},
      transitions: [{from, to, count}]
    """
    sessions: Dict[str, List[Dict[str, Any]]] = {}
    transitions: Dict[tuple, int] = {}

    for event in events:
        sid = event.get("session_id")
        frm, to = event.get("from_page"), event.get("to_page")
        if not sid or not frm or not to:
            continue
        sessions.setdefault(sid, []).append(event)
        transitions[(frm, to)] = transitions.get((frm, to), 0) + 1

    submitted = 0
    drop_offs: Dict[str, int] = {}
    for steps in sessions.values():
        if any(s.get("to_page") == SUBMIT for s in steps):
            submitted += 1
            continue
        ordered = sorted(steps, key=lambda s: s.get("created_at") or 0)
        last_page = ordered[-1].get("to_page")
        if last_page and last_page != SUBMIT:
            drop_offs[last_page] = drop_offs.get(last_page, 0) + 1

    return {
        "totalSessions": len(sessions),
        "submittedSessions": submitted,
        "dropOffs": drop_offs,
        "transitions": [{"from": frm, "to": to, "count": count} for (frm, to), count in sorted(transitions.items())],
    }
