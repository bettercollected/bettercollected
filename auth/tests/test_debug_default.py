"""Debug mode is off unless explicitly enabled, and 500s leak nothing."""

from fastapi.testclient import TestClient

from auth.app.asgi import get_application
from auth.config.application import Application

SECRET_MESSAGE = "boom-secret-detail-4711"


def test_debug_defaults_to_false():
    assert Application.model_fields["DEBUG"].default is False


def test_unhandled_error_answers_without_a_traceback():
    app = get_application()

    @app.get("/__boom")
    async def boom():
        raise RuntimeError(SECRET_MESSAGE)

    app.debug = False
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/__boom")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    for leak in (SECRET_MESSAGE, "Traceback", ".py", "RuntimeError"):
        assert leak not in response.text
