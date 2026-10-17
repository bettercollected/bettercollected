"""Google Gemini-backed AI provider: chat (JSON mode; callers validate the
reply and retry once) and page analysis for the form import.
"""

import asyncio
import json
from typing import Any, Dict, Optional

from backend.app.services.ai.usage import record_tokens
from backend.app.services.ai_form_provider import (
    PAGE_MAX_TOKENS,
    PAGE_TIMEOUT_S,
    AIFormProvider,
    call_provider,
)
from backend.config import settings


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


class GoogleAIFormProvider(AIFormProvider):
    """Google Gemini."""

    def __init__(self) -> None:
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

    async def chat(
        self,
        system: str,
        messages: list,
        *,
        max_output_tokens: Optional[int] = None,
        json_mode: bool = False,
        json_schema: Optional[dict] = None,
    ) -> str:
        """Plain multi-turn chat (no tools) — used by AI form editing.
        ``json_schema`` is not passed on (Gemini's schema dialect differs
        from strict JSON schema): JSON mode, and the caller validates."""
        json_mode = json_mode or json_schema is not None
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
