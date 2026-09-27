"""The SDK wrapper maps the service's answers and errors onto the backend's
conventions, without a network."""

import datetime as dt
from http import HTTPStatus

import pytest
from custom_domain import RateLimitedError, TransportError, ValidationError
from custom_domain.errors import ApiError, AuthenticationError

from backend.app.exceptions import HTTPException
from backend.app.services.custom_domain_service import (
    CustomDomainService,
    cleared_fields,
    domain_fields,
    domain_payload,
    idempotency_key,
)
from backend.config.custom_domain import CustomDomainSettings
from tests.app.custom_domain.fake import FakeClient, domain_dict, signed_event

pytestmark = pytest.mark.asyncio

ENABLED = CustomDomainSettings(
    api_url="https://domains.example.net",
    api_credential="cd_test",
    application_id="app-1",
    assertion_keys="1:secret-one,2:secret-two",
    webhook_secrets="whsec_new,whsec_old",
)


def service(client=None):
    return CustomDomainService(ENABLED, client or FakeClient())


def test_settings_parse_keys_and_secrets():
    assert ENABLED.enabled
    assert ENABLED.assertion_key_map() == {"1": "secret-one", "2": "secret-two"}
    assert ENABLED.webhook_secret_list() == ["whsec_new", "whsec_old"]
    assert not CustomDomainSettings(api_url="", api_credential="").enabled


def test_idempotency_key_is_stable_per_attempt_and_bounded():
    key = idempotency_key("64ae38bcdea80b08417d058a", "forms.customer.example", "n1")
    assert key == idempotency_key(
        "64ae38bcdea80b08417d058a", "forms.customer.example", "n1"
    )
    assert key != idempotency_key(
        "64ae38bcdea80b08417d058a", "other.customer.example", "n1"
    )
    assert key != idempotency_key(
        "64ae38bcdea80b08417d058a", "forms.customer.example", "n2"
    )
    assert len(idempotency_key("x" * 24, "a" * 253 + ".example", "f" * 32)) <= 255


async def test_register_mirrors_the_domain_onto_workspace_fields():
    client = FakeClient()
    domain = await service(client).register("Forms.Customer.Example", "ws1", "n1")
    assert client.calls[0][0] == "create" and client.calls[0][3].startswith("ws-ws1-")
    fields = domain_fields(domain)
    assert fields["custom_domain_id"] == domain.id
    assert fields["custom_domain_status"] == "pending_dns"
    assert fields["custom_domain_verified"] is False
    assert [r["type"] for r in fields["custom_domain_dns_records"]] == ["TXT", "CNAME"]
    assert [c["type"] for c in fields["custom_domain_checks"]] == [
        "ownership",
        "routing",
        "certificate",
        "origin",
    ]
    assert isinstance(fields["custom_domain_updated_at"], dt.datetime)
    payload = domain_payload(domain)
    assert payload["provider"] == "custom-domain" and payload["verified"] is False
    assert set(cleared_fields()) == set(fields)


async def test_ready_domain_is_verified():
    client = FakeClient()
    domain = await service(client).register("forms.customer.example", "ws1", "n1")
    client.set_status(domain.id, "ready")
    refreshed = await service(client).fetch(domain.id)
    assert domain_fields(refreshed)["custom_domain_verified"] is True


async def test_error_mapping():
    client = FakeClient()
    svc = service(client)
    await svc.register("taken.example", "ws1", "n1")
    with pytest.raises(HTTPException) as raised:
        await svc.register("taken.example", "ws2", "n2")
    assert raised.value.status_code == HTTPStatus.CONFLICT

    client.fail_next = ValidationError(
        422, "apex_not_supported", "apex domains are not supported"
    )
    with pytest.raises(HTTPException) as raised:
        await svc.register("example.com", "ws1", "n3")
    assert raised.value.status_code == HTTPStatus.BAD_REQUEST
    assert "apex" in raised.value.content

    client.fail_next = RateLimitedError(
        429, "rate_limited", "slow down", retry_after=42
    )
    with pytest.raises(HTTPException) as raised:
        await svc.recheck("any")
    assert raised.value.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert raised.value.content["retry_after"] == 42
    assert raised.value.headers == {"Retry-After": "42"}

    for error in (
        TransportError("ConnectError"),
        ApiError(502, "http_error", "bad gateway"),
        AuthenticationError(401, "unauthorized", "revoked"),
    ):
        client.fail_next = error
        with pytest.raises(HTTPException) as raised:
            await svc.fetch("any")
        assert raised.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE


async def test_missing_domains_are_tolerated_where_it_is_safe():
    svc = service()
    assert await svc.fetch("missing") is None
    assert await svc.delete("missing") is None
    with pytest.raises(HTTPException) as raised:
        await svc.recheck("missing")
    assert raised.value.status_code == HTTPStatus.NOT_FOUND


def test_webhook_verification():
    svc = service()
    domain = domain_dict("forms.customer.example", "ws1", status="ready")
    body, signature = signed_event("whsec_old", "domain.ready", domain)
    event = svc.verify_webhook(signature, body)  # previous secret still verifies
    assert (
        event.type == "domain.ready"
        and event.domain.hostname == "forms.customer.example"
    )

    body, signature = signed_event("whsec_wrong", "domain.ready", domain)
    with pytest.raises(HTTPException) as raised:
        svc.verify_webhook(signature, body)
    assert raised.value.status_code == HTTPStatus.BAD_REQUEST
    with pytest.raises(HTTPException):
        svc.verify_webhook(None, body)

    unconfigured = CustomDomainService(
        CustomDomainSettings(
            api_url="https://x", api_credential="cd_x", webhook_secrets=""
        )
    )
    with pytest.raises(HTTPException) as raised:
        unconfigured.verify_webhook(signature, body)
    assert raised.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE
