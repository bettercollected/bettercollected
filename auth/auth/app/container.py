from dependency_injector import containers, providers

from auth.app.repositories.credentials_repository import CredentialRepository
from auth.app.repositories.provider_repository import ProviderRepository
from auth.app.repositories.user_repository import UserRepository
from auth.app.services.auth_service import AuthService
from common.services.http_client import HttpClient


class AppContainer(containers.DeclarativeContainer):
    # Define non-decorated objects here
    http_client: HttpClient = providers.Singleton(
        HttpClient
    )

    provider_repository: ProviderRepository = providers.Singleton(
        ProviderRepository
    )
    user_repository: UserRepository = providers.Singleton(
        UserRepository
    )
    credentials_repository: CredentialRepository = providers.Singleton(
        CredentialRepository
    )
    auth_service: AuthService = providers.Singleton(
        AuthService,
        provider_repository=provider_repository,
        user_repository=user_repository,
        credentials_repository=credentials_repository,
        http_client=http_client
    )


container = AppContainer()
