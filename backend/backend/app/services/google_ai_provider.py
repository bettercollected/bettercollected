"""Google Gemini-backed AI form provider using function-calling tools.

Gemini cannot combine function calling with a JSON response type, so the
generated form is validated and retried once; chat calls use JSON mode.
"""

import asyncio
import json
from typing import Any, Dict, Optional

from backend.app.services.ai.errors import ai_step_limit, ai_unusable
from backend.app.services.ai.structured import (
    InvalidReply,
    correction_message,
    parse_generated_form,
)
from backend.app.services.ai.untrusted import UNTRUSTED_CONTENT_RULES
from backend.app.services.ai.usage import record_tokens
from backend.app.services.ai_form_provider import (
    PAGE_MAX_TOKENS,
    PAGE_TIMEOUT_S,
    AIFormProvider,
    call_provider,
)
from backend.app.services.ai_form_tools import (
    _gemini_tools,
    execute_tool,
    parse_tool_args,
)
from backend.app.services.unsplash_service import UnsplashService
from backend.app.services.form_generation_rules import (
    HONEST_FORM_RULES,
    LANGUAGE_RULES,
    SECTION_TITLE_RULES,
)
from backend.config import settings

SYSTEM_PROMPT = """
You are a form designer AI. Your task is to generate a valid JSON object that
describes a multi-page form. Follow the schema and rules below exactly.

## Workflow (follow in order)
1. Call `get_available_themes` ONCE → use `Leaflet` (the default for new forms) unless the request asks for other colours or a particular mood, then pick the theme that fits → set `theme_name`.
2. Call `get_available_layouts` ONCE → learn available layouts.
3. Call `search_images` for the WELCOME PAGE with a query about the form's subject only,
   built from its title, description and first questions (e.g. "community centre activities"
   or "hospital patient care"), and pass the chosen `theme_name`. Never put the theme
   name, the style or colour words in the query.
   If photos are returned use the best URL as `welcome_image_url`.
4. For EACH top-level field/group (= one slide), call `search_images` separately with a
   query about that slide's topic only, e.g. "personal information paperwork" or
   "team feedback office" (again no theme, style or colour words).
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
    sectionTitle?: string;  // optional short name of this page's section (see below)
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
SYSTEM_PROMPT += HONEST_FORM_RULES
SYSTEM_PROMPT += LANGUAGE_RULES
SYSTEM_PROMPT += SECTION_TITLE_RULES
SYSTEM_PROMPT += UNTRUSTED_CONTENT_RULES


def _genai():
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-generativeai package is not installed. "
            "Run: uv add google-generativeai"
        ) from exc
    return genai


def _usage_tokens(response: Any) -> Optional[int]:
    usage = getattr(response, "usage_metadata", None)
    total = getattr(usage, "total_token_count", None)
    return total if isinstance(total, int) else None


def _text(response: Any) -> str:
    # .text raises when the answer has no text part (blocked, empty)
    try:
        return response.text or ""
    except Exception:  # noqa: BLE001
        return ""


def _function_calls(response: Any) -> list:
    try:
        parts = list(response.parts or [])
    except Exception:  # noqa: BLE001
        return []
    return [p.function_call for p in parts if getattr(p.function_call, "name", "")]


class GoogleAIFormProvider(AIFormProvider):
    """Generates forms using Google Gemini with function calling."""

    def __init__(self, unsplash_service: UnsplashService) -> None:
        self._unsplash = unsplash_service
        self._model_name = settings.google_ai.MODEL
        self._api_key = settings.google_ai.API_KEY

    def _model(
        self,
        system: str,
        generation_config: Dict[str, Any],
        tools: Optional[list] = None,
    ):
        genai = _genai()
        genai.configure(api_key=self._api_key)
        return genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system,
            generation_config=generation_config,
            tools=tools or None,
        )

    async def _call(
        self,
        send,
        request_timeout: Optional[float] = None,
        call_timeout: Optional[float] = None,
    ):
        """One request (the SDK is synchronous: run in a thread), bounded by
        a request timeout and the call timeout; tokens counted."""
        request_options = {
            "timeout": request_timeout or settings.ai.REQUEST_TIMEOUT_SECONDS
        }
        loop = asyncio.get_running_loop()
        response = await call_provider(
            lambda: loop.run_in_executor(None, lambda: send(request_options)),
            call_timeout or settings.ai.CALL_TIMEOUT_SECONDS,
        )
        await record_tokens(_usage_tokens(response))
        return response

    async def generate_form(self, prompt: str) -> Dict[str, Any]:
        return await call_provider(
            lambda: self._generate(prompt), settings.ai.GENERATION_TIMEOUT_SECONDS
        )

    async def _generate(self, prompt: str) -> Dict[str, Any]:
        """The tool loop, bounded like OpenAI's: AI_MAX_TOOL_ITERATIONS round
        trips (the answer and its one corrective retry included) and
        AI_MAX_TOOL_CALLS tool calls."""
        config = settings.ai
        model = self._model(
            SYSTEM_PROMPT,
            {"max_output_tokens": config.MAX_OUTPUT_TOKENS_GENERATE},
            tools=_gemini_tools(),
        )
        chat = model.start_chat()
        content: Any = prompt
        tool_calls = 0
        retried = False
        for _ in range(max(1, config.MAX_TOOL_ITERATIONS)):
            message = content
            response = await self._call(
                lambda options: chat.send_message(message, request_options=options)
            )
            calls = _function_calls(response)
            if calls:
                tool_calls += len(calls)
                if tool_calls > config.MAX_TOOL_CALLS:
                    raise ai_step_limit()
                genai = _genai()
                content = []
                for fc in calls:
                    result = await execute_tool(
                        fc.name, parse_tool_args(dict(fc.args or {})), self._unsplash
                    )
                    content.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=fc.name, response={"result": result}
                            )
                        )
                    )
                continue
            try:
                return parse_generated_form(_text(response))
            except InvalidReply as invalid:
                if retried:
                    raise ai_unusable() from None
                retried = True
                content = correction_message(invalid.problems)
        raise ai_step_limit()

    async def chat(
        self,
        system: str,
        messages: list,
        *,
        max_output_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """Plain multi-turn chat (no tools) — used by AI form editing."""
        generation_config: Dict[str, Any] = {
            "max_output_tokens": max_output_tokens or settings.ai.MAX_OUTPUT_TOKENS_CHAT
        }
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
        model = self._model(system, generation_config)
        history = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [m["content"]],
            }
            for m in messages[:-1]
        ]
        session = model.start_chat(history=history)
        last = messages[-1]["content"]
        response = await self._call(
            lambda options: session.send_message(last, request_options=options)
        )
        return _text(response)

    supports_vision = True

    async def analyze_page(
        self, system: str, prompt: str, image_png, schema: dict
    ) -> dict:
        model = self._model(
            system,
            {
                "response_mime_type": "application/json",
                "max_output_tokens": PAGE_MAX_TOKENS,
            },
        )
        parts = [
            prompt
            + "\n\nAnswer with one JSON object that follows this schema:\n"
            + json.dumps(schema)
        ]
        if image_png:
            parts.append({"mime_type": "image/png", "data": image_png})
        response = await self._call(
            lambda options: model.generate_content(parts, request_options=options),
            request_timeout=PAGE_TIMEOUT_S,
            call_timeout=PAGE_TIMEOUT_S * (1 + max(0, settings.ai.CLIENT_MAX_RETRIES)),
        )
        text = (_text(response) or "{}").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
