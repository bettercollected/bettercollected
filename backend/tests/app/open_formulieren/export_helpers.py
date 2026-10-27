"""Forms to export and pieces to look at an exported archive."""

import io
import json
import zipfile
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List, Optional

from common.models.standard_form import StandardForm

from backend.app.services.open_formulieren.report import Report


def choice(cid: str, text: str) -> Dict[str, Any]:
    return {"id": cid, "value": text}


def q(
    fid: str,
    ftype: str,
    title: Any,
    *,
    props: Optional[Dict[str, Any]] = None,
    rules: Optional[Dict[str, Any]] = None,
    internal: bool = False,
) -> Dict[str, Any]:
    field = {
        "id": fid,
        "type": ftype,
        "title": title,
        "properties": props or {},
        "validations": rules or {},
    }
    if internal:
        field["internal"] = True
    return field


def when(action: str, operator: str, *conditions) -> Dict[str, Any]:
    """A show/hide rule; a condition is ``(field_id, comparison, value)``."""
    return {
        "action": action,
        "operator": operator,
        "conditions": [
            {"fieldId": f, "comparison": c, **({"value": v} if v is not None else {})}
            for f, c, v in conditions
        ],
    }


def slide(sid: str, fields: List[Dict[str, Any]], title: Optional[str] = None, jumps=None):
    props: Dict[str, Any] = {"fields": fields}
    if title:
        props["section_title"] = title
    if jumps:
        props["jumps"] = jumps
    return {"id": sid, "type": "slide", "properties": props}


def form_of(*pages, title: str = "Sample form", **extra) -> StandardForm:
    for index, page in enumerate(pages):
        page["index"] = index
    return StandardForm.model_validate(
        {"builder_version": "v2", "title": title, "fields": list(pages), **extra}
    )


# the title of a staff-only question, found nowhere in an archive
INTERNAL_TITLE = "Internal ref STAFFONLY-7f3a"
# the "required" yes/no, the url, the "other plan" rule ... see KITCHEN_SINK


def kitchen_sink() -> StandardForm:
    """A form with every question type we can export, rules of every shape and
    the things that cannot be exported (a calculated field, a rating, page
    jumps, a staff-only question)."""
    p1 = slide(
        "p1",
        [
            q("name", "short_text", "Your name",
              props={"placeholder": "Jane", "description": "As on your passport",
                     "why_we_ask": "So we can greet you"},
              rules={"required": True, "max_length": 50, "regex": "^[A-Za-z ]+$"}),
            q("email", "email", "Email address",
              props={"why_we_ask": "Needed for the receipt"}, rules={"required": True}),
            q("phone", "phone_number", "Phone"),
            q("bio", "long_text", "About you", rules={"max_length": 500}),
            q("age", "number", "Age", rules={"min_value": 0, "max_value": 120}),
            q("site", "url", "Website"),
            q("staff", "short_text", INTERNAL_TITLE, internal=True),
        ],
        "About you",
    )
    p2 = slide(
        "p2",
        [
            q("plan", "multiple_choice", "Plan",
              props={"choices": [choice("c-free", "Free"), choice("c-pro", "Pro"), choice("c-team", "Team")]},
              rules={"required": True}),
            q("topics", "multiple_choice", "Topics",
              props={"allow_multiple_selection": True,
                     "choices": [choice("t-news", "News"), choice("t-events", "Events"), choice("t-offers", "Offers")]},
              rules={"min_choices": 1, "max_choices": 2}),
            q("country", "dropdown", "Country",
              props={"choices": [choice("n-nl", "Netherlands"), choice("n-be", "Belgium"), choice("n-de", "Germany")]}),
            q("newsletter", "yes_no", "Newsletter", rules={"required": True}),
            q("born", "date", "Date of birth",
              props={"date_rules": [
                  {"comparison": "on_or_before", "target": "today"},
                  {"comparison": "after", "target": "date", "date": "1900-01-01"},
              ]}),
            q("doc", "file_upload", "Attachment"),
            q("half1", "short_text", "First half", props={"col_span": 6}),
            q("half2", "short_text", "Second half", props={"col_span": 6}),
        ],
        "Choices",
        jumps=[{"operator": "AND", "target": "p3",
                "conditions": [{"fieldId": "plan", "comparison": "IS_EQUAL", "value": "Free"}]}],
    )
    p3 = slide(
        "p3",
        [
            q("intro", "text", "Please read this carefully."),
            q("reason", "long_text", "Why Pro?",
              props={"logic": when("SHOW", "AND", ("plan", "IS_EQUAL", "Pro"))}),
            q("other", "short_text", "Other plan",
              props={"logic": when("HIDE", "AND", ("plan", "IS_NOT_EQUAL", "Free"))}),
            q("guardian", "short_text", "Guardian name",
              props={"logic": when("SHOW", "AND", ("age", "LESS_THAN", 18))}),
            q("combo", "short_text", "Combo",
              props={"logic": when("SHOW", "AND", ("plan", "IS_EQUAL", "Team"), ("topics", "CONTAINS", "Offers"))}),
            q("why_not", "short_text", "Why not",
              props={"logic": when("SHOW", "AND", ("newsletter", "IS_EQUAL", "No"))}),
            q("explain", "long_text", "Explain",
              props={"logic": when("SHOW", "AND", ("name", "CONTAINS", "x"))}),
            {
                "id": "family",
                "type": "group",
                "title": "Family",
                "properties": {
                    "repeat": {"minItems": 1, "maxItems": 4, "itemLabel": "Member"},
                    "description": "Add each member",
                    "fields": [
                        q("m_name", "short_text", "Member name", rules={"required": True}),
                        q("m_age", "number", "Member age"),
                    ],
                },
                "validations": {},
            },
            q("total", "calculated", "Total", props={"expression": {"var": "age"}}),
            q("stars", "rating", "Rate us", props={"steps": 5}),
        ],
        "Extras",
    )
    p4 = slide("p4", [q("office", "short_text", "Office use", internal=True)], "Office")
    return form_of(
        p1, p2, p3, p4,
        title="Kitchen sink",
        hidden_fields=["utm_source"],
        settings={
            "response_expiration": "30",
            "response_expiration_type": "days",
            "privacy_policy_url": "https://example.org/privacy",
        },
    )


# --------------------------------------------------------------- the archive


def entries(data: bytes) -> Dict[str, Any]:
    """The decoded JSON entries of an exported archive (README as text)."""
    out: Dict[str, Any] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            raw = archive.read(name)
            out[name] = raw.decode() if name.endswith(".txt") else json.loads(raw)
    return out


def components(archive: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Every component of every step, nested ones included."""
    stack = [
        c
        for d in archive["formDefinitions.json"]
        for c in d["configuration"]["components"]
    ]
    while stack:
        comp = stack.pop(0)
        yield comp
        stack[0:0] = comp.get("components", [])
        for column in comp.get("columns", []):
            stack[0:0] = column.get("components", [])


def by_key(archive: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {c["key"]: c for c in components(archive)}


def built(form: StandardForm) -> SimpleNamespace:
    """``form`` shaped like the importer's result, for ``describe``."""
    return SimpleNamespace(form=form, summary={}, report=Report())
