"""Stored records of the registration feature (``services/registration``):
the services a workspace sends submissions to, a form's registration settings
and one delivery per response. None of them holds an answer: a delivery keeps
ids, a status and counters only.
"""

import datetime as dt
import enum
from typing import List, Optional

from common.records import Record, RecordId
from pydantic import BaseModel, field_validator


def _utc(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


class ServiceKind(str, enum.Enum):
    GENERIC_JSON = "generic_json"


class ServiceAuth(str, enum.Enum):
    NONE = "none"
    HEADER = "header"
    BASIC = "basic"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RETRYING = "retrying"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RegistrationServiceDocument(Record):
    """A destination a workspace's admins registered. ``secret_sealed`` is the
    sealed secret (``services/registration/secrets.py``); it is never returned
    by the API nor logged."""

    workspace_id: RecordId
    name: str
    kind: ServiceKind = ServiceKind.GENERIC_JSON
    base_url: str
    auth: ServiceAuth = ServiceAuth.NONE
    # the header's name for ``header`` auth, the user name for ``basic``
    auth_name: Optional[str] = None
    secret_sealed: Optional[str] = None
    secret_set_at: Optional[dt.datetime] = None
    organisation_name: str
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    _tz = field_validator("secret_set_at")(_utc)

    class Settings:
        name = "registration_services"


class VariableMapping(BaseModel):
    """One variable that may leave: ``source`` in the form's variables
    namespace, ``key`` the name used in the body."""

    source: str
    key: str


class FormRegistrationDocument(Record):
    workspace_id: RecordId
    form_id: str
    enabled: bool = False
    service_id: Optional[str] = None
    path: str = ""
    variables: List[VariableMapping] = []
    metadata_variables: List[str] = []
    transform_to_list: List[str] = []
    updated_by: Optional[str] = None

    class Settings:
        name = "form_registrations"


class RegistrationDeliveryDocument(Record):
    """Ids, status and counters; never answers, bodies, addresses or the
    destination's replies."""

    workspace_id: RecordId
    form_id: str
    response_id: str
    registration_id: str
    service_id: Optional[str] = None
    kind: ServiceKind = ServiceKind.GENERIC_JSON
    service_name: Optional[str] = None
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    manual_attempts: int = 0
    last_error_code: Optional[str] = None
    last_http_status: Optional[int] = None
    last_attempt_at: Optional[dt.datetime] = None
    next_attempt_at: Optional[dt.datetime] = None
    delivered_at: Optional[dt.datetime] = None

    _tz = field_validator("last_attempt_at", "next_attempt_at", "delivered_at")(_utc)

    class Settings:
        name = "registration_deliveries"
