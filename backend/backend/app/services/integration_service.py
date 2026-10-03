import json
from http import HTTPStatus

from beanie import PydanticObjectId
from bson import ObjectId
from common.configs.crypto import Crypto
from common.constants import MESSAGE_FORBIDDEN, MESSAGE_NOT_FOUND
from common.models.user import User
from common.services.http_client import HttpClient
from cryptography.fernet import InvalidToken

from backend.app.exceptions import HTTPException
from backend.app.models.enum.form_integration import FormIntegrationType
from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.integration_action_service import IntegrationActionService
from backend.app.repositories.form_repository import FormRepository
from backend.app.services.integration_provider_factory import IntegrationProviderFactory


class IntegrationService:
    def __init__(
        self,
        form_provider_service: FormPluginProviderService,
        crypto: Crypto,
        http_client: HttpClient,
        integration_action_service: IntegrationActionService,
        form_repo: FormRepository,
        workspace_form_repo: WorkspaceFormRepository,
        workspace_user_repo: WorkspaceUserRepository,
        action_repository: ActionRepository,
    ):
        self._crypto = crypto
        self._workspace_form_repo = workspace_form_repo
        self._workspace_user_repo = workspace_user_repo
        self._action_repository = action_repository
        self.integration__provider_factory = IntegrationProviderFactory(
            form_provider_service,
            crypto,
            http_client,
            integration_action_service,
            form_repo,
        )

    async def get_oauth_url(
        self, integration_type: FormIntegrationType, client_referer_url: str, user: User
    ):
        return await self.integration__provider_factory.get_integration_provider(
            integration_type
        ).get_basic_integration_oauth_url(
            client_referer_url=client_referer_url, user_id=user.id
        )

    async def handle_oauth_callback(
        self,
        integration_type: FormIntegrationType,
        state: str,
        code: str,
        user: User,
        form_id: str,
        action_id: str,
    ):
        provider = self.integration__provider_factory.get_integration_provider(
            integration_type
        )
        self._check_state_belongs_to_user(state, user)
        await self._check_user_can_configure_form(form_id, user)
        await self._check_action(integration_type, action_id)
        return await provider.handle_basic_integration_callback(
            state=state, code=code, form_id=form_id, action_id=action_id
        )

    def _check_state_belongs_to_user(self, state: str, user: User):
        """The state was minted by get_oauth_url for the signed-in user."""
        try:
            state_data = json.loads(self._crypto.decrypt(state))
        except (InvalidToken, ValueError, TypeError):
            raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid OAuth state.")
        if not isinstance(state_data, dict) or state_data.get("user_id") != user.id:
            raise HTTPException(HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN)

    async def _check_user_can_configure_form(self, form_id: str, user: User):
        """Only members of a workspace holding the form may attach credentials."""
        for (
            workspace_id
        ) in await self._workspace_form_repo.get_workspace_ids_for_form_id(form_id):
            if await self._workspace_user_repo.has_user_access_in_workspace(
                workspace_id, user
            ):
                return
        raise HTTPException(HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN)

    async def _check_action(self, integration_type: FormIntegrationType, action_id):
        """The action must exist and be an action of this integration."""
        action = (
            await self._action_repository.get_action_by_id(
                action_id=PydanticObjectId(action_id)
            )
            if ObjectId.is_valid(action_id)
            else None
        )
        if action is None or action.name != integration_type.value:
            raise HTTPException(HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND)
