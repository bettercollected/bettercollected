"""OpenAI-backed AI form provider using function-calling tools."""

import json
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from backend.app.services.ai_form_provider import AIFormProvider
from backend.app.services.ai_form_tools import OPENAI_TOOLS, execute_tool
from backend.app.services.unsplash_service import UnsplashService
from backend.config import settings

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a form designer AI. Your task is to generate a valid JSON object that
describes a multi-page form. Follow the schema and rules below exactly.

## Workflow (follow in order)
1. Call `get_available_themes` ONCE → choose the best theme for the form type → set `theme_name`.
2. Call `get_available_layouts` ONCE → learn available layouts.
3. Call `search_images` for the WELCOME PAGE using a query like
   "{theme_name} {form_topic}" (e.g. "purple minimal healthcare" or "blue corporate survey").
   If photos are returned use the best URL as `welcome_image_url`.
4. For EACH top-level field/group (= one slide), call `search_images` separately with a
   query combining the chosen theme and the slide's topic, e.g.
   "purple personal information form" or "blue team feedback office".
   - If a photo is returned: set `image_url` on that field to the best photo URL and set
     `layout` to `TWO_COLUMN_IMAGE_LEFT` (odd slides) or `TWO_COLUMN_IMAGE_RIGHT` (even slides)
     to alternate sides and create visual variety.
   - If no photo is returned (empty results): set `layout` to `SINGLE_COLUMN_NO_BACKGROUND`
     and omit `image_url`.
5. Output a SINGLE valid JSON object as your final message — NO markdown fences, NO extra text.

## Output schema

// Inner fields (inside a group) — no layout/image_url needed
interface InnerField {
    title: string;
    description?: string;
    type: 'short_text' | 'long_text' | 'multiple_choice' | 'dropdown' | 'yes_no' |
           'rating' | 'linear_rating' | 'number' | 'email' | 'phone_number' | 'date' |
           'file_upload' | 'url';
    properties?: {
        placeholder?: string;
        required?: boolean;
        allowOther?: boolean;
        allowMultiple?: boolean;
        choices?: string[];   // required for multiple_choice / dropdown (>= 2)
        steps?: number;       // required for rating / linear_rating
        startFrom?: number;
    };
}

// Top-level field = one slide/page of the form
interface SlideField {
    title: string;
    description?: string;
    type: 'group' | 'short_text' | 'long_text' | 'multiple_choice' | 'dropdown' |
          'yes_no' | 'rating' | 'linear_rating' | 'number' | 'email' |
          'phone_number' | 'date' | 'file_upload' | 'url';
    layout: string;        // layout value for THIS slide (from get_available_layouts)
    image_url?: string;    // Unsplash photo URL for THIS slide (from search_images)
    properties?: {
        placeholder?: string;
        required?: boolean;
        allowOther?: boolean;
        allowMultiple?: boolean;
        choices?: string[];
        steps?: number;
        startFrom?: number;
        fields?: InnerField[];  // only when type = 'group'
    };
}

interface Form {
    title: string;
    description?: string;
    theme_name: string;           // from get_available_themes
    welcome_image_url?: string;   // URL from search_images for the welcome page
    cover_image_url?: string;     // same as welcome_image_url or a second search result
    fields: SlideField[];         // each element is one slide, with its own layout & image_url
}

## Strict rules
1. EVERY top-level field MUST have a `layout` value (never omit it).
2. When `image_url` is present on a slide, `layout` MUST be `TWO_COLUMN_IMAGE_LEFT` or
   `TWO_COLUMN_IMAGE_RIGHT`. Never use a single-column layout when an image is set.
3. When no image is available for a slide, use `SINGLE_COLUMN_NO_BACKGROUND`.
4. Wrap logically related questions in a `group` (= one page). Each group needs a
   meaningful `title` and at least two `properties.fields`.
5. `choices` required for `multiple_choice` / `dropdown` (≥ 2 options).
6. `steps` required for `rating` / `linear_rating` (positive integer).
7. Use realistic, human-friendly content — no placeholder text like "Question 1".
8. Output must be syntactically valid JSON matching the Form schema exactly.
"""


class OpenAIFormProvider(AIFormProvider):
    """Generates forms using OpenAI chat completions with function calling."""

    def __init__(self, unsplash_service: UnsplashService) -> None:
        # Construct the client lazily (see `client`) so the app can boot
        # without an OpenAI key; only actually generating a form needs one.
        self._client: Optional[AsyncOpenAI] = None
        self._model = settings.open_ai.MODAL
        self._unsplash = unsplash_service

    @property
    def client(self) -> AsyncOpenAI:
        # `openai` >= 2.44 raises at construction when the API key is missing,
        # so building the client eagerly in __init__ would crash startup for
        # anyone not using AI form generation. Defer it to first use.
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.open_ai.API_KEY)
        return self._client

    async def generate_form(self, prompt: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        # Agentic tool-call loop — runs until the model emits a plain message.
        while True:
            response = await self.client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=OPENAI_TOOLS,
                tool_choice="auto",
            )
            choice = response.choices[0]

            # Model wants to call one or more tools
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                messages.append(choice.message)  # assistant turn with tool_calls

                for tc in choice.message.tool_calls:
                    tool_args = json.loads(tc.function.arguments or "{}")
                    result = await execute_tool(
                        tc.function.name, tool_args, self._unsplash
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        }
                    )
                # Continue the loop so the model can keep calling tools or respond
                continue

            # Model returned its final textual answer
            content = choice.message.content or ""
            # Strip optional markdown code fences
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)

    async def chat(self, system: str, messages: list) -> str:
        """Plain multi-turn chat (no tools) — used by AI form editing."""
        response = await self.client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, *messages],
        )
        return response.choices[0].message.content or ""
