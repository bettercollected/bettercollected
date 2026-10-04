"""The internal job routes (called by the Temporal worker and the
actions-executor with the ``api-key`` header) fail closed: 503 while the key
is unset, empty or the old public default, 403 for a missing or wrong key."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.services import internal_job_key
from backend.config import settings

KEY = "a-generated-job-key"
ROUTE = "/api/v1/temporal/delete/submissions/{}"


@pytest.fixture
def scheduler():
    with patch.object(
        container.form_schedular(), "delete_response", AsyncMock(return_value="ok")
    ) as deleted:
        yield deleted


class TestJobRoutes:
    @pytest.mark.parametrize("configured", ["", "   ", "random_api_key", None])
    async def test_not_configured_is_503(
        self, client: AsyncClient, monkeypatch, scheduler, configured
    ):
        monkeypatch.setattr(settings.temporal_settings, "api_key", configured)
        for sent in ({}, {"api-key": "random_api_key"}, {"api-key": ""}):
            response = await client.post(ROUTE.format("s1"), headers=sent)
            assert response.status_code == 503, response.text
        scheduler.assert_not_called()

    @pytest.mark.parametrize("sent", [{}, {"api-key": ""}, {"api-key": "wrong"}])
    async def test_wrong_key_is_403(
        self, client: AsyncClient, monkeypatch, scheduler, sent
    ):
        monkeypatch.setattr(settings.temporal_settings, "api_key", KEY)
        response = await client.post(ROUTE.format("s1"), headers=sent)
        assert response.status_code == 403, response.text
        scheduler.assert_not_called()

    async def test_right_key_passes(self, client: AsyncClient, monkeypatch, scheduler):
        monkeypatch.setattr(settings.temporal_settings, "api_key", KEY)
        response = await client.post(ROUTE.format("s1"), headers={"api-key": KEY})
        assert response.status_code == 200, response.text
        scheduler.assert_awaited_once_with(submission_id="s1")


class TestStartupCheck:
    @pytest.mark.parametrize("configured", ["", None, "random_api_key"])
    def test_logs_when_not_configured(self, monkeypatch, configured):
        monkeypatch.setattr(settings.temporal_settings, "api_key", configured)
        assert internal_job_key.log_if_job_api_key_missing() is False

    def test_configured(self, monkeypatch):
        monkeypatch.setattr(settings.temporal_settings, "api_key", KEY)
        assert internal_job_key.log_if_job_api_key_missing() is True

    def test_no_usable_default(self):
        from backend.config.temporal_settings import TemporalSettings

        assert TemporalSettings.model_fields["api_key"].default == ""
