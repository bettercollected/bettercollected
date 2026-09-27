"""Webhooks from the custom-domain service (docs/custom-domain.md).

The service POSTs signed ``domain.ready`` / ``domain.attention_required`` /
``domain.recovered`` / ``domain.deleted`` events here. The signature is the
only authentication: HMAC over the raw body with the subscription secret,
verified before anything is parsed. Deliveries are at least once and may be
out of order; the workspace service ignores stale ones.
"""

from classy_fastapi import Routable, post
from fastapi import Request

from backend.app.container import container
from backend.app.router import router


@router(prefix="/custom-domain", tags=["Custom domain"])
class CustomDomainRouter(Routable):
    @post("/webhooks")
    async def receive_webhook(self, request: Request):
        body = await request.body()
        event = container.custom_domain_service().verify_webhook(
            request.headers.get("X-Custom-Domain-Signature"), body
        )
        outcome = await container.workspace_service().apply_custom_domain_event(event)
        return {"ok": True, "event": event.type, "outcome": outcome}
