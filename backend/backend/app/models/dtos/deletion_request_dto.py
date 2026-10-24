"""Closing a deletion request by hand (staff, ``privacy.manage``)."""

import datetime as dt
import enum
from typing import Optional

from fastapi_camelcase import CamelModel
from pydantic import model_validator

from backend.app.schemas.standard_form_response import DeclineReason


class DeletionRequestOutcome(str, enum.Enum):
    # the workspace's stored copy of the response is deleted (if still there)
    COMPLETED = "completed"
    # nothing is deleted; a reason from the fixed list is required
    DECLINED = "declined"


class CloseDeletionRequestBody(CamelModel):
    outcome: DeletionRequestOutcome
    reason: Optional[DeclineReason] = None

    @model_validator(mode="after")
    def _reason_only_when_declined(self):
        if self.outcome is DeletionRequestOutcome.DECLINED and self.reason is None:
            raise ValueError("A declined request needs a reason.")
        if self.outcome is DeletionRequestOutcome.COMPLETED and self.reason is not None:
            raise ValueError("Only a declined request has a reason.")
        return self


class ClosedDeletionRequest(CamelModel):
    form_id: str
    response_id: str
    status: str
    closed_by: Optional[str] = None
    closed_at: Optional[dt.datetime] = None
    decline_reason: Optional[str] = None
