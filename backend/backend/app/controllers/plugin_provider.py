from http import HTTPStatus

from dependency_injector.wiring import Provide, inject

from backend.app.container import container
from backend.app.core.form_plugin_config import FormProvider
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from common.utils.cbv import cbv
from common.utils.router import CustomAPIRouter

router = CustomAPIRouter(prefix="/providers")


@cbv(router=router)
class PluginProviderRouter:
    def __init__(self):
        self._provider_service: FormPluginProviderService = (
            container.form_provider_service()
        )

    @router.get("", status_code=HTTPStatus.OK)
    async def _get_providers(self):
        return await self._provider_service.get_providers()

    @router.post("", status_code=HTTPStatus.CREATED)
    async def _add_provider(self, provider: FormProvider):
        return await self._provider_service.add_provider(provider)

    @router.patch("/{provider_name}", status_code=HTTPStatus.ACCEPTED)
    async def _update_provider(self, provider_name: str, provider: FormProvider):
        return await self._provider_service.update_provider(provider_name, provider)

    @router.get("/{provider_name}", status_code=HTTPStatus.OK)
    async def _get_provider(self, provider_name: str):
        return await self._provider_service.get_provider(provider_name)
