"""An in-memory stand-in for the custom-domain SDK client: the same methods
and models, no network. Errors are raised on demand to test the mapping."""

import datetime as dt
import hashlib
import hmac
import json
import uuid
from typing import Dict, List, Optional

from custom_domain import Domain, Webhook
from custom_domain.errors import ConflictError

EDGE = "bettercollected.edge.example.net"


def domain_dict(
    hostname: str,
    reference: str,
    *,
    status: str = "pending_dns",
    domain_id: Optional[str] = None,
    updated_at: Optional[dt.datetime] = None,
    deleted_at: Optional[dt.datetime] = None,
) -> dict:
    now = updated_at or dt.datetime.now(dt.timezone.utc)
    check = lambda t, s: {  # noqa: E731
        "type": t,
        "status": s,
        "error_code": None if s == "passing" else "txt_record_not_found",
        "message": None if s == "passing" else "No TXT record found",
        "observed_at": now.isoformat() if s != "pending" else None,
        "next_check_at": None,
    }
    passing = status in ("ready", "provisioning")
    return {
        "id": domain_id or str(uuid.uuid4()),
        "hostname": hostname,
        "reference": reference,
        "status": status,
        "dns_records": (
            []
            if status == "deleting"
            else [
                {
                    "name": f"_custom-domain-challenge.{hostname}",
                    "type": "TXT",
                    "value": "custom-domain-verify=token",
                    "purpose": "ownership",
                    "help": "Create a TXT record with exactly this name and value.",
                },
                {
                    "name": hostname,
                    "type": "CNAME",
                    "value": EDGE,
                    "purpose": "routing",
                    "help": "Point the hostname at the target with a CNAME record.",
                },
            ]
        ),
        "checks": [
            check("ownership", "passing" if passing else "failing"),
            check("routing", "passing" if passing else "failing"),
            check("certificate", "passing" if status == "ready" else "pending"),
            check("origin", "passing" if status == "ready" else "pending"),
        ],
        "metadata": {},
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "deleted_at": deleted_at.isoformat() if deleted_at else None,
    }


class FakeClient:
    def __init__(self):
        self.domains: Dict[str, dict] = {}
        self.calls: List[tuple] = []
        self.fail_next: Optional[Exception] = None
        self.webhooks: List[Webhook] = []
        self.replays: Dict[str, str] = (
            {}
        )  # idempotency key -> domain id, deleted or not

    def _maybe_fail(self):
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error

    def create_domain(
        self, hostname, reference, *, metadata=None, idempotency_key=None
    ):
        self.calls.append(("create", hostname, reference, idempotency_key))
        self._maybe_fail()
        if idempotency_key and idempotency_key in self.replays:
            return Domain.from_dict(self.domains[self.replays[idempotency_key]])
        for existing in self.domains.values():
            if existing["hostname"] == hostname and existing["status"] != "deleting":
                raise ConflictError(
                    409, "hostname_already_claimed", f"{hostname} is already claimed"
                )
        data = domain_dict(hostname, reference)
        self.domains[data["id"]] = data
        if idempotency_key:
            self.replays[idempotency_key] = data["id"]
        return Domain.from_dict(data)

    def get_domain(self, domain_id, *, include_deleted=False):
        self.calls.append(("get", str(domain_id)))
        self._maybe_fail()
        data = self.domains.get(str(domain_id))
        if data is None or (data["status"] == "deleting" and not include_deleted):
            from custom_domain import NotFoundError

            raise NotFoundError(404, "domain_not_found", "no such domain")
        return Domain.from_dict(data)

    def request_recheck(self, domain_id):
        self.calls.append(("recheck", str(domain_id)))
        self._maybe_fail()
        return self.get_domain(domain_id)

    def delete_domain(self, domain_id):
        self.calls.append(("delete", str(domain_id)))
        self._maybe_fail()
        data = self.get_domain(domain_id)
        self.domains[data.id]["status"] = "deleting"
        self.domains[data.id]["dns_records"] = []
        return Domain.from_dict(self.domains[data.id])

    def list_domains(
        self, *, reference=None, status=None, include_deleted=False, limit=50, offset=0
    ):
        from custom_domain import Page

        items = [
            Domain.from_dict(d)
            for d in list(self.domains.values())
            if (reference is None or d["reference"] == reference)
            and (include_deleted or d["status"] != "deleting")
        ]
        return Page(
            items=items[offset : offset + limit],
            limit=limit,
            offset=offset,
            next_offset=None,
        )

    def iter_domains(self, **kwargs):
        for data in list(self.domains.values()):
            if data["status"] != "deleting":
                yield Domain.from_dict(data)

    def create_webhook(self, url, events):
        self.calls.append(("webhook", url, tuple(events)))
        self._maybe_fail()
        hook = Webhook.from_dict(
            {
                "id": str(uuid.uuid4()),
                "url": url,
                "events": events,
                "active": True,
                "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "secret": "whsec_test",
            }
        )
        self.webhooks.append(hook)
        return hook

    # --- helpers for tests -------------------------------------------------

    def set_status(self, domain_id: str, status: str) -> None:
        self.domains[domain_id].update(
            domain_dict(
                self.domains[domain_id]["hostname"],
                self.domains[domain_id]["reference"],
                status=status,
                domain_id=domain_id,
            )
        )


def signed_event(
    secret: str, event_type: str, domain: dict, *, created_at=None, event_id=None
):
    """A webhook delivery (body + signature header) exactly as the service sends it."""
    created = created_at or dt.datetime.now(dt.timezone.utc)
    body = json.dumps(
        {
            "id": event_id or str(uuid.uuid4()),
            "type": event_type,
            "created_at": created.isoformat(),
            "data": {"domain": domain},
        }
    ).encode()
    timestamp = int(dt.datetime.now(dt.timezone.utc).timestamp())
    digest = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return body, f"t={timestamp},v1={digest}"
