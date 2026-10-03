import datetime
from typing import List, Optional

from fastapi_camelcase import CamelModel
from pydantic import field_validator

from backend.app.models.workspace import normalize_feedback_statuses


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

    @field_validator("feedback_statuses")
    @classmethod
    def _valid_statuses(cls, statuses: Optional[List[str]]) -> Optional[List[str]]:
        return None if statuses is None else normalize_feedback_statuses(statuses)
