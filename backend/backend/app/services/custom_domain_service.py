"""BetterCollected's side of the custom-domain service contract.

The service (github.com/sireto/custom-domain) owns DNS verification,
certificates and the edge. This module wraps its SDK: registering a hostname
for a workspace, reading its status, asking for a recheck, deleting it, and
verifying the signed webhooks it sends. Every API failure is mapped to the
backend's HTTPException so callers never see SDK types. The SDK client is
synchronous; calls run in a worker thread.
"""

import asyncio
import dataclasses
import hashlib
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Optional

from custom_domain import (
    ApiError,
    Client,
    ConflictError,
    Domain,
    NotFoundError,
    RateLimitedError,
    SignatureInvalid,
    TransportError,
    ValidationError,
    Webhook,
    WebhookEvent,
    parse_event,
    verify_webhook,
)
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.config.custom_domain import CustomDomainSettings

READY = "ready"
EVENTS = [
    "domain.ready",
    "domain.attention_required",
    "domain.recovered",
    "domain.deleted",
]
MESSAGE_DOMAIN_TAKEN = (
    "Workspace with given custom domain already exists or Domain already exists."
)
MESSAGE_UNAVAILABLE = (
    "The custom domain service is unavailable right now. Please try again later."
)


def _check(check) -> Dict[str, Any]:
    data = dataclasses.asdict(check)
    for key in ("observed_at", "next_check_at"):
        data[key] = data[key].isoformat() if data[key] else None
    return data


def domain_fields(domain: Domain) -> Dict[str, Any]:
    """The workspace fields that mirror a domain resource."""
    return {
        "custom_domain_id": domain.id,
        "custom_domain_status": domain.status,
        "custom_domain_verified": domain.status == READY,
        "custom_domain_dns_records": [
            dataclasses.asdict(record) for record in domain.dns_records
        ],
        "custom_domain_checks": [_check(check) for check in domain.checks],
        "custom_domain_updated_at": domain.updated_at,
    }


def cleared_fields() -> Dict[str, Any]:
    return {
        "custom_domain_id": None,
        "custom_domain_status": None,
        "custom_domain_verified": False,
        "custom_domain_dns_records": None,
        "custom_domain_checks": None,
        "custom_domain_updated_at": None,
    }


def domain_payload(domain: Domain) -> Dict[str, Any]:
    """What the settings page renders: the resource with ISO timestamps."""
    return {
        "provider": "custom-domain",
        "id": domain.id,
        "hostname": domain.hostname,
        "status": domain.status,
        "verified": domain.status == READY,
        "dns_records": [dataclasses.asdict(record) for record in domain.dns_records],
        "checks": [_check(check) for check in domain.checks],
        "updated_at": domain.updated_at.isoformat() if domain.updated_at else None,
    }


def idempotency_key(workspace_id: Any, hostname: str) -> str:
    digest = hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:32]
    return f"ws-{workspace_id}-{digest}"


class CustomDomainService:
    def __init__(self, settings: CustomDomainSettings, client: Optional[Client] = None):
        self._settings = settings
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    @property
    def settings(self) -> CustomDomainSettings:
        return self._settings

    def client(self) -> Client:
        if self._client is None:
            self._client = Client(
                self._settings.api_url, credential=self._settings.api_credential
            )
        return self._client

    async def _call(self, fn: Callable, *args, **kwargs):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except RateLimitedError as error:
            raise HTTPException(
                HTTPStatus.TOO_MANY_REQUESTS,
                {
                    "message": f"Please wait {error.retry_after} seconds before checking again.",
                    "retry_after": error.retry_after,
                },
                headers={"Retry-After": str(error.retry_after)},
            )
        except ConflictError as error:
            if error.code == "hostname_already_claimed":
                raise HTTPException(HTTPStatus.CONFLICT, MESSAGE_DOMAIN_TAKEN)
            raise HTTPException(HTTPStatus.CONFLICT, error.message)
        except ValidationError as error:
            raise HTTPException(HTTPStatus.BAD_REQUEST, error.message)
        except NotFoundError:
            raise
        except (ApiError, TransportError) as error:
            # credentials, 5xx, connection errors: our problem, not the customer's
            logger.error("custom-domain service call failed: {}", error)
            raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, MESSAGE_UNAVAILABLE)

    async def register(self, hostname: str, workspace_id: Any) -> Domain:
        """Register ``hostname`` for the workspace; safe to retry."""
        return await self._call(
            self.client().create_domain,
            hostname,
            str(workspace_id),
            metadata={"workspace_id": str(workspace_id)},
            idempotency_key=idempotency_key(workspace_id, hostname),
        )

    async def fetch(self, domain_id: str) -> Optional[Domain]:
        try:
            return await self._call(self.client().get_domain, domain_id)
        except NotFoundError:
            return None

    async def recheck(self, domain_id: str) -> Domain:
        try:
            return await self._call(self.client().request_recheck, domain_id)
        except NotFoundError:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Custom domain not found.")

    async def delete(self, domain_id: str) -> Optional[Domain]:
        """Stop serving ``domain_id``; a domain that is already gone is fine."""
        try:
            return await self._call(self.client().delete_domain, domain_id)
        except NotFoundError:
            return None

    async def subscribe(self, url: str) -> Webhook:
        return await self._call(self.client().create_webhook, url, EVENTS)

    def verify_webhook(self, signature: Optional[str], body: bytes) -> WebhookEvent:
        secrets = self._settings.webhook_secret_list()
        if not secrets:
            raise HTTPException(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Custom domain webhooks are not configured.",
            )
        try:
            verify_webhook(signature, body, secrets)
            return parse_event(body)
        except SignatureInvalid as error:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST, f"Invalid webhook: {error.code}"
            )
        except (KeyError, ValueError, TypeError):
            raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid webhook payload.")
