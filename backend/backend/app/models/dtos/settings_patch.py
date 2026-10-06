import datetime
from typing import List, Optional

from fastapi_camelcase import CamelModel
from pydantic import field_validator, model_validator

from backend.app.models.workspace import normalize_feedback_statuses
from backend.app.services.policy_url import checked_policy_url
from backend.app.services.retention import checked_retention
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

    @field_validator("privacy_policy_url")
    @classmethod
    def _valid_policy_url(cls, url: Optional[str]) -> Optional[str]:
        # http(s) only: respondents get it as a link ("" clears it).
        return checked_policy_url(url)

    @model_validator(mode="after")
    def _valid_retention(self) -> "SettingsPatchDto":
        if self.response_expiration_type is None:
            if self.response_expiration is not None:
                raise ValueError("Choose how long answers are kept.")
            return self
        # The same rule as form create and update (services/retention.py).
        self.response_expiration_type, self.response_expiration = checked_retention(
            self.response_expiration_type,
            self.response_expiration,
            datetime.date.today(),
        )
        return self
