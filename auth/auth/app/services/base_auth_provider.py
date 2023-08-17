from abc import ABCMeta, abstractmethod


class BaseAuthProvider(metaclass=ABCMeta):
    @abstractmethod
    async def get_basic_auth_url(self, client_referer_url: str, *args, **kwargs) -> str:
        pass

    @abstractmethod
    async def basic_auth_callback(
        self, code: str, state: str, *args, **kwargs
    ) -> (bool, str):
        pass
