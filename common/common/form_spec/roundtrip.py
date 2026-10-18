"""The round-trip guarantee of the form spec, as code.

``creator_view(form)`` is a stored form reduced to what the spec keeps:
for every page-based form, ``creator_view(spec_to_form(form_to_spec(f)))
== creator_view(f)``. What it drops is listed here, on purpose (see the
adapters' docstring and docs/spec/README.md for why).
"""

from typing import Any, Dict

from common.models.standard_form import FORM_LANGUAGES, StandardForm

EXCLUDED_FORM = frozenset(
    {
        "form_id",
        "imported_form_id",
        "type",
        "state",
        "published_at",
        "actions",
        "parameters",
        "secrets",
        "builder_version",
        "is_multi_page",
        "consent",
        "button_text",
        "cover_image",
        "row_titles",
        "column_titles",
    }
)
EXCLUDED_FIELD = frozenset({"index", "tag", "ref"})
EXCLUDED_PROPERTIES = frozenset(
    {
        "actions",
        "conditions",
        "logical_operator",
        "update_id",
        "mentions",
        "hidden",
        "button_text",
        "description",
    }
)
# a question's own theme and layout (pages keep theirs)
EXCLUDED_QUESTION_PROPERTIES = EXCLUDED_PROPERTIES | {"theme", "layout"}
# What a page is in the spec; anything else on a stored page (a title,
# validations, choices... that the page-based builder never sets) is not.
PAGE_KEYS = frozenset({"id", "type", "image_url", "properties"})
PAGE_PROPERTIES = frozenset(
    {
        "section_title",
        "layout",
        "theme",
        "show_question_numbers",
        "position",
        "jumps",
        "fields",
    }
)
# the form's own settings the document carries: its language and what the
# trust block holds (the rest is server-owned)
KEPT_SETTINGS = frozenset(
    {
        "language",
        "privacy_policy_url",
        "response_expiration",
        "response_expiration_type",
    }
)


def _strip(value: Any) -> Any:
    """Drop None values, then empty containers."""
    if isinstance(value, dict):
        out = {k: _strip(v) for k, v in value.items() if v is not None}
        return {k: v for k, v in out.items() if v not in ({}, [])}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def creator_view(form: StandardForm) -> Dict[str, Any]:
    """The stored form reduced to what the spec promises to keep."""
    data = form.model_dump(mode="json")
    for key in EXCLUDED_FORM:
        data.pop(key, None)
    data["settings"] = {
        k: v for k, v in (data.get("settings") or {}).items() if k in KEPT_SETTINGS
    }
    # only a language a form can declare is in the document
    if data["settings"].get("language") not in FORM_LANGUAGES:
        data["settings"].pop("language", None)

    def question(item: dict) -> dict:
        for key in EXCLUDED_FIELD:
            item.pop(key, None)
        props = item.get("properties") or {}
        if item.get("description") is None:
            # the spec's one description falls back to the properties copy
            item["description"] = props.get("description")
        for key in EXCLUDED_QUESTION_PROPERTIES:
            props.pop(key, None)
        for choice in props.get("choices") or []:
            choice.pop("ref", None)
        props["fields"] = [question(child) for child in props.get("fields") or []]
        return item

    def page(item: dict) -> dict:
        item = {k: v for k, v in item.items() if k in PAGE_KEYS}
        props = {
            k: v
            for k, v in (item.get("properties") or {}).items()
            if k in PAGE_PROPERTIES
        }
        props["fields"] = [question(child) for child in props.get("fields") or []]
        item["properties"] = props
        return item

    data["fields"] = [page(item) for item in data.get("fields") or []]
    return _strip(data)
