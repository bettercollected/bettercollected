from dependency_injector import containers, providers

from typeform.app.repositories.provider_repository import ProviderRepository
from typeform.app.services.auth_service import AuthService
from typeform.app.services.http_client import HttpClient


class AppContainer(containers.DeclarativeContainer):
    # Define non-decorated objects here
    http_client: HttpClient = providers.Singleton(
        HttpClient
    )

    # Register your newly dependencies defined via decorators here
    # so autocompletion can be used by ide
    provider_repository: ProviderRepository
    auth_service: AuthService


# Decorator for automatically creating the object with class name as key in the container
def service(name=None):
    def decorator(cls):
        provider_name = name or cls.__name__.lower()
        if provider_name in AppContainer.providers:
            raise ValueError(f"A service with the name '{provider_name}' already exists")
        AppContainer.providers[provider_name] = providers.Singleton(cls)
        return cls

    return decorator


# Decorator that also registers to container, but it is defined for repositories namespace
def repository(name=None):
    return service(name)
