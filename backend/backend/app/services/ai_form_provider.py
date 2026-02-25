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
