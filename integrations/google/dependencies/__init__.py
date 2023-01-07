from dependency_injector import containers, providers

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
