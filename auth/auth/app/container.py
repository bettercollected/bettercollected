from dependency_injector import containers, providers

from auth.app.repositories.provider_repository import ProviderRepository
from auth.app.repositories.user_repository import UserRepository
from auth.app.services.auth_provider_factory import AuthProviderFactory
from auth.app.services.auth_service import AuthService
from auth.config import settings
from common.configs.crypto import Crypto
from common.services.http_client import HttpClient


class AppContainer(containers.DeclarativeContainer):
    # Define non-decorated objects here
    http_client: HttpClient = providers.Singleton(HttpClient)

    provider_repository: ProviderRepository = providers.Singleton(ProviderRepository)
    user_repository: UserRepository = providers.Singleton(UserRepository)

    auth_provider_factory: AuthProviderFactory = providers.Singleton(AuthProviderFactory)

    auth_service: AuthService = providers.Singleton(
        AuthService,
        auth_provider_factory=auth_provider_factory,
        user_repository=user_repository,
        http_client=http_client,
    )


container = AppContainer()
