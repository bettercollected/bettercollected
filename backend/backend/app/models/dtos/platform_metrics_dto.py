"""Platform-wide counts for the admin metrics dashboard.

Aggregates only: no names, emails, workspace names or answers ever leave the
service in this shape.
"""

import datetime as dt
from typing import Dict, List, Optional

from fastapi_camelcase import CamelModel
from pydantic import BaseModel


class OrganizationMetrics(CamelModel):
    total: int
    new_last_30_days: int
    disabled: int


class UserMetrics(CamelModel):
    total: int
    new_last_30_days: int
    active_last_30_days: int
    by_plan: Dict[str, int]


class FormCreatorMetrics(CamelModel):
    total: int
    active_last_30_days: int


class FormResponderMetrics(CamelModel):
    identified: int
    anonymous_responses: int


class FormMetrics(CamelModel):
    total: int
    published: int
    new_last_30_days: int
    by_provider: Dict[str, int]


class ResponseMetrics(CamelModel):
    total: int
    last_7_days: int
    last_30_days: int


class WeeklyMetrics(CamelModel):
    week_start: dt.date
    new_users: Optional[int] = None
    new_organizations: int
    new_forms: int
    responses: int


class MetricsError(CamelModel):
    source: str
    message: str


class PlatformMetricsDto(CamelModel):
    generated_at: dt.datetime
    organizations: OrganizationMetrics
    users: Optional[UserMetrics] = None
    form_creators: FormCreatorMetrics
    form_responders: FormResponderMetrics
    forms: FormMetrics
    responses: ResponseMetrics
    weekly: List[WeeklyMetrics]
    errors: List[MetricsError] = []


class AuthUserWeek(BaseModel):
    week_start: dt.date
    count: int


class AuthUserMetrics(BaseModel):
    """What the auth service's ``GET /admin/metrics`` answers."""

    total: int
    new_last_30_days: int
    active_last_30_days: int
    by_plan: Dict[str, int]
    weekly_new: List[AuthUserWeek]
