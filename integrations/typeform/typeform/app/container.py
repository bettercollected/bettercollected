from dependency_injector import containers, providers

from typeform.app.services.http_client import HttpClient


class AppContainer(containers.DeclarativeContainer):
    # Define non-decorated objects here
    http_client: HttpClient = providers.Singleton(
        HttpClient
    )


container = AppContainer()
