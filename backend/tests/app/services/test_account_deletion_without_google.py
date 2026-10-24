"""Account deletion never depends on the Google Forms service.

Deleting the user's stored Google credentials there is best effort: when the
service is off (GOOGLE_FORMS_IMPORT=off), unreachable, slow or failing, the
account deletion still completes, and the leftover is logged with ids only.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.config import settings
from tests.app.controllers.data import testUser

GOOGLE_URL = "http://google-forms.invalid"
AUTH_LOGGER = "backend.app.services.auth_service"


@pytest.fixture()
async def google_provider_config():
    await container.form_provider_service().add_provider(
        FormProviderConfigDto(
            enabled=True,
            provider_name="google",
            provider_url=GOOGLE_URL,
            auth_callback_url=f"{GOOGLE_URL}/google/oauth/callback",
        )
    )


def _session(google):
    """aiohttp session whose DELETE to the Google service does ``google``
    (an exception to raise, or a status), and to auth answers 200."""

    async def delete(url, **kwargs):
        if url.startswith(GOOGLE_URL):
            if isinstance(google, BaseException):
                raise google
            return MagicMock(status=google)
        return MagicMock(status=200)

    session = MagicMock()
    session.delete = AsyncMock(side_effect=delete)
    return session


def _google_calls(session):
    return [c for c in session.delete.await_args_list if c.args[0].startswith(GOOGLE_URL)]


FAILURES = [
    pytest.param(aiohttp.ClientConnectionError("refused"), id="unreachable"),
    pytest.param(asyncio.TimeoutError(), id="timeout"),
    pytest.param(500, id="error-status"),
    pytest.param(404, id="not-found"),
]


@pytest.mark.parametrize("google", FAILURES)
async def test_credential_cleanup_is_best_effort_and_logged_with_ids(
    google_provider_config, caplog, google
):
    session = _session(google)
    with patch(
        "backend.app.services.auth_service.AiohttpClient.get_aiohttp_client",
        return_value=session,
    ), caplog.at_level(logging.WARNING, logger=AUTH_LOGGER):
        await container.auth_service().delete_credentials_from_integrations(testUser)

    assert len(_google_calls(session)) == 1
    logged = " ".join(r.getMessage() for r in caplog.records if r.name == AUTH_LOGGER)
    assert testUser.id in logged and "google" in logged
    assert testUser.sub not in logged  # ids only, never the address


async def test_a_missing_provider_url_does_not_block_either(
    google_provider_config, caplog
):
    session = _session(200)
    with patch(
        "backend.app.services.auth_service.AiohttpClient.get_aiohttp_client",
        return_value=session,
    ), patch.object(
        container.form_provider_service(),
        "get_provider_url",
        AsyncMock(side_effect=HTTPException(404, "not found")),
    ), caplog.at_level(logging.WARNING, logger=AUTH_LOGGER):
        await container.auth_service().delete_credentials_from_integrations(testUser)

    assert _google_calls(session) == []
    assert any(testUser.id in r.getMessage() for r in caplog.records)


async def test_the_request_has_a_short_timeout(google_provider_config):
    session = _session(200)
    with patch(
        "backend.app.services.auth_service.AiohttpClient.get_aiohttp_client",
        return_value=session,
    ):
        await container.auth_service().delete_credentials_from_integrations(testUser)

    timeout = _google_calls(session)[0].kwargs["timeout"]
    assert isinstance(timeout, aiohttp.ClientTimeout) and timeout.total <= 30


@pytest.mark.parametrize(
    "mode,google",
    [
        ("on", aiohttp.ClientConnectionError("refused")),
        ("readonly", 503),
        ("off", 200),
    ],
)
async def test_the_whole_account_deletion_completes(
    google_provider_config, workspace, monkeypatch, mode, google
):
    monkeypatch.setattr(settings.google_forms, "IMPORT", mode)
    session = _session(google)
    with patch(
        "backend.app.services.auth_service.AiohttpClient.get_aiohttp_client",
        return_value=session,
    ):
        await container.auth_service().delete_user(testUser)

    # off: the Google Forms service is never called
    assert len(_google_calls(session)) == (0 if mode == "off" else 1)
    # the account itself is deleted at the auth service
    auth_calls = [
        c
        for c in session.delete.await_args_list
        if c.args[0].endswith(f"/users/{testUser.id}")
    ]
    assert len(auth_calls) == 1
    # and the user's workspace is gone
    assert (
        await container.workspace_repo().get_default_workspace_by_owner_id(testUser.id)
        is None
    )
