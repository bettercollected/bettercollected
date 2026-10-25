"""
Seed flow-native v2 templates (branching logic as the starting point).

Idempotent: skips any template whose title already exists with builder_version
"v2". Uses the backend's own documents and template repository so the stored
encoding is exactly what the API writes — never hand-rolled JSON.

**This runs automatically on every backend startup** (see the call in
`backend/app/asgi.py`'s lifespan, right after `init_db`), gated by
`DEFAULT_SEED_FLOW_TEMPLATES` (default on) and skipped with a warning if
`DEFAULT_WORKSPACE_ID` isn't set. That means existing/already-deployed
environments pick up new or changed templates the next time the backend
restarts — no manual step required. See backend/AGENTS.md "Seed scripts" for
the full writeup (env vars, what's idempotent, how to add a template).

For one-off manual runs (e.g. to seed without restarting the app), run from
backend/:  uv run python -m scripts.seed_flow_templates
Env: the backend's own (DATABASE_URL), DEFAULT_WORKSPACE_ID (required — see
     above). Reads and writes go through the template repository, like the
     app's; no Mongo is connected.

Note: create_form_from_template copies template fields VERBATIM (no id
regeneration), so the slide/field ids referenced by jumps and visibility rules
below keep working in every form instantiated from these templates.
"""

import asyncio
import os
import uuid

from common.models.standard_form import LayoutType

from backend.app.constants.themes import themes
from backend.app.schemas.template import FormTemplateDocument
from scripts.dutch_first_templates import BILINGUAL_BUILDERS

# The predefined templates wear the Leaflet design, the one new forms start
# with. Its colours meet the theme_contrast publish check
# (services/theme_contrast.py), so forms made from them publish. The shared
# preset (colours and the Leaflet style) is read from
# backend/app/constants/themes.py, never copied here, so they cannot drift.
THEME_PRESET = "Leaflet"
# The layout Leaflet is made for, the one new forms use: one centred column;
# Leaflet itself sets the cover and the sections from one left edge.
LAYOUT = "SINGLE_COLUMN_NO_BACKGROUND"
# The theme earlier versions of this script stored. Only a template still
# wearing exactly this one is moved to Leaflet by the repair below; one whose
# theme was changed by hand keeps it.
LEGACY_THEME = {
    "title": "Default",
    "primary": "#2E2E2E",
    "secondary": "#0764EB",
    "tertiary": "#A2C5F8",
    "accent": "#F2F7FF",
}


def template_theme() -> dict:
    """A fresh copy of the theme the predefined templates wear."""
    return themes[THEME_PRESET].model_dump(exclude_none=True)


def welcome_description(payload: dict) -> str:
    """The welcome page's one-line description of a builder's payload: the
    flow templates give it as ``welcome``, the Dutch-first ones inside their
    own ``welcome_page``."""
    return payload.get("welcome") or payload["welcome_page"]["description"]


def _id() -> str:
    return str(uuid.uuid4())


def _cond(field_id: str, comparison: str, value: str = "", field_type: str = "dropdown") -> dict:
    return {"field_id": field_id, "field_type": field_type, "comparison": comparison, "value": value}


def _jump(field_id: str, value: str, target: str, field_type: str = "dropdown") -> dict:
    return {"operator": "AND", "conditions": [_cond(field_id, "IS_EQUAL", value, field_type)], "target": target}


def _slide(fields: list, jumps: list | None = None, section: str | None = None) -> dict:
    slide = {"id": _id(), "index": 0, "type": "slide", "properties": {"layout": LAYOUT, "fields": fields}}
    if section:
        # The page's section title: what the Leaflet section bar and the
        # welcome page's contents list show, instead of repeating the
        # page's first question.
        slide["properties"]["section_title"] = section
    if jumps:
        slide["properties"]["jumps"] = jumps
    return slide


def _q(qtype: str, title: str, extra_props: dict | None = None, required: bool = False, why: str | None = None) -> dict:
    field = {"id": _id(), "index": 0, "type": qtype, "title": title}
    if extra_props:
        field["properties"] = extra_props
    if why:
        # "Why we ask this": every question for contact details says why.
        field.setdefault("properties", {})["why_we_ask"] = why
    if required:
        field["validations"] = {"required": True}
    return field


WHY_REPLY = "So we can reply to your request. We use it for nothing else."
WHY_FOLLOW_UP = "So we can follow up on your enquiry."
WHY_APPLICATION = "So we can contact you about your application."
WHY_APPLICATION_PHONE = "So we can call you about your application, if you prefer that."
# Reasons for templates seeded before questions said why they ask (by title).
WHY_WE_ASK_BY_TITLE = {
    "Where should we reply?": WHY_REPLY,
    "Best email to reach you": WHY_FOLLOW_UP,
    "Contact email": WHY_APPLICATION,
    "Phone number": WHY_APPLICATION_PHONE,
}


def _choices(*labels: str) -> dict:
    return {"choices": [{"id": _id(), "value": label} for label in labels]}


def _yes_no() -> dict:
    # Same choices the builder creates for a yes/no field; the responder renders
    # its buttons from them.
    return _choices("Yes", "No")


def _missing_yes_no_choices(fields) -> list:
    """Yes/no fields (at any depth) stored without their Yes/No choices."""
    missing = []
    for field in fields or []:
        props = field.properties
        if getattr(field.type, "value", field.type) == "yes_no" and not (props and props.choices):
            missing.append(field)
        if props and props.fields:
            missing.extend(_missing_yes_no_choices(props.fields))
    return missing


async def repair_yes_no_choices(template_repo, template_id) -> bool:
    """Give a seeded template's yes/no fields the Yes/No choices that earlier
    versions of this script left out (forms created from them showed the
    question with nothing to answer), and its contact questions their "why
    we ask this" line. Reads and writes through the routed repository, so
    both stores are repaired. Returns True if it changed."""
    from common.models.standard_form import StandardChoice, StandardFieldProperty

    template = await template_repo.get_template_by_id(template_id)
    if template is None:
        return False
    missing = _missing_yes_no_choices(template.fields)
    for field in missing:
        if field.properties is None:
            field.properties = StandardFieldProperty()
        field.properties.choices = [
            StandardChoice(id=_id(), value="Yes"),
            StandardChoice(id=_id(), value="No"),
        ]
    explained = _add_missing_why_we_ask(template.fields)
    if missing or explained:
        await template_repo.save(template)
    return bool(missing or explained)


def _add_missing_why_we_ask(fields) -> int:
    """Give seeded contact questions their "why we ask this" line when an
    earlier version of this script left it out; never overwrites one."""
    from common.models.standard_form import StandardFieldProperty

    added = 0
    for field in fields or []:
        props = field.properties
        why = WHY_WE_ASK_BY_TITLE.get(field.title) if isinstance(field.title, str) else None
        if why and getattr(field.type, "value", field.type) in ("email", "phone_number"):
            if props is None:
                props = field.properties = StandardFieldProperty()
            if not props.why_we_ask:
                props.why_we_ask = why
                added += 1
        if props and props.fields:
            added += _add_missing_why_we_ask(props.fields)
    return added


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _value(value):
    return getattr(value, "value", value)


def _questions(fields) -> list:
    """(type, title) of every question, in order, at any depth: the shape a
    seeded template is recognised by, stored or freshly built."""
    out = []
    for field in fields or []:
        field_type = _value(_get(field, "type"))
        if field_type != "slide":
            out.append((field_type, _get(field, "title")))
        props = _get(field, "properties")
        if props is not None:
            out.extend(_questions(_get(props, "fields")))
    return out


def _seed_payload_of(template):
    """The payload this script seeded ``template`` from, or None when the
    template is not one of its own: a flow-builder template, public (in the
    gallery), not a copy imported into a workspace, with a builder's title
    and exactly that builder's questions (type and title, in order)."""
    if template.builder_version != "v2" or template.imported_from is not None:
        return None
    if not (template.settings and template.settings.is_public):
        return None
    for build in TEMPLATE_BUILDERS:
        payload = build()
        if payload["title"] == template.title and _questions(
            payload["fields"]
        ) == _questions(template.fields):
            return payload
    return None


def _wears_legacy_theme(theme) -> bool:
    """Is ``theme`` exactly the one earlier versions of this script stored?"""
    if theme is None:
        return False
    stored = theme.model_dump(exclude_none=True) if hasattr(theme, "model_dump") else dict(theme)
    normalised = {
        key: value.upper() if isinstance(value, str) and value.startswith("#") else value
        for key, value in stored.items()
    }
    return normalised == {key: value.upper() if value.startswith("#") else value for key, value in LEGACY_THEME.items()}


def _set_layout(page) -> None:
    if page is not None and _value(page.layout) != LAYOUT:
        page.layout = LayoutType(LAYOUT)


def _add_missing_section_titles(pages, seeded_pages) -> int:
    """Give each page the section title its builder gives it, where the
    stored page has none (empty or unset); a title set by hand stays.
    Pages are matched in order, and only when each holds exactly the
    builder page's questions."""
    pages = list(pages or [])
    if len(pages) != len(seeded_pages):
        return 0
    added = 0
    for page, seeded in zip(pages, seeded_pages):
        title = seeded["properties"].get("section_title")
        props = page.properties
        if not title or props is None or _questions(props.fields) != _questions(seeded["properties"]["fields"]):
            continue
        if not (props.section_title or "").strip():
            props.section_title = title
            added += 1
    return added


async def repair_leaflet_design(template_repo, template_id) -> bool:
    """Move a predefined template this script seeded before it used Leaflet
    to the Leaflet preset and style and the layout Leaflet is made for, and
    give its welcome page its one-line description and its pages their
    section titles where they have none.

    Touches only the script's own templates (``_seed_payload_of``). The
    theme changes only while it is still the old seeded one, so a theme
    changed by hand stays; a description or section title set by hand stays
    too. Never creates anything. Forms made from a template store their own
    copy of its theme, so they keep theirs. Idempotent: a repaired template
    no longer wears the old theme and has its description and section
    titles.
    Returns True if it changed."""
    from common.models.standard_form import Theme, WelcomePageField

    template = await template_repo.get_template_by_id(template_id)
    if template is None:
        return False
    payload = _seed_payload_of(template)
    if payload is None:
        return False
    changed = False
    if _wears_legacy_theme(template.theme):
        template.theme = Theme(**template_theme())
        for slide in template.fields or []:
            if _value(slide.type) == "slide" and slide.properties is not None:
                _set_layout(slide.properties)
        _set_layout(template.welcome_page)
        for ending in template.thankyou_page or []:
            _set_layout(ending)
        changed = True
    if template.welcome_page is None:
        template.welcome_page = WelcomePageField(
            title=template.title, layout=LayoutType(LAYOUT), buttonText="Start"
        )
    if not template.welcome_page.description:
        template.welcome_page.description = welcome_description(payload)
        changed = True
    if _add_missing_section_titles(template.fields, payload["fields"]):
        changed = True
    if changed:
        await template_repo.save(template)
    return changed


def support_triage() -> dict:
    topic = _q("dropdown", "What do you need help with?", _choices("Billing", "Technical issue", "Something else"), required=True)
    billing = _slide([_q("short_text", "Which invoice or charge is this about?")], section="Billing")
    technical = _slide([_q("long_text", "Describe the issue — what did you expect, and what happened?")], section="Technical issue")
    contact = _slide([_q("email", "Where should we reply?", required=True, why=WHY_REPLY)], section="Contact")
    intro = _slide(
        [topic],
        section="Your request",
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
        "welcome": "Tell us what you need help with, and we will make sure the right person answers.",
        "category": None,
        "fields": [intro, billing, technical, contact],
    }


def lead_qualification() -> dict:
    timeline = _q("yes_no", "Are you looking to get started in the next 3 months?", _yes_no(), required=True)
    details = _slide([_q("short_text", "What's the main problem you're hoping to solve?"), _q("number", "How many people are on your team?")], section="Your needs")
    contact = _slide([_q("email", "Best email to reach you", required=True, why=WHY_FOLLOW_UP)], section="Contact")
    intro = _slide(
        [timeline],
        section="Timing",
        # Not in the market → polite, short exit; qualified leads continue.
        jumps=[_jump(timeline["id"], "No", "__SUBMIT__", field_type="yes_no")],
    )
    return {
        "title": "Lead qualification",
        "description": "Qualify prospects in one question — unqualified visitors exit politely instead of filling pages that don't apply.",
        "welcome": "A few short questions, so we know how we can help you.",
        "category": None,
        "fields": [intro, details, contact],
    }


def job_screening() -> dict:
    authorized = _q("yes_no", "Are you legally authorized to work in this role's location?", _yes_no(), required=True)
    experience = _slide([_q("long_text", "Tell us about your most relevant experience."), _q("url", "Portfolio or LinkedIn")], section="Experience")
    contact = _slide([_q("email", "Contact email", required=True, why=WHY_APPLICATION), _q("phone_number", "Phone number", why=WHY_APPLICATION_PHONE)], section="Contact")
    intro = _slide(
        [authorized],
        section="Eligibility",
        jumps=[_jump(authorized["id"], "No", "__SUBMIT__", field_type="yes_no")],
    )
    return {
        "title": "Job application with screening",
        "description": "A knock-out screening question up front — ineligible applicants finish quickly, eligible ones continue to the full application.",
        "welcome": "Apply for this role: tell us about yourself and your experience.",
        "category": None,
        "fields": [intro, experience, contact],
    }


# Add new flow-native templates here — each is a zero-arg builder returning the
# payload shape above. Startup seeding and the CLI both iterate this tuple.
# The Dutch-first templates and their English twins are written in
# scripts/dutch_first_templates.py; their payloads also carry the template's
# language, welcome page and ending.
TEMPLATE_BUILDERS = (
    support_triage,
    lead_qualification,
    job_screening,
    *BILINGUAL_BUILDERS,
)


async def seed_flow_templates(workspace_id, template_repo) -> dict:
    """
    Create any of TEMPLATE_BUILDERS that don't already exist (matched by title +
    builder_version="v2", in any workspace). ``template_repo`` is the app's
    routed template repository: the existence check, the repair and the new
    templates all go through it, so whichever store serves templates (Mongo,
    mirrored or Postgres) is the one checked and written. Safe to call
    repeatedly: existing templates are left untouched, never overwritten,
    except that their missing yes/no choices are repaired and the script's
    own templates still wearing the old seeded theme move to Leaflet
    (``repair_leaflet_design``).

    Returns {"seeded": [...], "skipped": [...], "repaired": [...],
    "restyled": [...]} (titles).
    """
    seeded, skipped, repaired, restyled = [], [], [], []
    # The gallery's own templates, so one there is repaired even when a
    # template elsewhere has the same title.
    gallery = await template_repo.get_templates_with_creator(
        v2=True, workspace_id=workspace_id, predefined_workspace=True
    )
    for build in TEMPLATE_BUILDERS:
        payload = build()
        # Matched by title in any workspace, as before: DEFAULT_WORKSPACE_ID may
        # differ from the workspace an earlier run seeded into.
        existing = await template_repo.get_v2_template_by_title(payload["title"])
        if existing:
            skipped.append(payload["title"])
            if await repair_yes_no_choices(template_repo, existing.id):
                repaired.append(payload["title"])
            candidates = {existing.id} | {
                t.get("id") or t.get("_id")
                for t in gallery
                if t.get("title") == payload["title"]
            }
            for template_id in candidates:
                # Only the script's own templates, see _seed_payload_of.
                if await repair_leaflet_design(template_repo, template_id):
                    restyled.append(payload["title"])
            continue
        # fix slide/field indexes
        for i, slide in enumerate(payload["fields"]):
            slide["index"] = i
            for j, f in enumerate(slide["properties"]["fields"]):
                f["index"] = j
        template = FormTemplateDocument(
            builder_version="v2",
            type="form",
            workspace_id=workspace_id,
            title=payload["title"],
            description=payload["description"],
            fields=payload["fields"],
            theme=template_theme(),
            # The Dutch-first templates bring their own welcome page and
            # ending; the flow templates get the default ones.
            welcome_page=payload.get("welcome_page")
            or {
                "title": payload["title"],
                "description": payload["welcome"],
                "layout": LAYOUT,
                "buttonText": "Start",
            },
            thankyou_page=payload.get("thankyou_page") or [{"layout": LAYOUT}],
            settings={"is_public": True, "language": payload.get("language")},
        )
        await template_repo.save(template)
        seeded.append(payload["title"])
    return {
        "seeded": seeded,
        "skipped": skipped,
        "repaired": repaired,
        "restyled": restyled,
    }


async def _main() -> None:
    """Standalone CLI entry point: boots the stores the way the services do
    (Postgres from DATABASE_URL; the forms group is Postgres only since 4.1,
    so Mongo is never connected) and seeds through the app's template
    repository. Startup auto-seeding (asgi.py) calls seed_flow_templates()
    directly."""
    from backend.cli_store import routed_repositories
    from backend.config import settings
    from backend.db.startup import check_postgres_at_startup

    workspace_id = settings.default_workspace_settings.WORKSPACE_ID
    if not workspace_id:
        print("DEFAULT_WORKSPACE_ID is not set — refusing to seed without a stable predefined-templates workspace id.")
        return

    async with routed_repositories("forms") as container:
        await check_postgres_at_startup(container)
        result = await seed_flow_templates(workspace_id, container.form_template_repo())
    for title in result["seeded"]:
        print(f"seeded: {title}")
    for title in result["skipped"]:
        print(f"skip (exists): {title}")
    for title in result["restyled"]:
        print(f"moved to Leaflet: {title}")


if __name__ == "__main__":
    asyncio.run(_main())
