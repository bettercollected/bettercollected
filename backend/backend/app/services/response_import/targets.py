"""What a CSV column of an import may be filled into, and the auto-matching of
the file's headers to it.

Targets follow the export's own columns (``response_export/table.py``): a
question is ``q:<field id>``, a staff-only question ``internal:<field id>``, a
declared hidden field ``hidden:<name>`` and the submission time
``submitted_at``. A question inside a repeating group exported with the
``columns`` layout has one target per item and question,
``q:<group id>#<item>#<question id>``. They are worked out from the published
version of the form (what respondents answer): a question that exists only in
the draft is not offered. The draft's headers are accepted as well, because an
export is made from the draft.

Some columns are known and left out on purpose (``status`` ``ignored``: the
responder, the response id, a calculated question, a group exported as rows) or
cannot be imported (``unsupported``: a file upload, a drawn signature, a
matrix, a table). The mapping may not name them; auto-matching reports them so
the screen can say why a column was left alone.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from backend.app.services.internal_fields import INTERNAL_CAPABLE_TYPES
from backend.app.services.response_export import table

STATUS_OK = "ok"
STATUS_IGNORED = "ignored"
STATUS_UNSUPPORTED = "unsupported"

KEY_SUBMITTED_AT = table.KEY_SUBMITTED_AT
GROUP_SEPARATOR = "#"

# question types an answer can be read back for from the export's cell text
SIMPLE_TYPES = {
    "short_text",
    "long_text",
    "email",
    "url",
    "phone_number",
    "number",
    "rating",
    "linear_rating",
    "date",
    "day",
    "time",
    "currency",
    "date_range",
    "tags",
    "address",
    "yes_no",
    "multiple_choice",
    "dropdown",
    "signature",
}
# why a column is left alone (the codes the webapp translates)
IGNORED_RESPONDER = "responder_ignored"
IGNORED_RESPONSE_ID = "response_id_ignored"
IGNORED_CALCULATED = "calculated_ignored"
IGNORED_GROUP_ROWS = "group_rows_ignored"
UNSUPPORTED_TYPE = "type_unsupported"
UNSUPPORTED_OPTION_SOURCE = "option_source_unsupported"


@dataclass
class Target:
    key: str
    # the label shown for the target (the export's header for it)
    label: str
    kind: str  # question | internal | hidden | meta | responder
    status: str = STATUS_OK
    reason: Optional[str] = None
    definition: Optional[Dict[str, Any]] = field(default=None, repr=False)
    # a question inside a repeating group: the group's id and the item (from 0)
    group_id: Optional[str] = None
    item: Optional[int] = None
    # every header this target is matched by (normalised), in match order
    headers: List[str] = field(default_factory=list, repr=False)
    # the question's id, for the screens (never a title in the audit)
    field_id: Optional[str] = None


def normalise_header(text: Any) -> str:
    """A header compared loosely: Unicode form KC, case-folded, whitespace
    collapsed, the export's en dash and a hyphen alike, a leading apostrophe
    (the export's formula guard) dropped."""
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(r"\s+", " ", value).strip()
    return value.lstrip("'").strip()


def _field_status(field_: Dict[str, Any]) -> tuple:
    kind = field_.get("type")
    if kind == "calculated":
        return STATUS_IGNORED, IGNORED_CALCULATED
    properties = field_.get("properties")
    if isinstance(properties, dict) and properties.get("option_source"):
        # the options come from a list or another question: the submit path
        # resolves them (OptionSourceService.apply), the import does not (4.3)
        return STATUS_UNSUPPORTED, UNSUPPORTED_OPTION_SOURCE
    if kind in SIMPLE_TYPES:
        return STATUS_OK, None
    return STATUS_UNSUPPORTED, UNSUPPORTED_TYPE


def group_key(group_id: str, item: int, child_id: str) -> str:
    return f"{table.QUESTION_PREFIX}{group_id}{GROUP_SEPARATOR}{item}{GROUP_SEPARATOR}{child_id}"


def split_group_key(key: str) -> Optional[tuple]:
    """``(group id, item, child id)`` of a group target key, else None."""
    if not key.startswith(table.QUESTION_PREFIX) or GROUP_SEPARATOR not in key:
        return None
    parts = key[len(table.QUESTION_PREFIX) :].split(GROUP_SEPARATOR)
    if len(parts) != 3 or not parts[1].isdigit():
        return None
    return parts[0], int(parts[1]), parts[2]


def _by_id(fields: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(f.get("id")): f for f in fields}


def build_targets(published: Dict[str, Any], draft: Optional[Dict[str, Any]] = None) -> List[Target]:
    """Every target of the form, in the export's column order. ``published``
    and ``draft`` are form documents as plain dicts (``model_dump`` with
    ``exclude_none``)."""
    questions = _by_id(table.form_fields(published))
    internals = _by_id(table.internal_fields(published))
    draft_headers: Dict[str, List[str]] = {}
    if draft is not None:
        for column in table.catalogue(draft):
            draft_headers[column.key] = column.all_headers
    targets: List[Target] = []
    for column in table.catalogue(published):
        headers = [normalise_header(h) for h in column.all_headers]
        extra = [normalise_header(h) for h in draft_headers.get(column.key, [])]
        key = column.key
        if key == table.KEY_RESPONDER:
            targets.append(Target(key, column.header, "responder", STATUS_IGNORED, IGNORED_RESPONDER, headers=headers))
        elif key == table.KEY_RESPONSE_ID:
            targets.append(Target(key, column.header, "meta", STATUS_IGNORED, IGNORED_RESPONSE_ID, headers=headers + extra))
        elif key == table.KEY_SUBMITTED_AT:
            targets.append(Target(key, column.header, "meta", headers=headers + extra))
        elif key.startswith(table.HIDDEN_PREFIX):
            targets.append(Target(key, column.header, "hidden", headers=headers + extra))
        elif key.startswith(table.INTERNAL_PREFIX):
            field_ = internals.get(key[len(table.INTERNAL_PREFIX) :])
            if field_ is None:
                continue
            # staff fill internal questions in as text, number, date, email, link,
            # phone, yes/no or a choice (internal_fields.INTERNAL_CAPABLE_TYPES)
            status, reason = _field_status(field_)
            if field_.get("type") not in INTERNAL_CAPABLE_TYPES:
                status, reason = STATUS_UNSUPPORTED, UNSUPPORTED_TYPE
            targets.append(
                Target(key, column.header, "internal", status, reason, definition=field_,
                       headers=headers + extra, field_id=str(field_.get("id")))
            )
        elif key.startswith(table.QUESTION_PREFIX):
            field_ = questions.get(key[len(table.QUESTION_PREFIX) :])
            if field_ is None:
                continue
            if table.is_repeating_group(field_):
                targets.extend(_group_targets(column, field_, extra))
                continue
            status, reason = _field_status(field_)
            targets.append(
                Target(key, column.header, "question", status, reason, definition=field_,
                       headers=headers + extra, field_id=str(field_.get("id")))
            )
    return targets


def _group_targets(column, group: Dict[str, Any], extra: List[str]) -> List[Target]:
    group_id = str(group.get("id"))
    settings = table.repeat_settings(group)
    if settings.export_layout == "rows":
        return [
            Target(column.key, column.header, "question", STATUS_IGNORED, IGNORED_GROUP_ROWS,
                   definition=group, headers=[normalise_header(column.header)] + extra,
                   field_id=group_id, group_id=group_id)
        ]
    children = table._exportable_children(group)
    out: List[Target] = []
    headers = column.all_headers
    for item in range(settings.max_items):
        for index, child in enumerate(children):
            position = item * len(children) + index
            label = headers[position] if position < len(headers) else str(child.get("id"))
            status, reason = _field_status(child)
            if child.get("type") == "calculated":
                status, reason = STATUS_UNSUPPORTED, UNSUPPORTED_TYPE
            out.append(
                Target(
                    group_key(group_id, item, str(child.get("id"))),
                    label,
                    "question",
                    status,
                    reason,
                    definition=child,
                    group_id=group_id,
                    item=item,
                    headers=[normalise_header(label)],
                    field_id=str(child.get("id")),
                )
            )
    return out


def suggest_mapping(headers: Sequence[str], targets: Sequence[Target]):
    """``(mapping, notes)``: for each CSV column position (as text) the target
    key it is matched to; columns the export itself writes but an import leaves
    alone are listed as notes ``{"column": position, "code": ...}``.

    A header matches by the export's own text first, then by a question's id
    (``q:<id>`` or the bare id). Two questions with one title are matched in the
    order the columns come. A target is used once."""
    taken: Set[str] = set()
    mapping: Dict[str, str] = {}
    notes: List[Dict[str, Any]] = []
    by_header: Dict[str, List[Target]] = {}
    for target in targets:
        for header in dict.fromkeys(target.headers):
            by_header.setdefault(header, []).append(target)
    by_id: Dict[str, Target] = {}
    for target in targets:
        if target.status == STATUS_OK and target.field_id and target.kind == "question" and target.group_id is None:
            by_id.setdefault(target.field_id.casefold(), target)
    for position, header in enumerate(headers):
        wanted = normalise_header(header)
        if not wanted:
            continue
        chosen: Optional[Target] = None
        for candidate in by_header.get(wanted, []):
            if candidate.key not in taken:
                chosen = candidate
                break
        if chosen is None:
            bare = wanted[len(table.QUESTION_PREFIX) :] if wanted.startswith(table.QUESTION_PREFIX) else wanted
            candidate = by_id.get(bare)
            if candidate is not None and candidate.key not in taken:
                chosen = candidate
        if chosen is None:
            continue
        if chosen.status == STATUS_OK:
            taken.add(chosen.key)
            mapping[str(position)] = chosen.key
        else:
            taken.add(chosen.key)
            notes.append({"column": position, "code": chosen.reason})
    return mapping, notes
