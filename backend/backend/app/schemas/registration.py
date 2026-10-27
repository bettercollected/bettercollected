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
    OBJECTS_API = "objects_api"


class ServiceAuth(str, enum.Enum):
    NONE = "none"
    HEADER = "header"
    BASIC = "basic"
    # ``Authorization: Token <secret>``; the only method of an Objects API service
    TOKEN = "token"


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
    # Objects API only: the address the form's object type URLs must sit under.
    # We never connect to it (their Objects API does); it only fences the URL.
    objecttypes_base_url: Optional[str] = None
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
    # Objects API only: the segments of the path in ``record.data`` the answer
    # is written to (``key`` then holds them joined with ``.``)
    target_path: Optional[List[str]] = None


class FormRegistrationDocument(Record):
    workspace_id: RecordId
    form_id: str
    enabled: bool = False
    service_id: Optional[str] = None
    path: str = ""
    variables: List[VariableMapping] = []
    metadata_variables: List[str] = []
    transform_to_list: List[str] = []
    # Objects API only
    object_type_url: Optional[str] = None
    object_type_version: Optional[int] = None
    reference_path: Optional[List[str]] = None
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
    # Objects API: the created object's UUID (the only thing kept of the reply)
    remote_id: Optional[str] = None
    last_attempt_at: Optional[dt.datetime] = None
    next_attempt_at: Optional[dt.datetime] = None
    delivered_at: Optional[dt.datetime] = None

    _tz = field_validator("last_attempt_at", "next_attempt_at", "delivered_at")(_utc)

    class Settings:
        name = "registration_deliveries"
