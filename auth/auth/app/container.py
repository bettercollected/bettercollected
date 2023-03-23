from auth.app.repositories.provider_repository import ProviderRepository
from auth.app.repositories.user_repository import UserRepository
from auth.app.services.auth_provider_factory import AuthProviderFactory
from auth.app.services.auth_service import AuthService
from auth.config import settings

from common.services.http_client import HttpClient
from common.services.jwt_service import JwtService

from dependency_injector import containers, providers

from motor.motor_asyncio import AsyncIOMotorClient


class AppContainer(containers.DeclarativeContainer):
    database_client: AsyncIOMotorClient = providers.Singleton(
        AsyncIOMotorClient, settings.mongo_settings.URI
    )

    # Define non-decorated objects here
    http_client: HttpClient = providers.Singleton(HttpClient)

    provider_repository: ProviderRepository = providers.Singleton(ProviderRepository)
    user_repository: UserRepository = providers.Singleton(UserRepository)

    auth_provider_factory: AuthProviderFactory = providers.Singleton(
        AuthProviderFactory
    )

    jwt_service = providers.Singleton(JwtService, settings.AUTH_JWT_SECRET)

    auth_service: AuthService = providers.Singleton(
        AuthService,
        auth_provider_factory=auth_provider_factory,
        user_repository=user_repository,
        http_client=http_client,
    )


container = AppContainer()
