"""What one queued action run needs, fetched when it runs.

The queued job carries ids only. The answers, the responder's address and the
action's stored secrets stay in the backend until the run starts, so the job
queue's rows (and the worker's log lines, which print a job's arguments) never
hold them, and a run is judged on the data as it is *now*: a response erased
after it was queued, or an action switched off, is skipped.

The backend answers on its in-network route
``POST /temporal/workspaces/{w}/forms/{f}/actions/{a}/runs/{r}/context`` with
the ``api-key`` the executor already uses. 410 means the run no longer applies.
Nothing here puts a response body or a value in an exception message.
"""

from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from settings.application import settings

_TIMEOUT_SECONDS = 20
CONTEXT_KEYS = ("action", "form", "response", "workspace")


class RunContextUnavailable(Exception):
    """The backend could not say what to run (down, refused, malformed answer).
    Transient as far as the job is concerned: it is retried."""


def _segment(value: Any) -> str:
    text = str(value or "")
    if not text:
        raise RunContextUnavailable("a job id is empty")
    return quote(text, safe="")


def context_url(
    workspace_id: Any, form_id: Any, action_id: Any, response_id: Any
) -> str:
    return (
        f"{settings.server_url}/temporal/workspaces/{_segment(workspace_id)}"
        f"/forms/{_segment(form_id)}/actions/{_segment(action_id)}"
        f"/runs/{_segment(response_id)}/context"
    )


async def fetch_run_context(
    workspace_id: Any, form_id: Any, action_id: Any, response_id: Any
) -> Optional[Dict[str, Any]]:
    """The run's ``action``, ``form``, ``response``, ``workspace`` (JSON text)
    and ``user_email``, or None when the run no longer applies (410)."""
    url = context_url(workspace_id, form_id, action_id, response_id)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            res = await client.post(url, headers={"api-key": settings.api_key})
    except httpx.HTTPError as error:
        raise RunContextUnavailable(type(error).__name__) from None
    if res.status_code == 410:
        return None
    if res.status_code != 200:
        raise RunContextUnavailable(f"the backend answered {res.status_code}")
    try:
        body = res.json()
    except ValueError:
        raise RunContextUnavailable("the backend's answer is not JSON") from None
    if not isinstance(body, dict) or any(
        not isinstance(body.get(key), str) for key in CONTEXT_KEYS
    ):
        raise RunContextUnavailable("the backend's answer is incomplete")
    return body
