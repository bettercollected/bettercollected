"""Respondents' anonymous page transitions (flow analytics, #767).

The endpoint is public by design, so what it stores is held to what a
respondent of a published form can actually send: the form must be in the
workspace and published, both pages must be pages of its published version
(or the sentinels the webapp uses), and each client may send only so many per
form per window. Unknown and unpublished forms answer the same 404.
"""

import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Callable, Dict, FrozenSet, Optional, Tuple

from beanie import PydanticObjectId
from bson.errors import InvalidId

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.flow_event_dto import FlowEventRequest
from backend.app.repositories.flow_event_repository import FlowEventRepository
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.config import settings

# pages the webapp names that are not pages of the form
SENTINEL_PAGES = frozenset({"__welcome__", "__submit__", "__next__"})

RATE_LIMIT_SCOPE = "flow-events"
# how long a form's published pages are reused before they are read again
FORM_CACHE_SECONDS = 30.0
FORM_CACHE_SIZE = 2048


@dataclass(frozen=True)
class _ServableForm:
    form_id: str
    pages: FrozenSet[str]
    loaded_at: float


def _not_found() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Form not found")


class FlowEventService:
    def __init__(
        self,
        workspace_form_repo: WorkspaceFormRepository,
        form_repo: FormRepository,
        flow_event_repo: FlowEventRepository,
        rate_limiter: FixedWindowRateLimiter,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self._workspace_forms = workspace_form_repo
        self._forms = form_repo
        self._events = flow_event_repo
        self._limiter = rate_limiter
        self._monotonic = monotonic
        # (workspace, form id or slug) -> the published pages; only servable
        # forms are cached, so an unknown id is always looked up
        self._cache: Dict[Tuple[str, str], _ServableForm] = {}

    async def record(
        self,
        workspace_id: PydanticObjectId,
        form_ref: str,
        event: FlowEventRequest,
        client: Optional[str],
    ) -> None:
        form = await self._servable_form(workspace_id, form_ref)
        if form is None:
            raise _not_found()
        verdict = await self._limiter.hit(
            RATE_LIMIT_SCOPE,
            f"{form.form_id}\n{client or 'unknown'}",
            settings.api_settings.FLOW_EVENTS_PER_WINDOW,
            settings.api_settings.FLOW_EVENTS_WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise HTTPException(
                status_code=HTTPStatus.TOO_MANY_REQUESTS,
                content="Too many flow events; try again later.",
                headers={"Retry-After": str(verdict.retry_after)},
            )
        if not self._known_pages(form, event):
            # a page of a version published since the pages were cached?
            form = await self._servable_form(workspace_id, form_ref, fresh=True)
            if form is None:
                raise _not_found()
            if not self._known_pages(form, event):
                raise HTTPException(
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    content="Unknown page.",
                )
        await self._events.add(
            form_id=form.form_id,
            session_id=event.session_id,
            from_page=event.from_page,
            to_page=event.to_page,
        )

    @staticmethod
    def _known_pages(form: _ServableForm, event: FlowEventRequest) -> bool:
        return all(
            page in form.pages or page in SENTINEL_PAGES
            for page in (event.from_page, event.to_page)
        )

    async def _servable_form(
        self, workspace_id: PydanticObjectId, form_ref: str, fresh: bool = False
    ) -> Optional[_ServableForm]:
        key = (str(workspace_id), form_ref)
        now = self._monotonic()
        cached = self._cache.get(key)
        if (
            cached is not None
            and not fresh
            and now - cached.loaded_at < FORM_CACHE_SECONDS
        ):
            return cached
        self._cache.pop(key, None)
        form = await self._load(workspace_id, form_ref, now)
        if form is not None:
            if len(self._cache) >= FORM_CACHE_SIZE:
                self._cache.clear()
            self._cache[key] = form
        return form

    async def _load(
        self, workspace_id: PydanticObjectId, form_ref: str, now: float
    ) -> Optional[_ServableForm]:
        # what the public form fetch serves: a form of this workspace (by id
        # or custom slug) with a published version
        workspace_form = (
            await self._workspace_forms.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_ref
            )
        )
        if workspace_form is None:
            return None
        try:
            form_id = PydanticObjectId(workspace_form.form_id)
        except (InvalidId, TypeError, ValueError):
            return None
        published = await self._forms.get_latest_version_of_form(form_id)
        if published is None:
            return None
        pages = frozenset(
            str(field.id) for field in (published.fields or []) if field.id
        )
        return _ServableForm(
            form_id=str(workspace_form.form_id), pages=pages, loaded_at=now
        )
