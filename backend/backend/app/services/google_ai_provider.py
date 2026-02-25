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
        fields?: Field[];
    };
}

interface Form {
    title: string;
    description?: string;
    theme_name: string;
    welcome_image_url?: string;
    cover_image_url?: string;
    slide_layouts?: string[];
    fields: Field[];
}

## Strict rules
1. Use only the allowed `type` values (case-sensitive).
2. Wrap logically related fields in a `group` (= one page of the form).
3. Each `group` must have a meaningful `title` and at least two `properties.fields`.
4. `choices` is required for `multiple_choice` and `dropdown` (≥ 2 options).
5. `steps` is required for `rating` and `linear_rating` and must be a positive integer.
6. Use realistic, human-friendly content.
7. Always populate `theme_name`, `welcome_image_url`, and `slide_layouts`.
8. Output must be syntactically valid JSON matching the Form schema above.

Return ONLY the JSON object with no extra text or markdown fences.
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
