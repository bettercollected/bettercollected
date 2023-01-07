from fastapi import FastAPI
from fastapi_utils.timing import add_timing_middleware
from loguru import logger

from settings import settings
from handlers.cors import init_cors
from handlers.database import init_db, close_db
from handlers.exception import init_exception_handlers
from handlers.logging import init_logging
from handlers.swagger import init_swagger
from middlewares import include_middlewares
from routers import include_routers


def create_app(session=None):
    """
    Creates a FastAPI app instance with the specified session and repositories.

    The app is initialized with various settings from a `settings` module, including a title,
    description, version, and URLs for the documentation and OpenAPI specification. Logging
    and CORS handling are initialized, as well as exception handling and a timing middleware.
    Event handlers are added to manage the app's startup and shutdown, including initialization
    and closing of the database, and loading and shutting down of a scheduler. Finally,
    middlewares and routers are included, and the app's `session` and `repositories` attributes
    are set to the specified values.

    Parameters:
        session (Optional[Session]): A database session to be used for all database interactions
        within the app. Defaults to None.
        repositories (Optional[Dict[str, Any]]): A dictionary containing repositories to be used
        for data access within the app. Defaults to None.

    Returns:
        FastAPI: An instance of a FastAPI app.
    """
    app = FastAPI(
        title=settings.api_settings.title,
        description=settings.api_settings.description,
        version=settings.api_settings.version,
        docs_url=settings.api_settings.root_path + "/docs",
        openapi_url=settings.api_settings.root_path + "/openapi.json",
        redoc_url=settings.api_settings.root_path + "/redoc",
    )

    init_logging()
    init_cors(app)
    init_swagger(app)
    init_exception_handlers(app)

    add_timing_middleware(app, record=logger.info, exclude="untimed")

    app.add_event_handler("startup", init_db)
    app.add_event_handler("shutdown", close_db)
    app.add_event_handler(
        "startup", settings.scheduler_settings.load_schedule_or_create_blank
    )
    app.add_event_handler("shutdown", settings.scheduler_settings.shutdown_scheduler)

    @app.on_event("startup")
    def init_scheduler_service():
        # Container.scheduler_service()
        pass

    include_middlewares(app)
    include_routers(app)

    app.session = session
    return app


app = create_app()
