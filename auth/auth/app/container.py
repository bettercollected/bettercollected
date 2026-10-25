from common.services.http_client import HttpClient
from common.services.jwt_service import JwtService
from dependency_injector import containers, providers

from auth.app.repositories.user_repository import UserRepository
from auth.app.services.auth_provider_factory import AuthProviderFactory
from auth.app.services.auth_service import AuthService
from auth.app.services.notification_service import NotificationService
from auth.app.services.sso_service import SsoService
from auth.app.services.stripe_service import StripeService
from auth.app.services.user_service import UserService
from auth.config import settings
from auth.db.flags import load_auth_flags
from common.db import DatabaseSettings, build_engine, build_sessionmaker


class AppContainer(containers.DeclarativeContainer):
    # Define non-decorated objects here
    http_client: HttpClient = providers.Singleton(HttpClient)

    # Postgres only since 4.1 (auth/db/flags.py): a stale DB_* flag
    # naming Mongo refuses the start. Without DATABASE_URL the engine is None
    # and startup refuses (app/asgi.py).
    flags = providers.Singleton(load_auth_flags)
    db_settings = providers.Singleton(DatabaseSettings.from_env)
    pg_engine = providers.Singleton(
        build_engine, db_settings, application_name="bettercollected-auth"
    )
    pg_sessionmaker = providers.Singleton(build_sessionmaker, pg_engine)

    user_repository: UserRepository = providers.Singleton(
        UserRepository, pg_sessionmaker
    )

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

    stripe_service: StripeService = providers.Singleton(
        StripeService, user_repository=user_repository
    )

    user_service: UserService = providers.Singleton(
        UserService, user_repo=user_repository, stripe_service=stripe_service
    )

    notification_service: NotificationService = providers.Singleton(NotificationService)

    sso_service: SsoService = providers.Singleton(
        SsoService, user_repository=user_repository
    )


container = AppContainer()
