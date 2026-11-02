import pytest

from backend.config import settings


@pytest.fixture()
def totp_on(monkeypatch):
    monkeypatch.setattr(settings.totp, "ENABLED", True)


@pytest.fixture(autouse=True)
def notices(monkeypatch):
    """The mails about second-factor changes: recorded, never sent (auth is not
    running in tests)."""
    from backend.app.services.mfa.notifier import MfaNotifier

    sent = []

    async def record(self, notice):
        sent.append(notice)

    monkeypatch.setattr(MfaNotifier, "_send", record)
    return sent
