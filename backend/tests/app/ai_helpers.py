"""Shared test doubles for AI features: never a real provider.

``use_fake_provider`` replaces only the raw provider lookup inside
``OpenAIService``, so the workspace AI opt-in (``provider_for_workspace``)
still runs in every test that uses it.
"""

import datetime as dt

from backend.app.container import container
from tests.app.controllers.data import testUser


class FakeProvider:
    """Scripted provider: returns queued replies and records every call."""

    supports_vision = False

    def __init__(self):
        self.replies = []
        self.calls = []

    async def chat(self, system: str, messages: list) -> str:
        self.calls.append({"system": system, "messages": messages})
        return self.replies.pop(0)

    async def generate_form(self, prompt: str) -> dict:
        self.calls.append({"prompt": prompt})
        return self.replies.pop(0)

    async def analyze_page(self, system, prompt, image, schema):
        self.calls.append({"system": system, "prompt": prompt})
        return {}


def use_fake_provider(monkeypatch, fake) -> None:
    monkeypatch.setattr(
        container.openai_service(), "_get_provider", lambda provider=None: fake
    )


async def enable_ai(workspace, provider: str = "openai") -> None:
    await container.workspace_repo().set_fields(
        workspace,
        {
            "ai_enabled": True,
            "ai_provider": provider,
            "ai_enabled_by": testUser.id,
            "ai_enabled_at": dt.datetime.now(dt.timezone.utc),
        },
    )


async def disable_ai(workspace) -> None:
    await container.workspace_repo().set_fields(
        workspace, {"ai_enabled": False, "ai_provider": None}
    )
