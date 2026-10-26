from abc import ABCMeta, abstractmethod

from common.ids import RecordId


class BaseIntegrationProvider(metaclass=ABCMeta):
    @abstractmethod
    async def get_basic_integration_oauth_url(self, client_referer_url: str, *args, **kwargs) -> str:
        pass

    @abstractmethod
    async def handle_basic_integration_callback(self, code: str, state: str, form_id: RecordId,
                                                action_id: RecordId,
                                                *args, **kwargs) -> (
            bool, str):
        pass

