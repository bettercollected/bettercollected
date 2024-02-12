from abc import ABCMeta, abstractmethod

from beanie import PydanticObjectId


class BaseIntegrationProvider(metaclass=ABCMeta):
    @abstractmethod
    async def get_basic_integration_oauth_url(self, client_referer_url: str, *args, **kwargs) -> str:
        pass

    @abstractmethod
    async def handle_basic_integration_callback(self, code: str, state: str, form_id: PydanticObjectId,
                                                action_id: PydanticObjectId,
                                                *args, **kwargs) -> (
            bool, str):
        pass

