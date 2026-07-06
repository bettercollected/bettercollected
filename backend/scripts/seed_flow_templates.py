"""
Seed flow-native v2 templates (branching logic as the starting point).

Idempotent: skips any template whose title already exists with builder_version
"v2". Uses the backend's own Beanie documents so the stored encoding is exactly
what the API writes — never hand-rolled JSON.

Run from backend/:  uv run python -m scripts.seed_flow_templates
Env: MONGO_URI (default mongodb://root:root@localhost:27017), DB name
     bettercollected_backend.

Note: create_form_from_template copies template fields VERBATIM (no id
regeneration), so the slide/field ids referenced by jumps and visibility rules
below keep working in every form instantiated from these templates.
"""

import asyncio
import os
import uuid

from beanie import init_beanie
from pymongo import AsyncMongoClient

from backend.app.schemas.template import FormTemplateDocument
from backend.config import settings

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://root:root@localhost:27017")
DB_NAME = os.environ.get("BACKEND_DB", "bettercollected_backend")
# Predefined (gallery) templates are served only from this workspace — the
# same setting the templates API filters by.
TEMPLATE_WORKSPACE_ID = settings.default_workspace_settings.WORKSPACE_ID

THEME = {
    "title": "Default",
    "primary": "#2E2E2E",
    "secondary": "#0764EB",
    "tertiary": "#A2C5F8",
    "accent": "#F2F7FF",
}
LAYOUT = "SINGLE_COLUMN_NO_BACKGROUND"


def _id() -> str:
    return str(uuid.uuid4())


def _cond(field_id: str, comparison: str, value: str = "", field_type: str = "dropdown") -> dict:
    return {"field_id": field_id, "field_type": field_type, "comparison": comparison, "value": value}


def _jump(field_id: str, value: str, target: str, field_type: str = "dropdown") -> dict:
    return {"operator": "AND", "conditions": [_cond(field_id, "IS_EQUAL", value, field_type)], "target": target}


def _slide(fields: list, jumps: list | None = None) -> dict:
    slide = {"id": _id(), "index": 0, "type": "slide", "properties": {"layout": LAYOUT, "fields": fields}}
    if jumps:
        slide["properties"]["jumps"] = jumps
    return slide


def _q(qtype: str, title: str, extra_props: dict | None = None, required: bool = False) -> dict:
    field = {"id": _id(), "index": 0, "type": qtype, "title": title}
    if extra_props:
        field["properties"] = extra_props
    if required:
        field["validations"] = {"required": True}
    return field


def _choices(*labels: str) -> dict:
    return {"choices": [{"id": _id(), "value": label} for label in labels]}


def support_triage() -> dict:
    topic = _q("dropdown", "What do you need help with?", _choices("Billing", "Technical issue", "Something else"), required=True)
    billing = _slide([_q("short_text", "Which invoice or charge is this about?")])
    technical = _slide([_q("long_text", "Describe the issue — what did you expect, and what happened?")])
    contact = _slide([_q("email", "Where should we reply?", required=True)])
    intro = _slide(
        [topic],
        jumps=[
            _jump(topic["id"], "Billing", billing["id"]),
            _jump(topic["id"], "Technical issue", technical["id"]),
            # "Something else" routes straight to contact — irrelevant pages skipped.
            _jump(topic["id"], "Something else", contact["id"]),
        ],
    )
    # After the billing branch, skip the technical page.
    billing["properties"]["jumps"] = [_jump(topic["id"], "Billing", contact["id"])]
    return {
        "title": "Support triage",
        "description": "Route billing, technical and general requests to the right questions — respondents only see what applies to them.",
        "category": None,
        "fields": [intro, billing, technical, contact],
    }


def lead_qualification() -> dict:
    timeline = _q("yes_no", "Are you looking to get started in the next 3 months?", None, required=True)
    details = _slide([_q("short_text", "What's the main problem you're hoping to solve?"), _q("number", "How many people are on your team?")])
    contact = _slide([_q("email", "Best email to reach you", required=True)])
    intro = _slide(
        [timeline],
        # Not in the market → polite, short exit; qualified leads continue.
        jumps=[_jump(timeline["id"], "No", "__SUBMIT__", field_type="yes_no")],
    )
    return {
        "title": "Lead qualification",
        "description": "Qualify prospects in one question — unqualified visitors exit politely instead of filling pages that don't apply.",
        "category": None,
        "fields": [intro, details, contact],
    }


def job_screening() -> dict:
    authorized = _q("yes_no", "Are you legally authorized to work in this role's location?", None, required=True)
    experience = _slide([_q("long_text", "Tell us about your most relevant experience."), _q("url", "Portfolio or LinkedIn")])
    contact = _slide([_q("email", "Contact email", required=True), _q("phone_number", "Phone number")])
    intro = _slide(
        [authorized],
        jumps=[_jump(authorized["id"], "No", "__SUBMIT__", field_type="yes_no")],
    )
    return {
        "title": "Job application with screening",
        "description": "A knock-out screening question up front — ineligible applicants finish quickly, eligible ones continue to the full application.",
        "category": None,
        "fields": [intro, experience, contact],
    }


async def main() -> None:
    client = AsyncMongoClient(MONGO_URI)
    await init_beanie(database=client[DB_NAME], document_models=[FormTemplateDocument])

    for build in (support_triage, lead_qualification, job_screening):
        payload = build()
        existing = await FormTemplateDocument.find_one(
            FormTemplateDocument.title == payload["title"], FormTemplateDocument.builder_version == "v2"
        )
        if existing:
            print(f"skip (exists): {payload['title']}")
            continue
        # fix slide indexes
        for i, slide in enumerate(payload["fields"]):
            slide["index"] = i
            for j, f in enumerate(slide["properties"]["fields"]):
                f["index"] = j
        doc = FormTemplateDocument(
            builder_version="v2",
            type="form",
            workspace_id=TEMPLATE_WORKSPACE_ID,
            title=payload["title"],
            description=payload["description"],
            fields=payload["fields"],
            theme=THEME,
            welcome_page={"title": payload["title"], "layout": LAYOUT, "buttonText": "Start"},
            thankyou_page=[{"layout": LAYOUT}],
            settings={"is_public": True},
        )
        await doc.save()
        print(f"seeded: {payload['title']}")


if __name__ == "__main__":
    asyncio.run(main())
