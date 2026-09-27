"""Compile the Form Document Model into the draft form.

The redesign is a list of explicit rules (plans: "redesign is rules, not
vibes"), each recorded in the import report:

- one section = one page; long sections split, tiny ones merged into the
  previous page; the section title heads its page;
- a choice with an "Other" option gets a "Please specify" field shown only
  when "Other" is chosen; "if yes, mention…" follow-ups are shown only on yes;
- legal terms and declarations are kept verbatim as statements; long terms
  move to a "Terms and declarations" page before the end, with an agreement;
- signatures become "full name as signature" plus a confirmation (D1);
  thumbprints cannot be collected online and are listed as dropped;
- B.S./A.D. date pairs become two date fields for now (D6);
- a location sketch becomes landmark, distance and direction questions plus an
  optional map upload; photo boxes become image uploads;
- a table with open rows becomes a repeating group (one question per column,
  at most as many items as the paper has rows); a table with labelled rows
  stays a grid of fields; joint-applicant blocks asking the same questions
  become one repeating group with an item per applicant (D7);
- the labelled answer places of staff-only parts become internal fields on a
  page of their own at the end: never shown to respondents, filled in by
  staff on each submission, and never used by logic (D5, D10).

Everything goes through the typed edit operations (``apply_form_ops``), built
from an empty form in memory and saved once, so compiling again produces the
same form instead of adding to it.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

MAX_FIELDS_PER_PAGE = 12
TINY_SECTION = 2
LONG_STATEMENT_WORDS = 150
DEFAULT_OPEN_TABLE_ROWS = 5  # items of a table whose row count is unknown
MAX_GROUP_ITEMS = 50  # RepeatSettings' limit
MAX_GROUP_QUESTIONS = 20
INTERNAL_PAGE_TITLE = "For office use"

FIELD_TYPE = {
    "short_text": "short_text",
    "long_text": "long_text",
    "number": "number",
    "email": "email",
    "phone": "phone_number",
    "url": "url",
    "date": "date",
    "char_cells": "short_text",
    "yes_no": "yes_no",
    "file": "file_upload",
    "image": "file_upload",
}
OTHER = re.compile(r"^(other|others|अन्य|anya)\b", re.I)


@dataclass
class PlannedField:
    key: str
    spec: Dict[str, Any]
    source: Optional[str] = None
    # a repeating group: its settings (add_group) and its child questions
    group: Optional[Dict[str, Any]] = None
    children: List["PlannedField"] = field(default_factory=list)

    @property
    def weight(self) -> int:
        """How much of a page it takes: a group counts its questions."""
        return 1 + len(self.children) if self.group is not None else 1


@dataclass
class PlannedPage:
    title: str
    fields: List[PlannedField] = field(default_factory=list)
    internal: bool = False  # only internal fields: never shown to respondents


@dataclass
class Plan:
    pages: List[PlannedPage] = field(default_factory=list)
    logic: List[Dict[str, Any]] = field(default_factory=list)
    report: Dict[str, Any] = field(
        default_factory=lambda: {
            "rules": Counter(),
            "dropped": [],
            "staff_only": [],
            "groups": [],
        }
    )

    def rule(self, name: str) -> None:
        self.report["rules"][name] += 1


# a large or adversarial FDM must still give a form the editor can open and a
# document well under the database's size limit
MAX_FIELDS = 500
MAX_CHOICES = 50
MAX_TABLE_CELLS = 100
MAX_HELP_CHARS = 1000
MAX_CHOICE_CHARS = 300


def _spec(title: str, type_: str, **extra) -> Dict[str, Any]:
    spec = {"title": title.strip()[:500] or "Untitled question", "type": type_}
    spec.update({k: v for k, v in extra.items() if v is not None})
    if isinstance(spec.get("description"), str):
        spec["description"] = spec["description"][:MAX_HELP_CHARS]
    if spec.get("choices"):
        spec["choices"] = [str(c)[:MAX_CHOICE_CHARS] for c in spec["choices"]]
    return spec


def _statement(text: str) -> Dict[str, Any]:
    return {"title": text.strip()[:5000], "type": "text"}


def _clean(label: str) -> str:
    label = re.sub(r"[.…_]{3,}", "", label or "").strip()
    return label.rstrip(":：").strip()


clean_label = _clean  # leader dots and trailing colons off a label from the document


# --- planning ---------------------------------------------------------------------------


def _fields_for(
    q: dict, plan: Plan, in_group: bool = False
) -> Tuple[List[PlannedField], List[Dict[str, Any]]]:
    """Fields for one FDM question, plus visibility rules that refer to them.
    ``in_group``: asked once per item of an applicant group, so unprefixed."""
    kind = q["kind"]
    label = _clean(q.get("label") or "")
    if (
        not in_group
        and isinstance(q.get("applicant_index"), int)
        and q["applicant_index"] > 1
    ):
        label = f"Applicant {q['applicant_index']}: {label}"
        plan.rule("applicant_blocks_prefixed")
    required = q.get("required") if isinstance(q.get("required"), bool) else None
    key = q["id"]
    fields: List[PlannedField] = []
    logic: List[Dict[str, Any]] = []
    help_text = q.get("help")

    if kind in FIELD_TYPE:
        extra = {}
        if kind == "char_cells":
            extra["placeholder"] = "One character per box on the paper form"
            plan.rule("character_cells_to_text")
        if kind == "image":
            extra["description"] = "Upload a photo (JPG or PNG)."
            plan.rule("photo_box_to_upload")
        fields.append(
            PlannedField(
                key,
                _spec(
                    label,
                    FIELD_TYPE[kind],
                    required=required,
                    description=help_text or extra.pop("description", None),
                    **extra,
                ),
                q["id"],
            )
        )
    elif kind in ("single_choice", "multi_choice"):
        options = [
            o["label"].strip()
            for o in q.get("options") or []
            if o.get("label", "").strip()
        ]
        options = list(dict.fromkeys(options))
        if len(options) > MAX_CHOICES:
            plan.report["dropped"].append(
                {
                    "element": q["id"],
                    "label": label,
                    "reason": f"only the first {MAX_CHOICES} of {len(options)} options were kept",
                }
            )
            options = options[:MAX_CHOICES]
        if len(options) < 2:
            fields.append(
                PlannedField(
                    key, _spec(label, "short_text", required=required), q["id"]
                )
            )
            plan.rule("choice_with_one_option_to_text")
        else:
            fields.append(
                PlannedField(
                    key,
                    _spec(
                        label,
                        "multiple_choice",
                        required=required,
                        choices=options,
                        allow_multiple=kind == "multi_choice" or None,
                        description=help_text,
                    ),
                    q["id"],
                )
            )
            others = [
                o
                for o in q.get("options") or []
                if o.get("is_other") or OTHER.match(o.get("label", ""))
            ]
            if others:
                other_label = others[0]["label"].strip()
                fields.append(
                    PlannedField(
                        f"{key}:other", _spec("Please specify", "short_text"), q["id"]
                    )
                )
                logic.append(
                    {
                        "target": f"{key}:other",
                        "parent": key,
                        "comparison": "IS_EQUAL",
                        "value": other_label,
                    }
                )
                plan.rule("other_option_gets_specify_field")
    elif kind == "date_pair_bs_ad":
        base = re.sub(
            r"\(?\b(?:B\.?\s?S|A\.?\s?D)\b\.?\)?|वि\.?\s?सं\.?|ई\.?\s?सं\.?", "", label
        )
        base = re.sub(r"\s+", " ", base).strip(" :.-/") or label
        fields.append(
            PlannedField(
                f"{key}:bs",
                _spec(f"{base} (B.S.)", "date", required=required, col_span=6),
                q["id"],
            )
        )
        fields.append(
            PlannedField(
                f"{key}:ad", _spec(f"{base} (A.D.)", "date", col_span=6), q["id"]
            )
        )
        plan.rule("bs_ad_date_pair_to_two_dates")
    elif kind == "consent":
        fields.append(
            PlannedField(
                key, _spec(label or "I agree", "yes_no", required=True), q["id"]
            )
        )
        plan.rule("consent")
    elif kind == "signature":
        who = (
            f" ({label})"
            if label and label.lower() not in ("signature", "sign")
            else ""
        )
        fields.append(
            PlannedField(
                f"{key}:name",
                _spec(
                    f"Full name, as your signature{who}", "short_text", required=True
                ),
                q["id"],
            )
        )
        fields.append(
            PlannedField(
                f"{key}:confirm",
                _spec(
                    "I confirm that the information I have given is true and complete.",
                    "yes_no",
                    required=True,
                ),
                q["id"],
            )
        )
        plan.rule("signature_to_typed_name_and_confirmation")
    elif kind == "thumbprint":
        plan.report["dropped"].append(
            {
                "element": q["id"],
                "label": label,
                "reason": "Thumbprints cannot be collected online.",
            }
        )
    elif kind == "location_sketch":
        fields.append(
            PlannedField(
                f"{key}:landmark",
                _spec("Nearest landmark (school, hospital, bank…)", "short_text"),
                q["id"],
            )
        )
        fields.append(
            PlannedField(
                f"{key}:distance",
                _spec("Distance from the landmark (metres)", "number", col_span=6),
                q["id"],
            )
        )
        fields.append(
            PlannedField(
                f"{key}:direction",
                _spec(
                    "Direction from the landmark",
                    "multiple_choice",
                    choices=["North", "East", "South", "West"],
                    col_span=6,
                ),
                q["id"],
            )
        )
        fields.append(
            PlannedField(
                f"{key}:map",
                _spec("Map or sketch of the location (optional)", "file_upload"),
                q["id"],
            )
        )
        plan.rule("location_sketch_to_questions")
    elif kind in ("table_fixed_rows", "table_open_rows"):
        fields.extend(_table_fields(q, label, plan))
    else:
        fields.append(
            PlannedField(key, _spec(label, "short_text", required=required), q["id"])
        )
    return fields, logic


_COLUMN_TYPES = (
    (re.compile(r"e-?mail|ईमेल|इमेल", re.I), "email"),
    (
        re.compile(r"\b(?:phone|mobile|telephone)\b|फोन|मोबाइल|टेलिफोन", re.I),
        "phone_number",
    ),
    (re.compile(r"\bdate\b|\bdob\b|मिति", re.I), "date"),
)


def _column_type(header: str) -> str:
    for pattern, type_ in _COLUMN_TYPES:
        if pattern.search(header):
            return type_
    return "short_text"


def _table_fields(q: dict, label: str, plan: Plan) -> List[PlannedField]:
    table = q.get("table") or {}
    header = [_clean(str(h)) for h in (table.get("header") or []) if h]
    header = [h for h in header if h]
    row_labels = [r for r in (table.get("row_labels") or []) if r]
    if q["kind"] == "table_fixed_rows" and row_labels and len(header) >= 2:
        # labelled rows (Father, Mother...): each cell is its own question
        out: List[PlannedField] = []
        columns = header[1:]
        span = max(4, 12 // max(1, len(columns)))
        for r, row in enumerate(row_labels):
            for c, col in enumerate(columns):
                out.append(
                    PlannedField(
                        f"{q['id']}:r{r}c{c}",
                        _spec(f"{_clean(row)} – {col}", "short_text", col_span=span),
                        q["id"],
                    )
                )
        plan.rule("fixed_table_to_fields")
        if len(out) > MAX_TABLE_CELLS:
            plan.report["dropped"].append(
                {
                    "element": q["id"],
                    "label": label,
                    "reason": f"only the first {MAX_TABLE_CELLS} of {len(out)} table cells were kept",
                }
            )
            out = out[:MAX_TABLE_CELLS]
        return out

    # open rows: one item per row the respondent fills, one question per column
    columns = header or [label or "Entry"]
    if len(columns) > MAX_GROUP_QUESTIONS:
        plan.report["dropped"].append(
            {
                "element": q["id"],
                "label": label,
                "reason": f"only the first {MAX_GROUP_QUESTIONS} of {len(columns)} table columns were kept",
            }
        )
        columns = columns[:MAX_GROUP_QUESTIONS]
    rows = table.get("rows")
    rows = rows - 1 if isinstance(rows, int) and rows > 1 else DEFAULT_OPEN_TABLE_ROWS
    max_items = max(1, min(MAX_GROUP_ITEMS, rows))
    has_label = bool(label) and label != " / ".join(header)
    item_label = (label if has_label else columns[0])[:80]
    span = max(4, 12 // max(1, len(columns)))
    children = [
        PlannedField(
            f"{q['id']}:c{c}",
            _spec(col, _column_type(col), col_span=span if len(columns) > 1 else None),
            q["id"],
        )
        for c, col in enumerate(columns)
    ]
    plan.rule("open_table_to_repeating_group")
    plan.report["groups"].append(
        {"element": q["id"], "label": label, "from": "table", "max_items": max_items}
    )
    return [
        PlannedField(
            q["id"],
            _spec(label or " / ".join(columns), "group"),
            q["id"],
            group={
                "item_label": item_label,
                "min_items": 1 if q.get("required") is True else 0,
                "max_items": max_items,
            },
            children=children,
        )
    ]


# a question that cannot be asked inside a repeating group (uploads, tables,
# a location sketch with its map upload, a dropped thumbprint)
NOT_GROUPABLE = {
    "file",
    "image",
    "location_sketch",
    "table_fixed_rows",
    "table_open_rows",
    "thumbprint",
}


def _question_key(q: dict) -> Tuple[str, str]:
    """What makes two applicants' questions the same question."""
    text = (q.get("label") or "").lower()
    text = re.sub(r"applicant|आवेदक|[0-9०-९]+", " ", text)
    text = re.sub(r"[\s:：.…_()\-–/]+", " ", text)
    return (q.get("kind") or "", text.strip())


def _applicant_group(questions: List[dict], plan: Plan) -> Tuple[Dict[str, Any], set]:
    """Joint-applicant blocks that ask the same questions become one repeating
    group with an item per applicant: (group, ids of the questions it
    replaces). The group holds applicant 1's questions; applicants 2..n are
    its further items. Blocks that differ keep their "Applicant N:" prefixes."""
    blocks: Dict[int, List[dict]] = {}
    for q in questions:
        index = q.get("applicant_index")
        if isinstance(index, int) and 1 <= index <= MAX_GROUP_ITEMS:
            if q.get("kind") not in NOT_GROUPABLE:
                blocks.setdefault(index, []).append(q)
    indices = sorted(blocks)
    if len(indices) < 2 or indices != list(range(1, len(indices) + 1)):
        return {}, set()
    first = [_question_key(q) for q in blocks[1]]
    if not first or any(
        [_question_key(q) for q in blocks[i]] != first for i in indices[1:]
    ):
        return {}, set()
    members = blocks[1]
    if len(members) > MAX_GROUP_QUESTIONS:
        return {}, set()
    replaced = {q["id"] for i in indices for q in blocks[i]}
    plan.rule("applicant_blocks_to_repeating_group")
    plan.report["groups"].append(
        {
            "element": members[0]["id"],
            "label": "Applicants",
            "from": "applicant_blocks",
            "max_items": len(indices),
        }
    )
    return {
        "anchor": members[0]["id"],
        "members": members,
        "max_items": len(indices),
    }, replaced


# staff-only answer place (structuring.staff_fields) -> internal field type;
# only types staff can fill in from the dashboard (INTERNAL_CAPABLE_TYPES)
INTERNAL_TYPE = {
    "short_text": "short_text",
    "char_cells": "short_text",
    "signature": "short_text",
    "long_text": "long_text",
    "number": "number",
    "date": "date",
    "email": "email",
    "phone": "phone_number",
    "url": "url",
    "yes_no": "yes_no",
}


def _internal_fields(e: dict, plan: Plan) -> List[PlannedField]:
    """Internal fields for the labelled answer places of a staff-only part."""
    out: List[PlannedField] = []
    for n, f in enumerate(e.get("fields") or []):
        if not isinstance(f, dict):
            continue
        label = _clean(str(f.get("label") or ""))
        kind = f.get("kind")
        if not label:
            continue
        options = [
            str(o.get("label") or "").strip()
            for o in f.get("options") or []
            if isinstance(o, dict)
        ]
        options = list(dict.fromkeys(o for o in options if o))[:MAX_CHOICES]
        if kind in ("single_choice", "multi_choice") and len(options) >= 2:
            spec = _spec(
                label,
                "multiple_choice",
                choices=options,
                allow_multiple=kind == "multi_choice" or None,
            )
        elif kind in INTERNAL_TYPE:
            spec = _spec(label, INTERNAL_TYPE[kind])
        elif kind in ("single_choice", "multi_choice"):
            spec = _spec(label, "short_text")
        else:
            plan.report["dropped"].append(
                {
                    "element": e["id"],
                    "label": label,
                    "reason": "Staff can only fill in text, dates, numbers and choices online.",
                }
            )
            continue
        spec["internal"] = True
        out.append(PlannedField(f"{e['id']}:f{n}", spec, e["id"]))
    return out


def _chunks(fields: List[PlannedField]) -> List[List[PlannedField]]:
    """Fields packed into pages of at most MAX_FIELDS_PER_PAGE questions (a
    repeating group counts its questions and is never split)."""
    out: List[List[PlannedField]] = [[]]
    size = 0
    for f in fields:
        if out[-1] and size + f.weight > MAX_FIELDS_PER_PAGE:
            out.append([])
            size = 0
        out[-1].append(f)
        size += f.weight
    return out


def plan_form(fdm: dict) -> Plan:
    plan = Plan()
    elements = [e for e in fdm.get("elements") or [] if isinstance(e, dict)]
    staff_headings = {
        (e.get("heading") or "").strip().lower()
        for e in elements
        if e.get("type") == "staff_only"
    }
    sections: Dict[str, dict] = {
        e["id"]: e
        for e in elements
        if e.get("type") == "section"
        and (e.get("title") or "").strip().lower() not in staff_headings
    }
    order: List[str] = []
    buckets: Dict[str, List[Tuple[str, dict]]] = {}
    terms: List[dict] = []
    internal: List[PlannedField] = []
    applicants, replaced = _applicant_group(
        [e for e in elements if e.get("type") == "question"], plan
    )

    def bucket(section_id: Optional[str]) -> str:
        sid = section_id if section_id in sections else "__none__"
        if sid not in buckets:
            buckets[sid] = []
            order.append(sid)
        return sid

    for e in elements:
        if e.get("type") == "staff_only":
            fields = _internal_fields(e, plan)
            internal.extend(fields)
            plan.report["staff_only"].append(
                {
                    "element": e["id"],
                    "heading": e.get("heading") or "",
                    "layout_items": len(e.get("refs") or []),
                    "internal_fields": len(fields),
                }
            )
            if fields:
                plan.report["rules"]["staff_only_to_internal_fields"] += len(fields)
            else:
                plan.rule("staff_only_listed")
        elif e.get("type") == "statement":
            words = len((e.get("text") or "").split())
            if e.get("legal") and words >= LONG_STATEMENT_WORDS:
                terms.append(e)
                plan.rule("long_terms_to_terms_page")
            else:
                buckets[bucket(e.get("section"))].append(("statement", e))
        elif e.get("type") == "question":
            if e["id"] in replaced and e["id"] != applicants["anchor"]:
                continue  # asked inside the applicant group
            buckets[bucket(e.get("section"))].append(("question", e))
        elif e.get("type") == "section":
            bucket(e["id"])

    def follow_up(e: dict, fields: List[PlannedField]) -> None:
        if e.get("follow_up_of") and fields:
            parent = e["follow_up_of"]["question"]
            plan.logic.append(
                {
                    "target": fields[0].key,
                    "parent": parent,
                    "comparison": "IS_EQUAL",
                    "value": (
                        "Yes"
                        if e["follow_up_of"].get("when", "yes").lower()
                        in ("yes", "हो", "true")
                        else e["follow_up_of"]["when"]
                    ),
                }
            )
            plan.rule("follow_up_shown_on_yes")

    pending: List[PlannedPage] = []
    for sid in order:
        items = buckets[sid]
        if not items:
            continue
        title = _clean(sections[sid]["title"]) if sid in sections else "Details"
        page = PlannedPage(title=title)
        page.fields.append(
            PlannedField(f"{sid}:heading", {"title": title, "type": "text"})
        )
        for kind, e in items:
            if kind == "statement":
                page.fields.append(
                    PlannedField(e["id"], _statement(e["text"]), e["id"])
                )
                plan.rule("statement_verbatim")
                continue
            if applicants and e["id"] == applicants["anchor"]:
                children: List[PlannedField] = []
                for member in applicants["members"]:
                    fields, logic = _fields_for(member, plan, in_group=True)
                    children.extend(fields)
                    plan.logic.extend(logic)
                    follow_up(member, fields)
                page.fields.append(
                    PlannedField(
                        f"{e['id']}:applicants",
                        _spec("Applicants", "group"),
                        e["id"],
                        group={
                            "item_label": "Applicant",
                            "min_items": 1,
                            "max_items": applicants["max_items"],
                        },
                        children=children,
                    )
                )
                continue
            fields, logic = _fields_for(e, plan)
            page.fields.extend(fields)
            plan.logic.extend(logic)
            follow_up(e, fields)
        pending.append(page)

    # merge tiny sections into the previous page; split long ones
    merged: List[PlannedPage] = []
    for page in pending:
        questions = [f for f in page.fields if f.spec["type"] != "text"]
        if (
            merged
            and len(questions) <= TINY_SECTION
            and sum(f.weight for f in merged[-1].fields + page.fields)
            <= MAX_FIELDS_PER_PAGE + 2
        ):
            merged[-1].fields.extend(page.fields)
            plan.rule("tiny_section_merged")
        else:
            merged.append(page)
    for page in merged:
        heading, rest = page.fields[:1], page.fields[1:]
        chunks = _chunks(rest)
        for n, chunk in enumerate(chunks):
            if n:
                heading = [
                    PlannedField(
                        f"{page.fields[0].key}:cont{len(plan.pages)}",
                        {"title": f"{page.title} (continued)", "type": "text"},
                    )
                ]
                plan.rule("long_section_split")
            plan.pages.append(PlannedPage(page.title, heading + chunk))

    if terms:
        page = PlannedPage(
            "Terms and declarations",
            [
                PlannedField(
                    "__terms__:heading",
                    {"title": "Terms and declarations", "type": "text"},
                )
            ],
        )
        for t in terms:
            page.fields.append(PlannedField(t["id"], _statement(t["text"]), t["id"]))
        page.fields.append(
            PlannedField(
                "__terms__:agree",
                _spec(
                    "I have read and agree to the terms and declarations above.",
                    "yes_no",
                    required=True,
                ),
            )
        )
        # before the final page, which usually holds the signature
        plan.pages.insert(max(0, len(plan.pages) - 1), page)

    # staff-only parts: internal fields on pages of their own at the end (no
    # heading statement: respondents would see a page with only that on it)
    if internal:
        for chunk in _chunks(internal):
            plan.pages.append(PlannedPage(INTERNAL_PAGE_TITLE, chunk, internal=True))
    return plan


# --- theme ----------------------------------------------------------------------------


def _rgb(hex_colour: str) -> Tuple[float, float, float]:
    return tuple(int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * 255))) for v in rgb)


def _luminance(rgb) -> float:
    def lin(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_with_white(rgb) -> float:
    return 1.05 / (_luminance(rgb) + 0.05)


def _darken_for_white_text(rgb, target: float = 4.5):
    """Darken until white text on it reaches WCAG AA contrast."""
    r, g, b = rgb
    for _ in range(40):
        if _contrast_with_white((r, g, b)) >= target:
            break
        r, g, b = r * 0.93, g * 0.93, b * 0.93
    return (r, g, b)


def _tint(rgb, amount: float):
    return tuple(v + (1 - v) * amount for v in rgb)


def theme_from(layout: dict) -> Optional[Dict[str, Any]]:
    """Brand colour from the document's section bars, made readable."""
    fills = Counter()
    for page in layout.get("pages") or []:
        for p in page.get("primitives") or []:
            colour = p.get("fill")
            if p.get("kind") == "section_bar" and colour and len(colour) == 7:
                rgb = _rgb(colour)
                if max(rgb) - min(rgb) >= 0.2:  # saturated: a brand colour, not grey
                    fills[colour.lower()] += 1
    if not fills:
        return None
    brand = _rgb(fills.most_common(1)[0][0])
    primary = _darken_for_white_text(brand)
    return {
        "title": "Imported",
        "primary": _hex(primary),
        "secondary": _hex(_tint(primary, 0.85)),
        "tertiary": _hex(_tint(primary, 0.95)),
        "accent": _hex(brand),
        "style": "classic",
    }


# --- compiling ------------------------------------------------------------------------


def _enrich_tables(fdm: dict, layout: dict) -> None:
    """Model answers point at a table's layout item; take its header and rows from there."""
    tables = {
        p["id"]: p
        for page in layout.get("pages") or []
        for p in page.get("primitives") or []
        if p.get("kind") == "table"
    }
    for e in fdm.get("elements") or []:
        if (
            e.get("type") == "question"
            and e.get("kind", "").startswith("table_")
            and not e.get("table")
        ):
            p = next((tables[r] for r in e.get("slot_refs") or [] if r in tables), None)
            if p:
                e["table"] = {
                    "header": p.get("header"),
                    "row_labels": p.get("row_labels"),
                    "rows": p.get("rows"),
                    "cols": p.get("cols"),
                }


def _cap_fields(plan: Plan) -> None:
    budget = MAX_FIELDS
    cut = 0
    for page in plan.pages:
        kept: List[PlannedField] = []
        for f in page.fields:
            if f.weight <= budget:
                kept.append(f)
                budget -= f.weight
            else:
                cut += f.weight
                budget = 0
        page.fields = kept
    plan.pages = [page for page in plan.pages if page.fields]
    if cut:
        plan.report["dropped"].append(
            {"reason": f"the form was cut at {MAX_FIELDS} questions ({cut} left out)"}
        )


def _type(field) -> str:
    return str(getattr(field.type, "value", field.type))


def _align(
    planned: List[PlannedField], created: List[Any]
) -> List[Tuple[PlannedField, Any]]:
    """Planned fields paired with the fields the operations created, in page
    order; a planned group whose operation failed is skipped."""
    pairs = []
    j = 0
    for pf in planned:
        if j >= len(created):
            break
        if (_type(created[j]) == "group") == (pf.group is not None):
            pairs.append((pf, created[j]))
            j += 1
    return pairs


def build_form(fdm: dict, layout: dict, title: str) -> Tuple[Any, Dict[str, Any]]:
    """The draft form (a StandardForm) and the compile report."""
    from common.models.standard_form import StandardForm

    from backend.app.services.ai.ops import FormOps, apply_form_ops
    from backend.app.services.internal_fields import internal_logic_violations

    _enrich_tables(fdm, layout)
    plan = plan_form(fdm)
    _cap_fields(plan)
    form = StandardForm(title=title, fields=[])
    # pages first; groups go in once their page exists (add_page takes plain
    # questions only), at their planned position
    ops = [
        {"op": "add_page", "fields": [f.spec for f in page.fields if f.group is None]}
        for page in plan.pages
    ]
    theme = theme_from(layout)
    if theme:
        ops.append({"op": "update_theme", "theme": theme})
        plan.rule("theme_from_document")
    form, results = apply_form_ops(form, FormOps.model_validate({"ops": ops}).ops)
    failures = [r.message for r in results if not r.ok]
    pages = [f for f in (form.fields or []) if _type(f) == "slide"]
    group_ops = [
        {
            "op": "add_group",
            "page_id": page.id,
            "index": position,
            "title": pf.spec["title"],
            **pf.group,
            "fields": [c.spec for c in pf.children],
        }
        for planned, page in zip(plan.pages, pages)
        for position, pf in enumerate(planned.fields)
        if pf.group is not None
    ]
    if group_ops:
        form, results = apply_form_ops(
            form, FormOps.model_validate({"ops": group_ops}).ops
        )
        failures += [r.message for r in results if not r.ok]
        pages = [f for f in (form.fields or []) if _type(f) == "slide"]

    # map planned keys to the field ids the pages were given
    ids: Dict[str, str] = {}
    group_of: Dict[str, str] = {}  # child key -> its group's key
    choice_values: Dict[str, List[str]] = {}
    for planned, page in zip(plan.pages, pages):
        for pf, created in _align(planned.fields, page.properties.fields or []):
            pairs = [(pf, created)]
            if pf.group is not None:
                children = created.properties.fields or []
                pairs += list(zip(pf.children, children))
                for child in pf.children:
                    group_of[child.key] = pf.key
            for p, c in pairs:
                ids[p.key] = c.id
                choices = getattr(c.properties, "choices", None) or []
                choice_values[p.key] = [x.value for x in choices]
    logic_ops = []
    for rule in plan.logic:
        target, parent = ids.get(rule["target"]), ids.get(rule["parent"])
        if not target or not parent:
            continue
        if rule["parent"] in group_of and group_of[rule["parent"]] != group_of.get(
            rule["target"]
        ):
            continue  # a group's question is only seen by its own item
        value = rule["value"]
        if (
            choice_values.get(rule["parent"])
            and value not in choice_values[rule["parent"]]
        ):
            continue
        logic_ops.append(
            {
                "op": "set_field_logic",
                "field_id": target,
                "logic": {
                    "action": "SHOW",
                    "operator": "AND",
                    "conditions": [
                        {
                            "field_id": parent,
                            "comparison": rule["comparison"],
                            "value": value,
                        }
                    ],
                },
            }
        )
    if logic_ops:
        form, results = apply_form_ops(
            form, FormOps.model_validate({"ops": logic_ops}).ops
        )
        failures += [r.message for r in results if not r.ok]
    # the ops refuse logic on internal fields; say so loudly if any got through
    failures += internal_logic_violations(form)

    pages = [f for f in (form.fields or []) if _type(f) == "slide"]
    questions = [
        q
        for page in pages
        for f in page.properties.fields or []
        for q in [f, *(f.properties.fields or [] if _type(f) == "group" else [])]
    ]
    report = {
        "pages": len(pages),
        "fields": len(questions),
        "internal_fields": sum(1 for q in questions if q.internal),
        "repeating_groups": sum(1 for q in questions if _type(q) == "group"),
        "logic_rules": len(logic_ops),
        "rules": dict(plan.report["rules"]),
        "dropped": plan.report["dropped"],
        "staff_only": plan.report["staff_only"],
        "groups": plan.report["groups"],
        "theme": theme,
        "failures": failures[:20],
    }
    return form, report


_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


def with_stable_ids(form, seed: str):
    """The same form with every generated id (fields, choices, and the logic
    that points at them) replaced by a uuid5 derived from ``seed`` and the id's
    order of appearance. Compiling the same FDM again then yields the same ids,
    so a retried compile recognises its own draft."""
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, f"bettercollected:form-import:{seed}")
    mapping: Dict[str, str] = {}

    def stable(match) -> str:
        old = match.group(0).lower()
        if old not in mapping:
            mapping[old] = str(uuid.uuid5(namespace, str(len(mapping))))
        return mapping[old]

    text = _UUID.sub(stable, json.dumps(form.model_dump(mode="json")))
    return type(form).model_validate(json.loads(text))
