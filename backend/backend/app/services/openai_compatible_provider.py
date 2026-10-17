"""OpenAI-compatible AI form provider — the self-hosting story.

Points at any OpenAI-compatible endpoint (Ollama, vLLM, LM Studio,
OpenRouter, a corporate gateway…) via AI_COMPAT_BASE_URL / AI_COMPAT_MODEL,
so a self-hosted BetterCollected can run every AI feature without a prompt
ever leaving its own infrastructure.

Tool-free: many local models don't do function calling. JSON mode is
requested unless AI_COMPAT_JSON_MODE is off; replies are validated and
retried once either way.
"""

import json
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from backend.app.services.ai_form_provider import (
    PAGE_MAX_TOKENS,
    PAGE_TIMEOUT_S,
    AIFormProvider,
)
from backend.app.services.openai_provider import OpenAIClientCalls
from backend.config import settings


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

    async def chat(
        self,
        system: str,
        messages: list,
        *,
        max_output_tokens: Optional[int] = None,
        json_mode: bool = False,
        json_schema: Optional[dict] = None,
    ) -> str:
        # ``json_schema``: compatible servers differ in what they accept, so
        # only JSON mode is asked for and the reply is validated by the caller.
        json_mode = json_mode or json_schema is not None
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
