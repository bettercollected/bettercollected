import pytest

from backend.app.container import container
from backend.config import settings


@pytest.fixture()
def mails(monkeypatch):
    """The mail requests the backend would send to the auth service. Patched on
    the class: an instance attribute would outlive the test (monkeypatch puts
    the old bound method back) and shadow other tests' patches of the class."""
    sent = []

    async def post(self, url, **kwargs):
        sent.append(
            {"url": url, "json": kwargs.get("json"), "headers": kwargs.get("headers")}
        )
        return {"message": "Notice queued."}

    monkeypatch.setattr(type(container.http_client()), "post", post)
    return sent


@pytest.fixture(autouse=True)
def drafts_switched_on(monkeypatch):
    """SAVE_DRAFTS_ENABLED is on for these tests; the switch tests turn it off."""
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", True)
