"""Prompt assembly for AI form features — one place, not scattered per feature.

Precedence (plan §2.4): user prompt > org compliance > org guidelines >
user preference memory (memory arrives in P1). Compliance is the only block
that may veto the user's request; everything user-authored is fenced as data.
"""

from typing import Optional

from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from backend.app.services.ai.profile import render_prompt_block


def compose_generation_prompt(prompt: str, profile: Optional[WorkspaceAIProfileDocument]) -> str:
    """Ground a form-generation request in the workspace's AI profile.

    Provider-agnostic on purpose: the block is prepended to the user turn, so
    both current providers (Gemini system-instruction + chat, OpenAI messages)
    receive it without per-provider plumbing.
    """
    block = render_prompt_block(profile)
    if not block:
        return prompt
    return f"{block}\n\n## User request\n{prompt}"


# ---------------------------------------------------------------------------
# Chat editing (plan §2.2)
# ---------------------------------------------------------------------------

OPS_GUIDE = """## How to edit the form
You edit the form ONLY by returning operations. Reply with a single JSON
object — no markdown fences, no extra text:

{
  "reply": "<one or two friendly sentences describing what you did / any question>",
  "ops": [ <zero or more operations> ]
}

Operations (camelCase keys, referencing the ids from the form snapshot):
- {"op":"add_field","pageId":"...","field":{"title":"...","type":"<type>","required":true?,"placeholder":"?","choices":["?"],"steps":5?,"colSpan":6?},"afterFieldId":"?","index":0?}
- {"op":"update_field","fieldId":"...","patch":{"title":"?","description":"?","required":true?,"placeholder":"?","choices":["?"],"steps":5?,"colSpan":6?}}
- {"op":"remove_field","fieldId":"..."}
- {"op":"move_field","fieldId":"...","toPageId":"?","index":0}
- {"op":"add_page","index":0?,"fields":[<field specs>]?}
- {"op":"remove_page","pageId":"..."}
- {"op":"update_form_info","title":"?","description":"?"}

Field types you may create: short_text, long_text, email, number, url,
phone_number, date, yes_no, multiple_choice, dropdown, rating, linear_rating,
file_upload, text (a display-only statement).

Rules:
- multiple_choice / dropdown need "choices" with >= 2 options. yes_no choices are fixed.
- rating / linear_rating take "steps" (defaults 5 / 10).
- Prefer small precise edits over rebuilding; NEVER remove things the user did not ask to remove.
- Never design dark patterns: consent stays opt-in, opt-outs stay visible,
  optional fields stay clearly optional — refuse politely in "reply" if asked.
- If the request is unclear or nothing needs to change, return "ops": [] and ask in "reply"."""


def project_form(form) -> str:
    """Compact JSON snapshot of a form for the chat context window.

    Ids, types, titles and the properties the ops can touch — never TipTap
    blobs, theme values or response data. Small enough to resend every turn.
    """
    import json

    pages = []
    for slide in form.fields or []:
        if getattr(slide.type, "value", slide.type) != "slide":
            continue
        fields = []
        for f in (slide.properties.fields if slide.properties else None) or []:
            entry = {
                "id": f.id,
                "type": getattr(f.type, "value", f.type),
                "title": f.title if isinstance(f.title, str) else "(rich text)",
            }
            if f.validations and f.validations.required:
                entry["required"] = True
            props = f.properties
            if props:
                if props.choices:
                    entry["choices"] = [c.value for c in props.choices]
                if props.steps:
                    entry["steps"] = props.steps
                if props.placeholder:
                    entry["placeholder"] = props.placeholder
                if getattr(props, "col_span", None):
                    entry["colSpan"] = props.col_span
            fields.append(entry)
        pages.append({"pageId": slide.id, "index": slide.index, "fields": fields})
    snapshot = {"title": form.title, "description": form.description, "pages": pages}
    return json.dumps(snapshot, ensure_ascii=False)


def build_chat_system_prompt(form_snapshot: str, profile) -> str:
    """System prompt for a form-editing chat turn."""
    parts = [
        "You are the form-editing copilot inside BetterCollected, a privacy-first form builder.",
        OPS_GUIDE,
        "## Current form snapshot\n<form_snapshot>\n" + form_snapshot + "\n</form_snapshot>",
    ]
    block = render_prompt_block(profile)
    if block:
        parts.append(block)
    return "\n\n".join(parts)


def extract_json_object(text: str) -> dict:
    """Tolerant parse of the model's reply into a JSON object.

    Strips markdown fences and trailing prose; raises ValueError when no
    object can be recovered (the caller surfaces a clean error, never a 500).
    """
    import json

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("The model reply contained no JSON object.")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(cleaned[start:])
    if not isinstance(obj, dict):
        raise ValueError("The model reply was not a JSON object.")
    return obj
