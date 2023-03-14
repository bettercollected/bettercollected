from auth.config import settings


class TestReadyController:
    def test_should_return_ok(self, app_runner):

        response = app_runner.get("/api/auth/callback")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_should_return_not_found_when_invalid_uri(self, app_runner):
        # given / when
        response = app_runner.get("/api/ready/123")

        # then
        assert response.status_code == 404
