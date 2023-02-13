# flake8: noqa
from abc import abstractmethod
from typing import Optional, Protocol

from starlette.requests import Request


class BasePluginRoute(Protocol):
    @abstractmethod
    async def _authorize(self, email: str, request: Request):
        raise NotImplementedError

    @abstractmethod
    async def _callback(self, request: Request):
        raise NotImplementedError

    @abstractmethod
    async def _revoke(self, email: str):
        raise NotImplementedError

    @abstractmethod
    async def _list_forms(self, email: str):
        raise NotImplementedError

    @abstractmethod
    async def _get_form(self, form_id: str, email: str):
        raise NotImplementedError

    @abstractmethod
    async def _import_form(
        self, form_id: str, email: str, data_owner_field: Optional[str] = None
    ):
        raise NotImplementedError
