"""OpenAI-backed AI provider: chat (JSON mode or a strict JSON schema) and
page analysis for the form import."""

import json
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from backend.app.services.ai.usage import record_tokens
from backend.app.services.ai_form_provider import (
    PAGE_MAX_TOKENS,
    PAGE_TIMEOUT_S,
    AIFormProvider,
    call_provider,
)
from backend.config import settings


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


class OpenAIFormProvider(OpenAIClientCalls, AIFormProvider):
    """OpenAI chat completions."""

    def __init__(self) -> None:
        # Construct the client lazily (see `client`) so the app can boot
        # without an OpenAI key; only actually generating a form needs one.
        self._client: Optional[AsyncOpenAI] = None
        self._model = settings.open_ai.MODAL

    @property
    def client(self) -> AsyncOpenAI:
        # `openai` >= 2.44 raises at construction when the API key is missing,
        # so building the client eagerly in __init__ would crash startup for
        # anyone not using AI. Defer it to first use.
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.open_ai.API_KEY, **self._client_options()
            )
        return self._client

    async def chat(
        self,
        system: str,
        messages: list,
        *,
        max_output_tokens: Optional[int] = None,
        json_mode: bool = False,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Plain multi-turn chat (no tools) — used by AI form editing.
        ``json_schema`` ({"name", "schema"}, strict-mode rules) asks for
        structured output; otherwise ``json_mode`` asks for a JSON object."""
        extra: Dict[str, Any] = {}
        if json_schema is not None:
            extra = {
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {**json_schema, "strict": True},
                }
            }
        elif json_mode:
            extra = {"response_format": {"type": "json_object"}}
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
