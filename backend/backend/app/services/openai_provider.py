"""OpenAI-backed AI form provider using function-calling tools."""

import json
from typing import Any, Dict

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

## Workflow
1. Call `get_available_themes` to review themes and pick the best one.
2. Call `get_available_layouts` to review layouts and decide a layout per slide.
3. Call `search_images` with a relevant keyword to find an image for the
   form's welcome page and/or cover.
4. Output a SINGLE valid JSON object as your final message (no markdown fences).

## Output schema

interface Field {
    title: string;
    description?: string;
    type: 'short_text' | 'long_text' | 'multiple_choice' | 'dropdown' | 'yes_no' |
           'rating' | 'linear_rating' | 'number' | 'email' | 'phone_number' | 'date' |
           'file_upload' | 'url' | 'group';
    properties?: {
        placeholder?: string;
        required?: boolean;
        allowOther?: boolean;
        allowMultiple?: boolean;
        choices?: string[];
        steps?: number;
        startFrom?: number;
        fields?: Field[];   // only for type='group'
    };
}

interface Form {
    title: string;
    description?: string;
    theme_name: string;            // chosen theme name from get_available_themes
    welcome_image_url?: string;    // best URL from search_images
    cover_image_url?: string;      // optional second image for cover
    slide_layouts?: string[];      // ordered list of layout values, one per group/field
    fields: Field[];
}

## Strict rules
1. Use only the allowed `type` values (case-sensitive).
2. Wrap logically related fields in a `group` (= one page of the form).
3. Each `group` must have a meaningful `title` and at least two `properties.fields`.
4. `choices` is required for `multiple_choice` and `dropdown` (≥ 2 options).
5. `steps` is required for `rating` and `linear_rating` and must be a positive integer.
6. Use realistic, human-friendly content — no placeholder text like "Question 1".
7. Always populate `theme_name`, `welcome_image_url`, and `slide_layouts`.
8. Output must be syntactically valid JSON matching the Form schema above.
"""


class OpenAIFormProvider(AIFormProvider):
    """Generates forms using OpenAI chat completions with function calling."""

    def __init__(self, unsplash_service: UnsplashService) -> None:
        self._client = AsyncOpenAI(api_key=settings.open_ai.API_KEY)
        self._model = settings.open_ai.MODAL
        self._unsplash = unsplash_service

    async def generate_form(self, prompt: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        # Agentic tool-call loop — runs until the model emits a plain message.
        while True:
            response = await self._client.chat.completions.create(
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
