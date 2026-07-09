"""Google Gemini-backed AI form provider using function-calling tools."""

import json
from typing import Any, Dict

from backend.app.services.ai_form_provider import AIFormProvider
from backend.app.services.ai_form_tools import execute_tool, _gemini_tools
from backend.app.services.unsplash_service import UnsplashService
from backend.config import settings

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
     `layout` to `TWO_COLUMN_IMAGE_LEFT` (odd slides) or `TWO_COLUMN_IMAGE_RIGHT` (even slides).
   - If no photo is returned: set `layout` to `SINGLE_COLUMN_NO_BACKGROUND`, omit `image_url`.
5. Output a SINGLE valid JSON object — NO markdown fences, NO extra text.

## Output schema

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
        choices?: string[];
        steps?: number;
        startFrom?: number;
    };
}

interface SlideField {
    title: string;
    description?: string;
    type: 'group' | 'short_text' | 'long_text' | 'multiple_choice' | 'dropdown' |
          'yes_no' | 'rating' | 'linear_rating' | 'number' | 'email' |
          'phone_number' | 'date' | 'file_upload' | 'url';
    layout: string;       // layout value for THIS slide
    image_url?: string;   // Unsplash URL for THIS slide
    properties?: {
        placeholder?: string;
        required?: boolean;
        allowOther?: boolean;
        allowMultiple?: boolean;
        choices?: string[];
        steps?: number;
        startFrom?: number;
        fields?: InnerField[];
    };
}

interface Form {
    title: string;
    description?: string;
    theme_name: string;
    welcome_image_url?: string;
    cover_image_url?: string;
    fields: SlideField[];
}

## Strict rules
1. EVERY top-level field MUST have a `layout` value.
2. When `image_url` is set, `layout` MUST be `TWO_COLUMN_IMAGE_LEFT` or `TWO_COLUMN_IMAGE_RIGHT`.
3. When no image, use `SINGLE_COLUMN_NO_BACKGROUND`.
4. Wrap related fields in a `group`. Each group needs a title and at least two inner fields.
5. `choices` required for `multiple_choice` / `dropdown` (≥ 2 options).
6. `steps` required for `rating` / `linear_rating` (positive integer).
7. Use realistic, human-friendly content.
8. Output must be syntactically valid JSON. Return ONLY the JSON — no markdown, no extra text.
"""


class GoogleAIFormProvider(AIFormProvider):
    """Generates forms using Google Gemini with function calling."""

    def __init__(self, unsplash_service: UnsplashService) -> None:
        self._unsplash = unsplash_service
        self._model_name = settings.google_ai.MODEL
        self._api_key = settings.google_ai.API_KEY

    def _get_model(self):
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self._api_key)
            tools = _gemini_tools()
            return genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=SYSTEM_PROMPT,
                tools=tools if tools else None,
            )
        except ImportError as exc:
            raise RuntimeError(
                "google-generativeai package is not installed. "
                "Run: pip install google-generativeai"
            ) from exc

    async def generate_form(self, prompt: str) -> Dict[str, Any]:
        import asyncio

        model = self._get_model()
        chat = model.start_chat()

        # Gemini's Python SDK is synchronous; run in executor to avoid blocking.
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: chat.send_message(prompt))

        # Agentic tool-call loop
        while True:
            # Check if the model wants to call a function
            function_calls = []
            for part in response.parts:
                if part.function_call.name:
                    function_calls.append(part.function_call)

            if not function_calls:
                break  # Model gave a textual response

            # Execute each function call and send results back
            tool_results = []
            for fc in function_calls:
                args = dict(fc.args)
                result = await execute_tool(fc.name, args, self._unsplash)
                import google.generativeai as genai  # type: ignore

                tool_results.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fc.name,
                            response={"result": result},
                        )
                    )
                )

            response = await loop.run_in_executor(
                None, lambda: chat.send_message(tool_results)
            )

        # Extract the final text
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)

    async def chat(self, system: str, messages: list) -> str:
        """Plain multi-turn chat (no tools) — used by AI form editing."""
        import asyncio

        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(model_name=self._model_name, system_instruction=system)
        history = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [m["content"]]}
            for m in messages[:-1]
        ]
        session = model.start_chat(history=history)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: session.send_message(messages[-1]["content"]))
        return response.text
