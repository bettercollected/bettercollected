class TestReadyController:
    def test_should_return_ok(self, app_runner):
        response = app_runner.get("/ready")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
