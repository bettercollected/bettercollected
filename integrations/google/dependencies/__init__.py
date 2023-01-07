from dependency_injector import containers, providers

from repositories.form import FormRepository
from services.form import FormService
from settings import Settings


class Container(containers.DeclarativeContainer):
    """
    Container class for storing and accessing application-level dependencies.

    All the repositories and services used in the application are injected
    in this container.

    Attributes:
        wiring_config: A WiringConfiguration instance that specifies which
            packages to search for dependencies.
        config: A Configuration instance for storing and accessing
            application-level configuration.
    """

    wiring_config = containers.WiringConfiguration(
        packages=["services", "repositories"]
    )
    config = providers.Configuration(pydantic_settings=[Settings()])

    # Google form repository and service
    form_repo = providers.Factory(FormRepository)
    form_service = providers.Factory(
        FormService, form_repo=form_repo
    )  # Injecting form repo onto form service
