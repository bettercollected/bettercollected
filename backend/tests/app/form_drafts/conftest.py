import pytest

from backend.app.container import container


@pytest.fixture()
def mails(monkeypatch):
    """The mail requests the backend would send to the auth service."""
    sent = []

    async def post(url, **kwargs):
        sent.append(
            {"url": url, "json": kwargs.get("json"), "headers": kwargs.get("headers")}
        )
        return {"message": "Notice queued."}

    monkeypatch.setattr(container.http_client(), "post", post)
    return sent
