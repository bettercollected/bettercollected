"""Tool definitions and executor shared by all AI form providers.

Each tool is described in the JSON-Schema format expected by both
OpenAI function-calling and Google Gemini function-calling APIs.
The ``execute_tool`` coroutine maps tool names to their implementations.
"""

import json
from typing import Any, Dict

from backend.app.constants.layouts import get_layouts_for_ai
from backend.app.constants.themes import get_themes_for_ai
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
            "generation so you can choose the most appropriate theme for the "
            "form type requested by the user. Return the chosen theme_name in "
            "your final JSON under the key 'theme_name'."
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
            "Call this tool ONCE for the welcome page and then ONCE PER SLIDE using "
            "a query that combines the chosen theme name with the slide topic, e.g. "
            "'purple minimal personal information' or 'blue corporate team feedback'. "
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
                        "Keyword query combining the chosen theme and the slide topic, "
                        "e.g. 'purple minimal healthcare patients' or "
                        "'blue corporate office team survey'."
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
        query = tool_args.get("query", "")
        orientation = tool_args.get("orientation", "landscape")
        photos = await unsplash_service.search_photos(
            query=query, per_page=5, orientation=orientation
        )
        return photos

    raise ValueError(f"Unknown tool: {tool_name}")
