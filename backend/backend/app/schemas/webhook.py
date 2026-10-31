"""Stored records of form webhooks (``services/webhooks``): a form's webhooks,
the log of every delivery (the action log, shared with the email actions of
``services/email_actions``) and the audit trail of changes to a form's webhooks. None of them holds an answer, a response body or a secret in
the clear: the secret is sealed, the log keeps ids, a status and counters, the
audit trail names the fields that changed.
"""

import datetime as dt
import enum
from typing import List, Literal, Optional

from common.models.standard_form import FieldLogicCondition
from common.records import Record, RecordId
from pydantic import BaseModel, field_validator


def _utc(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


class WebhookField(BaseModel):
    """One question that may leave: ``source`` in the form's variables
    namespace, ``key`` the name used in the body."""

    source: str
    key: str


class ActionCondition(BaseModel):
    """When an action (a webhook or an email action) runs: the conditions of
    the form's logic (``FieldLogicCondition``), folded with ``operator``,
    evaluated by the server on the submitted answers when the submission is
    queued (``services/action_conditions.py``). No condition: always."""

    operator: Literal["AND", "OR"] = "AND"
    conditions: List[FieldLogicCondition] = []


class FormWebhookDocument(Record):
    """A destination a workspace's admins registered for one form.
    ``url_sealed`` is the sealed address and ``secret_sealed`` the sealed signing secret (``services/registration/
    secrets.py``'s envelope, naming the workspace and this webhook); it is
    never returned by the API nor logged."""

    workspace_id: RecordId
    form_id: str
    # the normalised address (https, ASCII host), sealed: it can hold a token
    # (``services/webhooks/sealing.py``); never returned by the list, logged or queued
    url_sealed: str
    # its host, in clear, for the list and the respondent's privacy panel
    host: str
    enabled: bool = False
    fields: List[WebhookField] = []
    # runs only when it holds on the submitted answers (None: every submission)
    condition: Optional[ActionCondition] = None
    secret_sealed: Optional[str] = None
    secret_set_at: Optional[dt.datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    _tz = field_validator("secret_set_at")(_utc)

    class Settings:
        name = "form_webhooks"


class LogStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RETRYING = "retrying"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionType(str, enum.Enum):
    WEBHOOK = "webhook"
    EMAIL = "email"


class ActionLogDocument(Record):
    """One run of a form action (today: one delivery of a webhook), the
    "Deliveries" view and the 30-day action log: ids, the action type, a status,
    the HTTP status, the attempt count and timings. Never an answer, a request
    body, a response body, an address or a secret; an error is one of our codes.
    The row's id is the delivery id sent to the destination (the same on every
    attempt, so a receiver can drop a repeat)."""

    workspace_id: RecordId
    form_id: str
    action_type: ActionType = ActionType.WEBHOOK
    # the webhook (or other action) this run belongs to
    action_id: str
    # ``submission`` (a stored response) or ``test`` (sample data, no response)
    event: str = "submission"
    # email actions only: ``team`` (the staff addresses) or ``respondent`` (the
    # copy to the address the respondent gave); never an address
    channel: Optional[str] = None
    # the host this delivery was queued for (the one the respondent was shown):
    # a run whose webhook points to another host by then is cancelled
    host: Optional[str] = None
    response_id: Optional[str] = None
    status: LogStatus = LogStatus.PENDING
    attempts: int = 0
    last_error_code: Optional[str] = None
    last_http_status: Optional[int] = None
    # how long the last attempt took, in milliseconds
    last_duration_ms: Optional[int] = None
    first_attempt_at: Optional[dt.datetime] = None
    last_attempt_at: Optional[dt.datetime] = None
    next_attempt_at: Optional[dt.datetime] = None
    finished_at: Optional[dt.datetime] = None

    _tz = field_validator(
        "first_attempt_at", "last_attempt_at", "next_attempt_at", "finished_at"
    )(_utc)

    class Settings:
        name = "action_logs"


class WebhookAuditDocument(Record):
    """Who changed a form's webhooks and when: the event, the webhook's id and
    the *names* of the fields that changed (never values, addresses or
    secrets)."""

    workspace_id: RecordId
    form_id: str
    webhook_id: str
    # created | updated | enabled | disabled | secret_rotated | deleted
    event: str
    actor_id: Optional[str] = None
    changed: List[str] = []
    host: Optional[str] = None

    class Settings:
        name = "webhook_audit_entries"
