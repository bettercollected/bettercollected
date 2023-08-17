from fastapi import Request

from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.workspace_service import WorkspaceService
from backend.config import settings
from common.services.http_client import HttpClient
from common.services.jwt_service import JwtService


class StripeService:
    def __init__(
        self,
        http_client: HttpClient,
        plugin_proxy_service: PluginProxyService,
        form_provider_service: FormPluginProviderService,
        jwt_service: JwtService,
        workspace_service: WorkspaceService,
    ):
        self.http_client = http_client
        self.plugin_proxy_service = plugin_proxy_service
        self.form_provider_service = form_provider_service
        self.jwt_service = jwt_service
        self.workspace_service = workspace_service

    async def get_plans(self):
        return await self.http_client.get(
            settings.auth_settings.BASE_URL + "/stripe/plans"
        )

    async def create_checkout_session(self, user, price_id: str):
        return await self.http_client.get(
            settings.auth_settings.BASE_URL + "/stripe/session/create/checkout",
            params={"user_id": user.id, "price_id": price_id},
        )

    async def create_portal_session(self, user):
        return await self.http_client.get(
            settings.auth_settings.BASE_URL + "/stripe/session/create/portal",
            params={"user_id": user.id},
        )

    async def webhooks(self, request: Request):
        body = await request.body()
        signature = request.headers.get("stripe-signature")
        response = await self.http_client.post(
            settings.auth_settings.BASE_URL + "/stripe/webhooks",
            params={"stripe_signature": signature},
            content=body,
            timeout=60000000,
        )
        json_response = response.json()
        user = json_response.get("user") if json_response else None
        if user:
            downgrade = json_response.get("downgrade")
            upgrade = json_response.get("upgrade")
            if downgrade:
                await self.workspace_service.downgrade_user_workspace(
                    user_id=user.get("_id")
                )
            if upgrade:
                await self.workspace_service.upgrade_user_workspace(
                    user_id=user.get("_id")
                )
        return response
