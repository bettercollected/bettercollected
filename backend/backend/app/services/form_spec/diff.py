"""A structured diff of two form spec documents (plain JSON, as
``form_to_spec_dict`` makes them).

Pages and fields are matched by id, so a renamed question is "changed", a
moved one "moved", and a field whose position shifted only because another
was added or removed is neither. Paths are JSON pointers: into the new
document for what exists there, into the old one for what was removed.
"""

from typing import Any, Dict, List, Optional, Tuple

_NESTED = "fields"


def _leaf_changes(before: Any, after: Any, path: str) -> List[Dict[str, Any]]:
    """Changed values between two JSON values; objects are compared key by
    key (an object that appears or goes away too), anything else (lists
    included) as a whole."""
    if isinstance(before, dict) and after is None:
        after = {}
    elif isinstance(after, dict) and before is None:
        before = {}
    if isinstance(before, dict) and isinstance(after, dict):
        changes: List[Dict[str, Any]] = []
        for key in list(before) + [k for k in after if k not in before]:
            if key == _NESTED:
                continue
            changes += _leaf_changes(before.get(key), after.get(key), f"{path}/{key}")
        return changes
    if before == after:
        return []
    return [{"path": path, "before": before, "after": after}]


def _pages(document: Dict[str, Any]) -> Dict[str, Tuple[str, Dict[str, Any]]]:
    return {
        page["id"]: (f"/pages/{p}", page)
        for p, page in enumerate(document.get("pages") or [])
    }


def _fields(
    document: Dict[str, Any],
) -> Dict[str, Tuple[str, str, Dict[str, Any]]]:
    """id -> (path, container id (a page's or a group's), field)."""
    found: Dict[str, Tuple[str, str, Dict[str, Any]]] = {}
    for p, page in enumerate(document.get("pages") or []):
        for f, field in enumerate(page.get("fields") or []):
            path = f"/pages/{p}/fields/{f}"
            found.setdefault(field["id"], (path, page["id"], field))
            for c, child in enumerate(field.get("fields") or []):
                found.setdefault(
                    child["id"], (f"{path}/fields/{c}", field["id"], child)
                )
    return found


def _reordered(before_order: List[str], after_order: List[str], kept: set) -> set:
    """Ids whose place among the items kept in both orders changed."""
    old = [i for i in before_order if i in kept]
    new = [i for i in after_order if i in kept]
    if old == new:
        return set()
    # The longest run kept in order stays; everything else moved.
    stay = _longest_common_subsequence(old, new)
    return set(new) - set(stay)


def _longest_common_subsequence(a: List[str], b: List[str]) -> List[str]:
    lengths = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            lengths[i][j] = (
                lengths[i + 1][j + 1] + 1
                if a[i] == b[j]
                else max(lengths[i + 1][j], lengths[i][j + 1])
            )
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            out.append(a[i])
            i, j = i + 1, j + 1
        # On a tie, keep the old order's item: what comes first in the new
        # order out of turn (moved forward) is the one reported as moved.
        elif lengths[i + 1][j] > lengths[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def _section(
    before: Dict[str, Tuple],
    after: Dict[str, Tuple],
    moved_ids: set,
    container: Optional[int] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    section: Dict[str, List[Dict[str, Any]]] = {
        "added": [],
        "removed": [],
        "moved": [],
        "changed": [],
    }
    for item_id, entry in after.items():
        if item_id not in before:
            section["added"].append({"id": item_id, "path": entry[0]})
    for item_id, entry in before.items():
        if item_id not in after:
            section["removed"].append({"id": item_id, "path": entry[0]})
    for item_id, entry in after.items():
        old = before.get(item_id)
        if old is None:
            continue
        if item_id in moved_ids or (
            container is not None and old[container] != entry[container]
        ):
            section["moved"].append({"id": item_id, "from": old[0], "to": entry[0]})
        changes = _leaf_changes(old[-1], entry[-1], entry[0])
        if changes:
            section["changed"].append(
                {"id": item_id, "path": entry[0], "changes": changes}
            )
    return section


def spec_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """``{form: [changes], pages: {...}, fields: {...}, changed: bool}``,
    each section with ``added``, ``removed``, ``moved`` and ``changed``."""
    form_changes = []
    for key in list(before) + [k for k in after if k not in before]:
        if key == "pages":
            continue
        form_changes += _leaf_changes(before.get(key), after.get(key), f"/{key}")

    pages_before, pages_after = _pages(before), _pages(after)
    kept_pages = set(pages_before) & set(pages_after)
    moved_pages = _reordered(list(pages_before), list(pages_after), kept_pages)

    fields_before, fields_after = _fields(before), _fields(after)
    kept_fields = set(fields_before) & set(fields_after)
    moved_fields = set()
    containers = {entry[1] for entry in fields_after.values()}
    for container in containers:
        old_order = [i for i, e in fields_before.items() if e[1] == container]
        new_order = [i for i, e in fields_after.items() if e[1] == container]
        same_container = {
            i
            for i in kept_fields
            if fields_before[i][1] == container and fields_after[i][1] == container
        }
        moved_fields |= _reordered(old_order, new_order, same_container)

    diff = {
        "form": form_changes,
        "pages": _section(pages_before, pages_after, moved_pages),
        "fields": _section(fields_before, fields_after, moved_fields, container=1),
    }
    diff["changed"] = bool(form_changes) or any(
        diff[part][kind]
        for part in ("pages", "fields")
        for kind in ("added", "removed", "moved", "changed")
    )
    return diff
