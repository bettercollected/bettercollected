from googleform.app.services.database_service import close_db, init_db
from googleform.config import settings
from googleform.app.router import root_api_router
from googleform.app.asgi import (
    get_application,
    on_startup,
    on_shutdown,
)
from googleform.app.exceptions import (
    HTTPException,
    http_exception_handler,
)


class TestGetApplication:
    def test_should_create_app_and_populate_defaults(self):
        # given / when
        app = get_application()

        # then
        assert app.title == settings.PROJECT_NAME
        assert app.debug == settings.DEBUG
        assert app.version == settings.VERSION
        assert app.docs_url == settings.API_ROOT_PATH + settings.DOCS_URL
        assert app.router.on_startup == [on_startup, init_db]
        assert app.router.on_shutdown == [on_shutdown, close_db]
        assert all(r in app.routes for r in root_api_router.routes)
        assert app.exception_handlers[HTTPException] == http_exception_handler
