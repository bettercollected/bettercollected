import logging
from http import HTTPStatus

from classy_fastapi import Routable, get, patch, post
from fastapi import Depends

from backend.app.container import container
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.router import router
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.user_service import get_logged_admin, get_user_if_logged_in
from common.models.user import User

log = logging.getLogger(__name__)


@router(prefix="/providers", tags=["Form Providers"])
class PluginProviderRouter(Routable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._provider_service: FormPluginProviderService = (
            container.form_provider_service()
        )

    @get("", status_code=HTTPStatus.OK)
    async def _get_providers(self, user: User = Depends(get_user_if_logged_in)):
        return await self._provider_service.get_providers(user)

    @post("", status_code=HTTPStatus.CREATED, dependencies=[Depends(get_logged_admin)])
    async def _add_provider(self, provider: FormProviderConfigDto):
        # TODO: Check admin user
        return await self._provider_service.add_provider(provider)

    @patch(
        "/{provider_name}",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(get_logged_admin)],
    )
    async def _update_provider(
        self, provider_name: str, provider: FormProviderConfigDto
    ):
        # TODO: Check admin user
        return await self._provider_service.update_provider(provider_name, provider)

    @get("/{provider_name}", status_code=HTTPStatus.OK)
    async def _get_provider(
        self, provider_name: str, user: User = Depends(get_user_if_logged_in)
    ):
        return await self._provider_service.get_provider(provider_name, user)
