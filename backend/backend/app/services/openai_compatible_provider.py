"""OpenAI-compatible AI form provider — the self-hosting story.

Points at any OpenAI-compatible endpoint (Ollama, vLLM, LM Studio,
OpenRouter, a corporate gateway…) via AI_COMPAT_BASE_URL / AI_COMPAT_MODEL,
so a self-hosted BetterCollected can run every AI feature without a prompt
ever leaving its own infrastructure.

Deliberately tool-free: many local models don't do function calling, so
generation asks for the JSON directly and skips theme/image tooling — the
converter tolerates their absence.
"""

import json
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from backend.app.services.ai_form_provider import AIFormProvider
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


class OpenAICompatibleFormProvider(AIFormProvider):
    def __init__(self) -> None:
        self._base_url = settings.ai.COMPAT_BASE_URL
        self._model = settings.ai.COMPAT_MODEL
        self._api_key = settings.ai.COMPAT_API_KEY or "not-needed"
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def generate_form(self, prompt: str) -> Dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)

    async def chat(self, system: str, messages: list) -> str:
        response = await self.client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, *messages],
        )
        return response.choices[0].message.content or ""
