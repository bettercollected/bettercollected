"""Core implementation - base plugin."""
from abc import abstractmethod
from typing import Protocol

from common.enums.form_provider import FormProvider


class BasePlugin(Protocol):
    """Base representation of plugin."""

    def __init__(self, provider: str | FormProvider):
        self.provider = provider

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    @abstractmethod
    def connect(self):
        raise NotImplementedError
