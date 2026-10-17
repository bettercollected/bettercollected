"""OpenAI-backed AI form provider using function-calling tools."""

import json
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from backend.app.services.ai.errors import ai_step_limit, ai_unusable
from backend.app.services.ai.structured import (
    InvalidReply,
    correction_message,
    generated_form_schema,
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
    OPENAI_TOOLS,
    execute_tool,
    parse_tool_args,
)
from backend.app.services.unsplash_service import UnsplashService
from backend.app.services.form_generation_rules import (
    HONEST_FORM_RULES,
    SECTION_TITLE_RULES,
)
from backend.config import settings

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

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
    sectionTitle?: string;  // optional short name of this page's section (see below)
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
SYSTEM_PROMPT += HONEST_FORM_RULES
SYSTEM_PROMPT += SECTION_TITLE_RULES
SYSTEM_PROMPT += UNTRUSTED_CONTENT_RULES

# The final answer as OpenAI structured output (strict JSON schema); tool
# calls stay possible alongside it.
FORM_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "generated_form",
        "schema": generated_form_schema(),
        "strict": True,
    },
}


def usage_tokens(response: Any) -> Optional[int]:
    """Tokens an OpenAI-style response reports (prompt and output), if any."""
    usage = getattr(response, "usage", None)
    total = getattr(usage, "total_tokens", None)
    return total if isinstance(total, int) else None


class OpenAIClientCalls:
    """Bounded chat-completion calls shared by the OpenAI and the
    OpenAI-compatible providers: a timeout on each request, the whole call
    (client retries included) within AI_CALL_TIMEOUT_SECONDS, tokens counted."""

    _model: Optional[str] = None

    @staticmethod
    def _client_options() -> Dict[str, Any]:
        return {
            "timeout": settings.ai.REQUEST_TIMEOUT_SECONDS,
            "max_retries": max(0, settings.ai.CLIENT_MAX_RETRIES),
        }

    async def _complete(
        self,
        request_timeout: Optional[float] = None,
        call_timeout: Optional[float] = None,
        **kwargs,
    ):
        kwargs.setdefault("model", self._model)
        kwargs["timeout"] = request_timeout or settings.ai.REQUEST_TIMEOUT_SECONDS
        response = await call_provider(
            lambda: self.client.chat.completions.create(**kwargs),
            call_timeout or settings.ai.CALL_TIMEOUT_SECONDS,
        )
        await record_tokens(usage_tokens(response))
        return response

    async def _form_reply(self, messages: list, **kwargs) -> Dict[str, Any]:
        """A tool-free generation whose reply must be a form: one corrective
        retry, then ``ai_unusable``."""
        for _ in range(2):
            response = await self._complete(messages=messages, **kwargs)
            content = response.choices[0].message.content or ""
            try:
                return parse_generated_form(content)
            except InvalidReply as invalid:
                messages = messages + [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": correction_message(invalid.problems)},
                ]
        raise ai_unusable()


class OpenAIFormProvider(OpenAIClientCalls, AIFormProvider):
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
            self._client = AsyncOpenAI(
                api_key=settings.open_ai.API_KEY, **self._client_options()
            )
        return self._client

    async def generate_form(self, prompt: str) -> Dict[str, Any]:
        return await call_provider(
            lambda: self._generate(prompt), settings.ai.GENERATION_TIMEOUT_SECONDS
        )

    async def _generate(self, prompt: str) -> Dict[str, Any]:
        """The tool loop: the model calls tools until it answers with the
        form. At most AI_MAX_TOOL_ITERATIONS round trips (the answer and its
        one corrective retry included) and AI_MAX_TOOL_CALLS tool calls."""
        config = settings.ai
        messages: list = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        tool_calls = 0
        retried = False
        for _ in range(max(1, config.MAX_TOOL_ITERATIONS)):
            response = await self._complete(
                messages=messages,
                tools=OPENAI_TOOLS,
                tool_choice="auto",
                response_format=FORM_RESPONSE_FORMAT,
                max_completion_tokens=config.MAX_OUTPUT_TOKENS_GENERATE,
            )
            message = response.choices[0].message
            calls = list(getattr(message, "tool_calls", None) or [])
            if calls:
                tool_calls += len(calls)
                if tool_calls > config.MAX_TOOL_CALLS:
                    raise ai_step_limit()
                messages.append(message)  # assistant turn with tool_calls
                for tc in calls:
                    result = await execute_tool(
                        tc.function.name,
                        parse_tool_args(tc.function.arguments),
                        self._unsplash,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        }
                    )
                continue

            content = message.content or ""
            try:
                return parse_generated_form(content)
            except InvalidReply as invalid:
                if retried:
                    raise ai_unusable() from None
                retried = True
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {"role": "user", "content": correction_message(invalid.problems)}
                )
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
        extra = {"response_format": {"type": "json_object"}} if json_mode else {}
        response = await self._complete(
            messages=[{"role": "system", "content": system}, *messages],
            max_completion_tokens=max_output_tokens
            or settings.ai.MAX_OUTPUT_TOKENS_CHAT,
            **extra,
        )
        return response.choices[0].message.content or ""

    supports_vision = True

    async def analyze_page(
        self, system: str, prompt: str, image_png, schema: dict
    ) -> dict:
        """Page analysis for the form import, with the page image and a strict schema.
        Uses the import model (PDF_IMPORT_OPENAI_MODEL), not the chat model."""
        import base64

        content = [{"type": "text", "text": prompt}]
        if image_png:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(image_png).decode("ascii"),
                        "detail": "high",
                    },
                }
            )
        response = await self._complete(
            request_timeout=PAGE_TIMEOUT_S,
            call_timeout=PAGE_TIMEOUT_S * (1 + max(0, settings.ai.CLIENT_MAX_RETRIES)),
            model=settings.pdf_import.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            response_format={
                "type": "json_schema",
                # the schema follows strict mode's rules (structuring.schema)
                "json_schema": {"name": "form_page", "schema": schema, "strict": True},
            },
            max_completion_tokens=PAGE_MAX_TOKENS,
        )
        return _json_answer(response.choices[0].message.content or "{}")


def _json_answer(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
