"""What changed between two versions of a form, as coded entries.

Both versions are read as form spec documents (``form_to_spec_dict``) and
compared by ``form_spec.diff.spec_diff`` (pages and questions matched by id).
This module only *classifies* that structured diff into entries a screen can
put in a sentence in the viewer's language: ``{kind, scope, ref, title,
params}``. No sentence is built here, so no translation lives on the server.

Values in ``params`` are the form's own content (question titles, choice
labels), cut to ``VALUE_LIMIT`` characters; never an answer. A change the
classifier has no word for is reported as ``other_changed`` with the spec keys
that changed, so nothing is dropped silently.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.form_spec.diff import _fields, _pages, spec_diff

#: longest title or label carried in an entry
VALUE_LIMIT = 160
#: most entries returned; ``truncated`` says when there were more
MAX_ENTRIES = 500

_TAG = re.compile(r"<[^>]*>")
_SPACES = re.compile(r"\s+")

# spec keys of a question that are a calculation
_CALCULATION_KEYS = {
    "expression",
    "format",
    "unansweredAsZero",
    "hiddenFromRespondents",
}
_LOGIC_KEYS = {"logic", "optionFilter"}


def plain(value: Any, limit: int = VALUE_LIMIT) -> str:
    """A title or label as one line of plain text: rich text documents and
    html are flattened, anything else is empty."""

    def walk(node: Any) -> str:
        if isinstance(node, dict):
            if isinstance(node.get("text"), str):
                return node["text"]
            return "".join(walk(child) for child in node.get("content") or [])
        if isinstance(node, list):
            return "".join(walk(child) for child in node)
        return ""

    if isinstance(value, str):
        text = _TAG.sub(" ", value)
    else:
        text = walk(value)
    text = _SPACES.sub(" ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _entry(
    kind: str,
    scope: str,
    ref: Optional[str] = None,
    title: Optional[str] = None,
    **params: Any,
) -> Dict[str, Any]:
    return {
        "kind": kind,
        "scope": scope,
        "ref": ref,
        "title": title,
        "params": {k: v for k, v in params.items() if v is not None},
    }


def _relative(path: str, base: str) -> List[str]:
    """The keys of ``path`` below ``base`` (a JSON pointer prefix)."""
    return [p for p in path[len(base) :].split("/") if p]


def _by_id(items: Any) -> Dict[str, Dict[str, Any]]:
    return {
        str(i["id"]): i
        for i in items or []
        if isinstance(i, dict) and i.get("id") is not None
    }


def _choice_label(choice: Optional[Dict[str, Any]]) -> str:
    choice = choice or {}
    return plain(choice.get("value") or choice.get("label") or "")


def _choice_entries(
    ref: str, title: str, before: Any, after: Any
) -> List[Dict[str, Any]]:
    old, new = _by_id(before), _by_id(after)
    entries: List[Dict[str, Any]] = []
    for choice_id, choice in new.items():
        if choice_id not in old:
            entries.append(
                _entry(
                    "choice_added",
                    "question",
                    ref,
                    title,
                    value=_choice_label(choice),
                )
            )
    for choice_id, choice in old.items():
        if choice_id not in new:
            entries.append(
                _entry(
                    "choice_removed",
                    "question",
                    ref,
                    title,
                    value=_choice_label(choice),
                )
            )
    for choice_id, choice in new.items():
        was = old.get(choice_id)
        if was is None:
            continue
        if _choice_label(was) != _choice_label(choice):
            entries.append(
                _entry(
                    "choice_renamed",
                    "question",
                    ref,
                    title,
                    before=_choice_label(was),
                    after=_choice_label(choice),
                )
            )
        if was.get("logic") != choice.get("logic"):
            entries.append(
                _entry(
                    "choice_logic_changed",
                    "question",
                    ref,
                    title,
                    value=_choice_label(choice),
                )
            )
    kept = [i for i in old if i in new]
    if kept != [i for i in new if i in old]:
        entries.append(_entry("choices_reordered", "question", ref, title))
    return entries


def _rule_entry(ref: str, title: str, before: Any, after: Any) -> Dict[str, Any]:
    old, new = _by_id(before), _by_id(after)
    added = [i for i in new if i not in old]
    removed = [i for i in old if i not in new]
    changed = [i for i in new if i in old and new[i] != old[i]]
    if not (added or removed or changed):
        # the same rules in another order
        return _entry("rules_reordered", "question", ref, title)
    return _entry(
        "rules_changed",
        "question",
        ref,
        title,
        added=len(added),
        removed=len(removed),
        changed=len(changed),
    )


def _field_changes(
    ref: str,
    title: str,
    base: str,
    old_field: Dict[str, Any],
    new_field: Dict[str, Any],
    changes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """The entries of one changed question, from its leaf ``changes``."""
    entries: List[Dict[str, Any]] = []
    validation_keys: List[str] = []
    other_keys: List[str] = []
    seen: set = set()

    def once(key: str) -> bool:
        if key in seen:
            return False
        seen.add(key)
        return True

    for change in changes:
        keys = _relative(change["path"], base)
        head = keys[0] if keys else ""
        if head == "title":
            if once("title"):
                entries.append(
                    _entry(
                        "title_changed",
                        "question",
                        ref,
                        plain(new_field.get("title")) or title,
                        before=plain(old_field.get("title")),
                        after=plain(new_field.get("title")),
                    )
                )
        elif head == "type":
            if once("type"):
                entries.append(
                    _entry(
                        "type_changed",
                        "question",
                        ref,
                        title,
                        before=str(old_field.get("type")),
                        after=str(new_field.get("type")),
                    )
                )
        elif head == "validations":
            sub = keys[1] if len(keys) > 1 else ""
            if sub == "required":
                if once("required"):
                    entries.append(
                        _entry(
                            "required_changed",
                            "question",
                            ref,
                            title,
                            required=bool(
                                (new_field.get("validations") or {}).get("required")
                            ),
                        )
                    )
            elif sub and sub not in validation_keys:
                validation_keys.append(sub)
            elif not sub and "validations" not in validation_keys:
                validation_keys.append("validations")
        elif head == "choices":
            if once("choices"):
                found = _choice_entries(
                    ref, title, old_field.get("choices"), new_field.get("choices")
                )
                # e.g. only an option's image changed
                entries += found or [
                    _entry("other_changed", "question", ref, title, keys=["choices"])
                ]
        elif head == "rules":
            if once("rules"):
                entries.append(
                    _rule_entry(ref, title, old_field.get("rules"), new_field.get("rules"))
                )
        elif head in _LOGIC_KEYS:
            if once("logic"):
                entries.append(_entry("logic_changed", "question", ref, title))
        elif head in _CALCULATION_KEYS:
            if once("calculation"):
                entries.append(_entry("calculation_changed", "question", ref, title))
        elif head == "description":
            if once("description"):
                entries.append(_entry("description_changed", "question", ref, title))
        elif head and head not in other_keys:
            other_keys.append(head)
    if validation_keys:
        entries.append(
            _entry(
                "validation_changed",
                "question",
                ref,
                title,
                keys=sorted(validation_keys),
            )
        )
    if other_keys:
        entries.append(
            _entry("other_changed", "question", ref, title, keys=sorted(other_keys))
        )
    return entries


def _form_entries(changes: List[Dict[str, Any]], before: Dict, after: Dict):
    entries: List[Dict[str, Any]] = []
    seen: set = set()
    for change in changes:
        keys = [p for p in change["path"].split("/") if p]
        head = keys[0] if keys else ""
        if head in seen:
            continue
        seen.add(head)
        if head == "title":
            entries.append(
                _entry(
                    "form_title_changed",
                    "form",
                    before=plain(before.get("title")),
                    after=plain(after.get("title")),
                )
            )
        elif head == "description":
            entries.append(_entry("form_description_changed", "form"))
        elif head == "language":
            entries.append(
                _entry(
                    "language_changed",
                    "form",
                    before=before.get("language"),
                    after=after.get("language"),
                )
            )
        elif head == "theme":
            entries.append(_entry("theme_changed", "form"))
        elif head == "welcomePage":
            entries.append(_entry("welcome_page_changed", "form"))
        elif head == "endings":
            entries.append(_entry("ending_changed", "form"))
        elif head == "logo":
            entries.append(_entry("logo_settings_changed", "form"))
        elif head == "hiddenFields":
            old = set(before.get("hiddenFields") or [])
            new = set(after.get("hiddenFields") or [])
            added = sorted(new - old)
            removed = sorted(old - new)
            if added:
                entries.append(
                    _entry("hidden_fields_added", "form", names=[plain(n, 80) for n in added])
                )
            if removed:
                entries.append(
                    _entry(
                        "hidden_fields_removed",
                        "form",
                        names=[plain(n, 80) for n in removed],
                    )
                )
            if not added and not removed:
                entries.append(_entry("other_changed", "form", keys=["hiddenFields"]))
        else:
            entries.append(_entry("other_changed", "form", keys=[head]))
    return entries


def compare_specs(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """``{changed, entries, truncated}`` for the spec documents of two
    versions of a form (``before`` the older side of the comparison)."""
    diff = spec_diff(before, after)
    entries: List[Dict[str, Any]] = _form_entries(diff["form"], before, after)

    pages_before, pages_after = _pages(before), _pages(after)
    page_numbers = {pid: i + 1 for i, pid in enumerate(pages_after)}
    old_numbers = {pid: i + 1 for i, pid in enumerate(pages_before)}

    def page_title(pid: str, side: Dict[str, Tuple[str, Dict[str, Any]]]) -> str:
        return plain((side.get(pid) or ("", {}))[1].get("sectionTitle"))

    for item in diff["pages"]["added"]:
        pid = item["id"]
        entries.append(
            _entry(
                "page_added",
                "page",
                pid,
                page_title(pid, pages_after),
                number=page_numbers.get(pid),
            )
        )
    for item in diff["pages"]["removed"]:
        pid = item["id"]
        entries.append(
            _entry(
                "page_removed",
                "page",
                pid,
                page_title(pid, pages_before),
                number=old_numbers.get(pid),
            )
        )
    for item in diff["pages"]["moved"]:
        pid = item["id"]
        entries.append(
            _entry(
                "page_moved",
                "page",
                pid,
                page_title(pid, pages_after),
                before=old_numbers.get(pid),
                after=page_numbers.get(pid),
            )
        )
    for item in diff["pages"]["changed"]:
        pid = item["id"]
        base = item["path"]
        heads: List[str] = []
        for change in item["changes"]:
            keys = _relative(change["path"], base)
            if keys and keys[0] not in heads:
                heads.append(keys[0])
        title = page_title(pid, pages_after)
        number = page_numbers.get(pid)
        if "jumps" in heads:
            entries.append(
                _entry("page_jumps_changed", "page", pid, title, number=number)
            )
        rest = [h for h in heads if h != "jumps"]
        if rest:
            entries.append(
                _entry(
                    "page_changed",
                    "page",
                    pid,
                    title,
                    number=number,
                    keys=sorted(rest),
                )
            )

    fields_before, fields_after = _fields(before), _fields(after)

    def field_title(fid: str, side: Dict[str, Tuple]) -> str:
        return plain((side.get(fid) or ("", "", {}))[2].get("title"))

    def page_of(fid: str, side: Dict[str, Tuple], numbers: Dict[str, int]):
        container = (side.get(fid) or ("", None, {}))[1]
        if container in numbers:
            return numbers[container]
        return None

    for item in diff["fields"]["added"]:
        fid = item["id"]
        field = fields_after[fid][2]
        entries.append(
            _entry(
                "question_added",
                "question",
                fid,
                field_title(fid, fields_after),
                type=str(field.get("type")),
                page=page_of(fid, fields_after, page_numbers),
            )
        )
    for item in diff["fields"]["removed"]:
        fid = item["id"]
        field = fields_before[fid][2]
        entries.append(
            _entry(
                "question_removed",
                "question",
                fid,
                field_title(fid, fields_before),
                type=str(field.get("type")),
                page=page_of(fid, fields_before, old_numbers),
            )
        )
    for item in diff["fields"]["moved"]:
        fid = item["id"]
        entries.append(
            _entry(
                "question_moved",
                "question",
                fid,
                field_title(fid, fields_after),
                before=page_of(fid, fields_before, old_numbers),
                after=page_of(fid, fields_after, page_numbers),
            )
        )
    for item in diff["fields"]["changed"]:
        fid = item["id"]
        entries += _field_changes(
            fid,
            field_title(fid, fields_after),
            item["path"],
            fields_before[fid][2],
            fields_after[fid][2],
            item["changes"],
        )

    truncated = len(entries) > MAX_ENTRIES
    return {
        "changed": bool(diff["changed"]),
        "entries": entries[:MAX_ENTRIES],
        "truncated": truncated,
    }
