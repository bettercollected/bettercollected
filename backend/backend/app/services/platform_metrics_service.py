"""Platform-wide metrics for platform admins (users whose token carries ADMIN).

Counts only, composed from the routed repositories of three groups (identity,
forms, responses) plus the auth service for users. Nothing is decrypted and no
identifying value is returned. The result is cached per process for a minute:
the page is refreshed often and the counts scan every response.

If the auth service cannot answer, the rest is still returned with
``users: None`` and an ``errors`` entry; such a partial result is not cached.
"""

import asyncio
import datetime as dt
import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from backend.app.models.dtos.platform_metrics_dto import AuthUserMetrics
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings
from common.services.http_client import HttpClient

CACHE_SECONDS = 60
WEEKS = 12
UNKNOWN_PROVIDER = "unknown"
USERS_UNAVAILABLE = "The auth service did not answer; user counts are unavailable."


def week_starts(now: dt.datetime, weeks: int = WEEKS) -> List[dt.datetime]:
    """Monday 00:00 UTC of the last ``weeks`` weeks, oldest first; the last
    one is the current (partial) week."""
    now = now.astimezone(dt.timezone.utc)
    monday = (now - dt.timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return [monday - dt.timedelta(weeks=weeks - 1 - i) for i in range(weeks)]


class PlatformMetricsService:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        workspace_form_repo: WorkspaceFormRepository,
        form_response_repo: FormResponseRepository,
        http_client: HttpClient,
    ):
        self._workspace_repo = workspace_repo
        self._workspace_form_repo = workspace_form_repo
        self._form_response_repo = form_response_repo
        self._http_client = http_client
        self._cached: Optional[Tuple[float, Dict[str, Any]]] = None
        self._lock = asyncio.Lock()

    def clear_cache(self) -> None:
        self._cached = None

    def _fresh(self) -> Optional[Dict[str, Any]]:
        if self._cached and time.monotonic() - self._cached[0] < CACHE_SECONDS:
            return self._cached[1]
        return None

    async def get_metrics(self, access_token: Optional[str]) -> Dict[str, Any]:
        """``access_token``: the requesting admin's, forwarded to auth."""
        cached = self._fresh()
        if cached is not None:
            return cached
        async with self._lock:  # one computation at a time; the rest reuse it
            cached = self._fresh()
            if cached is not None:
                return cached
            metrics = await self._collect(access_token)
            if not metrics["errors"]:
                self._cached = (time.monotonic(), metrics)
            return metrics

    async def _collect(self, access_token: Optional[str]) -> Dict[str, Any]:
        now = dt.datetime.now(dt.timezone.utc)
        weeks = week_starts(now)
        boundaries = [*weeks, weeks[-1] + dt.timedelta(weeks=1)]
        # One task per group: each runs its counts in turn, the groups (and the
        # auth call) side by side, so a request holds a handful of connections.
        organizations, forms, responses, users = await asyncio.gather(
            self._organization_counts(now, boundaries),
            self._form_counts(now, boundaries),
            self._response_counts(now, boundaries),
            self._user_metrics(access_token, weeks[0]),
        )
        organizations_weekly = organizations.pop("weekly")
        forms_weekly = forms.pop("weekly")
        responses_weekly = responses.pop("weekly")
        creators = forms.pop("creators")
        responders = responses.pop("responders")

        errors: List[Dict[str, str]] = []
        if users is None:
            errors.append({"source": "users", "message": USERS_UNAVAILABLE})
        new_users = {w.week_start: w.count for w in users.weekly_new} if users else {}

        return {
            "generated_at": now,
            "organizations": organizations,
            "users": (
                users.model_dump(exclude={"weekly_new"}) if users is not None else None
            ),
            "form_creators": creators,
            "form_responders": responders,
            "forms": forms,
            "responses": responses,
            "weekly": [
                {
                    "week_start": week.date(),
                    "new_users": new_users.get(week.date()) if users else None,
                    "new_organizations": organizations_weekly[i],
                    "new_forms": forms_weekly[i],
                    "responses": responses_weekly[i],
                }
                for i, week in enumerate(weeks)
            ],
            "errors": errors,
        }

    async def _organization_counts(
        self, now: dt.datetime, boundaries: List[dt.datetime]
    ) -> Dict[str, Any]:
        repo = self._workspace_repo
        return {
            "total": await repo.count_workspaces(),
            "new_last_30_days": await repo.count_workspaces(
                created_since=now - dt.timedelta(days=30)
            ),
            "disabled": await repo.count_disabled_workspaces(),
            "weekly": await repo.count_workspaces_created_per_period(boundaries),
        }

    async def _form_counts(
        self, now: dt.datetime, boundaries: List[dt.datetime]
    ) -> Dict[str, Any]:
        repo = self._workspace_form_repo
        since = now - dt.timedelta(days=30)
        by_provider: Dict[str, int] = {}
        for provider, count in (await repo.count_workspace_forms_by_provider()).items():
            key = provider or UNKNOWN_PROVIDER
            by_provider[key] = by_provider.get(key, 0) + count
        return {
            "total": await repo.count_workspace_forms(),
            "published": await repo.count_published_workspace_forms(),
            "new_last_30_days": await repo.count_workspace_forms(created_since=since),
            "by_provider": by_provider,
            "weekly": await repo.count_workspace_forms_created_per_period(boundaries),
            "creators": {
                "total": await repo.count_form_creators(),
                "active_last_30_days": await repo.count_form_creators(
                    created_since=since
                ),
            },
        }

    async def _response_counts(
        self, now: dt.datetime, boundaries: List[dt.datetime]
    ) -> Dict[str, Any]:
        repo = self._form_response_repo
        return {
            "total": await repo.count_responses(),
            "last_7_days": await repo.count_responses(
                submitted_since=now - dt.timedelta(days=7)
            ),
            "last_30_days": await repo.count_responses(
                submitted_since=now - dt.timedelta(days=30)
            ),
            "weekly": await repo.count_responses_per_period(boundaries),
            "responders": {
                "identified": await repo.count_identified_responders(),
                "anonymous_responses": await repo.count_anonymous_responses(),
            },
        }

    async def _user_metrics(
        self, access_token: Optional[str], first_week: dt.datetime
    ) -> Optional[AuthUserMetrics]:
        """User counts from the auth service, which checks the token is an
        admin's itself; None when it cannot answer."""
        if not access_token:
            return None
        try:
            body = await self._http_client.get(
                settings.auth_settings.BASE_URL + "/admin/metrics",
                params={"first_week": first_week.date().isoformat(), "weeks": WEEKS},
                headers=auth_service_headers(Authorization=f"Bearer {access_token}"),
                timeout=15,
            )
            return AuthUserMetrics.model_validate(body)
        except Exception as exc:  # noqa: BLE001 — reported as a partial result
            logger.warning(
                f"Platform metrics: user counts unavailable ({type(exc).__name__})"
            )
            return None
