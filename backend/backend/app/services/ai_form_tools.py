"""Tool definitions and executor shared by all AI form providers.

Each tool is described in the JSON-Schema format expected by both
OpenAI function-calling and Google Gemini function-calling APIs.
The ``execute_tool`` coroutine maps tool names to their implementations.
"""

import json
from typing import Any, Dict

from backend.app.constants.layouts import get_layouts_for_ai
from backend.app.constants.themes import (
    NEW_FORM_THEME,
    THEME_STYLES,
    get_themes_for_ai,
    theme_dict,
)
from backend.app.services.unsplash_service import UnsplashService

# ---------------------------------------------------------------------------
# Tool schema definitions (JSON-Schema / OpenAPI parameter descriptions)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "get_available_themes",
        "description": (
            "Returns all available visual themes with colour palettes and "
            "usage descriptions. Call this tool ONCE at the start of form "
            "generation. New forms use 'Leaflet' unless the user asks for "
            "other colours or a particular mood; then choose the most "
            "appropriate theme. Return the chosen theme_name in your final "
            "JSON under the key 'theme_name'."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_available_layouts",
        "description": (
            "Returns all available slide/page layout types with descriptions. "
            "Call this tool ONCE to understand layout options and choose the "
            "most suitable layout per slide. Return per-slide layout choices "
            "in your final JSON under the key 'slide_layouts' as an ordered "
            "list of layout values, one per top-level field/group."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "search_images",
        "description": (
            "Searches Unsplash for royalty-free images matching the given query. "
            "Call this tool ONCE for the welcome page and then ONCE PER SLIDE with "
            "a query about the form's subject or the slide's topic only, e.g. "
            "'community centre activities' or 'team feedback office'. Never put "
            "the theme name, the style or colour words in the query. "
            "If results are returned, take the first photo's 'url' and include it as "
            "'image_url' on that slide field and set the slide layout to "
            "TWO_COLUMN_IMAGE_LEFT or TWO_COLUMN_IMAGE_RIGHT. "
            "If results are empty, omit image_url and use SINGLE_COLUMN_NO_BACKGROUND."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Keywords for the form's subject or the slide topic only, "
                        "e.g. 'healthcare patients' or 'office team survey'. "
                        "No theme, style or colour words."
                    ),
                },
                "theme_name": {
                    "type": "string",
                    "description": (
                        "The theme you chose for this form (theme_name), "
                        "e.g. 'Leaflet'. Not part of the search."
                    ),
                },
                "orientation": {
                    "type": "string",
                    "enum": ["landscape", "portrait", "squarish"],
                    "description": "Preferred image orientation. Defaults to landscape.",
                },
            },
            "required": ["query"],
        },
    },
]

# ---------------------------------------------------------------------------
# OpenAI-compatible tool schema wrapper
# ---------------------------------------------------------------------------

OPENAI_TOOLS = [{"type": "function", "function": t} for t in TOOL_DEFINITIONS]

# ---------------------------------------------------------------------------
# Google Gemini-compatible tool schema wrapper
# ---------------------------------------------------------------------------


def _gemini_tools():
    """Lazily build Gemini FunctionDeclaration list to avoid hard import at module level."""
    try:
        import google.generativeai as genai  # type: ignore

        declarations = []
        for t in TOOL_DEFINITIONS:
            params = t["parameters"]
            schema = genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    k: genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description=v.get("description", ""),
                        enum=v.get("enum", []) or [],
                    )
                    for k, v in params.get("properties", {}).items()
                },
                required=params.get("required", []),
            )
            declarations.append(
                genai.protos.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=schema,
                )
            )
        return [genai.protos.Tool(function_declarations=declarations)]
    except ImportError:
        return []


# ---------------------------------------------------------------------------
# Image query
# ---------------------------------------------------------------------------

# The prompts already ask for subject-only queries; this is a safety net, so
# it only removes what is plainly a look marker and never a topic word.
_THEME_WORDS = frozenset({"theme", "themed", "style", "styled"})
_PUNCTUATION = "\"'.,;:!?()[]{}"


def _norm(word: str) -> str:
    return word.lower().strip(_PUNCTUATION)


def _strip_look_words(
    words: list[str], names: list[list[str]], bare_leaflet: bool
) -> list[str]:
    """Drop the look markers at the start of ``words`` (see ``image_query``)."""
    while words:
        normed = [_norm(w) for w in words]
        for name in names:
            n = len(name)
            # "<name> theme ..." or "theme <name> ..."
            if normed[:n] == name and len(words) > n and normed[n] in _THEME_WORDS:
                words = words[n + 1 :]
                break
            if normed[0] in _THEME_WORDS and normed[1 : n + 1] == name:
                words = words[n + 1 :]
                break
        else:
            if bare_leaflet and normed[0] == "leaflet":
                words = words[1:]
                continue
            break
    return words


def image_query(query: str, theme_name: str | None = None) -> str:
    """The subject part of an image search query.

    The photo should show what the form is about, never what it looks like.
    At either end of the query, a theme or style name (the name of the theme
    this form uses, or classic/sheet/studio/leaflet) is dropped only together
    with "theme"/"themed"/"style"/"styled" next to it: "Forest theme trail
    survey" -> "trail survey", while "Forest trail survey" and "Red Cross
    blood donation" stay whole. One exception: a bare "leaflet" at either end
    goes when the form's style is Leaflet (the new-form default). Nothing in
    the middle is touched. Returns "" when nothing but look markers was given.
    """
    theme_name = theme_name or NEW_FORM_THEME
    chosen = [_norm(t) for t in theme_name.split() if _norm(t)]
    names = [[style] for style in THEME_STYLES]
    if chosen and chosen not in names:
        names.append(chosen)
    preset = next(
        (v for k, v in theme_dict.items() if k.lower() == theme_name.strip().lower()),
        {},
    )
    leaflet_style = preset.get("style") == "leaflet"

    words = (query or "").split()
    words = _strip_look_words(words, names, leaflet_style)
    reversed_names = [name[::-1] for name in names]
    words = _strip_look_words(words[::-1], reversed_names, leaflet_style)[::-1]
    return " ".join(words)


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------


async def execute_tool(
    tool_name: str,
    tool_args: Dict[str, Any],
    unsplash_service: UnsplashService,
) -> Any:
    """Dispatch a tool call to its implementation and return a JSON-serialisable result."""

    if tool_name == "get_available_themes":
        return get_themes_for_ai()

    if tool_name == "get_available_layouts":
        return get_layouts_for_ai()

    if tool_name == "search_images":
        theme_name = str(tool_args.get("theme_name") or NEW_FORM_THEME)
        query = image_query(str(tool_args.get("query", "")), theme_name)
        if not query:
            # Only look words were given: no subject to show, so no photo.
            return []
        orientation = tool_args.get("orientation", "landscape")
        photos = await unsplash_service.search_photos(
            query=query, per_page=5, orientation=orientation
        )
        return photos

    raise ValueError(f"Unknown tool: {tool_name}")
