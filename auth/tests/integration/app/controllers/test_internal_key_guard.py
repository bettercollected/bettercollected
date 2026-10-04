"""The auth API is internal (#766): every route needs the shared key in
``X-Internal-Key`` except the health check and Stripe's signed webhook.

Walks the application's routes, so a new route is covered (and refused
without the key) unless it is added to ``OPEN`` on purpose."""

import re
from types import SimpleNamespace

import pytest
import stripe
from auth.app import get_application
from auth.config import settings
from tests.integration.conftest import INTERNAL_KEY, without_internal_key

ROOT = settings.API_ROOT_PATH
OPEN = {("GET", f"{ROOT}/ready"), ("POST", f"{ROOT}/stripe/webhooks")}
DUMMY_ID = "5f0000000000000000000000"


def _routes():
    # every API route, from the app's own schema (no route hides from it)
    for path, operations in get_application().openapi()["paths"].items():
        for method in operations:
            yield method.upper(), path


GUARDED = sorted(r for r in _routes() if r not in OPEN)


def _url(path: str) -> str:
    """The route's path relative to the test client's base URL, with every
    path parameter filled in."""
    path = re.sub(
        r"\{(\w+)\}", lambda m: "google" if "provider" in m[1] else DUMMY_ID, path
    )
    return path[len(ROOT) :].lstrip("/")


def test_every_expected_route_is_guarded():
    paths = {path[len(ROOT) :] for _, path in GUARDED}
    for path in (
        "/auth/status",
        "/auth/otp/send",
        "/auth/otp/validate",
        "/auth/{provider_name}/basic",
        "/auth/{provider}/basic/callback",
        "/auth/callback",
        "/users",
        "/users/invite/send/mail",
        "/users/{user_id}",
        "/users/{user_id}/upgrade",
        "/stripe/plans",
        "/stripe/session/create/checkout",
        "/stripe/session/create/portal",
        "/admin/metrics",
        "/notifications/submission-update",
    ):
        assert path in paths, path


@pytest.mark.parametrize("method,path", GUARDED)
@pytest.mark.parametrize("key", [None, "", "wrong-key", INTERNAL_KEY + "x"])
def test_refused_without_the_right_key(app_runner, method, path, key):
    client = without_internal_key(app_runner)
    headers = {} if key is None else {"X-Internal-Key": key}
    response = client.request(method, _url(path), headers=headers)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("method,path", GUARDED)
def test_unavailable_while_no_key_is_configured(app_runner, monkeypatch, method, path):
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", "")
    for client_key in (INTERNAL_KEY, ""):
        response = app_runner.request(
            method, _url(path), headers={"X-Internal-Key": client_key}
        )
        assert response.status_code == 503, response.text
        assert "AUTH_INTERNAL_NOTIFY_KEY" in response.text


@pytest.mark.parametrize("method,path", GUARDED)
def test_the_key_lets_the_request_through(app_runner, monkeypatch, method, path):
    """Past the guard: whatever the route makes of dummy input, it is not the
    guard's answer (each route's own behaviour is tested with its router)."""
    monkeypatch.setattr(stripe.Price, "list", lambda **_: SimpleNamespace(data=[]))
    try:
        response = app_runner.request(method, _url(path))
    except Exception:  # noqa: BLE001 — the route itself failed on dummy input
        return
    assert response.status_code != 503, response.text
    assert not (response.status_code == 403 and "Not allowed." in response.text)


def test_ready_needs_no_key(app_runner):
    response = without_internal_key(app_runner).get("ready")
    assert response.status_code == 200


@pytest.mark.parametrize("configured", [True, False])
def test_stripe_webhook_needs_no_key(app_runner, monkeypatch, configured):
    """Stripe calls it (through the backend) and its signature authenticates
    it: it answers on the signature alone, key or not."""
    if not configured:
        monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", "")
    client = without_internal_key(app_runner)
    try:
        response = client.post(
            "stripe/webhooks",
            params={"stripe_signature": "t=1,v1=forged"},
            content=b"{}",
        )
    except Exception:  # noqa: BLE001 — refused by the signature check
        return
    assert response.status_code not in (403, 503)
