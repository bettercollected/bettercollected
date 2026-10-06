import datetime
from typing import List, Optional

from fastapi_camelcase import CamelModel
from pydantic import field_validator, model_validator

from backend.app.models.workspace import normalize_feedback_statuses
from backend.app.services.retention import (
    MAX_RETENTION_DAYS,
    retention_date,
    retention_days,
)
from common.models.consent import ResponseRetentionType


class SettingsPatchDto(CamelModel):
    pinned: Optional[bool] = None
    custom_url: Optional[str] = None
    private: Optional[bool] = None
    response_data_owner_field: Optional[str] = None
    disable_branding: Optional[bool] = None
    hidden: Optional[bool] = False
    form_close_date: Optional[datetime.datetime | str] = None
    require_verified_identity: Optional[bool] = None
    show_submission_number: Optional[bool] = None
    allow_editing_response: Optional[bool] = None
    show_original_form: Optional[bool] = None
    privacy_policy_url: Optional[str] = None
    purpose: Optional[str] = None
    retention_text: Optional[str] = None
    respondent_feedback_enabled: Optional[bool] = None
    feedback_statuses: Optional[List[str]] = None
    # How long answers are kept: "days" with a number of days, "date" with a
    # YYYY-MM-DD day, or "forever" (until deleted). Applied to every new
    # submission and stated to respondents (services/retention.py).
    response_expiration_type: Optional[ResponseRetentionType] = None
    response_expiration: Optional[str] = None

    @field_validator("feedback_statuses")
    @classmethod
    def _valid_statuses(cls, statuses: Optional[List[str]]) -> Optional[List[str]]:
        return None if statuses is None else normalize_feedback_statuses(statuses)

    @model_validator(mode="after")
    def _valid_retention(self) -> "SettingsPatchDto":
        kind = self.response_expiration_type
        if kind is None:
            if self.response_expiration is not None:
                raise ValueError("Choose how long answers are kept.")
            return self
        if kind == ResponseRetentionType.FOREVER:
            self.response_expiration = None
        elif kind == ResponseRetentionType.DAYS:
            if retention_days(self.response_expiration) is None:
                raise ValueError(
                    f"Keep answers for 1 to {MAX_RETENTION_DAYS} days."
                )
            self.response_expiration = str(retention_days(self.response_expiration))
        else:
            day = retention_date(self.response_expiration)
            if day is None or day <= datetime.date.today():
                raise ValueError("Choose a date in the future to keep answers until.")
            self.response_expiration = day.isoformat()
        return self
