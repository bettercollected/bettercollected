"""Abstract interface for AI-based form generation providers."""

import abc
from typing import Any, Dict


class AIFormProvider(abc.ABC):
    """Base contract that all AI provider implementations must satisfy."""

    @abc.abstractmethod
    async def generate_form(self, prompt: str) -> Dict[str, Any]:
        """Generate a raw form dict from a natural-language prompt.

        The returned dict must conform to the intermediate form schema
        consumed by ``OpenAIService.convert_openai_form_to_standard_form``.
        It may additionally carry the following optional top-level keys
        that the converter will pick up:
            - ``theme_name``  (str)  – one of the available theme names
            - ``welcome_image_url`` (str) – URL for the welcome-page image
            - ``cover_image_url``   (str) – URL for the form cover image
            - ``slide_layouts``     (list[str]) – per-slide LayoutType values

        Args:
            prompt: Natural-language description of the desired form.

        Returns:
            Intermediate form dict.
        """

    async def chat(self, system: str, messages: "list[dict]") -> str:
        """Multi-turn chat completion (used by AI form editing).

        Args:
            system: System prompt.
            messages: [{"role": "user"|"assistant", "content": str}, ...]
                ending with the latest user message.

        Returns:
            The assistant's raw text reply.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support chat yet.")

    #: whether ``analyze_page`` can look at the page image
    supports_vision: bool = False

    async def analyze_page(
        self, system: str, prompt: str, image_png: "bytes | None", schema: dict
    ) -> dict:
        """One structured-output call about a document page (PDF form import).

        Args:
            system: System prompt.
            prompt: The page description (text, layout items, instructions).
            image_png: The rendered page, or None when the provider has no vision.
            schema: JSON schema the answer must follow.

        Returns:
            The parsed JSON answer.
        """
        raise NotImplementedError(f"{type(self).__name__} cannot analyze pages yet.")
