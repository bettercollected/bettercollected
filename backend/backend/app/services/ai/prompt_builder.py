"""Prompt assembly for AI form features — one place, not scattered per feature.

Precedence (plan §2.4): user prompt > org compliance > org guidelines >
user preference memory (memory arrives in P1). Compliance is the only block
that may veto the user's request; everything user-authored is fenced as data.
"""

from typing import Optional

from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from backend.app.services.ai.profile import render_prompt_block


def compose_generation_prompt(prompt: str, profile: Optional[WorkspaceAIProfileDocument]) -> str:
    """Ground a form-generation request in the workspace's AI profile.

    Provider-agnostic on purpose: the block is prepended to the user turn, so
    both current providers (Gemini system-instruction + chat, OpenAI messages)
    receive it without per-provider plumbing.
    """
    block = render_prompt_block(profile)
    if not block:
        return prompt
    return f"{block}\n\n## User request\n{prompt}"
