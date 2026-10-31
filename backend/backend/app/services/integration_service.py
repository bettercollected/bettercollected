from http import HTTPStatus

from common.records import RecordId
from bson import ObjectId
from common.configs.crypto import Crypto
from common.constants import MESSAGE_FORBIDDEN, MESSAGE_NOT_FOUND
from common.models.user import User
from common.services.http_client import HttpClient

from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresWorkspaceFormRepository,
)
from backend.app.exceptions import HTTPException
from backend.app.models.enum.form_integration import FormIntegrationType
from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.postgres.identity import PostgresSsoUsedStateRepository
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.integration_action_service import IntegrationActionService
from backend.app.services.integration_oauth_state import IntegrationOAuthState, mint
from backend.app.services.integration_provider_factory import IntegrationProviderFactory


class IntegrationService:
    def __init__(
        self,
        form_provider_service: FormPluginProviderService,
        crypto: Crypto,
        http_client: HttpClient,
        integration_action_service: IntegrationActionService,
        form_repo: PostgresFormRepository,
        workspace_form_repo: PostgresWorkspaceFormRepository,
        authorization_service: AuthorizationService,
        action_repository: PostgresActionRepository,
        used_state_repo: PostgresSsoUsedStateRepository,
    ):
        self._crypto = crypto
        self._state = IntegrationOAuthState(crypto, used_state_repo)
        self._workspace_form_repo = workspace_form_repo
        self._authorization = authorization_service
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
            client_referer_url=client_referer_url,
            state=mint(self._crypto, user, client_referer_url),
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
        # minted by get_oauth_url for this user's session, not expired
        state_data = self._state.read(state, user)
        await self._check_user_can_configure_form(form_id, user)
        await self._check_action(integration_type, action_id)
        # accepted once, before the code is exchanged
        await self._state.consume(state_data)
        return await provider.handle_basic_integration_callback(
            state=state, code=code, form_id=form_id, action_id=action_id
        )

    async def _check_user_can_configure_form(self, form_id: str, user: User):
        """Only members of a workspace holding the form may attach credentials."""
        for (
            workspace_id
        ) in await self._workspace_form_repo.get_workspace_ids_for_form_id(form_id):
            if await self._authorization.has_permission(
                user, Permission.FORM_EDIT, workspace_id
            ):
                return
        raise HTTPException(HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN)

    async def _check_action(self, integration_type: FormIntegrationType, action_id):
        """The action must exist and be an action of this integration."""
        action = (
            await self._action_repository.get_action_by_id(
                action_id=RecordId(action_id)
            )
            if ObjectId.is_valid(action_id)
            else None
        )
        if action is None or action.name != integration_type.value:
            raise HTTPException(HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND)
