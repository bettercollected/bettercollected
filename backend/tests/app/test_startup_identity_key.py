"""The API refuses to start without a usable RESPONDENT_IDENTITY_KEY: at least
32 random bytes. The check is the first thing the lifespan does."""

import secrets

import pytest
from fastapi import FastAPI

from backend.app.asgi import lifespan
from backend.app.utils.respondent_identity import IdentityKeyError
from backend.config import settings


@pytest.mark.parametrize(
    "value",
    ["", "   ", secrets.token_hex(16), "a" * 64, "changeme"],
    ids=["missing", "blank", "16-bytes", "all-alike", "placeholder"],
)
async def test_the_start_is_refused(monkeypatch, value):
    monkeypatch.setattr(settings.respondent_identity, "KEY", value)
    with pytest.raises(IdentityKeyError, match="Refusing to start the backend") as refused:
        async with lifespan(FastAPI()):
            pytest.fail("the lifespan must not start")
    message = str(refused.value)
    assert "RESPONDENT_IDENTITY_KEY" in message and "openssl rand -hex 32" in message
    if value.strip():
        assert value not in message
