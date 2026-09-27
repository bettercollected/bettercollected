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
- tables become rows of fields (interim until tables and repeating groups can
  be created by the edit operations); staff-only parts are listed in the
  report (interim until internal fields exist).

Everything goes through the typed edit operations (``apply_form_ops``), built
from an empty form in memory and saved once, so compiling again produces the
same form instead of adding to it.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

MAX_FIELDS_PER_PAGE = 12
TINY_SECTION = 2
LONG_STATEMENT_WORDS = 150
MAX_OPEN_TABLE_ROWS = 5

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


@dataclass
class PlannedPage:
    title: str
    fields: List[PlannedField] = field(default_factory=list)


@dataclass
class Plan:
    pages: List[PlannedPage] = field(default_factory=list)
    logic: List[Dict[str, Any]] = field(default_factory=list)
    report: Dict[str, Any] = field(
        default_factory=lambda: {
            "rules": Counter(),
            "dropped": [],
            "interim": [],
            "staff_only": [],
        }
    )

    def rule(self, name: str) -> None:
        self.report["rules"][name] += 1


def _spec(title: str, type_: str, **extra) -> Dict[str, Any]:
    spec = {"title": title.strip()[:500] or "Untitled question", "type": type_}
    spec.update({k: v for k, v in extra.items() if v is not None})
    return spec


def _statement(text: str) -> Dict[str, Any]:
    return {"title": text.strip()[:5000], "type": "text"}


def _clean(label: str) -> str:
    label = re.sub(r"[.…_]{3,}", "", label or "").strip()
    return label.rstrip(":：").strip()


# --- planning ---------------------------------------------------------------------------


def _fields_for(q: dict, plan: Plan) -> Tuple[List[PlannedField], List[Dict[str, Any]]]:
    """Fields for one FDM question, plus visibility rules that refer to them."""
    kind = q["kind"]
    label = _clean(q.get("label") or "")
    if q.get("applicant_index") and q["applicant_index"] > 1:
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


def _table_fields(q: dict, label: str, plan: Plan) -> List[PlannedField]:
    table = q.get("table") or {}
    header = [h for h in (table.get("header") or []) if h]
    row_labels = [r for r in (table.get("row_labels") or []) if r]
    out: List[PlannedField] = []
    if q["kind"] == "table_fixed_rows" and row_labels and len(header) >= 2:
        columns = header[1:]
        span = max(4, 12 // max(1, len(columns)))
        for r, row in enumerate(row_labels):
            for c, col in enumerate(columns):
                out.append(
                    PlannedField(
                        f"{q['id']}:r{r}c{c}",
                        _spec(
                            f"{_clean(row)} – {_clean(col)}",
                            "short_text",
                            col_span=span,
                        ),
                        q["id"],
                    )
                )
        plan.report["interim"].append(
            {
                "element": q["id"],
                "label": label,
                "as": f"{len(row_labels)} rows × {len(columns)} fields",
            }
        )
    else:
        columns = header or [label or "Entry"]
        rows = max(1, min(MAX_OPEN_TABLE_ROWS, (table.get("rows") or 2) - 1))
        span = max(4, 12 // max(1, len(columns)))
        for r in range(rows):
            for c, col in enumerate(columns):
                out.append(
                    PlannedField(
                        f"{q['id']}:r{r}c{c}",
                        _spec(f"{_clean(col)} ({r + 1})", "short_text", col_span=span),
                        q["id"],
                    )
                )
        plan.report["interim"].append(
            {
                "element": q["id"],
                "label": label,
                "as": f"{rows} numbered rows (repeating groups later)",
            }
        )
    plan.rule("table_to_rows_of_fields")
    return out


def plan_form(fdm: dict) -> Plan:
    plan = Plan()
    elements = fdm.get("elements") or []
    staff_headings = {
        (e.get("heading") or "").strip().lower()
        for e in elements
        if e["type"] == "staff_only"
    }
    sections: Dict[str, dict] = {
        e["id"]: e
        for e in elements
        if e["type"] == "section"
        and (e.get("title") or "").strip().lower() not in staff_headings
    }
    order: List[str] = []
    buckets: Dict[str, List[Tuple[str, dict]]] = {}
    terms: List[dict] = []

    def bucket(section_id: Optional[str]) -> str:
        sid = section_id if section_id in sections else "__none__"
        if sid not in buckets:
            buckets[sid] = []
            order.append(sid)
        return sid

    for e in elements:
        if e["type"] == "staff_only":
            plan.report["staff_only"].append(
                {
                    "element": e["id"],
                    "heading": e.get("heading") or "",
                    "layout_items": len(e.get("refs") or []),
                }
            )
            plan.rule("staff_only_listed")
        elif e["type"] == "statement":
            words = len((e.get("text") or "").split())
            if e.get("legal") and words >= LONG_STATEMENT_WORDS:
                terms.append(e)
                plan.rule("long_terms_to_terms_page")
            else:
                buckets[bucket(e.get("section"))].append(("statement", e))
        elif e["type"] == "question":
            buckets[bucket(e.get("section"))].append(("question", e))
        elif e["type"] == "section":
            bucket(e["id"])

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
            fields, logic = _fields_for(e, plan)
            page.fields.extend(fields)
            plan.logic.extend(logic)
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
        pending.append(page)

    # merge tiny sections into the previous page; split long ones
    merged: List[PlannedPage] = []
    for page in pending:
        questions = [f for f in page.fields if f.spec["type"] != "text"]
        if (
            merged
            and len(questions) <= TINY_SECTION
            and len(merged[-1].fields) + len(page.fields) <= MAX_FIELDS_PER_PAGE + 2
        ):
            merged[-1].fields.extend(page.fields)
            plan.rule("tiny_section_merged")
        else:
            merged.append(page)
    for page in merged:
        heading, rest = page.fields[:1], page.fields[1:]
        while len(rest) > MAX_FIELDS_PER_PAGE:
            plan.pages.append(
                PlannedPage(page.title, heading + rest[:MAX_FIELDS_PER_PAGE])
            )
            rest = rest[MAX_FIELDS_PER_PAGE:]
            heading = (
                [
                    PlannedField(
                        f"{heading[0].key}:cont{len(plan.pages)}",
                        {"title": f"{page.title} (continued)", "type": "text"},
                    )
                ]
                if heading
                else []
            )
            plan.rule("long_section_split")
        plan.pages.append(PlannedPage(page.title, heading + rest))

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


def build_form(fdm: dict, layout: dict, title: str) -> Tuple[Any, Dict[str, Any]]:
    """The draft form (a StandardForm) and the compile report."""
    from common.models.standard_form import StandardForm

    from backend.app.services.ai.ops import FormOps, apply_form_ops

    _enrich_tables(fdm, layout)
    plan = plan_form(fdm)
    form = StandardForm(title=title, fields=[])
    ops = [
        {"op": "add_page", "fields": [f.spec for f in page.fields]}
        for page in plan.pages
    ]
    theme = theme_from(layout)
    if theme:
        ops.append({"op": "update_theme", "theme": theme})
        plan.rule("theme_from_document")
    form, results = apply_form_ops(form, FormOps.model_validate({"ops": ops}).ops)
    failures = [r.message for r in results if not r.ok]

    # map planned keys to the field ids the pages were given
    ids: Dict[str, str] = {}
    choice_values: Dict[str, List[str]] = {}
    pages = [
        f
        for f in (form.fields or [])
        if str(getattr(f.type, "value", f.type)) == "slide"
    ]
    for planned, page in zip(plan.pages, pages):
        for pf, created in zip(planned.fields, page.properties.fields or []):
            ids[pf.key] = created.id
            choices = getattr(created.properties, "choices", None) or []
            choice_values[pf.key] = [c.value for c in choices]
    logic_ops = []
    for rule in plan.logic:
        target, parent = ids.get(rule["target"]), ids.get(rule["parent"])
        if not target or not parent:
            continue
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
    report = {
        "pages": len(pages),
        "fields": sum(len(p.properties.fields or []) for p in pages),
        "logic_rules": len(logic_ops),
        "rules": dict(plan.report["rules"]),
        "dropped": plan.report["dropped"],
        "interim": plan.report["interim"],
        "staff_only": plan.report["staff_only"],
        "theme": theme,
        "failures": failures[:20],
    }
    return form, report
