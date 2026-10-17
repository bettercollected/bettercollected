"""OpenAI-compatible AI form provider — the self-hosting story.

Points at any OpenAI-compatible endpoint (Ollama, vLLM, LM Studio,
OpenRouter, a corporate gateway…) via AI_COMPAT_BASE_URL / AI_COMPAT_MODEL,
so a self-hosted BetterCollected can run every AI feature without a prompt
ever leaving its own infrastructure.

Deliberately tool-free: many local models don't do function calling, so
generation asks for the JSON directly and skips theme/image tooling — the
converter tolerates their absence. JSON mode is requested unless
AI_COMPAT_JSON_MODE is off; replies are validated and retried once either way.
"""

import json
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from backend.app.services.ai.untrusted import UNTRUSTED_CONTENT_RULES
from backend.app.services.ai_form_provider import (
    PAGE_MAX_TOKENS,
    PAGE_TIMEOUT_S,
    AIFormProvider,
    call_provider,
)
from backend.app.services.form_generation_rules import (
    HONEST_FORM_RULES,
    SECTION_TITLE_RULES,
)
from backend.app.services.openai_provider import OpenAIClientCalls
from backend.config import settings

GENERATION_SYSTEM_PROMPT = """
You are a form designer AI. Generate a valid JSON object describing a
multi-page form for the user's request. Output ONLY the JSON — no markdown
fences, no commentary.

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
        choices?: string[];   // required for multiple_choice / dropdown (>= 2)
        steps?: number;       // required for rating / linear_rating
    };
}

interface SlideField {
    title: string;
    sectionTitle?: string;  // optional short name of this page's section (see below)
    type: 'group';
    layout: 'SINGLE_COLUMN_NO_BACKGROUND';
    properties: { fields: InnerField[] };
}

interface Form {
    title: string;
    description?: string;
    fields: SlideField[];   // each SlideField is one page
}

## Rules
1. Wrap related fields into 'group' pages (2-6 fields per page).
2. Every layout is 'SINGLE_COLUMN_NO_BACKGROUND'.
3. 'choices' required for multiple_choice/dropdown (>= 2 options); 'steps' for ratings.
4. Realistic, human-friendly content. Valid JSON only.
"""
GENERATION_SYSTEM_PROMPT += HONEST_FORM_RULES
GENERATION_SYSTEM_PROMPT += SECTION_TITLE_RULES
GENERATION_SYSTEM_PROMPT += UNTRUSTED_CONTENT_RULES


def _json_mode() -> Dict[str, Any]:
    if settings.ai.COMPAT_JSON_MODE:
        return {"response_format": {"type": "json_object"}}
    return {}


class OpenAICompatibleFormProvider(OpenAIClientCalls, AIFormProvider):
    def __init__(self) -> None:
        self._base_url = settings.ai.COMPAT_BASE_URL
        self._model = settings.ai.COMPAT_MODEL
        self._api_key = settings.ai.COMPAT_API_KEY or "not-needed"
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                **self._client_options(),
            )
        return self._client

    async def generate_form(self, prompt: str) -> Dict[str, Any]:
        return await call_provider(
            lambda: self._form_reply(
                [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.ai.MAX_OUTPUT_TOKENS_GENERATE,
                **_json_mode(),
            ),
            settings.ai.GENERATION_TIMEOUT_SECONDS,
        )

    async def chat(
        self,
        system: str,
        messages: list,
        *,
        max_output_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        response = await self._complete(
            messages=[{"role": "system", "content": system}, *messages],
            max_tokens=max_output_tokens or settings.ai.MAX_OUTPUT_TOKENS_CHAT,
            **(_json_mode() if json_mode else {}),
        )
        return response.choices[0].message.content or ""

    @property
    def supports_vision(self) -> bool:
        # self-hosted models often have no vision: opt in with AI_COMPAT_VISION=true
        return bool(settings.ai.COMPAT_VISION)

    async def analyze_page(
        self, system: str, prompt: str, image_png, schema: dict
    ) -> dict:
        import base64

        content = [
            {
                "type": "text",
                "text": prompt
                + "\n\nAnswer with one JSON object that follows this schema:\n"
                + json.dumps(schema),
            }
        ]
        if image_png and self.supports_vision:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(image_png).decode("ascii")
                    },
                }
            )
        response = await self._complete(
            request_timeout=PAGE_TIMEOUT_S,
            call_timeout=PAGE_TIMEOUT_S * (1 + max(0, settings.ai.CLIENT_MAX_RETRIES)),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            max_tokens=PAGE_MAX_TOKENS,
        )
        return _json_answer(response.choices[0].message.content or "{}")


def _json_answer(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
